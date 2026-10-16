"""
admin_extras.py — fonctions supplémentaires du panneau d'administration
(F1NSK / ORSAT). Chargé par admin_server.py via init().

  • Mise à jour en un clic : git pull, build du frontend et redémarrage de ce
    qui a changé, avec journal en direct (logs/update_last.log).
  • Sauvegarde / restauration de la configuration (.zip), sauvegarde
    automatique quotidienne (7 jours), historique des fichiers modifiés depuis
    le panneau (Config Editor, signets…) avec retour en arrière.
  • Santé du serveur : services, certificat https, disque, journaux, crash.log.
  • Qualité du signal : bruit de fond et pics par bande, mesurés toutes les
    10 minutes sur le waterfall du spectrumserver (logs/signal_quality.jsonl).
  • Carte des auditeurs : visites géolocalisées des dernières heures.

Toutes les routes sont réservées à l'administrateur connecté.
"""

import ctypes
import ctypes.util
import io
import json
import os
import re
import shutil
import socket
import ssl
import struct
import subprocess
import threading
import time
import base64
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, unquote

from flask import jsonify, request, send_file, Response

_G = {}            # fonctions et constantes d'admin_server (voir init)
BASE = Path(__file__).resolve().parent
LOGS = BASE / "logs"
BACKUPS = BASE / "backups"
HISTORY = BACKUPS / "history"
HISTORY_KEEP = 30
DAILY_KEEP = 7
UPDATE_LOG = LOGS / "update_last.log"
SIGNAL_FILE = LOGS / "signal_quality.jsonl"
SIGNAL_EVERY = 600          # s entre deux mesures
SIGNAL_KEEP_DAYS = 35


def _now_utc():
    return datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════════════
#  Historique des fichiers modifiés depuis le panneau
# ══════════════════════════════════════════════════════════════════════════

def _hist_key(p: Path) -> str:
    try:
        rel = str(p.relative_to(_G["get_sdr_dir"]().resolve()))
    except Exception:
        rel = str(p)
    return quote(rel, safe="")


def _hist_dir_for(p: Path) -> Path:
    return HISTORY / _hist_key(p)


def save_version(path, reason="edit"):
    """Copie le contenu actuel du fichier dans l'historique (s'il existe)."""
    p = Path(path).resolve()
    if not p.is_file():
        return
    d = _hist_dir_for(p)
    d.mkdir(parents=True, exist_ok=True)
    now = _now_utc()
    target = d / (now.strftime("%Y%m%d-%H%M%S-") + "%06d" % now.microsecond)
    while target.exists():
        time.sleep(0.001)
        now = _now_utc()
        target = d / (now.strftime("%Y%m%d-%H%M%S-") + "%06d" % now.microsecond)
    shutil.copy2(p, target)
    versions = sorted(x for x in d.iterdir() if x.is_file())
    for old in versions[:-HISTORY_KEEP]:
        try:
            old.unlink()
        except OSError:
            pass


def wrap_write(original):
    def write_file_safe(path, content):
        try:
            p = Path(path).resolve()
            if p.is_file():
                old = p.read_text(encoding="utf-8", errors="replace")
                if old != content:
                    save_version(p)
        except Exception as e:
            print("[history] %s" % e)
        return original(path, content)
    write_file_safe.__wrapped__ = original
    return write_file_safe


def _hist_files():
    out = []
    if not HISTORY.is_dir():
        return out
    for d in sorted(HISTORY.iterdir()):
        if not d.is_dir():
            continue
        vs = sorted((x for x in d.iterdir() if x.is_file()), reverse=True)
        if not vs:
            continue
        out.append({"key": d.name, "path": unquote(d.name), "count": len(vs),
                    "last": _stamp_iso(vs[0].name)})
    out.sort(key=lambda x: x["last"], reverse=True)
    return out


def _stamp_iso(name):
    try:
        return datetime.strptime(name[:15], "%Y%m%d-%H%M%S").replace(
            tzinfo=timezone.utc).isoformat()
    except ValueError:
        return ""


def _hist_target(key):
    """Chemin réel d'un fichier de l'historique (refuse tout ce qui sort du dossier SDR)."""
    rel = unquote(key)
    base = _G["get_sdr_dir"]().resolve()
    p = (base / rel).resolve() if not os.path.isabs(rel) else Path(rel).resolve()
    p.relative_to(base)
    return p


# ══════════════════════════════════════════════════════════════════════════
#  Sauvegarde / restauration
# ══════════════════════════════════════════════════════════════════════════

def _backup_candidates():
    """Fichiers de configuration (chemins relatifs à BASE)."""
    names = set()
    pats = ["admin_config.json", "station.conf", "*.toml", "*.json",
            "frontend/site_information.json", "frontend/dist/wf-message.json",
            "logs/blocklist.json", "logs/admin_trusted.json", ".listener_secret",
            "frequencylist/*"]
    skip = {"package.json", "package-lock.json", "jsconfig.json"}
    for pat in pats:
        for f in BASE.glob(pat):
            if f.is_file() and f.name not in skip and f.stat().st_size < 20 * 1024 * 1024:
                names.add(str(f.relative_to(BASE)))
    return sorted(names)


def _allowed_restore(name: str) -> bool:
    if not name or name.startswith("/") or ".." in Path(name).parts or "\\" in name:
        return False
    if name == "MANIFEST.json":
        return False
    import fnmatch
    pats = ["admin_config.json", "station.conf", "*.toml", "*.json",
            "frontend/site_information.json", "frontend/dist/wf-message.json",
            "logs/blocklist.json", "logs/admin_trusted.json", ".listener_secret",
            "frequencylist/*"]
    for pat in pats:
        if fnmatch.fnmatchcase(name, pat) and ("/" in pat or "/" not in name):
            return True
    return False


def _git(*args, timeout=20):
    try:
        r = subprocess.run(["git", "--no-pager", "-C", str(BASE)] + list(args),
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)


def make_backup_zip() -> bytes:
    buf = io.BytesIO()
    files = _backup_candidates()
    _, head = _git("log", "-1", "--format=%h %s")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            try:
                z.write(BASE / rel, rel)
            except OSError:
                pass
        z.writestr("MANIFEST.json", json.dumps({
            "created": _now_utc().isoformat(), "host": socket.gethostname(),
            "commit": head.strip(), "files": files}, indent=2, ensure_ascii=False))
    return buf.getvalue()


def _daily_backup():
    try:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        name = "auto-%s.zip" % _now_utc().strftime("%Y-%m-%d")
        target = BACKUPS / name
        if not target.exists():
            target.write_bytes(make_backup_zip())
        autos = sorted(BACKUPS.glob("auto-*.zip"))
        for old in autos[:-DAILY_KEEP]:
            old.unlink()
    except Exception as e:
        print("[backup] sauvegarde quotidienne : %s" % e)


# ══════════════════════════════════════════════════════════════════════════
#  Mise à jour en un clic
# ══════════════════════════════════════════════════════════════════════════

_upd = {"proc": None, "started": 0}
_upd_lock = threading.Lock()

UPDATE_SCRIPT = r'''
set -u
cd "$BASE_DIR" || exit 1
say() { printf '%s\n' "$*"; }
step() { printf '\n▶ %s\n' "$*"; }
finish() { say ""; say "### FIN rc=$1 $2"; exit "$1"; }

say "Mise à jour PhantomSDR-Plus — $(date '+%d/%m/%Y %H:%M:%S')"
say "Dossier : $BASE_DIR"

# Fichier régénéré par chaque build : sans intérêt, il bloquerait le pull.
git checkout -- frontend/stats.html 2>/dev/null || true

# Les fichiers propres à la station (config, marqueurs, infos du site…) sont
# modifiés localement par nature : ils ne bloquent la mise à jour que si la
# nouvelle version modifie aussi ces mêmes fichiers.
step "Vérification des nouveautés (git fetch)"
git --no-pager fetch 2>&1 || finish 1 "(échec du git fetch)"
dirty=$(git diff --name-only HEAD)
incoming=$(git diff --name-only HEAD @{u} 2>/dev/null)
clash=$(printf '%s\n' "$dirty" | grep -Fxf <(printf '%s\n' "$incoming") | grep -v '^$' || true)
if [ -n "$dirty" ]; then
  say "Fichiers modifiés localement (conservés) :"
  printf '%s\n' "$dirty" | sed 's/^/  • /'
fi
if [ -n "$clash" ]; then
  say ""
  say "✗ La nouvelle version modifie aussi ces fichiers modifiés localement :"
  printf '%s\n' "$clash" | sed 's/^/  • /'
  say "  La mise à jour s'arrête pour ne rien écraser. Copiez vos modifications,"
  say "  puis annulez-les (git checkout -- <fichier>) avant de relancer."
  finish 1 "(conflit avec des fichiers modifiés localement)"
fi

old=$(git rev-parse HEAD)
step "Récupération des nouveautés (git pull)"
git --no-pager pull --ff-only 2>&1 || finish 1 "(échec du git pull)"
new=$(git rev-parse HEAD)

if [ "$old" = "$new" ] && [ "${FORCE_BUILD:-0}" != "1" ]; then
  say ""
  say "✓ Déjà à jour, rien à faire."
  finish 0 ""
fi

changed=$(git diff --name-only "$old" "$new")
if [ "$old" != "$new" ]; then
  step "Nouveautés"
  git --no-pager log --format='  • %h %s' "$old..$new"
  say ""
  say "Fichiers modifiés :"
  printf '%s\n' "$changed" | sed 's/^/  /'
fi

need_build=0; need_ci=0; need_proxy=0; need_admin=0; need_srv=0
printf '%s\n' "$changed" | grep -q '^frontend/' && need_build=1
printf '%s\n' "$changed" | grep -qE '^frontend/(package\.json|package-lock\.json)$' && need_ci=1
printf '%s\n' "$changed" | grep -qE '^(proxy\.py|listener_intel\.py)$' && need_proxy=1
printf '%s\n' "$changed" | grep -qE '^(admin_server\.py|admin_extras\.py|listener_intel\.py|thermal_guard\.py)$' && need_admin=1
printf '%s\n' "$changed" | grep -qE '^(src/|meson\.build|meson_options\.txt)' && need_srv=1
[ "${FORCE_BUILD:-0}" = "1" ] && need_build=1

if [ "$need_build" = "1" ]; then
  NODEBIN=$(ls -d "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -1)
  [ -n "$NODEBIN" ] && export PATH="$NODEBIN:$PATH"
  if ! command -v npm >/dev/null 2>&1; then
    say "✗ npm introuvable (ni dans le PATH ni dans ~/.nvm)."
    finish 1 "(npm introuvable)"
  fi
  if [ "$need_ci" = "1" ]; then
    step "Installation des dépendances du frontend (npm ci) — quelques minutes"
    npm --prefix "$BASE_DIR/frontend" ci --no-audit --no-fund 2>&1 || finish 1 "(échec npm ci)"
  fi
  step "Construction du frontend (npm run build) — 1 à 3 minutes"
  npm --prefix "$BASE_DIR/frontend" run build 2>&1 || finish 1 "(échec du build)"
  git checkout -- frontend/stats.html 2>/dev/null || true
  say "✓ Frontend reconstruit : les auditeurs auront la nouvelle version au prochain rechargement."
fi

if [ "$need_srv" = "1" ]; then
  say ""
  say "⚠ Le code du serveur radio (C++) a changé : il faudra le recompiler"
  say "  (./recompile.sh depuis le terminal). Ce n'est pas fait automatiquement,"
  say "  pour ne pas couper la réception sans vous."
fi

restart_unit() {
  pid=$(systemctl show -p MainPID --value "$1" 2>/dev/null)
  case "$pid" in ''|*[!0-9]*) pid=0;; esac
  if [ "$pid" -gt 1 ]; then
    kill "$pid" && say "✓ $1 relancé (systemd le redémarre en 1 à 2 s)"
  else
    say "⚠ $1 n'est pas géré par systemd : redémarrez-le à la main."
  fi
}

if [ "$need_proxy" = "1" ]; then
  step "Redémarrage du proxy"
  restart_unit phantomsdr-proxy
  sleep 3
fi

if [ "$need_admin" = "1" ]; then
  step "Redémarrage du panneau d'administration"
  say "La page se rechargera toute seule dans quelques secondes."
  say ""
  say "### FIN rc=0 (redémarrage du panneau)"
  sleep 1
  restart_unit phantomsdr-admin
  exit 0
fi

say ""
say "✓ Mise à jour terminée."
finish 0 ""
'''


def _update_running():
    p = _upd.get("proc")
    return bool(p and p.poll() is None)


# ══════════════════════════════════════════════════════════════════════════
#  Santé du serveur
# ══════════════════════════════════════════════════════════════════════════

UNITS = [("phantomsdr-proxy", "Proxy web (ports publics)"),
         ("phantomsdr-admin", "Panneau d'administration"),
         ("caddy", "Caddy (https)"),
         ("phantomsdr-websdr-relay", "Relais websdr.org"),
         ("thermal-guard", "Garde thermique")]


def _unit_info(unit):
    props = "LoadState,ActiveState,SubState,MainPID,NRestarts,ActiveEnterTimestamp"
    try:
        r = subprocess.run(["systemctl", "show", unit, "-p", props],
                           capture_output=True, text=True, timeout=4)
    except Exception as e:
        return {"unit": unit, "error": str(e)}
    d = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k] = v
    if d.get("LoadState") in ("not-found", "", None):
        return None
    return {"unit": unit, "active": d.get("ActiveState", ""), "sub": d.get("SubState", ""),
            "pid": int(d.get("MainPID") or 0), "restarts": d.get("NRestarts", ""),
            "since": d.get("ActiveEnterTimestamp", "")}


def _caddy_domains():
    out = []
    for f in ("/etc/caddy/Caddyfile",):
        try:
            for line in Path(f).read_text().splitlines():
                m = re.match(r"^\s*([a-z0-9.-]+\.[a-z]{2,})(:\d+)?\s*(,|\{)", line, re.I)
                if m:
                    out.append(m.group(1))
        except OSError:
            pass
    return out


def _cert_info(host):
    if not host:
        return {"ok": False, "msg": "nom de domaine inconnu"}
    res = {"host": host}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection(("127.0.0.1", 443), timeout=4) as s:
            with ctx.wrap_socket(s, server_hostname=host) as t:
                c = t.getpeercert()
        exp = datetime.strptime(c["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        issuer = dict(x[0] for x in c.get("issuer", []))
        res.update(ok=True, expires=exp.isoformat(),
                   days=int((exp - _now_utc()).total_seconds() // 86400),
                   issuer=issuer.get("organizationName", "") or issuer.get("commonName", ""))
    except ssl.SSLCertVerificationError as e:
        res.update(ok=False, msg="certificat invalide : %s" % e.verify_message)
    except Exception as e:
        res.update(ok=False, msg=str(e))
    return res


def _dir_size(p: Path):
    total = 0
    if p.is_file():
        return p.stat().st_size
    for root, dirs, files in os.walk(p):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git")]
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _tail(path: Path, n=25):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 64 * 1024))
            data = f.read().decode("utf-8", errors="replace")
        return data.splitlines()[-n:]
    except OSError:
        return []


# ══════════════════════════════════════════════════════════════════════════
#  Qualité du signal (waterfall du spectrumserver)
# ══════════════════════════════════════════════════════════════════════════

BANDS = [("160m", 1810, 2000), ("80m", 3500, 3800), ("60m", 5351, 5367),
         ("40m", 7000, 7200), ("30m", 10100, 10150), ("20m", 14000, 14350),
         ("17m", 18068, 18168), ("15m", 21000, 21450), ("12m", 24890, 24990),
         ("10m", 28000, 29700)]


class _Zstd:
    """Décompression zstd en flux (une trame par message, ZSTD_e_flush)."""

    def __init__(self):
        self.kind = None
        try:
            import zstandard
            self._d = zstandard.ZstdDecompressor().decompressobj()
            self.kind = "zstandard"
            return
        except Exception:
            pass
        try:
            from compression import zstd as _cz      # Python ≥ 3.14
            self._d = _cz.ZstdDecompressor()
            self.kind = "stdlib"
            return
        except Exception:
            pass
        name = ctypes.util.find_library("zstd") or "libzstd.so.1"
        lib = ctypes.CDLL(name)

        class Buf(ctypes.Structure):
            _fields_ = [("ptr", ctypes.c_void_p), ("size", ctypes.c_size_t), ("pos", ctypes.c_size_t)]
        self._Buf = Buf
        lib.ZSTD_createDStream.restype = ctypes.c_void_p
        lib.ZSTD_initDStream.argtypes = [ctypes.c_void_p]
        lib.ZSTD_decompressStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(Buf), ctypes.POINTER(Buf)]
        lib.ZSTD_decompressStream.restype = ctypes.c_size_t
        lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
        lib.ZSTD_freeDStream.argtypes = [ctypes.c_void_p]
        self._lib = lib
        self._ds = lib.ZSTD_createDStream()
        lib.ZSTD_initDStream(self._ds)
        self.kind = "libzstd"

    def feed(self, data: bytes) -> bytes:
        if self.kind in ("zstandard", "stdlib"):
            return self._d.decompress(data)
        lib, Buf = self._lib, self._Buf
        src = ctypes.create_string_buffer(data, len(data))
        inb = Buf(ctypes.cast(src, ctypes.c_void_p), len(data), 0)
        out = bytearray()
        chunk = ctypes.create_string_buffer(1 << 17)
        while True:
            outb = Buf(ctypes.cast(chunk, ctypes.c_void_p), len(chunk), 0)
            r = lib.ZSTD_decompressStream(self._ds, ctypes.byref(outb), ctypes.byref(inb))
            if lib.ZSTD_isError(r):
                raise ValueError("zstd error")
            out += chunk.raw[:outb.pos]
            if inb.pos >= inb.size and outb.pos < outb.size:
                break
        return bytes(out)

    def close(self):
        if self.kind == "libzstd":
            try:
                self._lib.ZSTD_freeDStream(self._ds)
            except Exception:
                pass


def _cbor(data: bytes, i=0):
    """Décodeur CBOR minimal (map, entiers, octets, texte, tableaux, flottants)."""
    ib = data[i]
    mt, ai = ib >> 5, ib & 31
    i += 1
    if ai < 24:
        val = ai
    elif ai == 24:
        val = data[i]; i += 1
    elif ai == 25:
        val = struct.unpack_from(">H", data, i)[0]; i += 2
    elif ai == 26:
        val = struct.unpack_from(">I", data, i)[0]; i += 4
    elif ai == 27:
        val = struct.unpack_from(">Q", data, i)[0]; i += 8
    else:
        raise ValueError("cbor: longueur indéfinie non gérée")
    if mt == 0:
        return val, i
    if mt == 1:
        return -1 - val, i
    if mt == 2:
        return data[i:i + val], i + val
    if mt == 3:
        return data[i:i + val].decode("utf-8", "replace"), i + val
    if mt == 4:
        arr = []
        for _ in range(val):
            v, i = _cbor(data, i)
            arr.append(v)
        return arr, i
    if mt == 5:
        m = {}
        for _ in range(val):
            k, i = _cbor(data, i)
            v, i = _cbor(data, i)
            m[k] = v
        return m, i
    if mt == 6:
        return _cbor(data, i)
    if mt == 7:
        if ai == 25:
            # demi-précision : rare ici
            return float(val), i
        if ai == 26:
            return struct.unpack(">f", struct.pack(">I", val))[0], i
        if ai == 27:
            return struct.unpack(">d", struct.pack(">Q", val))[0], i
        return {20: False, 21: True, 22: None}.get(val), i
    raise ValueError("cbor: type %d" % mt)


class _WS:
    """Client websocket minimal (lecture du waterfall en local)."""

    def __init__(self, host, port, path, timeout=8):
        self.s = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n"
               "User-Agent: PhantomSDR-admin-signal-monitor\r\n\r\n") % (path, host, port, key)
        self.s.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            c = self.s.recv(4096)
            if not c:
                raise ConnectionError("handshake interrompu")
            head += c
        hdr, self.buf = head.split(b"\r\n\r\n", 1)
        if b" 101 " not in hdr.split(b"\r\n", 1)[0]:
            raise ConnectionError("handshake refusé : %r" % hdr[:80])

    def _read(self, n):
        while len(self.buf) < n:
            c = self.s.recv(65536)
            if not c:
                raise ConnectionError("connexion fermée")
            self.buf += c
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _send(self, op, payload=b""):
        mask = os.urandom(4)
        n = len(payload)
        hdr = bytes([0x80 | op])
        if n < 126:
            hdr += bytes([0x80 | n])
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.s.sendall(hdr + mask + masked)

    def send_text(self, text):
        self._send(1, text.encode())

    def recv(self):
        """(opcode, payload) d'un message complet."""
        data, op0 = b"", None
        while True:
            b1, b2 = self._read(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if b2 & 0x80 else None
            payload = self._read(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == 9:
                self._send(10, payload)
                continue
            if op == 10:
                continue
            if op == 8:
                raise ConnectionError("fermé par le serveur")
            if op != 0:
                op0 = op
            data += payload
            if fin:
                return op0, data

    def close(self):
        try:
            self._send(8, struct.pack(">H", 1000))
        except Exception:
            pass
        try:
            self.s.close()
        except Exception:
            pass


def _pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    k = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[k]


def measure_signal(port, frames_per_window=4):
    """Une mesure : bruit de fond (20e centile), pic et part de points saturés
    par bande, à partir du waterfall local."""
    ws = _WS("127.0.0.1", port, "/waterfall")
    z = _Zstd()
    try:
        info = None
        t0 = time.time()
        while info is None and time.time() - t0 < 8:
            op, data = ws.recv()
            if op == 1:
                try:
                    j = json.loads(data.decode("utf-8", "replace"))
                    if "fft_result_size" in j:
                        info = j
                except ValueError:
                    pass
        if not info:
            raise RuntimeError("pas de paramètres reçus du spectrumserver")
        size = int(info["fft_result_size"])
        bw = float(info["total_bandwidth"])
        base = float(info.get("basefreq") or 0)
        hz_per_bin = bw / size

        def grab(l, r):
            if l is not None:
                ws.send_text(json.dumps({"cmd": "window", "l": int(l), "r": int(r)}))
            got, rows, t1 = 0, [], time.time()
            skip_first = l is not None
            while got < frames_per_window + (2 if skip_first else 0) and time.time() - t1 < 6:
                op, data = ws.recv()
                if op != 2:
                    continue
                raw = z.feed(data)
                if not raw:
                    continue
                pos = 0
                while pos < len(raw):
                    try:
                        pkt, pos = _cbor(raw, pos)
                    except (IndexError, ValueError):
                        break
                    if not isinstance(pkt, dict) or "data" not in pkt:
                        continue
                    got += 1
                    if skip_first and got <= 2:
                        continue      # trames encore à l'ancienne fenêtre
                    rows.append((int(pkt.get("l", 0)), int(pkt.get("r", 0)),
                                 struct.unpack("%db" % len(pkt["data"]), pkt["data"])))
            return rows

        def stats(rows, f_lo=None, f_hi=None):
            vals = []
            for l, r, d in rows:
                n = len(d)
                if not n or r <= l:
                    continue
                step = (r - l) / n
                for i, v in enumerate(d):
                    f = base + (l + (i + 0.5) * step) * hz_per_bin
                    if f_lo is not None and not (f_lo <= f <= f_hi):
                        continue
                    vals.append(v)
            if not vals:
                return None
            sat = sum(1 for v in vals if v >= 127) * 100.0 / len(vals)
            # [bruit de fond (20e centile), signaux forts (99,5e centile), % saturés]
            return [round(_pct(vals, 0.2), 1), round(_pct(vals, 0.995), 1), round(sat, 2)]

        out = {"ts": int(time.time()), "bands": {}}
        whole = grab(None, None)
        out["all"] = stats(whole)
        f_max = base + bw
        for name, lo, hi in BANDS:
            lo_hz, hi_hz = lo * 1000.0, hi * 1000.0
            if hi_hz < base or lo_hz > f_max:
                continue
            l = max(0, int((lo_hz - base) / hz_per_bin))
            r = min(size, int((hi_hz - base) / hz_per_bin) + 1)
            if r - l < 8:
                mid = (l + r) // 2
                l, r = max(0, mid - 4), min(size, mid + 4)
            st = stats(grab(l, r), lo_hz, hi_hz)
            if st:
                out["bands"][name] = st
        out["decoder"] = z.kind
        return out
    finally:
        z.close()
        ws.close()


_sig_state = {"last_error": "", "last_ok": 0, "busy": False}
_sig_lock = threading.Lock()


def _sdr_port():
    try:
        ports = _G["sdr_ports"]()
        if ports:
            return int(ports[0])
    except Exception:
        pass
    return int(_G["load_admin_config"]().get("public_port", 8081))


def sample_signal_now():
    if not _sig_lock.acquire(blocking=False):
        return False, "mesure déjà en cours"
    _sig_state["busy"] = True
    try:
        m = measure_signal(_sdr_port())
        LOGS.mkdir(exist_ok=True)
        with open(SIGNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(m, separators=(",", ":")) + "\n")
        _sig_state.update(last_ok=m["ts"], last_error="")
        return True, ""
    except Exception as e:
        _sig_state["last_error"] = "%s" % e
        return False, str(e)
    finally:
        _sig_state["busy"] = False
        _sig_lock.release()


def _purge_signal():
    try:
        if not SIGNAL_FILE.is_file():
            return
        cut = time.time() - SIGNAL_KEEP_DAYS * 86400
        with open(SIGNAL_FILE, encoding="utf-8") as f:
            first = f.readline()
        if first and json.loads(first).get("ts", 0) >= cut:
            return
        keep = []
        with open(SIGNAL_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    if json.loads(line).get("ts", 0) >= cut:
                        keep.append(line)
                except ValueError:
                    pass
        tmp = SIGNAL_FILE.with_suffix(".tmp")
        tmp.write_text("".join(keep), encoding="utf-8")
        tmp.replace(SIGNAL_FILE)
    except Exception as e:
        print("[signal] purge : %s" % e)


def _background():
    time.sleep(60)
    last_sig = 0
    last_day = ""
    while True:
        try:
            day = _now_utc().strftime("%Y-%m-%d")
            if day != last_day:
                _daily_backup()
                _purge_signal()
                last_day = day
            if time.time() - last_sig >= SIGNAL_EVERY:
                last_sig = time.time()
                ok, err = sample_signal_now()
                if not ok:
                    print("[signal] mesure impossible : %s" % err)
        except Exception as e:
            print("[extras] %s" % e)
        time.sleep(30)


# ══════════════════════════════════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════════════════════════════════

def _send(src, name):
    try:
        return send_file(src, as_attachment=True, download_name=name, mimetype="application/zip")
    except TypeError:                                   # Flask < 2.0
        return send_file(src, as_attachment=True, attachment_filename=name,
                         mimetype="application/zip")


def init(app, g):
    """g = globals() d'admin_server : login_required, get_sdr_dir,
    load_admin_config, get_process_status, write_file_safe, _sdr_ports, LI."""
    _G.update(login_required=g["login_required"], get_sdr_dir=g["get_sdr_dir"],
              load_admin_config=g["load_admin_config"],
              get_process_status=g.get("get_process_status"),
              sdr_ports=g.get("_sdr_ports"), LI=g.get("LI"))
    g["write_file_safe"] = wrap_write(g["write_file_safe"])
    lr = g["login_required"]

    # ── JavaScript des pages ────────────────────────────────────────────
    @app.route("/admin/extras.js")
    @lr
    def extras_js():
        js = (BASE / "admin_extras.js").read_text(encoding="utf-8")
        return Response(js, mimetype="text/javascript",
                        headers={"Cache-Control": "no-cache"})

    # ── Mise à jour ─────────────────────────────────────────────────────
    @app.route("/admin/api/update/status")
    @lr
    def upd_status():
        rc, cur = _git("log", "-1", "--format=%h|%s|%cI")
        if rc != 0:
            return jsonify({"ok": True, "commit": "?", "subject": "dossier non géré par git : " + cur.strip()[:200],
                            "date": "", "branch": "", "remote": "", "running": _update_running(),
                            "has_log": UPDATE_LOG.is_file()})
        h, s, d = (cur.strip().split("|", 2) + ["", "", ""])[:3]
        _, br = _git("rev-parse", "--abbrev-ref", "HEAD")
        _, remote = _git("config", "--get", "remote.origin.url")
        return jsonify({"ok": True, "commit": h, "subject": s, "date": d,
                        "branch": br.strip(), "remote": remote.strip(),
                        "running": _update_running(),
                        "has_log": UPDATE_LOG.is_file()})

    @app.route("/admin/api/update/check", methods=["POST"])
    @lr
    def upd_check():
        rc, out = _git("fetch", "--quiet", timeout=60)
        if rc != 0:
            return jsonify({"ok": False, "msg": "git fetch a échoué : " + out.strip()[-400:]})
        _, log = _git("log", "--format=%h|%s|%cI", "HEAD..@{u}")
        commits = []
        for line in log.strip().splitlines():
            parts = (line.split("|", 2) + ["", "", ""])[:3]
            commits.append({"h": parts[0], "s": parts[1], "d": parts[2]})
        _, files = _git("diff", "--name-only", "HEAD", "@{u}")
        files = [f for f in files.strip().splitlines() if f]
        _, dirty = _git("status", "--porcelain", "--untracked-files=no")
        dirty = [l for l in dirty.splitlines() if l.strip() and "frontend/stats.html" not in l]
        plan = []
        if any(f.startswith("frontend/") for f in files):
            plan.append("Reconstruction du frontend (1 à 3 min)")
        if any(f in ("proxy.py", "listener_intel.py") for f in files):
            plan.append("Redémarrage du proxy (coupure de 2 s)")
        if any(f in ("admin_server.py", "admin_extras.py", "listener_intel.py", "thermal_guard.py") for f in files):
            plan.append("Redémarrage du panneau (la page se recharge)")
        if any(f.startswith("src/") or f.startswith("meson") for f in files):
            plan.append("⚠ Code C++ modifié : recompilation manuelle à prévoir")
        return jsonify({"ok": True, "commits": commits, "files": files, "plan": plan,
                        "dirty": dirty})

    @app.route("/admin/api/update/run", methods=["POST"])
    @lr
    def upd_run():
        data = request.get_json(silent=True) or {}
        with _upd_lock:
            if _update_running():
                return jsonify({"ok": False, "msg": "Une mise à jour est déjà en cours"})
            LOGS.mkdir(exist_ok=True)
            env = dict(os.environ, BASE_DIR=str(BASE), GIT_TERMINAL_PROMPT="0",
                       GIT_SSH_COMMAND=os.environ.get("GIT_SSH_COMMAND", "ssh -o BatchMode=yes"),
                       FORCE_BUILD="1" if data.get("force_build") else "0",
                       NO_COLOR="1", TERM="dumb")
            logf = open(UPDATE_LOG, "w", encoding="utf-8")
            try:
                _upd["proc"] = subprocess.Popen(
                    ["/bin/bash", "-c", UPDATE_SCRIPT], cwd=str(BASE), env=env,
                    stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                    start_new_session=True)
            finally:
                logf.close()
            _upd["started"] = time.time()
        return jsonify({"ok": True})

    @app.route("/admin/api/update/log")
    @lr
    def upd_log():
        try:
            pos = int(request.args.get("pos", "0"))
        except ValueError:
            pos = 0
        text = ""
        try:
            with open(UPDATE_LOG, "rb") as f:
                f.seek(pos)
                raw = f.read()
            text = raw.decode("utf-8", errors="replace")
            pos += len(raw)
        except OSError:
            pass
        running = _update_running()
        return jsonify({"ok": True, "text": text, "pos": pos, "running": running})

    # ── Sauvegardes ─────────────────────────────────────────────────────
    @app.route("/admin/api/backup/info")
    @lr
    def bk_info():
        autos = []
        if BACKUPS.is_dir():
            for f in sorted(BACKUPS.glob("*.zip"), reverse=True):
                autos.append({"name": f.name, "size": f.stat().st_size,
                              "date": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat()})
        return jsonify({"ok": True, "files": _backup_candidates(), "saved": autos,
                        "history": _hist_files()})

    @app.route("/admin/api/backup/download")
    @lr
    def bk_download():
        name = request.args.get("name", "")
        if name:
            f = (BACKUPS / name).resolve()
            if f.parent != BACKUPS.resolve() or not f.is_file() or f.suffix != ".zip":
                return jsonify({"ok": False, "msg": "introuvable"}), 404
            return _send(str(f), f.name)
        data = make_backup_zip()
        fname = "phantomsdr-config-%s.zip" % datetime.now().strftime("%Y-%m-%d_%H%M")
        return _send(io.BytesIO(data), fname)

    @app.route("/admin/api/backup/restore", methods=["POST"])
    @lr
    def bk_restore():
        up = request.files.get("file")
        preview = request.form.get("preview") == "1"
        if not up:
            return jsonify({"ok": False, "msg": "aucun fichier reçu"})
        try:
            z = zipfile.ZipFile(io.BytesIO(up.read()))
        except zipfile.BadZipFile:
            return jsonify({"ok": False, "msg": "ce n'est pas un fichier .zip valide"})
        names = [n for n in z.namelist() if not n.endswith("/")]
        ok_names = [n for n in names if _allowed_restore(n)]
        refused = [n for n in names if n not in ok_names and n != "MANIFEST.json"]
        manifest = {}
        if "MANIFEST.json" in names:
            try:
                manifest = json.loads(z.read("MANIFEST.json"))
            except ValueError:
                pass
        if preview:
            changed = []
            for n in ok_names:
                cur = BASE / n
                new = z.read(n)
                changed.append({"name": n, "state": "nouveau" if not cur.exists()
                                else ("identique" if cur.read_bytes() == new else "modifié")})
            return jsonify({"ok": True, "files": changed, "refused": refused,
                            "manifest": {k: manifest.get(k) for k in ("created", "host", "commit")}})
        BACKUPS.mkdir(parents=True, exist_ok=True)
        before = BACKUPS / ("avant-restauration-%s.zip" % _now_utc().strftime("%Y-%m-%d_%H%M%S"))
        before.write_bytes(make_backup_zip())
        done = []
        for n in ok_names:
            target = (BASE / n).resolve()
            try:
                target.relative_to(BASE)
            except ValueError:
                continue
            data = z.read(n)
            if target.exists() and target.read_bytes() == data:
                continue
            if target.exists():
                save_version(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            done.append(n)
        return jsonify({"ok": True, "restored": done, "refused": refused,
                        "safety": before.name})

    @app.route("/admin/api/history/versions")
    @lr
    def hist_versions():
        key = request.args.get("key", "")
        try:
            target = _hist_target(key)
        except Exception:
            return jsonify({"ok": False, "msg": "accès refusé"}), 403
        d = HISTORY / quote(unquote(key), safe="")
        vs = []
        if d.is_dir():
            for f in sorted((x for x in d.iterdir() if x.is_file()), reverse=True):
                vs.append({"v": f.name, "date": _stamp_iso(f.name), "size": f.stat().st_size})
        return jsonify({"ok": True, "path": str(target), "versions": vs})

    @app.route("/admin/api/history/read")
    @lr
    def hist_read():
        key, v = request.args.get("key", ""), request.args.get("v", "")
        try:
            target = _hist_target(key)
        except Exception:
            return jsonify({"ok": False, "msg": "accès refusé"}), 403
        f = (HISTORY / quote(unquote(key), safe="") / v).resolve()
        if f.parent != (HISTORY / quote(unquote(key), safe="")).resolve() or not f.is_file():
            return jsonify({"ok": False, "msg": "version introuvable"}), 404
        cur = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
        return jsonify({"ok": True, "content": f.read_text(encoding="utf-8", errors="replace"),
                        "current": cur})

    @app.route("/admin/api/history/restore", methods=["POST"])
    @lr
    def hist_restore():
        data = request.get_json(silent=True) or {}
        key, v = data.get("key", ""), data.get("v", "")
        try:
            target = _hist_target(key)
        except Exception:
            return jsonify({"ok": False, "msg": "accès refusé"}), 403
        f = (HISTORY / quote(unquote(key), safe="") / v).resolve()
        if f.parent != (HISTORY / quote(unquote(key), safe="")).resolve() or not f.is_file():
            return jsonify({"ok": False, "msg": "version introuvable"}), 404
        content = f.read_text(encoding="utf-8", errors="replace")
        ok, msg = g["write_file_safe"](str(target), content)
        return jsonify({"ok": ok, "msg": msg})

    # ── Santé ───────────────────────────────────────────────────────────
    @app.route("/admin/api/health")
    @lr
    def health():
        units = [dict(u, label=lbl) for u, lbl in
                 ((_unit_info(n), lbl) for n, lbl in UNITS) if u]
        try:
            sdr = _G["get_process_status"]() if _G.get("get_process_status") else {}
        except Exception as e:
            sdr = {"error": str(e)}
        host = (request.host or "").split(":")[0]
        if not host or re.match(r"^[0-9.]+$", host) or host in ("localhost",):
            doms = _caddy_domains()
            host = doms[0] if doms else ""
        cert = _cert_info(host)
        du_base = shutil.disk_usage(str(BASE))
        disk = {"total": du_base.total, "used": du_base.used, "free": du_base.free}
        sizes = []
        for label, p in (("Journaux (logs/)", LOGS), ("Sauvegardes (backups/)", BACKUPS),
                         ("Frontend publié (dist/)", BASE / "frontend" / "dist"),
                         ("Dépendances frontend (node_modules/)", BASE / "frontend" / "node_modules")):
            if p.exists():
                sizes.append({"label": label, "size": _dir_size(p)})
        for lf in sorted(BASE.glob("*.log")) + sorted(BASE.glob("*.txt")):
            if lf.name.startswith("log") or lf.suffix == ".log":
                sizes.append({"label": lf.name, "size": lf.stat().st_size})
        try:
            up = float(Path("/proc/uptime").read_text().split()[0])
            load = os.getloadavg()
        except Exception:
            up, load = 0, (0, 0, 0)
        mem = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, v = line.split(":", 1)
                if k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
                    mem[k] = int(v.split()[0]) * 1024
        except Exception:
            pass
        crash = _tail(BASE / "crash.log", 25)
        return jsonify({"ok": True, "units": units, "sdr": sdr, "cert": cert, "disk": disk,
                        "sizes": sizes, "uptime": up, "load": load, "mem": mem,
                        "crash": crash, "signal": dict(_sig_state)})

    # ── Qualité du signal ───────────────────────────────────────────────
    @app.route("/admin/api/signal")
    @lr
    def signal():
        try:
            hours = max(1, min(24 * SIGNAL_KEEP_DAYS, int(request.args.get("hours", "24"))))
        except ValueError:
            hours = 24
        cut = time.time() - hours * 3600
        rows = []
        if SIGNAL_FILE.is_file():
            with open(SIGNAL_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    if d.get("ts", 0) >= cut:
                        rows.append(d)
        rows.sort(key=lambda d: d.get("ts", 0))
        return jsonify({"ok": True, "rows": rows, "bands": [b[0] for b in BANDS],
                        "every": SIGNAL_EVERY, "state": dict(_sig_state)})

    @app.route("/admin/api/signal/sample", methods=["POST"])
    @lr
    def signal_sample():
        ok, err = sample_signal_now()
        return jsonify({"ok": ok, "msg": err})

    # ── Carte : visites récentes géolocalisées ──────────────────────────
    @app.route("/admin/api/map/visits")
    @lr
    def map_visits():
        LI = _G.get("LI")
        try:
            hours = max(1, min(24 * 90, int(request.args.get("hours", "24"))))
        except ValueError:
            hours = 24
        cut = _now_utc() - timedelta(hours=hours)
        days = int(hours // 24) + 1
        by = {}
        for i in range(days, -1, -1):
            d = (_now_utc() - timedelta(days=i)).strftime("%Y-%m-%d")
            for e in LI.read_jsonl(LI.LOGS / ("usage_%s.jsonl" % d)):
                if e.get("ev") != "visit" or e.get("lat") is None:
                    continue
                try:
                    ts = datetime.strptime(e.get("ts", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if ts < cut:
                    continue
                k = e.get("iph", "?")
                st = by.setdefault(k, {"n": 0})
                st["n"] += 1
                st.update(lat=e.get("lat"), lon=e.get("lon"), city=e.get("city", ""),
                          country=e.get("country", ""), cc=e.get("countryCode", ""),
                          net=e.get("net", ""), last=e.get("ts", ""))
        return jsonify({"ok": True, "visits": list(by.values()), "hours": hours})

    threading.Thread(target=_background, daemon=True, name="admin-extras").start()
