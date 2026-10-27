#!/usr/bin/env python3
"""
PhantomSDR-Plus Reverse Proxy
==============================
Reads all configuration from admin_config.json (written by setup_admin.sh):

  proxy_port   → port this proxy listens on          (e.g. 8902)
  port         → admin panel internal port           (e.g. 3000)
  public_port  → spectrumserver port                 (e.g. 8900)
  sdr_host     → host used to reach spectrumserver   (127.0.0.1)

Routes:
  /admin*  → Admin panel     (localhost:{port})
  /log*    → ORSAT-LOG, carnet de trafic (localhost:{log_port}, si log_port est défini)
  /*       → Spectrumserver  ({sdr_host}:{public_port})

Several receivers on one port: see receivers.toml.example. With a
receivers.toml next to this file, /* goes to one of the receivers listed there
(chosen by ?rx=, the rx cookie, the Host header, else the default), and the
proxy can also listen on the public port the listeners already use.

Note on sdr_host
----------------
Older versions had to set this to the machine's LAN IP because spectrumserver
closed WebSockets arriving from 127.0.0.1.  That filter is gone, so the upstream
is plain loopback: no DHCP lease change or downed interface can break the proxy,
and setup no longer has to guess which of docker0 / vmnet* / a VPN is the "real"
interface.  Override sdr_host in admin_config.json only if spectrumserver runs
on a different machine.

Run:  python3 proxy.py            (foreground)
      bash manage_admin.sh start  (background with logging)
"""

import asyncio
import logging
import re
import sys
import time
import json
import mimetypes
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import listener_intel as LI   # statistiques privées (panneau admin uniquement)

try:
    import aiohttp
    from aiohttp import web, ClientSession, ClientTimeout, WSMsgType
except ImportError:
    print("[ERROR] aiohttp is not installed. Run:", file=sys.stderr)
    print("        pip3 install aiohttp --break-system-packages", file=sys.stderr)
    sys.exit(1)

# ── Load configuration ─────────────────────────────────────────────────────────
# Two sources. station.conf is written by configure-station.sh on a station set
# up with it, and gives the ports of the whole station. admin_config.json is
# written by setup_admin.sh and wins wherever both name the same port, so a
# station installed before station.conf existed behaves exactly as it did.
_STATION_KEYS = {
    "PORT_PUBLIC": "proxy_port",   # the one port listeners use
    "PORT_SDR":    "public_port",  # spectrumserver, on loopback behind us
    "PORT_ADMIN":  "port",         # admin panel, on loopback behind us
    "PORT_RADE":   "rade_port",
    "PORT_STATS":  "stats_port",
    "PORT_RELAY":  "relay_port",
    "PORT_TLS":    "tls_port",     # loopback port the https front (Caddy) uses
}


def _read_station_conf(path: Path) -> dict:
    """The ports in station.conf (shell KEY=value lines), as admin_config keys."""
    out = {}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return out
    for line in lines:
        m = re.match(r'\s*([A-Z_]+)=["\']?(\d+)["\']?\s*(#.*)?$', line)
        if m and m.group(1) in _STATION_KEYS:
            out[_STATION_KEYS[m.group(1)]] = int(m.group(2))
    return out


_cfg = _read_station_conf(Path(__file__).parent / "station.conf")
_cfg_path = Path(__file__).parent / "admin_config.json"
try:
    with open(_cfg_path) as _f:
        _cfg.update(json.load(_f))
except FileNotFoundError:
    if not _cfg:
        print(f"[ERROR] admin_config.json not found at {_cfg_path}", file=sys.stderr)
        print("        Run configure-station.sh or setup_admin.sh first.", file=sys.stderr)
        sys.exit(1)
except json.JSONDecodeError as _e:
    print(f"[ERROR] admin_config.json is invalid JSON: {_e}", file=sys.stderr)
    sys.exit(1)

for _key in ("port", "public_port", "proxy_port"):
    if _key not in _cfg:
        print(f"[ERROR] Missing '{_key}' in admin_config.json.", file=sys.stderr)
        print("        Re-run configure-station.sh or setup_admin.sh.", file=sys.stderr)
        sys.exit(1)


# sdr_host: loopback by default — spectrumserver serves local connections now
# (see src/websocket.cpp on_open). An explicit sdr_host in admin_config.json is
# still honoured for the unusual case of spectrumserver running on another host.
_sdr_host = _cfg.get("sdr_host") or "127.0.0.1"
_sdr_port = int(_cfg["public_port"])

LISTEN_HOST    = "0.0.0.0"
LISTEN_PORT    = int(_cfg["proxy_port"])
ADMIN_UPSTREAM = f"http://127.0.0.1:{int(_cfg['port'])}"
SDR_UPSTREAM   = f"http://{_sdr_host}:{_sdr_port}"


def _running_sdr_port():
    """spectrumserver's real port: [server] port of the --config file of the
    spectrumserver process running on this machine, or None."""
    for cmd in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            argv = cmd.read_bytes().split(b"\0")
        except OSError:
            continue
        if not argv or not argv[0].endswith(b"spectrumserver"):
            continue
        args = [a.decode(errors="replace") for a in argv if a]
        conf = None
        for i, a in enumerate(args):
            if a in ("--config", "-c") and i + 1 < len(args):
                conf = args[i + 1]
            elif a.startswith("--config="):
                conf = a.split("=", 1)[1]
        if not conf:
            continue
        try:
            section = ""
            for line in Path(conf).read_text().splitlines():
                line = line.split("#", 1)[0].strip()
                m = re.match(r"^\[([^\]]+)\]$", line)
                if m:
                    section = m.group(1).strip()
                    continue
                m = re.match(r"^port\s*=\s*(\d+)$", line)
                if m and section in ("", "server"):
                    return int(m.group(1))
        except OSError:
            continue
    return None


if _sdr_port == LISTEN_PORT and _sdr_host in ("127.0.0.1", "localhost", "::1"):
    # public_port in admin_config.json is spectrumserver's own port, but the
    # admin panel used to describe it as "the port users connect to", so it is
    # easily set to the proxy's port. Rather than refuse to start (the whole
    # station goes off the air), find the port spectrumserver really uses.
    _real = None
    for _attempt in range(30):          # at boot spectrumserver may start after us
        _real = _running_sdr_port()
        if _real:
            break
        import time as _time
        _time.sleep(2)
    if _real and _real != LISTEN_PORT:
        print(f"[WARN] admin_config.json: public_port ({_sdr_port}) equals proxy_port — using "
              f"spectrumserver's real port {_real} from its config.", file=sys.stderr)
        print(f"       Fix it for good: set public_port to {_real} in admin_config.json.", file=sys.stderr)
        _sdr_port = _real
        SDR_UPSTREAM = f"http://{_sdr_host}:{_sdr_port}"
    else:
        print(f"[ERROR] admin_config.json: public_port (spectrumserver) and proxy_port are "
              f"both {LISTEN_PORT} — the proxy would forward to itself.", file=sys.stderr)
        print("        Give spectrumserver its own port: bash configure-station.sh", file=sys.stderr)
        sys.exit(1)

# ── Side services behind the same public port ──────────────────────────────────
# A station set up with configure-station.sh forwards ONE port on its router.
# The RADE sidecar, the statistics server and the WebSDR relay then listen on
# loopback, and the page reaches each of them here under a path prefix that is
# stripped on the way through (/stats/api/system-stats → /api/system-stats).
# A station whose config names none of these ports gets no such route, and
# those paths go to spectrumserver exactly as before.
SIDE_SERVICES: "dict[str, str]" = {}
# /log : ORSAT-LOG, le carnet de trafic (dépôt Orsat-LOG, run.py --central), sur log_port.
for _prefix, _key in (("/rade", "rade_port"), ("/stats", "stats_port"),
                      ("/relay", "relay_port"), ("/log", "log_port")):
    if _cfg.get(_key):
        SIDE_SERVICES[_prefix] = f"http://127.0.0.1:{int(_cfg[_key])}"


def _side_service(request: web.Request) -> "tuple[str, str] | None":
    """(upstream, path for it) when the request is for a side service."""
    path = request.path
    for prefix, upstream in SIDE_SERVICES.items():
        if path == prefix or path.startswith(prefix + "/"):
            rest = path[len(prefix):] or "/"
            qs = request.rel_url.query_string
            return upstream, rest + ("?" + qs if qs else "")
    return None

# ── Several receivers behind one port (receivers.toml) ─────────────────────────
# Optional. Without the file there is one SDR upstream, exactly as before. With
# it, every non-admin request goes to one of the receivers listed there, chosen
# in this order:
#   1. ?rx=<id> in the URL — the page, and every socket and poll it opens
#      (frontend/src/lib/rx.js adds it)
#   2. the rx cookie, set on any response to a request with a valid ?rx=
#   3. the receiver whose `hostnames` list holds the Host header's name
#   4. the default receiver
# A Kiwi client carries none of these, so it always lands on the default.
# [front] port is a second listening port next to proxy_port: the public port
# the listeners, the directories and websdr.org already know.
RX_COOKIE   = "rx"
RECEIVERS: "dict[str, dict]" = {}
DEFAULT_RX  = ""
FRONT_PORT  = 0
_rx_path = Path(__file__).parent / "receivers.toml"
if _rx_path.exists():
    try:
        import tomllib
        with open(_rx_path, "rb") as _f:
            _rxcfg = tomllib.load(_f)
    except Exception as _e:
        print(f"[ERROR] {_rx_path.name}: {_e}", file=sys.stderr)
        sys.exit(1)
    # Ports this proxy itself listens on. A receiver on this computer that
    # names one of them would make the proxy forward to itself: every request
    # opens another connection to us until nothing answers (2026-10-11, after
    # the main receiver moved behind the proxy and receivers.toml kept 8900).
    _own_ports = {LISTEN_PORT, int(_rxcfg.get("front", {}).get("port", 0) or 0)}
    for _r in _rxcfg.get("receiver", []):
        _id = str(_r.get("id", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", _id) or "port" not in _r:
            print(f"[ERROR] {_rx_path.name}: every [[receiver]] needs an id "
                  f"(letters, digits, - and _) and a port", file=sys.stderr)
            sys.exit(1)
        _port = int(_r["port"])
        if (str(_r.get("host", _sdr_host)) in ("127.0.0.1", "localhost", "::1")
                and _port in _own_ports):
            if "instance" not in _r and _sdr_port not in _own_ports:
                print(f"[WARN]  {_rx_path.name}: receiver '{_id}' names port {_port}, "
                      f"which is this proxy's — using spectrumserver's {_sdr_port} "
                      f"(fix it with: bash configure-station.sh --apply)", file=sys.stderr)
                _port = _sdr_port
            else:
                print(f"[ERROR] {_rx_path.name}: receiver '{_id}' names port {_port}, "
                      f"which is this proxy's — left out; give it its own port",
                      file=sys.stderr)
                continue
        RECEIVERS[_id] = {
            "name":      str(_r.get("name", _id)),
            "upstream":  f"http://{_r.get('host', _sdr_host)}:{_port}",
            "host":      str(_r.get("host", _sdr_host)),
            "port":      _port,
            "hostnames": [str(h).lower() for h in _r.get("hostnames", [])],
            # Where the page's receiver picker sends a visitor. Absolute when
            # the receiver has its own public port; else this proxy + ?rx=.
            "url":       str(_r.get("url") or ("/?rx=" + _id)),
        }
        if _r.get("default"):
            if DEFAULT_RX:
                print(f"[ERROR] {_rx_path.name}: more than one default receiver",
                      file=sys.stderr)
                sys.exit(1)
            DEFAULT_RX = _id
    if not RECEIVERS:
        print(f"[ERROR] {_rx_path.name}: no [[receiver]] entries", file=sys.stderr)
        sys.exit(1)
    DEFAULT_RX   = DEFAULT_RX or next(iter(RECEIVERS))
    SDR_UPSTREAM = RECEIVERS[DEFAULT_RX]["upstream"]
    FRONT_PORT   = int(_rxcfg.get("front", {}).get("port", 0) or 0)


def _pick_receiver(request: web.Request) -> "tuple[str, str]":
    """Return (upstream, id to remember in the rx cookie, or "")."""
    if not RECEIVERS:
        return SDR_UPSTREAM, ""
    rid = request.query.get("rx", "")
    if rid in RECEIVERS:
        return RECEIVERS[rid]["upstream"], rid
    rid = request.cookies.get(RX_COOKIE, "")
    if rid in RECEIVERS:
        return RECEIVERS[rid]["upstream"], ""
    host = (request.host or "").lower()
    host = host[:host.rfind(":")] if host.rfind(":") > host.rfind("]") else host
    for rid, r in RECEIVERS.items():
        if host in r["hostnames"]:
            return r["upstream"], ""
    return SDR_UPSTREAM, ""


def _upstream_path(request: web.Request) -> str:
    """The request path and query for the upstream, minus our own rx=: it
    only picks the receiver, and spectrumserver matches some paths (/users)
    exactly, query and all."""
    url = request.rel_url
    if "rx" in url.query:
        rest = [(k, v) for k, v in url.query.items() if k != "rx"]
        url = url.with_query(rest or None)
    return str(url)


# Which receivers answer right now, for /receivers.json: a stopped receiver
# drops out of the page's picker instead of leading to an error page. One TCP
# connect per receiver, half a second at most, and the answer is reused for
# a few seconds so that every open page re-reading the list costs nothing.
_UP_CACHE: "dict[str, bool]" = {}
_UP_CACHE_AT = 0.0
_UP_CACHE_S = 5.0


async def _receiver_up(r: dict) -> bool:
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(r["host"], r["port"]), timeout=0.5)
        writer.close()
        return True
    except Exception:
        return False


async def _receivers_up() -> "dict[str, bool]":
    global _UP_CACHE, _UP_CACHE_AT
    now = asyncio.get_running_loop().time()
    if now - _UP_CACHE_AT > _UP_CACHE_S:
        ids = list(RECEIVERS)
        results = await asyncio.gather(*(_receiver_up(RECEIVERS[i]) for i in ids))
        _UP_CACHE, _UP_CACHE_AT = dict(zip(ids, results)), now
    return _UP_CACHE


def _local_port(request: web.Request) -> int:
    """The port this request arrived on (proxy_port or the front port)."""
    try:
        return int(request.transport.get_extra_info("sockname")[1])
    except Exception:
        return LISTEN_PORT

# ── Active WebSocket registry (powers the admin "kick") ─────────────────────────
# proxy.py owns every client WebSocket, so it can disconnect a user simply by
# closing the matching ws_client — no CAP_NET_ADMIN / 'ss -K' privilege needed.
# admin_server.py calls the localhost-only /__proxy_control/kick endpoint below.
ACTIVE_WS: "dict[str, set]" = {}

# Close code sent to a kicked listener. A plain 1000 is indistinguishable from
# an ordinary dropped connection, and audio.js reconnects after one of those —
# so the kicked browser came straight back with sound while its waterfall, which
# has no reconnect, stayed frozen. 4001 is in the private range and the frontend
# treats it as terminal (KICKED_CLOSE_CODE in frontend/src/refused.js).
KICK_CLOSE_CODE = 4001


def _norm_ip(ip: str) -> str:
    ip = (ip or "").strip()
    if ip.startswith("::ffff:"):
        ip = ip[7:]  # IPv4-mapped IPv6 → plain IPv4, so keys match ss/admin list
    return ip


def _register_ws(ip: str, ws) -> None:
    ACTIVE_WS.setdefault(ip, set()).add(ws)


def _unregister_ws(ip: str, ws) -> None:
    conns = ACTIVE_WS.get(ip)
    if conns is not None:
        conns.discard(ws)
        if not conns:
            ACTIVE_WS.pop(ip, None)


async def handle_kick(request: web.Request) -> web.Response:
    """Localhost-only control endpoint: close all WebSockets from a given IP.

    Called by admin_server.py's /admin/api/kick. Restricted to loopback so it
    can never be reached by an external client through the public proxy port.
    """
    if not _is_local(request):
        return web.json_response({"ok": False, "msg": "forbidden"}, status=403)
    try:
        data = await request.json()
    except Exception:
        data = {}
    ip = _norm_ip(data.get("ip", ""))
    if not ip:
        return web.json_response({"ok": False, "msg": "no ip"}, status=400)

    closed = 0
    for ws in list(ACTIVE_WS.get(ip, ())):
        try:
            if not ws.closed:
                await ws.close(code=KICK_CLOSE_CODE,
                               message=b"disconnected by the sysop")
                closed += 1
        except Exception:
            pass
    return web.json_response({"ok": True, "count": closed})

# ── Client-identity headers ───────────────────────────────────────────────────
# spectrumserver believes X-Forwarded-For / X-Real-IP from a loopback peer, and
# every connection this proxy makes to it IS loopback. Whatever a client sends
# in these headers is therefore dropped (in any letter case) before ours are
# added, or a visitor could claim to be 127.0.0.1 and skip the per-IP limits.
_CLIENT_ID_HEADERS = frozenset(("x-forwarded-for", "x-forwarded-host",
                                "x-forwarded-proto", "x-forwarded-port",
                                "x-real-ip", "forwarded"))


# ── The https front ───────────────────────────────────────────────────────────
# setup-https.sh puts Caddy on port 443 and points it at tls_port, a second
# listener of this proxy on loopback only. Everything arriving there comes from
# Caddy, so request.remote is 127.0.0.1 for every visitor — which this proxy
# (and spectrumserver behind it) would otherwise take for "this computer":
# allowed to kick, exempt from the per-IP limits. On that listener the visitor
# is the address Caddy reports in X-Forwarded-For (the last entry, the one
# Caddy itself appended), and the request is never local.
TLS_PORT = int(_cfg.get("tls_port") or 0)


def _via_tls(request: web.Request) -> bool:
    return bool(TLS_PORT) and _local_port(request) == TLS_PORT


def _client(request: web.Request) -> str:
    """The visitor's address, whichever listener the request came in on."""
    if _via_tls(request):
        fwd = request.headers.get("X-Forwarded-For", "")
        last = fwd.split(",")[-1].strip() if fwd else ""
        return last or "0.0.0.0"
    return request.remote or ""


def _is_local(request: web.Request) -> bool:
    if _via_tls(request):
        return False
    return _norm_ip(request.remote) in ("127.0.0.1", "::1")

# ─────────────────────────────────────────────────────────────────────────────

# Le spectrumserver ne connaît que html/js/css/wasm et sert tout le reste en
# text/plain : Firefox refuse alors de lire les sons .opus de la base de
# signaux (« not suitable »). On corrige le type d'après l'extension.
_EXTRA_TYPES = {
    ".opus": "audio/ogg", ".ogg": "audio/ogg", ".oga": "audio/ogg",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac",
    ".webp": "image/webp", ".svg": "image/svg+xml", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".ico": "image/x-icon",
    ".pdf": "application/pdf", ".json": "application/json",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
    ".mp4": "video/mp4", ".webm": "video/webm",
}


def _fix_static_type(headers: dict, url: str) -> None:
    key = next((k for k in headers if k.lower() == "content-type"), None)
    cur = (headers.get(key, "") if key else "").split(";")[0].strip().lower()
    if cur and cur != "text/plain":
        return
    path = url.split("?", 1)[0].split("#", 1)[0]
    ext = path[path.rfind("."):].lower() if "." in path.rsplit("/", 1)[-1] else ""
    ctype = _EXTRA_TYPES.get(ext) or (mimetypes.guess_type(path)[0] if ext else None)
    if not ctype or ctype == "text/plain":
        return
    if key:
        del headers[key]
    headers["Content-Type"] = ctype


# Taille maximale d'une requête. aiohttp refuse au-delà de 1 Mo (client_max_size), ce qui
# suffit au WebSDR et au panneau ; le carnet ORSAT-LOG reçoit des fichiers ADIF de plusieurs
# Mo (export QRZ.com), d'où une limite propre à /log, sous celle du carnet lui-même (50 Mo).
LOG_MAX_BODY = 60 * 1024 * 1024


async def _read_body(request: web.Request) -> bytes:
    if request.path == "/log" or request.path.startswith("/log/"):
        size = request.content_length
        if size is not None and size > LOG_MAX_BODY:
            raise web.HTTPRequestEntityTooLarge(max_size=LOG_MAX_BODY, actual_size=size)
        chunks, total = [], 0
        while True:
            chunk = await request.content.read(1 << 16)
            if not chunk:
                break
            total += len(chunk)
            if total > LOG_MAX_BODY:
                raise web.HTTPRequestEntityTooLarge(max_size=LOG_MAX_BODY, actual_size=total)
            chunks.append(chunk)
        return b"".join(chunks)
    return await request.read()        # 1 Mo au plus ailleurs (défaut aiohttp)


async def proxy_request(request: web.Request, upstream: str,
                        set_rx: str = "", path: str = "") -> web.StreamResponse:
    url = upstream + (path or _upstream_path(request))
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length", "accept-encoding")
               and k.lower() not in _CLIENT_ID_HEADERS}
    headers["Accept-Encoding"]   = "identity"
    headers["X-Forwarded-For"]   = _client(request)
    headers["X-Forwarded-Host"]  = request.headers.get("Host", "")
    headers["X-Forwarded-Proto"] = "https" if _via_tls(request) else "http"
    headers["X-Forwarded-Port"]  = "443" if _via_tls(request) else str(_local_port(request))
    try:
        timeout = ClientTimeout(total=60)
        async with ClientSession(timeout=timeout) as session:
            body = await _read_body(request)
            async with session.request(
                method=request.method,
                url=url,
                headers=headers,
                data=body,
                allow_redirects=False,
                ssl=False,
            ) as resp:
                fwd = {k: v for k, v in resp.headers.items()
                       if k.lower() not in ("transfer-encoding", "connection")}
                _fix_static_type(fwd, url)
                response = web.StreamResponse(status=resp.status, headers=fwd)
                if set_rx:
                    response.set_cookie(RX_COOKIE, set_rx, max_age=31536000,
                                        path="/", samesite="Lax")
                await response.prepare(request)
                async for chunk in resp.content.iter_chunked(65536):
                    await response.write(chunk)
                await response.write_eof()
                return response
    except aiohttp.ClientConnectorError:
        names = {u: p.strip("/").upper() + " service" for p, u in SIDE_SERVICES.items()}
        target = ("Admin panel" if upstream == ADMIN_UPSTREAM
                  else names.get(upstream, "Spectrumserver"))
        return web.Response(
            status=502,
            text=f"502 Bad Gateway — {target} is not running on {upstream}",
        )
    except Exception as e:
        return web.Response(status=500, text=f"Proxy error: {e}")


async def proxy_websocket(request: web.Request, upstream: str,
                          path: str = "") -> web.WebSocketResponse:
    """Bidirectional WebSocket tunnel.

    Key fixes vs the original:
      • max_msg_size=0 on both sides — removes the 4 MB default cap that
        silently kills large FFT frames from the RX-888 at 60 MSPS.
      • heartbeat=30 — keeps long-lived connections alive through NAT.
      • Sec-WebSocket-Protocol forwarded — correct subprotocol negotiation.
      • X-Forwarded-* on WS upgrade — real client IP visible in server logs.
      • Close codes propagated — browser gets a meaningful disconnect reason.
    """
    raw_protocols = request.headers.get("Sec-WebSocket-Protocol", "")
    protocol_list = [p.strip() for p in raw_protocols.split(",") if p.strip()]

    ws_client = web.WebSocketResponse(
        max_msg_size=0,
        protocols=protocol_list,
        autoping=True,
        heartbeat=30.0,
    )
    await ws_client.prepare(request)

    # Register for the admin kick (see handle_kick). request.remote is the real
    # client IP because the browser connects to this proxy directly.
    client_ip = _norm_ip(_client(request))
    _register_ws(client_ip, ws_client)

    ws_url = upstream.replace("http://", "ws://") + (path or _upstream_path(request))

    _skip = frozenset(("host", "upgrade", "connection",
                        "sec-websocket-key", "sec-websocket-version",
                        "sec-websocket-protocol", "sec-websocket-extensions"))
    fwd_headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in _skip
                   and k.lower() not in _CLIENT_ID_HEADERS}
    fwd_headers["X-Forwarded-For"]   = _client(request)
    fwd_headers["X-Forwarded-Host"]  = request.headers.get("Host", "")
    fwd_headers["X-Forwarded-Proto"] = "wss" if _via_tls(request) else "ws"
    fwd_headers["X-Forwarded-Port"]  = "443" if _via_tls(request) else str(_local_port(request))

    try:
        async with ClientSession() as session:
            try:
                async with session.ws_connect(
                    ws_url,
                    headers=fwd_headers,
                    protocols=protocol_list,
                    max_msg_size=0,
                    heartbeat=30.0,
                    autoclose=True,
                    autoping=True,
                ) as ws_upstream:

                    async def forward_up():
                        """Browser → Spectrumserver"""
                        async for msg in ws_client:
                            if msg.type == WSMsgType.TEXT:
                                await ws_upstream.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                await ws_upstream.send_bytes(msg.data)
                            elif msg.type == WSMsgType.ERROR:
                                break
                        # The loop ends at the browser's close frame without
                        # yielding it (aiohttp's iterator swallows it), so the
                        # close is passed on here, code and all.
                        if not ws_upstream.closed:
                            await ws_upstream.close(
                                code=ws_client.close_code or 1000)

                    async def forward_down():
                        """Spectrumserver → Browser"""
                        async for msg in ws_upstream:
                            if msg.type == WSMsgType.TEXT:
                                await ws_client.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                await ws_client.send_bytes(msg.data)
                            elif msg.type == WSMsgType.ERROR:
                                break
                        # Same here: the server's close frame ends the loop
                        # unseen, and its code is what the page acts on (4003
                        # refused by a limit, 4001 kicked by the sysop), so
                        # it must reach the browser rather than a plain 1000.
                        if not ws_client.closed:
                            await ws_client.close(
                                code=ws_upstream.close_code or 1000,
                                message=b"upstream closed")

                    task_up   = asyncio.ensure_future(forward_up())
                    task_down = asyncio.ensure_future(forward_down())
                    done, pending = await asyncio.wait(
                        {task_up, task_down},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

            except aiohttp.ClientConnectorError:
                if not ws_client.closed:
                    await ws_client.close(code=1014, message=b"upstream unreachable")
            except aiohttp.WSServerHandshakeError:
                if not ws_client.closed:
                    await ws_client.close(code=1014, message=b"upstream handshake failed")
            except Exception:
                if not ws_client.closed:
                    await ws_client.close(code=1011, message=b"proxy error")

    except Exception:
        pass

    if not ws_client.closed:
        await ws_client.close()
    _unregister_ws(client_ip, ws_client)
    return ws_client


# ── Statistiques privées des auditeurs ─────────────────────────────────────────
# Tout ce qui suit ne sert qu'au panneau admin (page « Analyse auditeurs »).
#  • /__usage : la page signale ses décodeurs et quelques infos de navigateur.
#    Le proxy y ajoute l'identifiant HMAC de l'auditeur et la fiche ip-api de
#    son IP, puis l'écrit dans logs/usage_*.jsonl — jamais l'IP en clair.
#  • chaque chargement de la page est noté (provenance, navigateur, https).
#  • /users, /users.json et /logs/users_*.jsonl contiennent les IP : pour le
#    public, le proxy les remplace par l'identifiant HMAC. Le panneau, lui,
#    les lit directement sur la boucle locale.
_usage_hits: "dict[str, list]" = {}
_known_listeners: "set[str]" = set()


def _load_known_listeners() -> None:
    limit = (datetime.now(timezone.utc) - timedelta(days=LI.RETENTION_DAYS)).strftime("%Y-%m-%d")
    for p in LI.LOGS.glob("usage_*.jsonl"):
        if p.stem[6:] >= limit:
            for e in LI.read_jsonl(p):
                if e.get("ev") == "visit" and e.get("iph"):
                    _known_listeners.add(e["iph"])


def _usage_rate_ok(ip: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _usage_hits.get(ip, []) if now - t < 60]
    if len(hits) >= 30:
        _usage_hits[ip] = hits
        return False
    hits.append(now)
    _usage_hits[ip] = hits
    return True


def _geo_fields(g: dict) -> dict:
    keep = ("country", "countryCode", "regionName", "city", "lat", "lon", "timezone",
            "isp", "org", "as", "asname", "mobile", "proxy", "hosting", "local")
    out = {k: g[k] for k in keep if k in g}
    out["net"] = LI.net_kind(g)
    return out


async def _record(ip: str, event: dict) -> None:
    loop = asyncio.get_running_loop()
    try:
        g = await loop.run_in_executor(None, LI.geo, ip)
        event["iph"] = LI.ip_hash(ip)
        event.update(_geo_fields(g))
        await loop.run_in_executor(None, LI.append, event)
    except Exception as e:                      # les stats ne doivent jamais gêner
        logging.getLogger("usage").warning("usage log: %s", e)


_USAGE_STR = {"ev": 12, "decoder": 16, "prev": 16, "lang": 16, "tz": 48, "screen": 16,
              "ref": 300, "path": 64}


async def handle_usage(request: web.Request) -> web.Response:
    if request.method != "POST":
        return web.Response(status=405)
    ip = _client(request)
    if not _usage_rate_ok(ip):
        return web.Response(status=204)
    try:
        raw = await request.content.read(4096)
        d = json.loads(raw.decode("utf-8", "replace"))
        if not isinstance(d, dict):
            raise ValueError
    except Exception:
        return web.Response(status=400)
    ev = str(d.get("ev", ""))[:12]
    if ev not in ("hello", "decoder"):
        return web.Response(status=400)
    rec = {k: str(d[k])[:n] for k, n in _USAGE_STR.items() if d.get(k) not in (None, "")}
    if isinstance(d.get("langs"), list):
        rec["langs"] = [str(x)[:16] for x in d["langs"][:4]]
    for k in ("dpr", "touch"):
        if isinstance(d.get(k), (int, float)):
            rec[k] = d[k]
    if ev == "hello":
        rec["https"] = _via_tls(request)
        rec["src"] = LI.ref_host(rec.get("ref", ""), request.headers.get("Host", ""))
        rec.update(LI.classify_ua(request.headers.get("User-Agent", "")))
    asyncio.create_task(_record(ip, rec))
    return web.Response(status=204)


def _note_visit(request: web.Request) -> None:
    if request.method != "GET" or request.path not in ("/", "/index.html"):
        return
    if "text/html" not in request.headers.get("Accept", "") or _is_local(request):
        return
    ip = _client(request)
    iph = LI.ip_hash(ip)
    ua = request.headers.get("User-Agent", "")
    rec = {"ev": "visit", "https": _via_tls(request),
           "src": LI.ref_host(request.headers.get("Referer", ""), request.headers.get("Host", "")),
           "query": request.query_string[:120], "accept_lang": request.headers.get("Accept-Language", "")[:40],
           "ua": ua[:200], "returning": iph in _known_listeners}
    rec.update(LI.classify_ua(ua))
    _known_listeners.add(iph)
    asyncio.create_task(_record(ip, rec))


def _anon_ip(ip: str) -> str:
    return ip if LI.is_private(ip) else "h:" + LI.ip_hash(ip)


async def _public_listener_data(request: web.Request, upstream: str):
    """/users, /users.json et /logs/users_*.jsonl pour le public : IP remplacées."""
    path = request.path
    is_users = path in ("/users", "/users.json")
    is_log = path.startswith("/logs/") and path.endswith(".jsonl")
    if not (is_users or is_log) or _is_local(request) or request.method != "GET":
        return None
    try:
        async with ClientSession(timeout=ClientTimeout(total=20)) as session:
            async with session.get(upstream + _upstream_path(request)) as resp:
                status = resp.status
                body = await resp.read()
    except Exception:
        return web.Response(status=502, text="502 Bad Gateway")
    if status != 200:
        return web.Response(status=status, body=body)
    text = body.decode("utf-8", "replace")
    if is_users:
        try:
            d = json.loads(text)
            for u in d.get("users", []):
                ip = u.get("ip", "")
                if ip:
                    if LI.is_sysop(ip):
                        u["geo"] = "SYSOP"
                    elif u.get("geo") == ip:
                        u["geo"] = ""
                    u["ip"] = _anon_ip(ip)
            text = json.dumps(d, ensure_ascii=False)
        except ValueError:
            return web.Response(status=502, text="502 Bad Gateway")
        ctype = "application/json"
    else:
        out = []
        for line in text.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("ip"):
                if LI.is_sysop(e["ip"]):
                    e["geo"] = "SYSOP"
                elif e.get("geo") == e["ip"]:
                    e["geo"] = ""
                e["ip"] = _anon_ip(e["ip"])
            out.append(json.dumps(e, ensure_ascii=False))
        text = "\n".join(out) + ("\n" if out else "")
        ctype = "application/x-ndjson"
    return web.Response(text=text, content_type=ctype.split(";")[0],
                        headers={"Cache-Control": "no-store",
                                 "Access-Control-Allow-Origin": "*"})


# A station with https sends the browsers that open its plain http page to the
# https one: same name, port 443, same query (frequency, mode...). Only a page
# load is redirected — GET of "/" asking for text/html, under a DNS name — so
# the websdr.org callback, Kiwi clients, directory polls, http-only diversity
# partners and LAN access by IP address keep using http exactly as before.
# Off with "https_redirect": false in admin_config.json.
HTTPS_REDIRECT = bool(TLS_PORT) and _cfg.get("https_redirect", True) is not False
_IP_RE = re.compile(r"^[0-9.]+$|^\[?[0-9a-fA-F:]+\]?$")


def _https_redirect(request: web.Request):
    if not HTTPS_REDIRECT or _via_tls(request) or request.method != "GET":
        return None
    is_admin = request.path == "/admin" or request.path.startswith("/admin/")
    if request.path not in ("/", "/index.html") and not is_admin:
        return None
    if request.headers.get("Upgrade") or "text/html" not in request.headers.get("Accept", ""):
        return None
    host = (request.headers.get("Host") or "").strip()
    name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    if not name or "." not in name or _IP_RE.match(name) or name.endswith((".local", ".lan", ".home")):
        return None
    if _is_local(request):
        return None
    qs = request.query_string
    if is_admin:                       # le mot de passe du panneau ne circule jamais en clair
        return web.HTTPFound(f"https://{name}{request.path}" + (f"?{qs}" if qs else ""))
    return web.HTTPFound(f"https://{name}/" + (f"?{qs}" if qs else ""))


# ── Sécurité : détection des tentatives anormales ─────────────────────────────
# Tout le trafic web (http et https via Caddy) passe ici : chaque requête
# suspecte est notée dans logs/security_*.jsonl pour la page « Analyse
# auditeurs » du panneau. Les IP bannies depuis le panneau (logs/blocklist.json)
# reçoivent un 403. Après 5 échecs de connexion au panneau en 15 min, la
# connexion est refusée 30 min à cette IP.
_sec_404: "dict[str, list]" = {}
_sec_404_logged: "dict[str, float]" = {}
_sec_blocked_logged: "dict[str, float]" = {}
_login_fail: "dict[str, list]" = {}
_login_lock: "dict[str, float]" = {}
LOGIN_MAX_FAIL, LOGIN_WINDOW, LOGIN_LOCK = 5, 900, 1800
# Blocage global : contre un réseau de machines qui essaie depuis des milliers
# d'IP différentes. Au-delà de GLOBAL_MAX_FAIL échecs en 1 h (toutes IP
# confondues), la connexion au panneau est refusée 15 min — sauf aux IP qui se
# sont déjà connectées avec succès (90 derniers jours), pour que le
# propriétaire ne soit jamais enfermé dehors.
GLOBAL_MAX_FAIL, GLOBAL_WINDOW, GLOBAL_LOCK = 30, 3600, 900
_login_fail_all: "list[float]" = []
_global_lock_until = 0.0
_TRUSTED_FILE = Path(__file__).resolve().parent / "logs" / "admin_trusted.json"
_TRUSTED_TTL = 90 * 86400


def _load_trusted() -> dict:
    try:
        data = json.loads(_TRUSTED_FILE.read_text())
        cut = time.time() - _TRUSTED_TTL
        return {k: v for k, v in data.items() if isinstance(v, (int, float)) and v > cut}
    except Exception:
        return {}


_admin_trusted = _load_trusted()


# Restriction par pays du panneau admin : "admin_countries": ["FR"] dans
# admin_config.json (relu à chaque modification, sans redémarrage). Absent ou
# vide = aucune restriction. Toujours autorisés : réseau local, et IP déjà
# connectées avec succès au panneau (90 j) — sécurité contre l'auto-blocage.
_countries_cache = {"mtime": None, "val": ()}


def _admin_countries() -> tuple:
    try:
        m = _cfg_path.stat().st_mtime
        if m != _countries_cache["mtime"]:
            with open(_cfg_path) as f:
                v = json.load(f).get("admin_countries") or []
            _countries_cache.update(mtime=m, val=tuple(str(c).upper() for c in v if c))
    except Exception:
        pass
    return _countries_cache["val"]


async def _admin_country_denied(request: web.Request, ip: str):
    allowed = _admin_countries()
    if not allowed or _is_trusted(ip):
        return None
    loop = asyncio.get_running_loop()
    try:
        g = await loop.run_in_executor(None, LI.geo, ip)
    except Exception:
        g = {}
    cc = (g.get("countryCode") or "").upper()
    if g.get("local") or cc in allowed:
        return None
    now = time.monotonic()
    if now - _sec_blocked_logged.get("cc:" + ip, 0) > 600:
        _sec_blocked_logged["cc:" + ip] = now
        asyncio.create_task(_sec_record(request, ip, "admin_country", 403, {"cc": cc or "?"}))
    msg = ("403 — Panneau d'administration non accessible depuis ce pays."
           if cc else "403 — Localisation impossible pour le moment, réessayez dans une minute.")
    return web.Response(status=403, text=msg)


def _is_trusted(ip: str) -> bool:
    try:
        t = _admin_trusted.get(LI.ip_hash(ip))
        return bool(t and t > time.time() - _TRUSTED_TTL)
    except Exception:
        return False


def _mark_trusted(ip: str) -> None:
    try:
        _admin_trusted[LI.ip_hash(ip)] = time.time()
        _TRUSTED_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _TRUSTED_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_admin_trusted))
        tmp.replace(_TRUSTED_FILE)
    except Exception as e:
        logging.getLogger("security").warning("admin trusted: %s", e)


async def _sec_record(request: web.Request, ip: str, cat: str, status: int, extra: dict = None) -> None:
    if LI.is_sysop(ip):
        return   # le sysop n'est pas un suspect
    ev = {"ip": LI.norm_ip(ip), "cat": cat, "method": request.method,
          "path": (request.raw_path or "")[:300], "status": status,
          "ua": request.headers.get("User-Agent", "")[:200],
          "https": _via_tls(request), "host": request.headers.get("Host", "")[:80]}
    if extra:
        ev.update(extra)
    loop = asyncio.get_running_loop()
    try:
        g = await loop.run_in_executor(None, LI.geo, ip)
        ev.update(_geo_fields(g))
        if g.get("rdns"):
            ev["rdns"] = g["rdns"]
        ev["iph"] = LI.ip_hash(ip)
        await loop.run_in_executor(None, LI.append_security, ev)
    except Exception as e:
        logging.getLogger("security").warning("security log: %s", e)


def _sec_after(request: web.Request, ip: str, status: int) -> None:
    now = time.monotonic()
    cat = LI.classify_request(request.method, request.raw_path or request.path, status)
    if request.path in ("/admin", "/admin/") and request.method == "POST":
        if status == 200:                      # page de login réaffichée = mauvais code
            fails = [t for t in _login_fail.get(ip, []) if now - t < LOGIN_WINDOW] + [now]
            _login_fail[ip] = fails
            cat = "admin_login_fail"
            global _login_fail_all, _global_lock_until
            _login_fail_all = [t for t in _login_fail_all if now - t < GLOBAL_WINDOW] + [now]
            if len(_login_fail_all) >= GLOBAL_MAX_FAIL and _global_lock_until <= now:
                _global_lock_until = now + GLOBAL_LOCK
                _login_fail_all = []
                asyncio.create_task(_sec_record(request, ip, "admin_global_lock", 429,
                                                {"fails": GLOBAL_MAX_FAIL}))
            if len(fails) >= LOGIN_MAX_FAIL:
                _login_lock[ip] = now + LOGIN_LOCK
                asyncio.create_task(_sec_record(request, ip, "admin_locked", 429,
                                                {"fails": len(fails)}))
        elif status in (301, 302, 303):
            _login_fail.pop(ip, None)
            _mark_trusted(ip)
            cat = "admin_login_ok"
    if status == 404 and not cat:
        hits = [t for t in _sec_404.get(ip, []) if now - t < 300] + [now]
        _sec_404[ip] = hits
        if len(hits) >= 20 and now - _sec_404_logged.get(ip, 0) > 300:
            _sec_404_logged[ip] = now
            cat = "burst404"
    if cat:
        asyncio.create_task(_sec_record(request, ip, cat, status))


async def handle(request: web.Request) -> web.StreamResponse:
    ip = _client(request)
    local = _is_local(request)
    # Liste blanche (dans LI.is_blocked) et IP déjà connectées au panneau admin
    # (90 j) : jamais bloquées, pour que l'administrateur ne s'auto-bannisse pas.
    # Une IP prise seulement dans une PLAGE bannie (liste importée…) garde
    # l'accès à la page de connexion du panneau : l'administrateur en
    # déplacement peut se connecter, et devient alors une IP de confiance.
    kind = None if (local or _is_trusted(ip)) else LI.block_kind(ip)
    if kind == "range" and (request.path == "/admin" or request.path.startswith("/admin/")):
        kind = None
    if kind:
        now = time.monotonic()
        if now - _sec_blocked_logged.get(ip, 0) > 600:
            _sec_blocked_logged[ip] = now
            asyncio.create_task(_sec_record(request, ip, "blocked", 403))
        return web.Response(status=403, text="403 Forbidden")
    if not local and (request.path == "/admin" or request.path.startswith("/admin/")):
        denied = await _admin_country_denied(request, ip)
        if denied is not None:
            return denied
    if (not local and request.method == "POST" and request.path in ("/admin", "/admin/")
            and _login_lock.get(ip, 0) > time.monotonic()):
        return web.Response(status=429, text="Trop de tentatives de connexion. Réessayez dans 30 minutes.")
    if (not local and request.method == "POST" and request.path in ("/admin", "/admin/")
            and _global_lock_until > time.monotonic() and not _is_trusted(ip)):
        return web.Response(status=429, text="Connexion au panneau temporairement suspendue "
                            "(trop de tentatives sur le serveur). Réessayez dans 15 minutes.")
    try:
        resp = await _handle(request)
    except web.HTTPException as e:
        resp = e
    if not local:
        try:
            _sec_after(request, ip, getattr(resp, "status", 0) or 0)
        except Exception as e:
            logging.getLogger("security").warning("security check: %s", e)
    return resp



# ── Relais de la réception en diversité ───────────────────────────────────────
# Une page servie en https ne peut pas ouvrir de connexion vers un récepteur en
# http (contenu mixte, refusé par le navigateur) : c'est le cas de la plupart des
# KiwiSDR. La page passe alors par /divrelay/<id>/… et ce proxy fait la connexion.
# Relais FERMÉ : seuls les partenaires inscrits dans le panneau admin
# (diversity_partners.json) sont joignables, et rien de la requête de l'auditeur
# n'est transmis à part le chemin, le corps et le sous-protocole websocket — pas
# de cookie, pas d'en-tête d'identification.
DIV_RELAY_PREFIX = "/divrelay/"
DIV_RELAY_MAX = 30                     # connexions websocket relayées en même temps
_div_relay_open = 0


def _div_partner_origin(pid: str):
    try:
        d = json.loads((Path(__file__).resolve().parent / "diversity_partners.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for p in d.get("partners", []):
        if str(p.get("id")) == pid and p.get("enabled", True):
            m = re.match(r"^(https?|wss?)://([^/?#\s]+)", str(p.get("addr", "")).strip(), re.I)
            if m:
                scheme = {"ws": "http", "wss": "https"}.get(m.group(1).lower(), m.group(1).lower())
                return f"{scheme}://{m.group(2)}"
    return None


async def handle_div_relay(request: web.Request) -> web.StreamResponse:
    global _div_relay_open
    pid, _, sub = request.path[len(DIV_RELAY_PREFIX):].partition("/")
    origin = _div_partner_origin(pid)
    if not origin:
        return web.Response(status=404, text="partenaire inconnu")
    qs = request.rel_url.query_string
    target = origin + "/" + sub + ("?" + qs if qs else "")
    ua = {"User-Agent": "ORSAT-diversity-relay", "Origin": origin}

    if request.headers.get("Upgrade", "").lower() == "websocket":
        if _div_relay_open >= DIV_RELAY_MAX:
            return web.Response(status=503, text="relais complet")
        protocols = [x.strip() for x in request.headers.get("Sec-WebSocket-Protocol", "").split(",") if x.strip()]
        ws_client = web.WebSocketResponse(max_msg_size=0, protocols=protocols, heartbeat=30.0)
        await ws_client.prepare(request)
        _div_relay_open += 1
        try:
            async with ClientSession() as session:
                async with session.ws_connect(target.replace("http", "ws", 1), headers=ua, protocols=protocols,
                                              max_msg_size=0, heartbeat=30.0, timeout=15) as ws_up:
                    async def pump(src, dst):
                        async for msg in src:
                            if msg.type == WSMsgType.TEXT:
                                await dst.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                await dst.send_bytes(msg.data)
                            else:
                                break
                    tasks = [asyncio.create_task(pump(ws_client, ws_up)), asyncio.create_task(pump(ws_up, ws_client))]
                    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for t in tasks:
                        t.cancel()
        except Exception as e:
            logging.getLogger("proxy").info("relais diversité %s : %s", pid, e)
        finally:
            _div_relay_open -= 1
            if not ws_client.closed:
                await ws_client.close()
        return ws_client

    # HTTP simple (UberSDR : POST /connection) : corps et type de contenu seulement
    body = await request.read() if request.can_read_body else None
    hdr = dict(ua)
    if request.headers.get("Content-Type"):
        hdr["Content-Type"] = request.headers["Content-Type"]
    try:
        async with ClientSession(timeout=ClientTimeout(total=15)) as session:
            async with session.request(request.method, target, data=body, headers=hdr, allow_redirects=False) as r:
                data = await r.content.read(1024 * 1024)
                return web.Response(status=r.status, body=data,
                                    headers={"Content-Type": r.headers.get("Content-Type", "application/octet-stream"),
                                             "Cache-Control": "no-store"})
    except Exception as e:
        return web.Response(status=502, text=f"partenaire injoignable : {e}")

async def _handle(request: web.Request) -> web.StreamResponse:
    if request.path == "/__usage":
        return await handle_usage(request)
    _redir = _https_redirect(request)
    if _redir is not None:
        return _redir
    _note_visit(request)
    if request.path == "/__proxy_control/kick":
        return await handle_kick(request)
    if request.path.startswith(DIV_RELAY_PREFIX):
        return await handle_div_relay(request)
    # Récepteurs partenaires de la réception en diversité, fixés dans le panneau admin
    # (admin_extras.py). Absent : 404, la page garde son annuaire intégré.
    if request.path == "/diversity.json" and request.method == "GET":
        try:
            d = json.loads((Path(__file__).resolve().parent / "diversity_partners.json").read_text(encoding="utf-8"))
            parts = [p for p in d.get("partners", []) if p.get("enabled", True)]
        except (OSError, ValueError, AttributeError):
            return web.Response(status=404, text="404 Not Found")
        return web.json_response({"partners": parts}, headers={"Cache-Control": "no-cache"})
    # spectrumserver's /~~kick is allowed for a loopback TCP peer — and to it,
    # everything relayed from here is loopback. Without this check anyone who
    # could reach this port could disconnect and ban any listener.
    if "~~kick" in request.path and not _is_local(request):
        return web.json_response({"ok": False, "msg": "forbidden"}, status=403)
    # Le carnet n'a que des adresses relatives : il doit être servi sous « /log/ ».
    if request.path == "/log" and "/log" in SIDE_SERVICES:
        qs = request.rel_url.query_string
        return web.HTTPFound("/log/" + ("?" + qs if qs else ""))
    side = _side_service(request)
    if side:
        upstream, path = side
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return await proxy_websocket(request, upstream, path)
        return await proxy_request(request, upstream, path=path)
    if request.path.startswith("/admin"):
        upstream, set_rx = ADMIN_UPSTREAM, ""
    elif request.path == "/receivers.json" and RECEIVERS:
        # The receiver list for the page's picker: ids, names and public URLs,
        # never the internal ports — and only the receivers that are running,
        # so a stopped one's button disappears. Readable cross-origin, because
        # a receiver with its own public port serves its page from another
        # origin.
        up = await _receivers_up()
        return web.json_response(
            [{"id": rid, "name": r["name"], "url": r["url"],
              "default": rid == DEFAULT_RX}
             for rid, r in RECEIVERS.items() if up.get(rid, True)],
            headers={"Cache-Control": "no-cache",
                     "Access-Control-Allow-Origin": "*"})
    else:
        upstream, set_rx = _pick_receiver(request)
        anon = await _public_listener_data(request, upstream)
        if anon is not None:
            return anon
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await proxy_websocket(request, upstream)
    return await proxy_request(request, upstream, set_rx)


# ── Access-log noise filter ───────────────────────────────────────────────────
# The admin dashboard polls these paths every few seconds. Logging each poll
# buries the interesting traffic and inflates proxy.log roughly tenfold, so
# successful polls are dropped. Anything that is not a plain 200 still gets
# logged, so failures on these paths remain visible.
# /admin/api/logs/clear is quiet for a different reason: the admin panel
# truncates proxy.log while serving it, and this access line would be written
# afterwards — leaving one line behind and making the clear look like it failed.
#
# Keep this list identical to _QUIET_PATHS in admin_server.py. It drifted once:
# the panel silenced eight paths while the proxy silenced three, so admin.log
# stayed readable and proxy.log filled with the same polls the panel had already
# decided were noise — /admin/api/thermal alone was 72 of 78 lines, ~3 MB/day
# from a single open dashboard tab. These are the sysop's own polls; they say
# nothing about who used the receiver, which is the point of an access log.
_QUIET_PATHS = ("/admin/api/status", "/admin/api/thermal", "/admin/api/logs",
                "/admin/api/logs/clear",
                "/admin/api/autorun/status", "/admin/api/users", "/admin/api/sdr-users",
                "/admin/api/graph-stats", "/admin/api/chat",
                # websdr.org's registration check, every 10 s while listed
                "/~~orgstatus")
_ACCESS_RE = re.compile(r'"[A-Z]+ (?P<path>[^ ?"]+)[^"]*" (?P<status>\d{3})')


class QuietPollFilter(logging.Filter):
    def filter(self, record):
        m = _ACCESS_RE.search(record.getMessage())
        if not m or m.group("status") != "200":
            return True
        return m.group("path") not in _QUIET_PATHS


# ── websdr.org callback: HTTP/1.1 without a Host header ────────────────────────
# websdr.org confirms a registration by connecting back and sending
# "GET /~~orgstatus HTTP/1.1" with no Host line. aiohttp refuses that (400,
# "Missing 'Host' header") in both its C and Python parsers, so the request
# never reached spectrumserver and the station was never listed. The first
# request on each connection is inspected: when it carries a Host header (every
# browser does) the connection is left alone from then on; when it does not,
# "Host: localhost" is added, and for as long as that client sends bodiless
# GET/HEADs on the kept-alive connection, each of them gets the same treatment.
from aiohttp import web_protocol as _wp

_HOSTFIX_MAX = 16384
_orig_data_received = _wp.RequestHandler.data_received
_orig_connection_lost = _wp.RequestHandler.connection_lost
_hostfix_state: "dict[int, dict]" = {}   # RequestHandler has __slots__: keyed by id()


def _hostfix_data_received(self, data: bytes) -> None:
    st = _hostfix_state.setdefault(id(self), {"on": True, "buf": b""})
    if not st["on"]:
        return _orig_data_received(self, data)
    buf = st["buf"] + data
    out = b""
    while st["on"]:
        end = buf.find(b"\r\n\r\n")
        sep = 4
        if end < 0:
            end, sep = buf.find(b"\n\n"), 2
        if end < 0:
            if len(buf) > _HOSTFIX_MAX:      # not a header we can read: let aiohttp judge
                st["on"] = False
            break
        head, buf = buf[:end], buf[end + sep:]
        lines = [l.rstrip(b"\r") for l in head.split(b"\n")]
        names = [l.split(b":", 1)[0].strip().lower() for l in lines[1:]]
        if b"host" in names:
            st["on"] = False                 # an ordinary client
        elif lines[0].rstrip().endswith(b"HTTP/1.1"):
            lines.insert(1, b"Host: localhost")
        bodiless = (lines[0].split(b" ", 1)[0] in (b"GET", b"HEAD")
                    and b"content-length" not in names
                    and b"transfer-encoding" not in names
                    and b"upgrade" not in names)
        if not bodiless:
            st["on"] = False
        out += b"\r\n".join(lines) + b"\r\n\r\n"
    if not st["on"]:
        out, buf = out + buf, b""
        _hostfix_state[id(self)] = {"on": False, "buf": b""}
    else:
        st["buf"] = buf
    if out:
        _orig_data_received(self, out)


def _hostfix_connection_lost(self, exc) -> None:
    _hostfix_state.pop(id(self), None)
    _orig_connection_lost(self, exc)


_wp.RequestHandler.data_received   = _hostfix_data_received
_wp.RequestHandler.connection_lost = _hostfix_connection_lost


async def main():
    # AppRunner (unlike web.run_app) never calls basicConfig, so aiohttp's
    # access logger stays unconfigured and every request line is discarded.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("aiohttp.access").addFilter(QuietPollFilter())

    try:
        _load_known_listeners()
    except Exception as e:
        print(f"[WARN] statistiques auditeurs : {e}", file=sys.stderr)
    app = web.Application()
    app.router.add_route("*", "/{path_info:.*}", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, LISTEN_HOST, LISTEN_PORT)
    await site.start()
    if FRONT_PORT and FRONT_PORT != LISTEN_PORT:
        await web.TCPSite(runner, LISTEN_HOST, FRONT_PORT).start()
    if TLS_PORT:
        # loopback only: nothing but the https front may reach it
        await web.TCPSite(runner, "127.0.0.1", TLS_PORT).start()

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  PhantomSDR-Plus Reverse Proxy                       ║")
    print(f"║  Listening : http://0.0.0.0:{LISTEN_PORT:<5}                ║")
    print(f"║  /admin*   → Admin panel  (localhost:{int(_cfg['port']):<5})        ║")
    print(f"║  /*        → SDR server   ({_sdr_host}:{_sdr_port:<5})  ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    for prefix, upstream in SIDE_SERVICES.items():
        print(f"  {prefix + '/*':<9} → {upstream}")
    if TLS_PORT:
        print(f"  https front (Caddy) → 127.0.0.1:{TLS_PORT}, visitors by X-Forwarded-For")
    if RECEIVERS:
        if FRONT_PORT and FRONT_PORT != LISTEN_PORT:
            print(f"  also listening on :{FRONT_PORT} (receivers.toml [front])")
        for rid, r in RECEIVERS.items():
            mark = "  (default)" if rid == DEFAULT_RX else ""
            print(f"  ?rx={rid:<8} → {r['upstream']}  {r['name']}{mark}")

    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[stopped]")
