#!/usr/bin/env python3
"""orsat-tci-server.py — serveur TCI local pour un WebSDR PhantomSDR-ORSAT.

Le programme tourne sur le PC de l'auditeur. Il se connecte au WebSDR comme le
ferait un navigateur (socket /audio, flux FLAC) et republie ce qu'il reçoit en
TCI sur ws://127.0.0.1:40001. Un logiciel TCI (ORSAT-LOG, Log4OM, WSJT-X,
Décodium...) voit alors le WebSDR comme un récepteur local :

  - fréquence (vfo / dds), dans les deux sens : le logiciel TCI peut changer
    la fréquence d'écoute ;
  - mode (modulation) et filtre (rx_filter_band) ;
  - audio RX (audio_start), 8 / 12 / 24 / 48 kHz, int16 / int24 / int32 / float32,
    mono ou stéréo ;
  - S-mètre (rx_smeter).

Rien n'est modifié sur le serveur : le pont n'est qu'un auditeur de plus. Il
n'ouvre la connexion au WebSDR que lorsqu'au moins un logiciel TCI est connecté,
et la referme peu après le départ du dernier, pour ne pas occuper une place
d'auditeur pour rien. Le récepteur est déclaré receive_only : aucune commande
d'émission n'est exécutée.

Dépendances : Python 3.9+, ffmpeg dans le PATH, et
    pip install websockets cbor2 numpy

Exemple :
    python3 orsat-tci-server.py --server https://orsat.ddns.net
"""

import argparse
import asyncio
import json
import logging
import math
import shutil
import ssl
import struct
import sys
import time
from urllib.parse import urlsplit

try:
    import cbor2
    import numpy as np
    import websockets
except ImportError as e:  # pragma: no cover
    sys.exit(f"Module manquant ({e.name}). Installez : pip install websockets cbor2 numpy")

log = logging.getLogger("orsat-tci")

# Version annoncée au serveur sur /audio?v=… (voir frontend/src/clientVersion.js
# et min_client_version côté serveur). Le pont parle le protocole de cette version.
CLIENT_VERSION = 2

INTERNAL_RATE = 48000                  # ffmpeg décode et rééchantillonne vers 48 kHz
TCI_RATES = (8000, 12000, 24000, 48000)
TCI_FORMATS = {"int16": 0, "int24": 1, "int32": 2, "float32": 3}
TCI_STREAM_RX_AUDIO = 1

# Mode TCI -> (démodulation PhantomSDR, filtre par défaut en Hz relatif à la fréquence affichée)
MODES = {
    "usb":  ("USB",    (0, 2700)),
    "lsb":  ("LSB",    (-2700, 0)),
    "digu": ("USB",    (0, 3000)),
    "digl": ("LSB",    (-3000, 0)),
    "cw":   ("USB",    (-250, 250)),   # porteuse décalée du pitch : tonalité à cw_pitch Hz
    "am":   ("AM-ENV", (-4500, 4500)),
    "sam":  ("AM",     (-4500, 4500)),
    "nfm":  ("FM",     (-5000, 5000)),
}
MODE_ALIASES = {"fm": "nfm", "dsb": "am", "cwu": "cw", "cwl": "cw", "pktusb": "digu", "pktlsb": "digl"}


# ─────────────────────────────────────────────────────────────────────────────
# Décimation 48 kHz -> 24 / 12 / 8 kHz (filtre FIR à état, par client)
# ─────────────────────────────────────────────────────────────────────────────
class Decimator:
    def __init__(self, factor):
        self.f = factor
        if factor == 1:
            return
        n = 24 * factor + 1
        t = np.arange(n) - (n - 1) / 2
        fc = 0.45 / factor
        h = 2 * fc * np.sinc(2 * fc * t) * np.hamming(n)
        self.h = (h / h.sum()).astype(np.float32)
        self.hist = np.zeros(n - 1, np.float32)
        self.phase = 0

    def process(self, x):
        if self.f == 1:
            return x
        buf = np.concatenate([self.hist, x])
        y = np.convolve(buf, self.h, mode="valid")          # len(y) == len(x)
        self.hist = buf[-(len(self.h) - 1):]
        out = y[self.phase::self.f]
        self.phase = (self.phase - len(y)) % self.f
        return out.astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Un logiciel TCI connecté
# ─────────────────────────────────────────────────────────────────────────────
class TciClient:
    def __init__(self, ws, peer):
        self.ws = ws
        self.peer = peer
        self.audio_on = False
        self.rate = 48000
        self.fmt = "float32"
        self.channels = 2
        self.samples = 2048            # valeurs par trame (toutes voies confondues)
        self._dec = Decimator(1)
        self._buf = np.zeros(0, np.float32)
        self.queue = asyncio.Queue(maxsize=64)

    def set_rate(self, rate):
        self.rate = rate
        self._dec = Decimator(INTERNAL_RATE // rate)
        self._buf = np.zeros(0, np.float32)

    def send_text(self, text):
        self._put(text)

    def _put(self, item):
        try:
            self.queue.put_nowait(item)
        except asyncio.QueueFull:
            # Client trop lent : on jette de l'audio plutôt que de bloquer tout le monde.
            if isinstance(item, str):
                try:
                    self.queue.get_nowait()
                    self.queue.put_nowait(item)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    def push_audio(self, mono48):
        if not self.audio_on:
            return
        self._buf = np.concatenate([self._buf, self._dec.process(mono48)])
        frames = max(1, self.samples // self.channels)
        while len(self._buf) >= frames:
            block, self._buf = self._buf[:frames], self._buf[frames:]
            self._put(self._frame(block))

    def _frame(self, mono):
        data = np.repeat(mono, 2) if self.channels == 2 else mono
        if self.fmt == "float32":
            payload = data.astype("<f4").tobytes()
        elif self.fmt == "int16":
            payload = (np.clip(data, -1, 1) * 32767).astype("<i2").tobytes()
        elif self.fmt == "int32":
            payload = (np.clip(data, -1, 1) * 2147483647).astype("<i4").tobytes()
        else:  # int24 : 3 octets little-endian par échantillon
            v = (np.clip(data, -1, 1) * 8388607).astype("<i4")
            payload = v.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
        header = struct.pack("<16I", 0, self.rate, TCI_FORMATS[self.fmt], 0, 0,
                             len(data), TCI_STREAM_RX_AUDIO, self.channels, *([0] * 8))
        return header + payload

    async def sender(self):
        while True:
            item = await self.queue.get()
            await self.ws.send(item)


# ─────────────────────────────────────────────────────────────────────────────
# Le pont : état du « récepteur », connexion au WebSDR, serveur TCI
# ─────────────────────────────────────────────────────────────────────────────
class Bridge:
    def __init__(self, args):
        self.args = args
        self.clients = set()
        self.freq = args.freq            # Hz ; None = fréquence par défaut du serveur
        self.mode = args.mode
        self.band = MODES[self.mode][1]
        self.settings = None
        self.ws_up = None
        self.power = 0.0
        self.dbm = -140.0
        self._up_task = None
        self._idle_handle = None
        self._dirty = asyncio.Event()
        self._have_settings = asyncio.Event()
        self._last_demod = None
        self._last_demod_at = 0.0

    # ── Conversions fréquence <-> bin ────────────────────────────────────────
    def _bin(self, hz):
        s = self.settings
        return (hz - s["basefreq"]) / s["total_bandwidth"] * s["fft_result_size"]

    def _hz(self, idx):
        s = self.settings
        return s["basefreq"] + idx / s["fft_result_size"] * s["total_bandwidth"]

    def limits(self):
        if not self.settings:
            return 0, 30_000_000
        s = self.settings
        return int(s["basefreq"]), int(s["basefreq"] + s["total_bandwidth"])

    def _max_bins(self):
        s = self.settings
        return math.ceil(s["audio_max_sps"] * s["fft_result_size"] / s["sps"] / 4) * 4 - 1

    # ── Messages TCI vers les clients ────────────────────────────────────────
    def broadcast(self, text):
        for c in self.clients:
            c.send_text(text)

    def state_lines(self):
        f = int(self.freq or 0)
        lo, hi = self.band
        return [f"dds:0,{f};", "if:0,0,0;", f"vfo:0,0,{f};", f"modulation:0,{self.mode};",
                f"rx_filter_band:0,{lo},{hi};"]

    def hello(self, c):
        lo, hi = self.limits()
        half = int(self.settings["audio_max_sps"] // 2) if self.settings else 24000
        lines = [
            # « ExpertSDR3 » désigne la variante du protocole TCI, que les logiciels
            # vérifient ; l'appareil réel est annoncé par la ligne device.
            "protocol:ExpertSDR3,1.9;", "device:PhantomSDR-ORSAT;", "receive_only:true;",
            "trx_count:1;", "channels_count:1;", f"vfo_limits:{lo},{hi};",
            f"if_limits:{-half},{half};", "modulations_list:" + ",".join(MODES) + ";",
            "audio_samplerate:48000;", "audio_stream_sample_type:float32;",
            "audio_stream_channels:2;", "audio_stream_samples:2048;",
            *self.state_lines(),
            "rx_enable:0,true;", "trx:0,false;", "tune:0,false;", "split_enable:0,false;",
            "rit_enable:0,false;", "xit_enable:0,false;", "mute:false;", "start;", "ready;",
        ]
        for line in lines:
            c.send_text(line)

    # ── Réglage du WebSDR ────────────────────────────────────────────────────
    def retune(self):
        self._dirty.set()

    async def _tuner(self):
        """Envoie au WebSDR le dernier état voulu, au plus toutes les 50 ms.
        Le serveur ignore un changement de mode reçu < 100 ms après le précédent :
        on espace donc les commandes demodulation."""
        while True:
            await self._dirty.wait()
            self._dirty.clear()
            ws, s = self.ws_up, self.settings
            if not ws or not s or self.freq is None:
                continue
            demod = MODES[self.mode][0]
            try:
                if demod != self._last_demod:
                    wait = 0.15 - (time.monotonic() - self._last_demod_at)
                    if wait > 0:
                        await asyncio.sleep(wait)
                    await ws.send(json.dumps({"cmd": "demodulation", "demodulation": demod}))
                    self._last_demod, self._last_demod_at = demod, time.monotonic()
                await ws.send(json.dumps(self._window_cmd()))
            except websockets.ConnectionClosed:
                pass
            await asyncio.sleep(0.05)

    def _window_cmd(self):
        f = self.freq
        lo, hi = self.band
        l, r = math.floor(self._bin(f + lo)), math.ceil(self._bin(f + hi))
        maxb = self._max_bins()
        if r - l > maxb:                     # le serveur refuse une bande trop large
            c = (l + r) / 2
            l, r = math.floor(c - maxb / 2), math.floor(c - maxb / 2) + maxb
        top = self.settings["fft_result_size"] - 1
        l, r = max(0, min(l, top)), max(0, min(r, top))
        m = f - self.args.cw_pitch if self.mode == "cw" else f
        return {"cmd": "window", "l": l, "m": self._bin(m), "r": r}

    # ── Connexion au WebSDR ──────────────────────────────────────────────────
    def _audio_url(self):
        u = urlsplit(self.args.server if "://" in self.args.server else "http://" + self.args.server)
        scheme = {"https": "wss", "wss": "wss"}.get(u.scheme, "ws")
        base = u.path.rstrip("/")
        return f"{scheme}://{u.netloc}{base}/audio?v={self.args.client_version}"

    def _client_count_changed(self):
        if self.clients:
            if self._idle_handle:
                self._idle_handle.cancel()
                self._idle_handle = None
            if not self._up_task or self._up_task.done():
                self._up_task = asyncio.create_task(self._upstream_loop())
        elif self._up_task and not self._idle_handle:
            self._idle_handle = asyncio.get_running_loop().call_later(10, self._stop_upstream)

    def _stop_upstream(self):
        self._idle_handle = None
        if not self.clients and self._up_task:
            log.info("Plus aucun logiciel TCI : déconnexion du WebSDR")
            self._up_task.cancel()
            self._up_task = None

    async def _upstream_loop(self):
        delay = 3
        while True:
            try:
                await self._upstream_once()
                delay = 3
            except asyncio.CancelledError:
                raise
            except websockets.ConnectionClosed as e:
                code = e.rcvd.code if e.rcvd else None
                reason = e.rcvd.reason if e.rcvd else ""
                if code and 4000 <= code < 5000:
                    log.warning("Connexion refusée par le WebSDR (%s %s)", code, reason)
                    delay = max(delay, 30)
                else:
                    log.warning("Connexion au WebSDR perdue (%s)", code)
            except (OSError, websockets.InvalidHandshake, asyncio.TimeoutError, ValueError) as e:
                log.warning("WebSDR injoignable : %s", e)
            finally:
                self.ws_up = None
            log.info("Nouvelle tentative dans %d s", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120)   # le serveur bannit les reconnexions trop rapides

    async def _upstream_once(self):
        url = self._audio_url()
        ctx = ssl.create_default_context() if url.startswith("wss") else None
        log.info("Connexion à %s", url)
        async with websockets.connect(url, ssl=ctx, max_size=None, open_timeout=15,
                                      ping_interval=20, user_agent_header="orsat-tci-server") as ws:
            first = await asyncio.wait_for(ws.recv(), 15)
            while not isinstance(first, str):
                first = await asyncio.wait_for(ws.recv(), 15)
            s = json.loads(first)
            self.settings = s
            self._have_settings.set()
            log.info("WebSDR : %.3f–%.3f MHz, audio %d Hz",
                     s["basefreq"] / 1e6, (s["basefreq"] + s["total_bandwidth"]) / 1e6,
                     s["audio_max_sps"])
            if self.freq is None:
                d = s.get("defaults", {})
                self.freq = int(round(self._hz(d.get("m", s["fft_result_size"] / 2))))
                self.broadcast_state()
            lo, hi = self.limits()
            self.broadcast(f"vfo_limits:{lo},{hi};")

            await ws.send(json.dumps({"cmd": "codec_caps", "opus": False}))  # flux FLAC
            self.ws_up = ws
            self._last_demod = None
            self.retune()

            dec = await asyncio.create_subprocess_exec(
                self.args.ffmpeg, "-hide_banner", "-loglevel", "error",
                "-fflags", "nobuffer", "-flags", "low_delay", "-probesize", "32",
                "-analyzeduration", "0", "-f", "flac", "-i", "pipe:0",
                "-ac", "1", "-ar", str(INTERNAL_RATE), "-f", "f32le", "pipe:1",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=None if self.args.verbose else asyncio.subprocess.DEVNULL)
            reader = asyncio.create_task(self._pcm_reader(dec))
            try:
                async for msg in ws:
                    if isinstance(msg, str):
                        continue
                    pkt = cbor2.loads(msg)
                    pwr = pkt.get("pwr")
                    if isinstance(pwr, (int, float)) and math.isfinite(pwr):
                        self.power = max(1e-15, 0.5 * self.power + 0.5 * pwr)
                    data = pkt.get("data")
                    if data and pkt.get("codec", "flac") == "flac":
                        dec.stdin.write(data)
                        await dec.stdin.drain()
            finally:
                reader.cancel()
                if dec.returncode is None:
                    dec.kill()
                await dec.wait()

    async def _pcm_reader(self, dec):
        scale = float(self.settings.get("audio_scale") or 1)
        gain = 1 / scale if scale > 1 else 1.0
        chunk = 960 * 4                                 # 20 ms à 48 kHz
        while True:
            raw = await dec.stdout.read(chunk)
            if not raw:
                return
            raw = raw[: len(raw) // 4 * 4]
            mono = np.frombuffer(raw, "<f4") * np.float32(gain)
            for c in self.clients:
                c.push_audio(mono)

    def broadcast_state(self):
        for line in self.state_lines():
            self.broadcast(line)

    async def _smeter(self):
        while True:
            await asyncio.sleep(0.2)
            if self.ws_up and self.settings and self.clients:
                db = 20 * math.log10(math.sqrt(self.power) / 2) + float(self.settings.get("smeter_offset") or 0)
                self.dbm = round(db, 1)
                self.broadcast(f"rx_smeter:0,0,{self.dbm};")

    # ── Commandes TCI reçues ─────────────────────────────────────────────────
    def handle(self, c, text):
        for cmd in text.split(";"):
            cmd = cmd.strip()
            if not cmd:
                continue
            name, _, rest = cmd.partition(":")
            name = name.strip().lower()
            args = [a.strip() for a in rest.split(",")] if rest else []
            try:
                self._command(c, name, args)
            except (ValueError, IndexError):
                log.debug("Commande TCI ignorée : %s", cmd)

    def _command(self, c, name, args):
        if name in ("vfo", "dds"):
            n = 2 if name == "vfo" else 1           # vfo:rx,chan,freq / dds:rx,freq
            if len(args) > n:
                self.set_freq(int(float(args[n])))
            else:
                c.send_text(f"vfo:0,0,{int(self.freq or 0)};" if name == "vfo" else f"dds:0,{int(self.freq or 0)};")
        elif name == "if":
            c.send_text("if:0,0,0;")
        elif name == "modulation":
            if len(args) > 1:
                self.set_mode(args[1])
            else:
                c.send_text(f"modulation:0,{self.mode};")
        elif name == "rx_filter_band":
            if len(args) > 2:
                lo, hi = sorted((int(float(args[1])), int(float(args[2]))))
                if hi > lo:
                    self.band = (lo, hi)
                    self.retune()
                    self.broadcast(f"rx_filter_band:0,{lo},{hi};")
            else:
                c.send_text(f"rx_filter_band:0,{self.band[0]},{self.band[1]};")
        elif name == "audio_start":
            c.audio_on = True
            c.send_text("audio_start:0;")
        elif name == "audio_stop":
            c.audio_on = False
            c.send_text("audio_stop:0;")
        elif name == "audio_samplerate":
            if args and int(args[0]) in TCI_RATES:
                c.set_rate(int(args[0]))
            c.send_text(f"audio_samplerate:{c.rate};")
        elif name == "audio_stream_sample_type":
            if args and args[0].lower() in TCI_FORMATS:
                c.fmt = args[0].lower()
            c.send_text(f"audio_stream_sample_type:{c.fmt};")
        elif name == "audio_stream_channels":
            if args and args[0] in ("1", "2"):
                c.channels = int(args[0])
            c.send_text(f"audio_stream_channels:{c.channels};")
        elif name == "audio_stream_samples":
            if args:
                c.samples = max(32, min(2048, int(args[0])))
            c.send_text(f"audio_stream_samples:{c.samples};")
        elif name == "rx_smeter":
            c.send_text(f"rx_smeter:0,0,{self.dbm};")
        elif name in ("trx", "tune"):                # récepteur seul : jamais d'émission
            c.send_text(f"{name}:0,false;")
        elif name == "rx_enable":
            c.send_text("rx_enable:0,true;")
        elif name == "vfo_limits":
            lo, hi = self.limits()
            c.send_text(f"vfo_limits:{lo},{hi};")
        elif name == "modulations_list":
            c.send_text("modulations_list:" + ",".join(MODES) + ";")
        elif name in ("split_enable", "rit_enable", "xit_enable"):
            c.send_text(f"{name}:0,false;")
        # Les autres commandes (émission, macros CW, IQ, spectre...) sont ignorées.

    def set_freq(self, f):
        lo, hi = self.limits()
        if lo <= f <= hi:
            self.freq = f
            self.retune()
        self.broadcast(f"vfo:0,0,{int(self.freq or 0)};")
        self.broadcast(f"dds:0,{int(self.freq or 0)};")

    def set_mode(self, name):
        m = name.lower()
        m = MODE_ALIASES.get(m, m)
        if m in MODES and m != self.mode:
            self.mode = m
            self.band = MODES[m][1]
            self.retune()
            self.broadcast(f"rx_filter_band:0,{self.band[0]},{self.band[1]};")
        self.broadcast(f"modulation:0,{self.mode};")

    # ── Serveur TCI ──────────────────────────────────────────────────────────
    async def on_client(self, ws):
        peer = "%s:%s" % ws.remote_address[:2] if ws.remote_address else "?"
        c = TciClient(ws, peer)
        self.clients.add(c)
        log.info("Logiciel TCI connecté (%s) — %d client(s)", peer, len(self.clients))
        self._client_count_changed()
        # Attendre les réglages du WebSDR pour annoncer la vraie fréquence et les
        # vraies limites, plutôt qu'un vfo:0 que certains logiciels prendraient au mot.
        try:
            await asyncio.wait_for(self._have_settings.wait(), 8)
        except asyncio.TimeoutError:
            log.warning("WebSDR pas encore joint : annonce sans ses réglages")
        self.hello(c)
        sender = asyncio.create_task(c.sender())
        try:
            async for msg in ws:
                if isinstance(msg, str):
                    self.handle(c, msg)
        except websockets.ConnectionClosed:
            pass
        finally:
            sender.cancel()
            self.clients.discard(c)
            log.info("Logiciel TCI déconnecté (%s) — %d client(s)", peer, len(self.clients))
            self._client_count_changed()

    async def run(self):
        host, _, port = self.args.listen.rpartition(":")
        asyncio.create_task(self._tuner())
        asyncio.create_task(self._smeter())
        async with websockets.serve(self.on_client, host or "127.0.0.1", int(port), max_size=2**20):
            log.info("Serveur TCI prêt sur ws://%s:%s — WebSDR : %s", host or "127.0.0.1", port, self.args.server)
            await asyncio.Future()


def main():
    p = argparse.ArgumentParser(description="Serveur TCI local pour un WebSDR PhantomSDR-ORSAT")
    p.add_argument("--server", default="https://orsat.ddns.net",
                   help="adresse du WebSDR (défaut : https://orsat.ddns.net)")
    p.add_argument("--listen", default="127.0.0.1:40001",
                   help="adresse:port du serveur TCI local (défaut : 127.0.0.1:40001)")
    p.add_argument("--freq", type=int, default=None, help="fréquence de départ en Hz")
    p.add_argument("--mode", default="usb", choices=sorted(MODES), help="mode de départ")
    p.add_argument("--cw-pitch", type=int, default=750, help="tonalité CW en Hz (défaut : 750)")
    p.add_argument("--client-version", type=int, default=CLIENT_VERSION, help=argparse.SUPPRESS)
    p.add_argument("--ffmpeg", default="ffmpeg", help="chemin de ffmpeg")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("websockets").setLevel(logging.WARNING)
    if not shutil.which(args.ffmpeg):
        sys.exit("ffmpeg introuvable. Installez-le (Ubuntu : sudo apt install ffmpeg).")
    try:
        asyncio.run(Bridge(args).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
