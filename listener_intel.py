#!/usr/bin/env python3
"""
PhantomSDR-Plus — statistiques privées des auditeurs
=====================================================

Partagé par proxy.py (qui écrit) et admin_server.py (qui lit). Rien de ce que
ce module produit n'est servi au public : les fichiers vivent dans logs/ (que
spectrumserver ne sert que pour users_*.jsonl, que proxy.py anonymise pour le
public) et dans des fichiers cachés à la racine du dépôt.

  logs/usage_AAAA-MM-JJ.jsonl   visites (page chargée) et décodeurs utilisés,
                                une ligne JSON par événement, sans IP en clair :
                                l'auditeur y est un identifiant HMAC (iph).
  logs/aggregate_daily.json     un résumé par jour terminé (pays, FAI, VPN,
                                décodeurs, bandes, heures...). Conservé sans
                                limite : il ne contient aucune donnée par
                                auditeur.
  .listener_secret              clé HMAC (0600) — sans elle, les iph ne
                                peuvent pas être reliés à une IP.
  .listener_geo_cache.json      cache des réponses ip-api.com (30 jours).

Les fichiers détaillés (usage_*.jsonl et users_*.jsonl de spectrumserver)
sont supprimés après RETENTION_DAYS jours, une fois leur jour résumé.
"""

import hashlib
import hmac
import ipaddress
import json
import os
import re
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
LOGS = BASE / "logs"
SECRET_FILE = BASE / ".listener_secret"
CACHE_FILE = BASE / ".listener_geo_cache.json"
AGG_FILE = LOGS / "aggregate_daily.json"

RETENTION_DAYS = 90
GEO_TTL = 30 * 86400
GEO_FIELDS = ("status,message,country,countryCode,regionName,city,zip,lat,lon,"
              "timezone,isp,org,as,asname,mobile,proxy,hosting")
GEO_MAX_PER_MIN = 40          # ip-api.com gratuit : 45 requêtes / minute

_lock = threading.RLock()
_cache = None
_cache_dirty = 0.0
_calls = []
_secret_bytes = None


# ── Identité ─────────────────────────────────────────────────────────────────

def norm_ip(ip: str) -> str:
    ip = (ip or "").strip().strip("[]")
    return ip[7:] if ip.startswith("::ffff:") else ip


def is_private(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(norm_ip(ip))
    except ValueError:
        return True
    return a.is_private or a.is_loopback or a.is_link_local or a.is_reserved


def _secret() -> bytes:
    global _secret_bytes
    if _secret_bytes:
        return _secret_bytes
    with _lock:
        try:
            _secret_bytes = SECRET_FILE.read_bytes()
        except FileNotFoundError:
            s = os.urandom(32)
            try:
                fd = os.open(str(SECRET_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(s)
                _secret_bytes = s
            except FileExistsError:
                _secret_bytes = SECRET_FILE.read_bytes()
    return _secret_bytes


def ip_hash(ip: str) -> str:
    """Identifiant stable et non réversible d'un auditeur (sans la clé)."""
    ip = norm_ip(ip)
    if not ip or is_private(ip):
        return "local"
    return hmac.new(_secret(), ip.encode(), hashlib.sha256).hexdigest()[:16]


# ── Géolocalisation (ip-api.com, avec cache) ────────────────────────────────

def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_FILE.read_text())
        except Exception:
            _cache = {}
    return _cache


def _save_cache(force: bool = False) -> None:
    global _cache_dirty
    if not _cache_dirty or (not force and time.time() - _cache_dirty < 20):
        return
    try:
        disk = json.loads(CACHE_FILE.read_text())
    except Exception:
        disk = {}
    disk.update(_cache or {})
    now = time.time()
    disk = {k: v for k, v in disk.items() if now - v.get("t", 0) < GEO_TTL}
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(disk))
    os.chmod(tmp, 0o600)
    tmp.replace(CACHE_FILE)
    _cache_dirty = 0.0


_rdns_pool = ThreadPoolExecutor(max_workers=4)


def rdns(ip: str, timeout: float = 2.0) -> str:
    """Nom inverse (PTR) de l'IP — souvent le FAI et son central (lfbn-bor-1...)."""
    ip = norm_ip(ip)
    if not ip or is_private(ip):
        return ""
    try:
        return _rdns_pool.submit(lambda: socket.gethostbyaddr(ip)[0]).result(timeout=timeout).lower()
    except Exception:
        return ""


def geo(ip: str, allow_lookup: bool = True) -> dict:
    """Fiche d'une IP : ville, FAI, AS, mobile / VPN-proxy / datacenter.

    {} si l'IP est inconnue et que la limite de requêtes est atteinte (la
    fiche arrive au prochain appel)."""
    global _cache_dirty
    ip = norm_ip(ip)
    if not ip:
        return {}
    if is_private(ip):
        return {"local": True, "city": "Réseau local", "countryCode": ""}
    key = ip_hash(ip)
    with _lock:
        c = _load_cache()
        hit = c.get(key)
        fresh = hit and time.time() - hit.get("t", 0) < GEO_TTL
        if fresh and "rdns" in hit["d"]:
            return hit["d"]
        if fresh:                       # fiche d'avant le reverse DNS : on complète
            if not allow_lookup:
                return hit["d"]
            d = dict(hit["d"])
        else:
            d = None
        if d is None and not allow_lookup:
            return {}
        if d is None:
            now = time.time()
            _calls[:] = [t for t in _calls if now - t < 60]
            if len(_calls) >= GEO_MAX_PER_MIN:
                return {}
            _calls.append(now)
    if d is None:
        try:
            url = "http://ip-api.com/json/%s?fields=%s&lang=fr" % (ip, GEO_FIELDS)
            with urllib.request.urlopen(url, timeout=4) as r:
                d = json.loads(r.read().decode())
        except Exception:
            return {}
        if d.get("status") != "success":
            return {}
        d.pop("status", None)
        d.pop("message", None)
    d["rdns"] = rdns(ip)
    with _lock:
        _load_cache()[key] = {"t": time.time(), "d": d}
        if not _cache_dirty:
            _cache_dirty = time.time()
        _save_cache()
    return d


def flush() -> None:
    with _lock:
        _save_cache(force=True)


def net_kind(g: dict) -> str:
    """vpn | datacenter | mobile | local | fixe | ? — pour un badge."""
    if not g:
        return "?"
    if g.get("local"):
        return "local"
    if g.get("proxy"):
        return "vpn"
    if g.get("hosting"):
        return "datacenter"
    if g.get("mobile"):
        return "mobile"
    return "fixe"


# ── Navigateur, système, provenance ─────────────────────────────────────────

def classify_ua(ua: str) -> dict:
    ua = ua or ""
    if re.search(r"bot|crawl|spider|curl|wget|python|httpclient", ua, re.I):
        browser = "Robot"
    elif "Edg/" in ua:
        browser = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        browser = "Opera"
    elif "Firefox/" in ua:
        browser = "Firefox"
    elif "Chrome/" in ua or "CriOS/" in ua:
        browser = "Chrome"
    elif "Safari/" in ua:
        browser = "Safari"
    else:
        browser = "Autre"
    if "Android" in ua:
        osn = "Android"
    elif re.search(r"iPhone|iPad|iPod", ua):
        osn = "iOS"
    elif "Windows" in ua:
        osn = "Windows"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        osn = "macOS"
    elif "CrOS" in ua:
        osn = "ChromeOS"
    elif "Linux" in ua:
        osn = "Linux"
    else:
        osn = "Autre"
    return {"browser": browser, "os": osn,
            "device": "mobile" if re.search(r"Mobi|Android|iPhone|iPad", ua) else "ordinateur"}


def ref_host(ref: str, own_host: str = "") -> str:
    try:
        h = (urlparse(ref).hostname or "").lower()
    except Exception:
        return ""
    own = (own_host or "").split(":")[0].lower()
    if not h or h == own:
        return ""
    return h[4:] if h.startswith("www.") else h


# ── Journal ─────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def append(event: dict) -> None:
    event.setdefault("ts", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    with _lock:
        LOGS.mkdir(exist_ok=True)
        with open(LOGS / ("usage_%s.jsonl" % _today()), "a", encoding="utf-8") as f:
            f.write(line + "\n")


def read_jsonl(path: Path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except ValueError:
                        continue
    except FileNotFoundError:
        return


# ── Sécurité : tentatives anormales ─────────────────────────────────────────
# logs/security_AAAA-MM-JJ.jsonl — une ligne par événement suspect vu par
# proxy.py (qui reçoit tout le trafic web, http comme https). L'IP y est en
# clair : c'est précisément ce qu'il faut pour bannir. Effacé après 90 jours.
# logs/blocklist.json — IP refusées par proxy.py (bannissements du panneau).

BLOCK_FILE = LOGS / "blocklist.json"

_SCAN_RE = re.compile(
    r"(\.php|\.asp|\.aspx|\.jsp|\.cgi|wp-|wordpress|xmlrpc|phpmyadmin|pma/|/\.env|"
    r"/\.git|/\.svn|/\.aws|/\.ssh|/\.ds_store|cgi-bin|/boaform|/hnap1|/shell|/manager/html|"
    r"/actuator|/solr|/owa/|autodiscover|vendor/phpunit|/console|/druid|/server-status|"
    r"/etc/passwd|/proc/self|/bin/sh|/remote/login|/sslvpn|/dana-na|/global-protect|"
    r"/geoserver|/jenkins|/telescope|/debug|/backup|\.sql|\.bak$|\.zip$|\.tar|/config\.json|"
    r"/api/v1/pods|/containers/json|/cdn-cgi/|/developmentserver|/ecp/|/mgmt|/setup\.cgi)",
    re.I)
_TRAV_RE = re.compile(r"(\.\./|\.\.%2f|%2e%2e|%252e|\\\.\.)", re.I)
_OK_METHODS = {"GET", "POST", "HEAD", "OPTIONS"}

SEC_LABELS = {
    "scan": "Recherche de failles (chemins typiques)",
    "traversal": "Tentative de remontée de dossiers (../)",
    "method": "Méthode HTTP inhabituelle",
    "forbidden": "Action interdite refusée (kick, contrôle du proxy…)",
    "burst404": "Rafale de pages introuvables (balayage)",
    "admin_login_fail": "Échec de connexion au panneau admin",
    "admin_login_ok": "Connexion réussie au panneau admin",
    "admin_locked": "Panneau verrouillé après échecs répétés",
    "admin_country": "Accès au panneau refusé : pays non autorisé",
    "admin_global_lock": "Panneau suspendu 15 min : trop d'échecs, toutes IP confondues",
    "blocked": "Requête d'une IP bannie refusée",
}


def classify_request(method: str, path: str, status: int):
    """Catégorie de sécurité d'une requête, ou None si elle est normale."""
    m = (method or "").upper()
    if m not in _OK_METHODS:
        return "method"
    if _TRAV_RE.search(path or ""):
        return "traversal"
    if _SCAN_RE.search(path or "") and not (path or "").startswith("/admin"):
        return "scan"
    if status == 403:
        return "forbidden"
    return None


def append_security(event: dict) -> None:
    event.setdefault("ts", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    with _lock:
        LOGS.mkdir(exist_ok=True)
        with open(LOGS / ("security_%s.jsonl" % _today()), "a", encoding="utf-8") as f:
            f.write(line + "\n")


_block_cache = {"mtime": None, "data": {}, "nets": []}


def _build_nets(data: dict) -> list:
    """Plages CIDR de la liste (clés contenant « / »), prêtes à comparer."""
    nets = []
    for k, v in data.items():
        if "/" in k:
            try:
                nets.append((ipaddress.ip_network(k, strict=False), v))
            except ValueError:
                pass
    return nets


def load_blocklist() -> dict:
    """{ip: {"until": epoch, "reason": str, "since": epoch}} — relu si modifié."""
    try:
        mt = BLOCK_FILE.stat().st_mtime
    except FileNotFoundError:
        _block_cache.update(mtime=None, data={}, nets=[])
        return {}
    if mt != _block_cache["mtime"]:
        try:
            d = json.loads(BLOCK_FILE.read_text())
            _block_cache.update(mtime=mt, data=d, nets=_build_nets(d))
        except Exception:
            pass
    return _block_cache["data"]


# logs/allowlist.json — liste blanche : IP / plages jamais bloquées, même si
# elles tombent dans une plage bannie (l'administrateur, des OM de confiance…).
ALLOW_FILE = LOGS / "allowlist.json"
_allow_cache = {"mtime": None, "data": {}, "nets": []}


def load_allowlist() -> dict:
    """{ip ou plage: {"since": epoch, "note": str}} — relu si modifié."""
    try:
        mt = ALLOW_FILE.stat().st_mtime
    except FileNotFoundError:
        _allow_cache.update(mtime=None, data={}, nets=[])
        return {}
    if mt != _allow_cache["mtime"]:
        try:
            d = json.loads(ALLOW_FILE.read_text())
            _allow_cache.update(mtime=mt, data=d, nets=_build_nets(d))
        except Exception:
            pass
    return _allow_cache["data"]


def is_allowed(ip: str) -> bool:
    ip = norm_ip(ip)
    if ip in load_allowlist():
        return True
    nets = _allow_cache.get("nets") or []
    if nets:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for net, _ in nets:
            if a.version == net.version and a in net:
                return True
    return False


def save_allowlist(data: dict) -> None:
    with _lock:
        LOGS.mkdir(exist_ok=True)
        tmp = ALLOW_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        tmp.replace(ALLOW_FILE)


def is_blocked(ip: str) -> bool:
    ip = norm_ip(ip)
    if is_allowed(ip):
        return False
    now = time.time()
    b = load_blocklist().get(ip)
    if b and (not b.get("until") or b["until"] > now):
        return True
    nets = _block_cache.get("nets") or []
    if nets:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for net, v in nets:
            if a.version == net.version and a in net and (not v.get("until") or v["until"] > now):
                return True
    return False


def save_blocklist(data: dict) -> None:
    now = time.time()
    data = {k: v for k, v in data.items() if not v.get("until") or v["until"] > now}
    with _lock:
        LOGS.mkdir(exist_ok=True)
        tmp = BLOCK_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        tmp.replace(BLOCK_FILE)


# ── Bandes ───────────────────────────────────────────────────────────────────

_BANDS = [
    (0.1357, 0.1378, "2200 m"), (0.472, 0.479, "630 m"), (0.15, 0.285, "GO (LW)"),
    (0.5265, 1.6065, "PO (MW)"), (1.8, 2.0, "160 m"), (2.3, 2.495, "120 m BC"),
    (3.2, 3.4, "90 m BC"), (3.5, 3.8, "80 m"), (3.9, 4.0, "75 m BC"),
    (4.75, 5.06, "60 m BC"), (5.3515, 5.3665, "60 m"), (5.9, 6.2, "49 m BC"),
    (7.0, 7.2, "40 m"), (7.2, 7.45, "41 m BC"), (9.4, 9.9, "31 m BC"),
    (10.1, 10.15, "30 m"), (11.6, 12.1, "25 m BC"), (13.57, 13.87, "22 m BC"),
    (14.0, 14.35, "20 m"), (15.1, 15.8, "19 m BC"), (17.48, 17.9, "16 m BC"),
    (18.068, 18.168, "17 m"), (21.0, 21.45, "15 m"), (21.45, 21.85, "13 m BC"),
    (24.89, 24.99, "12 m"), (26.965, 27.405, "CB"), (28.0, 29.7, "10 m"),
]


def band_of(freq_hz) -> str:
    try:
        mhz = float(freq_hz) / 1e6
    except (TypeError, ValueError):
        return "?"
    for lo, hi, name in _BANDS:
        if lo <= mhz <= hi:
            return name
    return "hors bande"


# ── Résumés quotidiens ──────────────────────────────────────────────────────

def _inc(d: dict, k, n=1):
    if k in (None, ""):
        k = "?"
    d[k] = d.get(k, 0) + n


def aggregate_day(date: str) -> dict:
    """Résumé d'un jour à partir des fichiers détaillés (sans donnée nominative)."""
    out = {"listeners": 0, "sessions": 0, "listen_s": 0, "visits": 0,
           "countries": {}, "cities": {}, "isps": {}, "net": {}, "decoders": {},
           "decoder_users": 0, "bands": {}, "modes": {}, "hours": {},
           "sources": {}, "browsers": {}, "os": {}, "devices": {}, "langs": {},
           "https": 0, "returning": 0}
    listeners = set()
    sess = {}
    for e in read_jsonl(LOGS / ("users_%s.jsonl" % date)):
        ip = e.get("ip", "")
        iph = ip_hash(ip)
        listeners.add(iph)
        sid = e.get("id") or iph
        s = sess.setdefault(sid, {"iph": iph, "ip": ip, "dur": 0, "hour": None})
        if s["hour"] is None and e.get("ts"):
            s["hour"] = e["ts"][11:13]
        if e.get("event") == "tune":
            _inc(out["bands"], band_of(e.get("freq_hz")))
            _inc(out["modes"], (e.get("mode") or "?").upper())
        elif e.get("event") == "disconnect":
            s["dur"] = max(s["dur"], int(e.get("duration_s") or 0))
    seen_geo = set()
    for s in sess.values():
        out["sessions"] += 1
        out["listen_s"] += s["dur"]
        if s["hour"]:
            _inc(out["hours"], s["hour"])
        if s["iph"] in seen_geo:
            continue
        seen_geo.add(s["iph"])
        g = geo(s["ip"])
        _inc(out["countries"], g.get("country") or ("Local" if g.get("local") else "?"))
        if g.get("city"):
            _inc(out["cities"], "%s, %s" % (g["city"], g.get("countryCode", "")))
        _inc(out["isps"], g.get("isp") or ("Local" if g.get("local") else "?"))
        _inc(out["net"], net_kind(g))
    dec_users = set()
    for e in read_jsonl(LOGS / ("usage_%s.jsonl" % date)):
        ev = e.get("ev")
        if ev == "visit":
            out["visits"] += 1
            if e.get("https"):
                out["https"] += 1
            _inc(out["sources"], e.get("src") or "direct")
            _inc(out["browsers"], e.get("browser"))
            _inc(out["os"], e.get("os"))
            _inc(out["devices"], e.get("device"))
            if e.get("returning"):
                out["returning"] += 1
        elif ev == "hello":
            _inc(out["langs"], (e.get("lang") or "?")[:2])
        elif ev == "decoder" and e.get("decoder") not in (None, "", "none"):
            _inc(out["decoders"], e["decoder"].upper())
            dec_users.add(e.get("iph"))
    out["listeners"] = len(listeners)
    out["decoder_users"] = len(dec_users)
    return out


def load_aggregates() -> dict:
    try:
        return json.loads(AGG_FILE.read_text())
    except Exception:
        return {}


def maintain() -> dict:
    """Résume chaque jour terminé pas encore résumé, puis efface le détail
    au-delà de RETENTION_DAYS. Appelé par le panneau (au plus une fois par heure)."""
    with _lock:
        agg = load_aggregates()
        today = _today()
        dates = set()
        for p in LOGS.glob("users_*.jsonl"):
            dates.add(p.stem[6:])
        for p in LOGS.glob("usage_*.jsonl"):
            dates.add(p.stem[6:])
        changed = False
        for d in sorted(dates):
            if d < today and d not in agg:
                agg[d] = aggregate_day(d)
                changed = True
        if changed:
            LOGS.mkdir(exist_ok=True)
            tmp = AGG_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(agg, ensure_ascii=False))
            tmp.replace(AGG_FILE)
        limit = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
        for pat, cut in (("users_*.jsonl", 6), ("usage_*.jsonl", 6), ("security_*.jsonl", 9)):
            for p in LOGS.glob(pat):
                d = p.stem[cut:]
                if d < limit and (d in agg or pat.startswith("security")):
                    try:
                        p.unlink()
                    except OSError:
                        pass
        flush()
        return agg
