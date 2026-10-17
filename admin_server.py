#!/usr/bin/env python3
"""
PhantomSDR-Plus Admin Panel — Internal service (localhost only).
Do NOT run this directly for public access.
Use proxy.py to expose it on the main port alongside spectrumserver.

Direct access (internal/dev only): http://127.0.0.1:8901/admin
Via proxy (production):            http://server_address:8900/admin
Default password: admin (change on first login!)
"""

import os
import sys
import json
import hashlib
import hmac
import secrets
import subprocess
import threading
import time
import signal
import ipaddress
import re
import glob
import logging
from collections import deque
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import listener_intel as LI   # statistiques privées des auditeurs

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

try:
    import tomli_w
except ImportError:
    tomli_w = None

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# CPU over-temperature guard. Optional: a missing or broken thermal_guard.py
# must never stop the panel itself from starting.
try:
    import thermal_guard
    HAS_THERMAL = True
except Exception:
    thermal_guard = None
    HAS_THERMAL = False

from flask import (Flask, render_template_string, request, session,
                   redirect, url_for, jsonify, Response, flash)

# ─── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
ADMIN_CONFIG_FILE = BASE_DIR / "admin_config.json"
ADMIN_PORT = int(os.environ.get("ADMIN_PORT", 3000))    # internal only — proxy.py exposes it publicly
ADMIN_BIND = os.environ.get("ADMIN_BIND", "127.0.0.1")  # localhost by default; set "0.0.0.0" for standalone
PUBLIC_PORT = int(os.environ.get("PUBLIC_PORT", 8900))  # display default only — port users actually connect to

def _get_or_create_secret_key():
    """Load secret key from config (persistent across restarts) or create and save one."""
    env_key = os.environ.get("ADMIN_SECRET")
    if env_key:
        return env_key
    try:
        if ADMIN_CONFIG_FILE.exists():
            with open(ADMIN_CONFIG_FILE) as f:
                cfg = json.load(f)
            key = cfg.get("secret_key")
            if key:
                return key
            # First run: generate, persist, return
            key = os.urandom(24).hex()
            cfg["secret_key"] = key
            with open(ADMIN_CONFIG_FILE, "w") as f:
                json.dump(cfg, f, indent=2)
            return key
    except Exception:
        pass
    return os.urandom(24).hex()  # fallback: ephemeral key (config unreadable)

SECRET_KEY = _get_or_create_secret_key()

DEFAULT_CONFIG = {
    "password_hash": hashlib.sha256(b"admin").hexdigest(),
    "port": ADMIN_PORT,
    "sdr_base_dir": str(BASE_DIR),
    "log_lines": 200,
    "start_script": "",
    "stop_script":  "",
    "public_port":  PUBLIC_PORT   # port users connect to (proxy.py / nginx / spectrumserver direct)
}

# ─── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY
# Cookie de session : invisible au JavaScript, non envoyé depuis un autre site,
# connexion qui expire après 12 h sans activité (prolongée à chaque requête).
from datetime import timedelta as _td
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=_td(hours=12),
)


from flask.sessions import SecureCookieSessionInterface as _SCSI


class _SessionIface(_SCSI):
    """En https, le cookie est marqué Secure (jamais renvoyé en clair) ; en
    http (accès local par IP), il reste utilisable."""
    def get_cookie_secure(self, app):
        try:
            return bool(request.is_secure)
        except Exception:
            return False


app.session_interface = _SessionIface()

# Trust X-Forwarded-* headers from proxy.py so Flask generates correct
# external URLs for redirects and url_for() calls.
try:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1, x_port=1)
except ImportError:
    pass  # Werkzeug < 1.0 — skip, redirects may use internal URL

log_buffer = []
log_lock = threading.Lock()

# ── Waterfall message (fixed banner shown to all connected users) ──────────────
_wf_message      = {"text": "", "color": "#ffffff"}
_wf_message_lock = threading.Lock()

LOG_FILES = {
    "logwebsdr.txt": "logwebsdr.txt",
    "spectrumserver.log": "spectrumserver.log",
    "admin.log": "admin.log",
    "rade.log": "rade.log",
    "crash.log": "crash.log",
    "autorun.log": "autorun.log",
    "proxy.log": "proxy.log",
}

# Logs that "Clear Logs" must leave alone. Empty by sysop decision: the button
# clears every log in LOG_FILES, autorun.log included.
#
# Both exclusions that used to live here are gone for the same reason — a button
# labelled "Clear Logs" that silently keeps a file looks broken, and neither file
# needed protecting. proxy.log is an access log the sysop owns; autorun.log is
# the decoder log, and while its spot history cannot be reconstructed, logrotate
# (logrotate/phantomsdr) keeps the rotated archives in logproxy/, so a clear
# costs only what has accumulated since the last rotation.
#
# Clearing autorun.log under a running decoder is safe: the daemon holds it open
# O_APPEND, so an in-place truncate takes effect immediately and the daemon goes
# on appending to the same inode. Whatever cannot be written is named in the
# toast rather than reported as success.
CLEAR_EXCLUDE = set()

# ─── Helpers ───────────────────────────────────────────────────────────────────
def load_admin_config():
    if ADMIN_CONFIG_FILE.exists():
        with open(ADMIN_CONFIG_FILE) as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_admin_config(cfg):
    with open(ADMIN_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# Mot de passe : PBKDF2-SHA256 salé (« pbkdf2$itérations$sel$empreinte »).
# L'ancien format (SHA-256 nu, 64 caractères hexa) reste accepté et est
# converti automatiquement à la première connexion réussie.
PBKDF2_ITER = 240000
MIN_PASSWORD_LEN = 12

def hash_password(pwd):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), bytes.fromhex(salt), PBKDF2_ITER)
    return f"pbkdf2${PBKDF2_ITER}${salt}${dk.hex()}"

def _verify_hash(pwd, stored):
    stored = stored or ""
    if stored.startswith("pbkdf2$"):
        try:
            _, it, salt, h = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), bytes.fromhex(salt), int(it))
            return hmac.compare_digest(dk.hex(), h)
        except (ValueError, TypeError):
            return False
    legacy = hashlib.sha256(pwd.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored)

def check_password(pwd):
    cfg = load_admin_config()
    stored = cfg.get("password_hash", "")
    if not _verify_hash(pwd, stored):
        return False
    if not stored.startswith("pbkdf2$"):
        try:
            cfg["password_hash"] = hash_password(pwd)
            save_admin_config(cfg)
        except Exception:
            pass
    return True

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_sdr_dir():
    cfg = load_admin_config()
    return Path(cfg.get("sdr_base_dir", str(BASE_DIR)))

def find_config_files():
    base = get_sdr_dir()
    files = {}
    for pattern in ["config.toml", "config-*.toml", "config.example.*.toml"]:
        for f in sorted(base.glob(pattern)):
            files[f.name] = str(f)
    return files

def find_editable_files():
    """Find all editable files (.sh .toml .cpp .h .txt .json .html) in PhantomSDR-Plus dir."""
    import os
    base  = get_sdr_dir()
    exts  = {'.sh', '.toml', '.cpp', '.h', '.txt', '.json', '.html'}
    files = {}
    skip  = {'node_modules', 'build', 'dist', '__pycache__', '.git'}
    for root, dirs, filenames in os.walk(str(base)):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip]
        for fn in sorted(filenames):
            if Path(fn).suffix.lower() in exts:
                if fn == "admin_config.json":
                    continue
                full = os.path.join(root, fn)
                rel  = os.path.relpath(full, str(base))
                files[rel] = full
    return dict(sorted(files.items()))

def find_json_files():
    base = get_sdr_dir()
    files = {}
    for pattern in ["*.json", "frontend/src/*.json", "frontend/*.json"]:
        for f in sorted(base.glob(pattern)):
            if f.name != "admin_config.json":
                files[str(f.relative_to(base))] = str(f)
    return files

def find_sh_files():
    """Discover all .sh files inside PhantomSDR-Plus directory. Returns {rel_path: abs_path}."""
    import os
    base  = get_sdr_dir()
    files = {}
    for root, dirs, filenames in os.walk(str(base)):
        dirs[:] = [d for d in dirs if not d.startswith('.')
                   and d not in ('node_modules', 'build', 'dist', '__pycache__')]
        for fn in sorted(filenames):
            if fn.endswith('.sh'):
                full = os.path.join(root, fn)
                rel  = os.path.relpath(full, str(base))
                files[rel] = full
    return dict(sorted(files.items()))

def find_config_files_all():
    """Find all .toml config files inside PhantomSDR-Plus directory. Returns {name: abs_path}."""
    base  = get_sdr_dir()
    files = {}
    for pattern in ["config.toml", "config-*.toml", "config.example.*.toml", "*.toml"]:
        for f in sorted(base.glob(pattern)):
            files[f.name] = str(f)
    return dict(sorted(files.items()))

def get_allowed_configs():
    return find_config_files_all()

def get_allowed_scripts():
    return find_sh_files()
# ─── First-run / Setup helpers ─────────────────────────────────────────────────

# ─── Where this copy came from ─────────────────────────────────────────────────
# PhantomSDR-Plus is developed at ORIGIN_REPO. A sysop who cloned a fork may not
# know that, so the panel shows a notice while the tree's origin remote points
# elsewhere — the same check the installers and update.sh make. A notice only:
# the GPL allows forks. The remote is read from .git/config directly when git
# is missing or refuses the tree (another user's checkout).
ORIGIN_REPO = "https://github.com/sv1btl/PhantomSDR-Plus"

def _origin_norm(url):
    u = url.strip().lower()
    u = re.sub(r"^[a-z+]+://", "", u)
    u = re.sub(r"^[^@/]*@", "", u)
    u = re.sub(r"^github\.com:", "github.com/", u)
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u

def tree_origin():
    """The tree's origin remote, credentials stripped, or "" when there is none."""
    url = ""
    try:
        url = subprocess.run(["git", "-C", str(BASE_DIR), "config", "--get",
                              "remote.origin.url"], capture_output=True,
                             text=True, timeout=5).stdout.strip()
    except Exception:
        url = ""
    if not url:
        try:
            section = None
            for line in (BASE_DIR / ".git" / "config").read_text(errors="replace").splitlines():
                line = line.strip()
                if line.startswith("["):
                    section = line
                elif section == '[remote "origin"]' and re.match(r"url\s*=", line):
                    url = line.split("=", 1)[1].strip()
                    break
        except Exception:
            url = ""
    # Never show a token: https://user:token@github.com/... -> https://github.com/...
    return re.sub(r"^([a-z+]+://)[^@/]*@", r"\1", url)

def fork_origin():
    """The fork this tree was cloned from, or None for the original / no git."""
    url = tree_origin()
    if url and _origin_norm(url) != "github.com/sv1btl/phantomsdr-plus":
        return url
    return None

def is_first_run():
    if not ADMIN_CONFIG_FILE.exists():
        return True
    try:
        return not load_admin_config().get("setup_complete", False)
    except Exception:
        return True

def auto_detect_sdr_candidates():
    import glob as _glob
    seen, found = set(), []
    def add(p):
        s = str(Path(p).resolve())
        if s not in seen:
            seen.add(s); found.append(s)
    add(BASE_DIR)
    for tmpl in ["~/PhantomSDR-Plus", "~/phantomsdr", "/opt/PhantomSDR-Plus",
                 "/usr/local/PhantomSDR-Plus", "/home/*/PhantomSDR-Plus"]:
        for hit in _glob.glob(str(Path(tmpl).expanduser())):
            if Path(hit).is_dir(): add(hit)
    try:
        r = subprocess.run(["pgrep", "-a", "-f", "spectrumserver"],
                           capture_output=True, text=True, timeout=3)
        for line in r.stdout.splitlines():
            for part in line.split():
                if "spectrumserver" in part and os.sep in part:
                    for anc in [Path(part).parent, Path(part).parent.parent]:
                        if anc.is_dir(): add(anc)
    except Exception:
        pass
    def score(s):
        p = Path(s)
        return (4*int((p/"build"/"spectrumserver").exists()) +
                3*int(bool(list(p.glob("config*.toml")))) +
                2*int((p/"frontend").is_dir()) +
                  int((p/"admin_server.py").exists()))
    found.sort(key=score, reverse=True)
    return found or [str(BASE_DIR)]


def get_process_status():
    status = {"running": False, "pid": None, "name": None, "cpu": 0, "mem": 0, "uptime": None}
    proc_name = "spectrumserver"
    try:
        proc_name = load_admin_config().get("sdr_process_name", "spectrumserver").strip() or "spectrumserver"
    except Exception:
        pass
    # pgrep first — works across users, no psutil needed
    try:
        r = subprocess.run(["pgrep", "-f", proc_name], capture_output=True, text=True, timeout=3)
        pids = [p for p in r.stdout.split() if p.isdigit()]
        if pids:
            status.update({"running": True, "pid": int(pids[0]), "name": proc_name})
    except Exception:
        pass
    # psutil enriches with CPU/mem/uptime
    if HAS_PSUTIL:
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline", "cpu_percent", "memory_info", "create_time"]):
                try:
                    pname = (proc.info["name"] or "").lower()
                    cmd   = " ".join(proc.info["cmdline"] or []).lower()
                    if proc_name.lower() in pname or proc_name.lower() in cmd:
                        ut = time.time() - proc.info["create_time"]
                        status.update({"running": True, "pid": proc.info["pid"],
                                       "name": proc.info["name"],
                                       "cpu": proc.cpu_percent(interval=0.1),
                                       "mem": round(proc.info["memory_info"].rss / 1024 / 1024, 1),
                                       "uptime": str(timedelta(seconds=int(ut)))})
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                except Exception:
                    pass
        except Exception:
            pass
    return status


def get_temperature():
    """Try multiple methods to get CPU temperature."""
    # psutil sensors
    if HAS_PSUTIL and hasattr(psutil, "sensors_temperatures"):
        try:
            temps = psutil.sensors_temperatures()
            for key in ("coretemp", "cpu_thermal", "acpitz", "k10temp", "zenpower"):
                if key in temps and temps[key]:
                    return round(temps[key][0].current, 1)
            # any first available
            for key, entries in temps.items():
                if entries:
                    return round(entries[0].current, 1)
        except Exception:
            pass
    # /sys/class/thermal fallback
    try:
        import glob
        for p in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
            with open(p) as f:
                val = int(f.read().strip())
            if val > 0:
                return round(val / 1000.0, 1)
    except Exception:
        pass
    # sensors command fallback
    try:
        r = subprocess.run(["sensors"], capture_output=True, text=True, timeout=2)
        import re
        m = re.search(r'[Tt]emp\d*:\s+\+?([\d.]+)', r.stdout)
        if m:
            return round(float(m.group(1)), 1)
    except Exception:
        pass
    return None

def get_system_stats():
    if not HAS_PSUTIL:
        return {"cpu": "N/A", "mem_used": "N/A", "mem_total": "N/A", "disk_used": "N/A", "disk_total": "N/A", "temp": None}
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu": psutil.cpu_percent(interval=0.5),
        "mem_used": round(mem.used / 1024**3, 1),
        "mem_total": round(mem.total / 1024**3, 1),
        "mem_pct": mem.percent,
        "disk_used": round(disk.used / 1024**3, 1),
        "disk_total": round(disk.total / 1024**3, 1),
        "disk_pct": disk.percent,
        "temp": get_temperature(),
    }

def get_top_processes(n=12):
    """Return top N processes sorted by CPU usage."""
    if not HAS_PSUTIL:
        # Fallback: use 'ps' command
        try:
            result = subprocess.run(
                ["ps", "aux", "--sort=-%cpu"],
                capture_output=True, text=True
            )
            lines = result.stdout.strip().split("\n")[1:n+1]
            procs = []
            for line in lines:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    procs.append({
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "name": parts[10][:40],
                    })
            return procs
        except Exception:
            return []
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status", "username"]):
        try:
            procs.append({
                "pid": proc.info["pid"],
                "name": (proc.info["name"] or "")[:35],
                "cpu": round(proc.info["cpu_percent"] or 0, 1),
                "mem": round(proc.info["memory_percent"] or 0, 1),
                "status": proc.info["status"],
                "user": (proc.info["username"] or "")[:12],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    return procs[:n]

# ── Stats history sampler (Graphs page) ───────────────────────────────────────
# A background thread samples a few cheap counters on a fixed interval and keeps
# them in a ring buffer, so the Graphs page has history the moment it is opened
# instead of having to build it up from scratch each visit. Nothing here touches
# the disk: the buffer is memory-only and is lost on restart by design.
# Two tiers. The fine tier gives a live 2s view; the coarse tier carries the
# long ranges. Storing a day at 2s would be ~43000 points — tens of MB to hold,
# a multi-MB first payload, and 40 points per pixel of canvas, which no screen
# can show. Aggregating to 30s keeps a day in 2880 points instead.
GRAPH_INTERVAL_S   = 2          # seconds between fine samples
GRAPH_FINE_S       = 3600       # how far back the fine tier reaches (1h)
GRAPH_COARSE_EVERY = 15         # fine samples per coarse point (15 x 2s = 30s)
GRAPH_COARSE_S     = 24 * 3600  # how far back the coarse tier reaches (24h)

GRAPH_COARSE_INTERVAL_S = GRAPH_INTERVAL_S * GRAPH_COARSE_EVERY
GRAPH_MAXLEN        = GRAPH_FINE_S // GRAPH_INTERVAL_S
GRAPH_COARSE_MAXLEN = GRAPH_COARSE_S // GRAPH_COARSE_INTERVAL_S
# Ranges longer than this are served from the coarse tier.
GRAPH_HISTORY_S     = GRAPH_COARSE_S   # deepest range the page can ask for

_graph_history = deque(maxlen=GRAPH_MAXLEN)
_graph_coarse  = deque(maxlen=GRAPH_COARSE_MAXLEN)
_graph_pending = []            # fine samples not yet folded into a coarse point
_graph_lock    = threading.Lock()
_graph_started = False


def _graph_fold(batch):
    """Average a run of fine samples into one coarse point.

    Averages over the readings that exist; a field is None only when every
    sample in the run lacked it, so an occasional failed read thins the average
    instead of punching a hole in the long-range view.
    """
    def avg(key, nd):
        vals = [p[key] for p in batch if p.get(key) is not None]
        return round(sum(vals) / len(vals), nd) if vals else None
    users = [p["u"] for p in batch if p.get("u") is not None]
    return {
        "t":  batch[-1]["t"],
        "l":  avg("l", 1),
        "f":  avg("f", 2),
        "fm": avg("fm", 2),
        "c":  avg("c", 1),
        "u":  round(sum(users) / len(users)) if users else None,
    }


def get_cpu_frequency():
    """Current CPU clock in GHz: (average across cores, fastest core, hw limit).

    psutil first, then the cpufreq sysfs tree.  Both read the same kernel data
    that cpufreq-info formats, so cpufrequtils is not required.  Any element may
    be None when the platform does not expose it.
    """
    if HAS_PSUTIL:
        try:
            per = psutil.cpu_freq(percpu=True)
            cur = [f.current for f in per if f and f.current]
            if cur:
                limit = max((f.max for f in per if f and f.max), default=0)
                return (round(sum(cur) / len(cur) / 1000, 2),
                        round(max(cur) / 1000, 2),
                        round(limit / 1000, 2) if limit else None)
        except Exception:
            pass
    try:
        cur, limit = [], 0
        for d in sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq")):
            try:
                with open(os.path.join(d, "scaling_cur_freq")) as f:
                    cur.append(int(f.read().strip()))
            except Exception:
                pass
            try:
                with open(os.path.join(d, "cpuinfo_max_freq")) as f:
                    limit = max(limit, int(f.read().strip()))
            except Exception:
                pass
        cur = [c for c in cur if c > 0]
        if cur:
            return (round(sum(cur) / len(cur) / 1e6, 2),
                    round(max(cur) / 1e6, 2),
                    round(limit / 1e6, 2) if limit else None)
    except Exception:
        pass
    return (None, None, None)


def _receivers_toml():
    """receivers.toml next to proxy.py (several receivers on one port), or {}."""
    try:
        import tomllib
        with open(BASE_DIR / "receivers.toml", "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _sdr_ports():
    """Every spectrumserver port on this box: public_port first, then any other
    receiver receivers.toml lists. One entry on a single-receiver station."""
    cfg = load_admin_config()
    ports = [int(cfg.get("public_port", PUBLIC_PORT))]
    for r in _receivers_toml().get("receiver", []):
        try:
            p = int(r.get("port"))
        except (TypeError, ValueError):
            continue
        if p not in ports:
            ports.append(p)
    return ports


def count_connected_users():
    """Number of clients currently on the WebSDR, or None if it cannot be read.

    Uses spectrumserver's own /users endpoint — the authoritative session list —
    rather than counting sockets with 'ss', which cannot see past the proxy.
    """
    import urllib.request
    total, seen = 0, False
    # Summed over every receiver; one that is down just adds nothing.
    for port in _sdr_ports():
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/users" % port, timeout=2) as r:
                d = json.loads(r.read().decode())
        except Exception:
            continue
        seen = True
        total += d["total"] if isinstance(d.get("total"), int) else len(d.get("users", []))
    return total if seen else None


def _graph_sampler():
    """Append one sample per interval.  Never raises — a bad sample is skipped."""
    if HAS_PSUTIL:
        try:
            psutil.cpu_percent(interval=None)   # prime the delta counter
        except Exception:
            pass
    while True:
        time.sleep(GRAPH_INTERVAL_S)
        # Thermal guard rides along on this loop — it needs a temperature every
        # couple of seconds and the sampler already wakes up to take one. Its
        # own try/except so a guard problem can never stop graph sampling.
        if HAS_THERMAL:
            try:
                thermal_guard.tick()
            except Exception:
                pass
        try:
            load = None
            if HAS_PSUTIL:
                # interval=None measures since the previous call, i.e. across the
                # whole sleep — no extra blocking sample needed.
                load = round(psutil.cpu_percent(interval=None), 1)
            freq, freq_max, _ = get_cpu_frequency()
            point = {
                "t": int(time.time()),
                "l": load,
                "f": freq,
                "fm": freq_max,
                "c": get_temperature(),
                "u": count_connected_users(),
            }
            with _graph_lock:
                _graph_history.append(point)
                _graph_pending.append(point)
                if len(_graph_pending) >= GRAPH_COARSE_EVERY:
                    _graph_coarse.append(_graph_fold(_graph_pending))
                    _graph_pending.clear()
        except Exception:
            pass


def start_graph_sampler():
    global _graph_started
    if _graph_started:
        return
    _graph_started = True
    threading.Thread(target=_graph_sampler, name="graph-sampler", daemon=True).start()


def start_thermal_guard():
    """Wire the CPU over-temperature guard to this panel's start/stop paths.

    The guard itself knows nothing about PhantomSDR: it is handed callbacks, so
    it acts through whatever start/stop method THIS sysop configured, and works
    the same whether the server is supervised by a watchdog, systemd or nothing.
    """
    if not HAS_THERMAL:
        return False

    def _start():
        name = (load_admin_config().get("start_script") or "").strip()
        if not name:
            return (False, "no start_script configured — not restarting")
        return run_script(name)

    def _running():
        try:
            return bool(get_process_status().get("running"))
        except Exception:
            return False

    try:
        thermal_guard.init(load_admin_config, stop_server, _start, _running, get_sdr_dir())
        return True
    except Exception as e:
        print("[WARN] thermal guard failed to start: %s" % e)
        return False


def run_script(script_name):
    base = get_sdr_dir()
    sh   = get_allowed_scripts()
    # Resolve absolute path from whitelist map
    if script_name in sh:
        script_path = Path(sh[script_name])
    elif Path(script_name).is_absolute() and Path(script_name).exists():
        script_path = Path(script_name)
    else:
        script_path = base / script_name
    if not script_path.exists():
        return False, "Script introuvable : " + str(script_path)
    try:
        script_path.chmod(script_path.stat().st_mode | 0o111)
        proc = subprocess.Popen(
            ["bash", str(script_path)],
            cwd=str(script_path.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            out, _ = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            out = "(running in background)"
        with log_lock:
            log_buffer.append("[" + datetime.now().strftime("%H:%M:%S") + "] RAN " + script_name + ": " + out[:200])
        return True, "Démarré : " + script_path.name + " (PID " + str(proc.pid) + ")" + chr(10) + out
    except Exception as e:
        return False, str(e)

def stop_server():
    cfg = load_admin_config()
    configured = cfg.get("stop_script", "").strip()
    if configured:
        return run_script(configured)
    base = get_sdr_dir()
    fallback = base / "stop-websdr.sh"
    if fallback.exists():
        return run_script("stop-websdr.sh")
    # Last resort: kill by process name
    try:
        subprocess.run(["killall", "spectrumserver"], capture_output=True)
        return True, "SIGTERM envoyé à spectrumserver"
    except Exception as e:
        return False, str(e)

def read_file_safe(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"# Error reading file: {e}"

def write_file_safe(path, content):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True, "Enregistré avec succès"
    except Exception as e:
        return False, str(e)

def tail_file_lines(path, n):
    """The last n lines of a file, without reading all of it.

    This used to be f.readlines()[-n:], which pulls the entire file into memory
    to show a hundred lines. spectrumserver.log reaches ~10 MB before it
    rotates and the viewer refreshes every 3 seconds; measured, the old path
    costs about 30 ms per refresh at that size against 0.2 ms here. Not fatal,
    but it is pure waste on a panel that is polling anyway, and it grows with
    the log. Walk backwards from the end in blocks until there are enough
    newlines. Verified line-for-line against tail(1), including on an empty
    file, one with no trailing newline, and one spanning several blocks.
    """
    block = 64 * 1024
    data = b""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        while pos > 0 and data.count(b"\n") <= n:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            data = f.read(step) + data
    text = data.decode("utf-8", errors="replace")
    return [l.rstrip() for l in text.splitlines()[-n:]]

def read_log_lines(log_name, n=100):
    base = get_sdr_dir()
    if log_name not in LOG_FILES:
        return []
    lf = base / LOG_FILES[log_name]
    lines = []
    if lf.exists():
        try:
            lines = tail_file_lines(lf, n)
        except Exception as e:
            lines = [f"Error reading {lf.name}: {e}"]
    if log_name == "admin.log":
        with log_lock:
            mem_lines = list(log_buffer[-50:])
        return lines + mem_lines   # file (older) first, in-memory (newer) last
    return lines

def tail_log(n=100, log_name=None):
    if log_name:
        return read_log_lines(log_name, n)

    base = get_sdr_dir()
    lines = []
    for name in LOG_FILES:
        lf = base / LOG_FILES[name]
        if lf.exists():
            try:
                file_lines = tail_file_lines(lf, n)
                lines.append(f"===== {lf.name} =====")
                lines.extend(file_lines)
            except Exception as e:
                lines.append(f"===== {lf.name} =====")
                lines.append(f"Error reading {lf.name}: {e}")

    # Fallback: journalctl only if no log files were found/read
    if not lines:
        try:
            result = subprocess.run(
                ["journalctl", "-u", "phantomsdr-admin", "-n", str(n), "--no-pager", "--output=short"],
                capture_output=True, text=True, timeout=3
            )
            if result.stdout.strip():
                lines = result.stdout.strip().splitlines()
        except Exception:
            pass

    # Also try journalctl for spectrumserver process
    if not lines:
        try:
            result = subprocess.run(
                ["journalctl", "_COMM=spectrumserver", "-n", str(n), "--no-pager", "--output=short"],
                capture_output=True, text=True, timeout=3
            )
            if result.stdout.strip():
                lines = result.stdout.strip().splitlines()
        except Exception:
            pass

    with log_lock:
        mem_lines = list(log_buffer[-50:])
    return lines + mem_lines   # file (older) first, in-memory (newer) last

# ─── HTML Template ─────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PhantomSDR Admin · Connexion</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --green:#00ff41;--green2:#00cc33;--amber:#ffb000;--red:#ff3333;
  --bg:#050a05;--panel:#0d1a0d;--border:#1a3a1a;--dim:#1f3a1f;
  --text:#c8ffc8;--text2:#7ab87a;--glow:0 0 10px #00ff4155,0 0 20px #00ff4122;
}
body{background:var(--bg);font-family:'Share Tech Mono',monospace;color:var(--text);
  min-height:100vh;display:flex;align-items:center;justify-content:center;
  background-image:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,65,0.015) 2px,rgba(0,255,65,0.015) 4px);}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 60% at 50% 40%,rgba(0,255,65,0.04) 0%,transparent 70%);pointer-events:none;}

.login-wrap{width:380px;animation:fadeIn .6s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}

.logo{text-align:center;margin-bottom:2rem;}
.logo-title{font-family:'Orbitron',sans-serif;font-weight:900;font-size:1.4rem;
  color:var(--green);text-shadow:var(--glow);letter-spacing:0.1em;}
.logo-sub{font-size:.7rem;color:var(--text2);letter-spacing:.3em;margin-top:.4rem;}
.logo-icon{font-size:3rem;margin-bottom:.5rem;filter:drop-shadow(0 0 12px #00ff41);}

.card{background:var(--panel);border:1px solid var(--border);border-radius:4px;
  padding:2rem;box-shadow:0 0 40px rgba(0,255,65,0.08),inset 0 1px 0 rgba(0,255,65,0.1);}

label{display:block;font-size:.7rem;color:var(--text2);letter-spacing:.2em;margin-bottom:.4rem;margin-top:1.2rem;}
label:first-of-type{margin-top:0;}

input[type=password]{width:100%;background:#071007;border:1px solid var(--border);
  color:var(--green);font-family:'Share Tech Mono',monospace;font-size:.9rem;
  padding:.7rem 1rem;border-radius:3px;outline:none;transition:.2s;caret-color:var(--green);}
input[type=password]:focus{border-color:var(--green);box-shadow:var(--glow);}

.btn{width:100%;margin-top:1.5rem;padding:.8rem;background:transparent;
  border:1px solid var(--green);color:var(--green);font-family:'Orbitron',sans-serif;
  font-size:.75rem;letter-spacing:.2em;cursor:pointer;border-radius:3px;
  transition:.2s;text-transform:uppercase;}
.btn:hover{background:rgba(0,255,65,0.1);box-shadow:var(--glow);}

.error{background:rgba(255,51,51,0.1);border:1px solid #ff333355;color:#ff6666;
  padding:.7rem 1rem;border-radius:3px;font-size:.8rem;margin-bottom:1rem;text-align:center;}

.blink{animation:blink 1.2s step-end infinite;}
@keyframes blink{50%{opacity:0}}

.scanlines{pointer-events:none;position:fixed;inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,0.08) 3px,rgba(0,0,0,0.08) 4px);
  z-index:9999;}
</style>
</head>
<body>
<div class="scanlines"></div>
<div class="login-wrap">
  <div class="logo">
    <div class="logo-icon">📡</div>
    <div class="logo-title">PHANTOM<span style="color:var(--amber)">SDR</span></div>
    <div class="logo-sub">PANNEAU D'ADMINISTRATION</div>
  </div>
  <div class="card">
    {% if error %}<div class="error">⚠ {{ error }}</div>{% endif %}
    <form method="post">
      <label>CODE D'ACCÈS</label>
      <input type="password" name="password" autofocus placeholder="••••••••">
      <button type="submit" class="btn">▶ SE CONNECTER<span class="blink">_</span></button>
    </form>
  </div>
</div>
</body>
</html>"""

SETUP_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PhantomSDR Admin &#183; Installation</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--green:#00ff41;--amber:#ffb000;--red:#ff3333;--blue:#00ccff;
  --bg:#050a05;--panel:#0d1a0d;--border:#1a3a1a;--text:#c8ffc8;--text2:#7ab87a;--text3:#4a8a4a;
  --glow:0 0 10px #00ff4155,0 0 20px #00ff4122;}
body{background:var(--bg);font-family:"Share Tech Mono",monospace;color:var(--text);
  min-height:100vh;display:flex;align-items:center;justify-content:center;
  background-image:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,65,0.015) 2px,rgba(0,255,65,0.015) 4px);}
body::before{content:"";position:fixed;inset:0;background:radial-gradient(ellipse 80% 60% at 50% 40%,rgba(0,255,65,0.04) 0%,transparent 70%);pointer-events:none;}
.scanlines{pointer-events:none;position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,0.08) 3px,rgba(0,0,0,0.08) 4px);z-index:9999;}
.wrap{width:500px;max-width:96vw;animation:fadeIn .5s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
.logo{text-align:center;margin-bottom:1.5rem;}
.logo-icon{font-size:2.5rem;filter:drop-shadow(0 0 10px #00ff41);}
.logo-title{font-family:"Orbitron",sans-serif;font-weight:900;font-size:1.3rem;color:var(--green);text-shadow:var(--glow);letter-spacing:.1em;margin-top:.4rem;}
.logo-sub{font-size:.65rem;color:var(--text3);letter-spacing:.3em;margin-top:.3rem;}
.card{background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:1.6rem;box-shadow:0 0 40px rgba(0,255,65,0.06);}
.step-label{font-family:"Orbitron",sans-serif;font-size:.6rem;color:var(--text3);letter-spacing:.25em;margin-bottom:1.2rem;padding-bottom:.5rem;border-bottom:1px solid var(--border);}
.field{margin-bottom:1rem;}
.field label{display:block;font-size:.65rem;color:var(--text2);letter-spacing:.15em;margin-bottom:.35rem;}
.field input,.field select{width:100%;background:#071007;border:1px solid var(--border);color:var(--green);
  font-family:"Share Tech Mono",monospace;font-size:.85rem;padding:.6rem .8rem;border-radius:3px;outline:none;transition:.15s;}
.field input:focus,.field select:focus{border-color:var(--green);box-shadow:var(--glow);}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:.7rem;}
.hint{font-size:.62rem;color:var(--text3);margin-top:.3rem;line-height:1.5;}
.detect-btn{display:inline-flex;align-items:center;gap:.4rem;padding:.35rem .7rem;font-size:.65rem;cursor:pointer;border-radius:2px;border:1px solid #00ccff55;color:var(--blue);background:transparent;font-family:"Share Tech Mono",monospace;transition:.15s;margin-bottom:.5rem;}
.detect-btn:hover{background:rgba(0,204,255,0.08);}
.btn{width:100%;margin-top:1.2rem;padding:.85rem;background:transparent;border:1px solid var(--green);color:var(--green);font-family:"Orbitron",sans-serif;font-size:.75rem;letter-spacing:.2em;cursor:pointer;border-radius:3px;transition:.2s;text-transform:uppercase;}
.btn:hover{background:rgba(0,255,65,0.1);box-shadow:var(--glow);}
.btn:disabled{opacity:.4;cursor:not-allowed;}
.err{background:rgba(255,51,51,0.1);border:1px solid #ff333355;color:#ff6666;padding:.6rem .9rem;border-radius:3px;font-size:.75rem;margin-top:.8rem;display:none;}
.ok-msg{background:rgba(0,255,65,0.08);border:1px solid #00ff4155;color:var(--green);padding:.6rem .9rem;border-radius:3px;font-size:.75rem;margin-top:.8rem;display:none;}
.blink{animation:blink 1.2s step-end infinite;}
@keyframes blink{50%{opacity:0}}
</style>
</head>
<body>
<div class="scanlines"></div>
<div class="wrap">
  <div class="logo">
    <div class="logo-icon">&#128225;</div>
    <div class="logo-title">PHANTOM<span style="color:var(--amber)">SDR</span></div>
    <div class="logo-sub">PREMIÈRE CONFIGURATION</div>
  </div>
  <div class="card">
    <div class="step-label">&#9654; CONFIGUREZ VOTRE STATION</div>
    <div class="field">
      <label>RÉPERTOIRE D'INSTALLATION SDR</label>
      <button class="detect-btn" onclick="autoDetect()" id="detect-btn">&#9889; DÉTECTION AUTO</button>
      <select id="dir-sel" onchange="dirSelChange()" style="margin-bottom:.4rem;display:none;"></select>
      <input type="text" id="sdr-dir" placeholder="/chemin/vers/PhantomSDR-Plus">
      <div class="hint">Dossier racine contenant config.toml, build/, frontend/, etc.</div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>NOM DU PROCESSUS SDR</label>
        <input type="text" id="proc-name" value="spectrumserver" placeholder="spectrumserver">
        <div class="hint">Pour détecter l'état EN LIGNE</div>
      </div>
      <div class="field">
        <label>PORT PUBLIC</label>
        <input type="number" id="pub-port" value="8900" placeholder="8900" min="1" max="65535">
        <div class="hint">Port auquel les auditeurs se connectent</div>
      </div>
    </div>
    <div class="field">
      <label>NOUVEAU MOT DE PASSE ADMIN <span style="color:var(--red)">*</span></label>
      <input type="password" id="new-pwd" placeholder="Choisissez un mot de passe robuste" autocomplete="new-password">
    </div>
    <div class="field">
      <label>CONFIRMER LE MOT DE PASSE</label>
      <input type="password" id="new-pwd2" placeholder="Répétez le mot de passe" autocomplete="new-password">
    </div>
    <div class="err" id="err-box"></div>
    <div class="ok-msg" id="ok-box">Configuration terminée ! Redirection…<span class="blink">_</span></div>
    <button class="btn" onclick="completeSetup()" id="setup-btn">&#9654; TERMINER LA CONFIGURATION<span class="blink">_</span></button>
  </div>
</div>
<script>
async function autoDetect() {
  var btn = document.getElementById("detect-btn");
  btn.textContent = "Detecting...";
  btn.disabled = true;
  try {
    var r = await fetch("/admin/api/autodetect");
    var d = await r.json();
    var candidates = d.candidates || [];
    var sel = document.getElementById("dir-sel");
    sel.innerHTML = "";
    if (candidates.length > 0) {
      sel.style.display = "block";
      candidates.forEach(function(c) {
        var opt = document.createElement("option");
        opt.value = c; opt.textContent = c;
        sel.appendChild(opt);
      });
      document.getElementById("sdr-dir").value = candidates[0];
      btn.textContent = "Trouvé : " + candidates.length + " candidat(s)";
    } else {
      btn.textContent = "Rien trouvé — saisissez le chemin à la main";
    }
  } catch(e) { btn.textContent = "Échec de la détection"; }
  btn.disabled = false;
}
function dirSelChange() {
  var v = document.getElementById("dir-sel").value;
  if (v) document.getElementById("sdr-dir").value = v;
}
function showErr(msg) {
  var el = document.getElementById("err-box");
  el.textContent = msg; el.style.display = "block";
  document.getElementById("ok-box").style.display = "none";
}
async function completeSetup() {
  document.getElementById("err-box").style.display = "none";
  var dir = document.getElementById("sdr-dir").value.trim();
  var pn  = document.getElementById("proc-name").value.trim() || "spectrumserver";
  var pp  = parseInt(document.getElementById("pub-port").value) || 8900;
  var pw  = document.getElementById("new-pwd").value;
  var pw2 = document.getElementById("new-pwd2").value;
  if (!dir)          { showErr("Le répertoire de base SDR est obligatoire"); return; }
  if (!pw)           { showErr("Le mot de passe est obligatoire"); return; }
  if (pw.length < 12) { showErr("Le mot de passe doit contenir au moins 12 caractères"); return; }
  if (pw !== pw2)    { showErr("Les mots de passe ne correspondent pas"); return; }
  var btn = document.getElementById("setup-btn");
  btn.disabled = true; btn.textContent = "Saving...";
  try {
    var r = await fetch("/admin/api/setup", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({sdr_base_dir: dir, sdr_process_name: pn,
                            public_port: pp, new_password: pw})
    });
    var d = await r.json();
    if (d.ok) {
      document.getElementById("ok-box").style.display = "block";
      btn.style.display = "none";
      setTimeout(function() { window.location.href = "/admin/dashboard"; }, 1200);
    } else {
      showErr(d.msg || "Échec de la configuration");
      btn.disabled = false; btn.textContent = "&#9654; TERMINER LA CONFIGURATION_";
    }
  } catch(e) {
    showErr("Erreur réseau : " + e.message);
    btn.disabled = false; btn.textContent = "&#9654; TERMINER LA CONFIGURATION_";
  }
}
autoDetect();
</script>
</body>
</html>"""

MAIN_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PhantomSDR · Panneau d'administration</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --green:#00ff41;--green2:#00cc33;--amber:#ffb000;--red:#ff4040;--blue:#00ccff;
  --bg:#050a05;--panel:#0a150a;--panel2:#0d1a0d;--border:#1a3a1a;--dim:#1f3a1f;
  --text:#c8ffc8;--text2:#7ab87a;--text3:#4a8a4a;
  --glow:0 0 8px #00ff4155,0 0 20px #00ff4122;
  --glow-amber:0 0 8px #ffb00055,0 0 20px #ffb00022;
  --glow-red:0 0 8px #ff404055;
}
html,body{height:100%;background:var(--bg);font-family:'Share Tech Mono',monospace;
  color:var(--text);font-size:20px;}
body{background-image:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,65,0.01) 2px,rgba(0,255,65,0.01) 4px);}

/* Layout */
.layout{display:flex;height:100vh;overflow:hidden;}
.sidebar{width:220px;min-width:220px;background:var(--panel);border-right:1px solid var(--border);
  display:flex;flex-direction:column;overflow-y:auto;}
.main{flex:1;overflow:hidden;display:flex;flex-direction:column;}
.topbar{background:var(--panel);border-bottom:1px solid var(--border);
  padding:.7rem 1.2rem;display:flex;align-items:center;justify-content:space-between;}
.content{flex:1;overflow-y:auto;padding:1.4rem;}

/* Sidebar */
.sidebar-logo{padding:1.2rem 1rem;border-bottom:1px solid var(--border);text-align:center;}
.sidebar-logo .title{font-family:'Orbitron',sans-serif;font-weight:900;font-size:1rem;
  color:var(--green);text-shadow:var(--glow);}
.sidebar-logo .sub{font-size:.6rem;color:var(--text3);letter-spacing:.3em;margin-top:.2rem;}
.sidebar-logo .icon{font-size:1.8rem;margin-bottom:.3rem;filter:drop-shadow(0 0 8px #00ff41);}

.nav-section{padding:.5rem 0;}
.nav-label{font-size:.55rem;color:var(--text3);letter-spacing:.3em;padding:.4rem 1rem .2rem;}
.nav-item{display:flex;align-items:center;gap:.6rem;padding:.55rem 1rem;
  cursor:pointer;color:var(--text2);transition:.15s;border-left:2px solid transparent;
  text-decoration:none;font-size:.8rem;}
.nav-item:hover{color:var(--green);background:rgba(0,255,65,0.05);border-left-color:var(--green2);}
.nav-item.active{color:var(--green);background:rgba(0,255,65,0.08);
  border-left-color:var(--green);text-shadow:var(--glow);}
.nav-item .icon{font-size:1rem;width:1.2rem;text-align:center;}

.sidebar-footer{margin-top:auto;padding:.8rem 1rem;border-top:1px solid var(--border);
  font-size:.65rem;color:var(--text3);}

/* Topbar */
.topbar-title{font-family:'Orbitron',sans-serif;font-size:.85rem;color:var(--green);}
.status-pill{display:inline-flex;align-items:center;gap:.4rem;
  padding:.3rem .7rem;border-radius:2px;font-size:.7rem;}
.status-pill.online{background:rgba(0,255,65,0.1);border:1px solid #00ff4155;color:var(--green);}
.status-pill.offline{background:rgba(255,64,64,0.1);border:1px solid #ff404055;color:var(--red);}
.status-dot{width:6px;height:6px;border-radius:50%;animation:pulse 2s infinite;}
.status-dot.online{background:var(--green);box-shadow:0 0 6px var(--green);}
.status-dot.offline{background:var(--red);}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

.topbar-right{display:flex;align-items:center;gap:1rem;}
.topbar-time{font-size:.7rem;color:var(--text3);}
.logout-btn{font-size:.65rem;color:var(--text3);text-decoration:none;
  padding:.2rem .5rem;border:1px solid var(--border);border-radius:2px;transition:.15s;}
.logout-btn:hover{color:var(--red);border-color:#ff404055;}

/* Cards */
.grid{display:grid;gap:1rem;}
.grid-2{grid-template-columns:1fr 1fr;}
.grid-3{grid-template-columns:1fr 1fr 1fr;}
.grid-4{grid-template-columns:repeat(4,1fr);}
.grid-5{grid-template-columns:repeat(5,1fr);}

.card{background:var(--panel);border:1px solid var(--border);border-radius:3px;padding:1rem;}
.card-header{font-family:'Orbitron',sans-serif;font-size:.7rem;color:var(--text2);
  letter-spacing:.15em;margin-bottom:.8rem;display:flex;align-items:center;gap:.5rem;}
.card-header .dot{width:6px;height:6px;border-radius:50%;background:var(--green);
  box-shadow:0 0 6px var(--green);}

/* Stat cards */
.stat-val{font-family:'Orbitron',sans-serif;font-size:1.6rem;font-weight:700;
  color:var(--green);text-shadow:var(--glow);}
.stat-label{font-size:.65rem;color:var(--text3);margin-top:.2rem;letter-spacing:.1em;}
.stat-sub{font-size:.7rem;color:var(--text2);margin-top:.3rem;}

/* Load/temperature thresholds. These are NOT the terminal palette above: they
   are the web UI's colours (App.svelte), so the same reading looks the same in
   both places.  The chrome stays green; only the numbers that mean "hot" move. */
:root{--stat-ok:#4ade80;--stat-warn:#fbbf24;--stat-bad:#ef4444;}

/* Progress bars */
.bar-wrap{background:#071207;border-radius:2px;height:6px;margin-top:.5rem;overflow:hidden;}
.bar-fill{height:100%;border-radius:2px;transition:.5s;background:var(--stat-ok);}
.bar-fill.warn{background:var(--stat-warn);}
.bar-fill.danger{background:var(--stat-bad);}

/* Buttons */
.btn{display:inline-flex;align-items:center;gap:.4rem;padding:.5rem .9rem;
  font-family:'Share Tech Mono',monospace;font-size:.75rem;cursor:pointer;
  border-radius:2px;transition:.15s;border:1px solid;background:transparent;letter-spacing:.05em;
  color:var(--text2);border-color:#ffffff40;text-decoration:none;}
.btn:hover{background:rgba(255,255,255,0.06);}
.btn-green{color:var(--green);border-color:#00ff4155;}
.btn-green:hover{background:rgba(0,255,65,0.1);box-shadow:var(--glow);}
.btn-red{color:var(--red);border-color:#ff404055;}
.btn-red:hover{background:rgba(255,64,64,0.1);box-shadow:var(--glow-red);}
.btn-amber{color:var(--amber);border-color:#ffb00055;}
.fork-notice{margin-bottom:1rem;padding:.7rem 1rem;border:1px solid #ffb00077;border-radius:4px;
  background:#ffb0000f;color:var(--amber);font-size:.8rem;line-height:1.5;overflow-wrap:anywhere;}
.fork-notice a{color:var(--amber);text-decoration:underline;}
.btn-amber:hover{background:rgba(255,176,0,0.1);box-shadow:var(--glow-amber);}
.btn-blue{color:var(--blue);border-color:#00ccff55;}
.btn-blue:hover{background:rgba(0,204,255,0.1);}
.btn-lg{padding:.7rem 1.4rem;font-size:.85rem;}
.btn:disabled{opacity:.4;cursor:not-allowed;}
/* Range picker on the Graphs page: the selected range must read as chosen, not
   merely hovered, so it gets the filled state the other buttons only borrow. */
.btn.graph-range{color:var(--text2);border-color:var(--border);}
.btn.graph-range:hover{color:var(--green);border-color:#00ff4155;}
.btn.graph-range.active{color:var(--green);border-color:#00ff4188;
  background:rgba(0,255,65,0.08);box-shadow:var(--glow);}
/* Larger type on the Graphs page only — these are readings meant to be read
   from across the room, not the dense label text the other pages use.  Scoped
   to #page-graphs so the shared card classes keep their sizing elsewhere. */
#page-graphs .card-header{font-size:.78rem;}
#page-graphs .stat-val{font-size:2rem;}
#page-graphs .stat-label{font-size:.78rem;}
#page-graphs .btn.graph-range{font-size:.82rem;padding:.55rem 1rem;}

/* Per-decoder spot tiles (Spot Reporting page) */
.ar-spot-tile{background:#071007;border:1px solid var(--border);border-radius:3px;
  padding:.6rem .7rem;text-align:center;}
.ar-spot-mode{font-family:'Orbitron',sans-serif;font-size:.72rem;color:var(--text2);
  letter-spacing:.18em;}
.ar-spot-count{font-family:'Orbitron',sans-serif;font-size:1.7rem;font-weight:700;
  color:var(--green);text-shadow:var(--glow);margin:.15rem 0 .1rem;}
.ar-spot-count.idle{color:var(--text3);text-shadow:none;}
.ar-spot-sub{font-size:.63rem;color:var(--text3);letter-spacing:.05em;line-height:1.5;}
/* Uploaded-count badge next to each mode in the bands/modes header */
.ar-hdr-badge{display:inline-block;margin-left:.35rem;padding:0 .35rem;border-radius:2px;
  font-family:'Share Tech Mono',monospace;font-size:.62rem;letter-spacing:0;
  background:rgba(0,255,65,0.12);color:var(--green);border:1px solid #00ff4144;}
.ar-hdr-badge:empty{display:none;}
/* All-time spot count printed beside each band/mode checkbox */
/* Sits tight against its own checkbox: the count belongs to that one slot, and
   a wide gap lets the eye pair it with the neighbouring column instead. The
   checkbox loses its default margin for the same reason. */
/* table.markers input sets width:100% for the text inputs on the Markers page.
   Inherited by these checkboxes it stretched each one across its whole cell,
   which shoved the count to the far right of the column — and off the edge
   entirely in the last one, so WSPR's numbers sat in the horizontal overflow. */
#ar-matrix input[type=checkbox]{width:auto;margin:0;vertical-align:middle;}
.ar-slot-tot{margin-left:.5rem;vertical-align:middle;
  font-family:'Share Tech Mono',monospace;font-size:.74rem;
  color:var(--green);text-shadow:0 0 6px #00ff4188;}
/* Decodes with nothing uploaded yet — amber rather than a dim grey: it is a
   normal waiting state (PSK Reporter only flushes every 5 min), so it should be
   as readable as the uploaded count, just distinguishable from it. */
.ar-slot-tot.none{color:var(--amber);text-shadow:0 0 6px #ffb00077;}
.ar-slot-tot:empty{display:none;}

/* Server control card */
.sdr-control{display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-start;}
.sdr-info{flex:1;min-width:200px;}
.sdr-info p{margin:.3rem 0;font-size:.75rem;color:var(--text2);}
.sdr-info .val{color:var(--green);}
.sdr-btns{display:flex;flex-direction:column;gap:.5rem;}
.script-select{background:#071207;border:1px solid var(--border);color:var(--text);
  font-family:'Share Tech Mono',monospace;font-size:.75rem;padding:.4rem .6rem;
  border-radius:2px;width:100%;margin-bottom:.5rem;}
.script-select:focus{border-color:var(--green);outline:none;}

/* Editor */
.editor-toolbar{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin-bottom:.7rem;}
.file-select{background:#071207;border:1px solid var(--border);color:var(--text);
  font-family:'Share Tech Mono',monospace;font-size:.75rem;padding:.4rem .7rem;
  border-radius:2px;flex:1;}
.file-select:focus{outline:none;border-color:var(--green);}
textarea.code{width:100%;background:#030803;border:1px solid var(--border);color:#c8ffc8;
  font-family:'Share Tech Mono',monospace;font-size:.75rem;line-height:1.6;
  padding:.8rem;border-radius:3px;resize:vertical;outline:none;
  min-height:400px;transition:.2s;}
textarea.code:focus{border-color:var(--green);box-shadow:var(--glow);}

/* Toast */
#toast{position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;display:flex;
  flex-direction:column;gap:.4rem;}
.toast{padding:.6rem 1rem;border-radius:3px;font-size:.75rem;
  animation:toastIn .3s ease;border:1px solid;}
.toast.ok{background:rgba(0,255,65,0.12);border-color:#00ff4155;color:var(--green);}
.toast.err{background:rgba(255,64,64,0.12);border-color:#ff404055;color:var(--red);}
@keyframes toastIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:none}}

/* Log viewer */
.log-box{background:#030803;border:1px solid var(--border);border-radius:3px;
  padding:.8rem;font-size:.7rem;line-height:1.8;height:400px;overflow-y:auto;
  color:var(--text2);word-break:break-all;}
.log-box::-webkit-scrollbar{width:4px;}
.log-box::-webkit-scrollbar-track{background:var(--bg);}
.log-box::-webkit-scrollbar-thumb{background:var(--dim);}
.log-line-err{color:var(--red);}
.log-line-warn{color:var(--amber);}
.log-line-ok{color:var(--green);}

/* Tabs inside sections */
.tab-bar{display:flex;flex-wrap:wrap;border-bottom:1px solid var(--border);margin-bottom:1rem;}
.tab{padding:.5rem 1rem;font-size:.7rem;cursor:pointer;color:var(--text3);
  border-bottom:2px solid transparent;transition:.15s;letter-spacing:.1em;}
.tab.active{color:var(--green);border-bottom-color:var(--green);}
.tab-pane{display:none;}
.tab-pane.active{display:block;}

/* Section heading */
.section-head{font-family:'Orbitron',sans-serif;font-size:.8rem;color:var(--green);
  letter-spacing:.15em;margin-bottom:1rem;padding-bottom:.5rem;
  border-bottom:1px solid var(--border);}

/* JSON editor helpers */
.json-path{font-size:.65rem;color:var(--text3);margin-bottom:.5rem;}

input[type=text],input[type=password],input[type=number]{
  background:#071207;border:1px solid var(--border);color:var(--text);
  font-family:'Share Tech Mono',monospace;font-size:.8rem;padding:.4rem .7rem;
  border-radius:2px;outline:none;transition:.15s;}
input:focus{border-color:var(--green);box-shadow:0 0 6px #00ff4122;}

/* Chat history */
.chat-log{background:#030803;border:1px solid var(--border);border-radius:3px;
  padding:.8rem;font-size:.75rem;line-height:2;height:500px;overflow-y:auto;}
.chat-msg{display:flex;align-items:baseline;gap:.5rem;border-bottom:1px solid #0a1a0a;padding:.3rem 0;}
.chat-msg-text{flex:1;}
.chat-nick{color:var(--amber);}
.chat-time{color:var(--text3);font-size:.65rem;}
.chat-del-btn{flex-shrink:0;background:transparent;border:1px solid #ff404044;color:#ff6060;
  font-family:'Share Tech Mono',monospace;font-size:.6rem;padding:.1rem .4rem;border-radius:2px;
  cursor:pointer;transition:.15s;line-height:1.4;}
.chat-del-btn:hover{background:rgba(255,64,64,0.15);border-color:#ff404088;}

/* Top processes table */
table.top-procs{width:100%;border-collapse:collapse;font-size:.72rem;}
table.top-procs th{color:var(--text3);font-weight:normal;letter-spacing:.1em;
  padding:.35rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;}
table.top-procs td{padding:.3rem .5rem;border-bottom:1px solid #0a1a0a;
  white-space:nowrap;overflow:hidden;max-width:200px;text-overflow:ellipsis;}
table.top-procs tr:hover td{background:rgba(0,255,65,0.04);}
table.top-procs .cpu-hi{color:var(--stat-bad);}
table.top-procs .cpu-med{color:var(--stat-warn);}
table.top-procs .cpu-ok{color:var(--stat-ok);}
table.top-procs .mem-col{color:var(--blue);}

/* ── Mobile Bottom Nav Bar ──────────────────────────────────── */
.bottom-nav{display:none;}
.hamburger{display:none;}
.sidebar-backdrop{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:199;}
.sidebar-backdrop.open{display:block;}

@media(max-width:768px){
  /* Hide desktop sidebar, show bottom nav */
  .sidebar{display:none !important;}
  .hamburger{display:none !important;}

  /* Layout: vertical stack, leave room for bottom nav */
  .layout{flex-direction:column;}
  .main{height:100vh;display:flex;flex-direction:column;}
  .content{flex:1;overflow-y:auto;padding:.6rem;padding-bottom:70px;}

  /* Topbar */
  .topbar{padding:.5rem .8rem;gap:.5rem;}
  .topbar-title{font-size:.8rem;flex:1;}
  .topbar-time{display:none;}
  .status-pill{padding:.2rem .5rem;font-size:.65rem;}

  /* Bottom navigation bar */
  .bottom-nav{
    display:flex;position:fixed;bottom:0;left:0;right:0;z-index:100;
    background:var(--panel);border-top:1px solid var(--border);
    height:58px;align-items:stretch;
    box-shadow:0 -4px 20px rgba(0,0,0,.5);
  }
  .bottom-nav a{
    flex:1;display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:2px;color:var(--text3);text-decoration:none;
    font-size:.5rem;letter-spacing:.05em;border-top:2px solid transparent;
    transition:.15s;padding:.3rem .1rem;min-width:0;
    -webkit-tap-highlight-color:transparent;
  }
  .bottom-nav a .bi{font-size:1.3rem;line-height:1;}
  .bottom-nav a span{font-size:.48rem;letter-spacing:.02em;white-space:nowrap;}
  .bottom-nav a.active{color:var(--green);border-top-color:var(--green);}
  .bottom-nav a:active{background:rgba(0,255,65,0.08);}

  /* Grids → single column */
  .grid-2,.grid-3,.grid-4,.grid-5{grid-template-columns:1fr !important;}

  /* Cards */
  .card{padding:.7rem;overflow-x:auto;}

  /* Stat values */
  .stat-val{font-size:1.3rem;}

  /* Buttons — full width on mobile for easy tapping */
  .btn{padding:.7rem 1rem;font-size:.85rem;min-height:44px;}
  .btn-lg{padding:.8rem 1.2rem;font-size:.9rem;}

  /* Form controls — larger for touch */
  .script-select,.file-select,
  input[type=text],input[type=password],input[type=number]{
    font-size:1rem;padding:.6rem .8rem;min-height:44px;}
  select{min-height:44px;}

  /* Log boxes */
  .log-box{height:220px !important;font-size:.7rem;}

  /* Tables: horizontal scroll */
  table.markers,table.top-procs{min-width:420px;}

  /* Textarea */
  textarea.code{min-height:200px;font-size:.8rem;}

  /* Toast position above bottom nav */
  #toast{bottom:70px;}

  /* Section heading */
  .section-head{font-size:.75rem;}
}

@media(max-width:390px){
  .bottom-nav a .bi{font-size:1.1rem;}
  .bottom-nav a span{display:none;}
  .bottom-nav{height:52px;}
  .content{padding-bottom:60px;}
}

.scanlines{pointer-events:none;position:fixed;inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,0.06) 3px,rgba(0,0,0,0.06) 4px);
  z-index:9999;}

/* Pages */
.page{display:none;}
.page.active{display:block;}

/* Markers table */
table.markers{width:100%;border-collapse:collapse;font-size:.75rem;}
table.markers th{color:var(--text3);font-weight:normal;letter-spacing:.1em;
  padding:.4rem .6rem;border-bottom:1px solid var(--border);text-align:left;}
table.markers td{padding:.4rem .6rem;border-bottom:1px solid #0a1a0a;vertical-align:middle;}
table.markers tr:hover td{background:rgba(0,255,65,0.03);}
table.markers input{width:100%;background:transparent;border:none;
  color:var(--text);font-family:'Share Tech Mono',monospace;font-size:.75rem;}
table.markers input:focus{background:#071207;outline:1px solid var(--border);}
</style>
</head>
<body>
<div class="scanlines"></div>
<div class="layout">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-logo">
      <div class="icon">📡</div>
      <div class="title">PHANTOM<span style="color:var(--amber)">SDR</span></div>
      <div class="sub">ADMIN v5.1.0</div>
    </div>
    <div class="nav-section">
      <div class="nav-label">PRINCIPAL</div>
      <a class="nav-item active" onclick="showPage('dashboard',this)" href="#">
        <span class="icon">⬡</span><span>Tableau de bord</span>
      </a>
    </div>
    <div class="nav-section">
      <div class="nav-label">CONFIGURATION</div>
      <a class="nav-item" onclick="showPage('config',this)" href="#">
        <span class="icon">⚙</span><span>Éditeur de config</span>
      </a>
      <a class="nav-item" onclick="showPage('siteinfo',this)" href="#">
        <span class="icon">◎</span><span>Infos du site</span>
      </a>
      <a class="nav-item" onclick="showPage('markers',this)" href="#">
        <span class="icon">◉</span><span>Marqueurs</span>
      </a>
      <a class="nav-item" onclick="showPage('reporting',this)" href="#">
        <span class="icon">📶</span><span>Envoi des spots</span>
      </a>
    </div>
    <div class="nav-section">
      <div class="nav-label">SURVEILLANCE</div>
      <a class="nav-item" onclick="showPage('logs',this)" href="#">
        <span class="icon">▤</span><span>Journaux</span>
      </a>
      <a class="nav-item" onclick="showPage('chat',this)" href="#">
        <span class="icon">◫</span><span>Historique du chat</span>
      </a>
      <a class="nav-item" onclick="showPage('graphs',this)" href="#">
        <span class="icon">📈</span><span>Graphiques</span>
      </a>
      <a class="nav-item" onclick="showPage('users',this)" href="#">
        <span class="icon">👥</span><span>Auditeurs connectés</span>
      </a>
      <a class="nav-item" onclick="showPage('listeners',this)" href="#">
        <span class="icon">🔎</span><span>Analyse auditeurs</span>
      </a>
      <a class="nav-item" onclick="showPage('wfmsg',this)" href="#">
        <span class="icon">📢</span><span>Message waterfall</span>
      </a>
      <a class="nav-item" onclick="showPage('map',this)" href="#">
        <span class="icon">🗺</span><span>Carte auditeurs</span>
      </a>
      <a class="nav-item" onclick="showPage('signal',this)" href="#">
        <span class="icon">📡</span><span>Qualité du signal</span>
      </a>
      <a class="nav-item" onclick="showPage('health',this)" href="#">
        <span class="icon">🩺</span><span>Santé du serveur</span>
      </a>
    </div>
    <div class="nav-section">
      <div class="nav-label">SYSTÈME</div>
      <a class="nav-item" onclick="showPage('update',this)" href="#">
        <span class="icon">🔄</span><span>Mise à jour</span>
      </a>
      <a class="nav-item" onclick="showPage('backup',this)" href="#">
        <span class="icon">💾</span><span>Sauvegardes</span>
      </a>
      <a class="nav-item" onclick="showPage('settings',this)" href="#">
        <span class="icon">◧</span><span>Réglages</span>
      </a>
    </div>
    <div class="sidebar-footer">
      PhantomSDR-Plus<br>Admin Panel
    </div>
  </div>

  <!-- Main -->
  <div class="main">
    <div class="topbar">
      <div class="topbar-title" id="page-title">TABLEAU DE BORD</div>
      <div class="topbar-right">
        <div id="sdr-status" class="status-pill offline">
          <div class="status-dot offline"></div>
          <span>HORS LIGNE</span>
        </div>
        <div class="topbar-time" id="clock">--:--:--</div>
        <a class="logout-btn" href="/admin/logout">⏻ DÉCONNEXION</a>
      </div>
    </div>

    <div class="content">

      {% if fork_origin %}
      <!-- Installed from a fork — see fork_origin() -->
      <div class="fork-notice">
        &#9432; Cette copie de PhantomSDR-Plus a été installée depuis un fork :
        <b>{{ fork_origin }}</b><br>
        Le PhantomSDR-Plus d'origine est développé sur
        <a href="{{ origin_repo }}" target="_blank" rel="noopener noreferrer">{{ origin_repo }}</a>.
        Un fork peut être plus ancien que l'original ou modifié par son auteur ; mises à jour,
        documentation et assistance proviennent de l'original.
      </div>
      {% endif %}

      <!-- ══════ DASHBOARD PAGE ══════ -->
      <div class="page active" id="page-dashboard">
        <div class="grid grid-5" style="margin-bottom:1rem;">
          <div class="card">
            <div class="card-header"><div class="dot"></div>ÉTAT DU SDR</div>
            <div class="stat-val" id="stat-status">--</div>
            <div class="stat-label">ÉTAT DU PROCESSUS</div>
            <div class="stat-sub" id="stat-pid">PID: --</div>
          </div>
          <div class="card">
            <div class="card-header"><div class="dot" style="background:var(--amber);box-shadow:0 0 6px var(--amber)"></div>UTILISATION CPU</div>
            <div class="stat-val" id="stat-cpu">--%</div>
            <div class="stat-label">CPU SYSTÈME</div>
            <div class="bar-wrap"><div class="bar-fill" id="bar-cpu" style="width:0%"></div></div>
          </div>
          <div class="card">
            <div class="card-header"><div class="dot" style="background:var(--blue);box-shadow:0 0 6px var(--blue)"></div>MÉMOIRE</div>
            <div class="stat-val" id="stat-mem">-- GB</div>
            <div class="stat-label">UTILISÉ / TOTAL</div>
            <div class="bar-wrap"><div class="bar-fill" id="bar-mem" style="width:0%"></div></div>
          </div>
          <div class="card">
            <div class="card-header"><div class="dot" style="background:#ff88ff;box-shadow:0 0 6px #ff88ff"></div>DISQUE</div>
            <div class="stat-val" id="stat-disk">-- GB</div>
            <div class="stat-label">UTILISÉ / TOTAL</div>
            <div class="bar-wrap"><div class="bar-fill" id="bar-disk" style="width:0%"></div></div>
          </div>
          <div class="card">
            <div class="card-header"><div class="dot" style="background:#ff4444;box-shadow:0 0 6px #ff4444"></div>TEMPÉRATURE</div>
            <div class="stat-val" id="stat-temp">--&#176;C</div>
            <div class="stat-label">TEMP. CPU</div>
            <div class="bar-wrap"><div class="bar-fill" id="bar-temp" style="width:0%;background:linear-gradient(90deg,#4ade80,#fbbf24,#ef4444)"></div></div>
            <div class="stat-sub" id="stat-temp-guard" style="margin-top:.3rem;">GARDE : --</div>
          </div>
        </div>

        <!-- ══════ RELAIS DIVERSITÉ WEBSDR ══════ -->
        <div class="card" id="relay-card" style="margin-bottom:1rem;display:none;">
          <div class="card-header">
            <div class="dot" id="rl-dot" style="background:var(--text3);box-shadow:none"></div>
            RELAIS DIVERSITÉ WEBSDR
            <span style="margin-left:auto;font-size:.6rem;color:var(--text3);" id="rl-ua"></span>
          </div>
          <div class="grid grid-4" style="gap:.6rem;margin-bottom:.6rem;">
            <div><div style="font-size:.6rem;color:var(--text3);">ÉTAT</div>
                 <div id="rl-state" style="font-size:.9rem;color:var(--green);">--</div></div>
            <div><div style="font-size:.6rem;color:var(--text3);">PORT</div>
                 <div id="rl-port" style="font-size:.9rem;color:var(--text);">--</div></div>
            <div><div style="font-size:.6rem;color:var(--text3);">SESSIONS</div>
                 <div id="rl-sessions" style="font-size:.9rem;color:var(--amber);">--</div></div>
            <div><div style="font-size:.6rem;color:var(--text3);">LIMITE PAR SITE</div>
                 <div id="rl-cap" style="font-size:.9rem;color:var(--text);">--</div></div>
          </div>
          <div id="rl-hosts" style="font-size:.7rem;color:var(--text2);"></div>
          <div id="rl-reason" style="font-size:.65rem;color:var(--text3);margin-top:.3rem;"></div>
        </div>

        <!-- ══════ GARDE THERMIQUE ══════ -->
        <div class="card" id="thermal-card" style="margin-bottom:1rem;display:none;">
          <div class="card-header">
            <div class="dot" id="tg-dot" style="background:#ff4444;box-shadow:0 0 6px #ff4444"></div>
            GARDE THERMIQUE
            <span style="margin-left:auto;font-size:.6rem;color:var(--text3);" id="tg-sensor"></span>
          </div>
          <div class="grid grid-4" style="gap:.6rem;margin-bottom:.6rem;">
            <div><div style="font-size:.6rem;color:var(--text3);">ÉTAT</div>
                 <div id="tg-state" style="font-size:.9rem;color:var(--green);">--</div></div>
            <div><div style="font-size:.6rem;color:var(--text3);">MODE</div>
                 <div id="tg-mode" style="font-size:.9rem;color:var(--text);">--</div></div>
            <div><div style="font-size:.6rem;color:var(--text3);">ARRÊT À</div>
                 <div id="tg-stop" style="font-size:.9rem;color:var(--amber);">--</div></div>
            <div><div style="font-size:.6rem;color:var(--text3);">REPRISE À</div>
                 <div id="tg-resume" style="font-size:.9rem;color:var(--blue);">--</div></div>
          </div>
          <div id="tg-reason" style="font-size:.7rem;color:var(--text2);margin-bottom:.4rem;"></div>
          <div id="tg-last" style="font-size:.68rem;color:var(--text3);font-family:'Share Tech Mono',monospace;word-break:break-word;"></div>
          <div style="margin-top:.6rem;">
            <button class="btn btn-amber" style="padding:.2rem .6rem;font-size:.65rem;"
                    onclick="thermalReset()">LEVER LE BLOCAGE</button>
            <span style="font-size:.6rem;color:var(--text3);margin-left:.5rem;">
              seuils et mode dans Réglages</span>
          </div>
        </div>

        <div class="card" style="margin-bottom:1rem;">
          <div class="card-header">
            <div class="dot" style="background:var(--green);box-shadow:0 0 6px var(--green)"></div>
            TERMINAL
            <span style="margin-left:.4rem;font-size:.6rem;color:var(--text3);" id="term-cwd">~</span>
            <span style="margin-left:auto;font-size:.6rem;color:var(--text3);cursor:pointer;" onmousedown="event.preventDefault()" onclick="termCopy()" title="Copier la sélection, ou toute la sortie si rien n'est sélectionné">&#10697; COPIER</span>
            <span style="margin-left:.8rem;font-size:.6rem;color:var(--text3);cursor:pointer;" onclick="termClear()">&#10005; CLEAR<#10005; EFFACER</span>
          </div>
          <div id="term-output"
            style="font-family:'Share Tech Mono',monospace;font-size:.75rem;line-height:1.5;
                   background:#020902;border:1px solid var(--border);border-radius:3px;
                   padding:.5rem .7rem;height:300px;overflow-y:auto;color:var(--text);
                   white-space:pre-wrap;word-break:break-all;user-select:text;-webkit-user-select:text;resize:vertical;"></div>
          <div style="display:flex;align-items:center;gap:.4rem;margin-top:.4rem;
                      background:#020902;border:1px solid var(--border);border-radius:3px;padding:.3rem .6rem;">
            <span style="color:var(--green);font-size:.75rem;flex-shrink:0;">$</span>
            <input id="term-input" type="text" autocomplete="off" spellcheck="false"
              style="flex:1;background:transparent;border:none;outline:none;
                     color:var(--green);font-family:'Share Tech Mono',monospace;font-size:.75rem;"
              placeholder="tapez une commande puis Entrée"
              onkeydown="termKey(event)">
            <button id="term-run" class="btn btn-green" style="padding:.2rem .6rem;font-size:.65rem;" onclick="termRun()">&#9654;</button>
            <button id="term-stop" class="btn" style="display:none;padding:.2rem .6rem;font-size:.65rem;color:#ff6666;border-color:#ff6666;" onclick="termKill()" title="Interrompre la commande (Ctrl+C)">&#9632; ARRÊT</button>
          </div>
        </div>
        
        <div class="grid grid-2" style="margin-bottom:1rem;">
          <div class="card">
            <div class="card-header">
              <div class="dot"></div>DERNIÈRES LIGNES DU JOURNAL
              <span style="margin-left:auto;font-size:.6rem;color:var(--text3);cursor:pointer;" onclick="loadLogs('dash-log')">↻ actualiser</span>
            </div>
            <div class="log-box" id="dash-log" style="height:280px;">Chargement…</div>
          </div>
          <div class="card">
            <div class="card-header">
              <div class="dot" style="background:var(--amber);box-shadow:0 0 6px var(--amber)"></div>
              PRINCIPAUX PROCESSUS
              <span style="margin-left:auto;font-size:.6rem;color:var(--text3);cursor:pointer;" onclick="updateStatus()">↻ actualiser</span>
            </div>
            <table class="top-procs">
              <thead>
                <tr>
                  <th>PID</th><th>NOM</th><th>UTILISATEUR</th><th>CPU%</th><th>MEM%</th>
                </tr>
              </thead>
              <tbody id="top-procs-tbody">
                <tr><td colspan="5" style="color:var(--text3);text-align:center;">Chargement…</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══════ CONFIG EDITOR PAGE ══════ -->
      <div class="page" id="page-config">
        <div class="section-head">ÉDITEUR DE FICHIERS</div>
        <div class="editor-toolbar">
          <select class="file-select" id="config-file-sel" onchange="loadConfigFile()" style="flex:1;min-width:0;"></select>
          <button class="btn btn-blue" onclick="loadConfigList(true)">🔄 RESCANNER</button>
          <button class="btn btn-blue" onclick="loadConfigFile()">↻ RECHARGER</button>
          <button class="btn btn-green" onclick="saveConfigFile()">💾 ENREGISTRER</button>
        </div>
        <div class="json-path" id="config-filepath">--</div>
        <textarea class="code" id="config-editor" rows="32" spellcheck="false" placeholder="Choisissez un fichier à modifier…"></textarea>
        <div style="margin-top:.5rem;display:flex;gap:.5rem;align-items:center;">
          <button class="btn btn-green" onclick="saveConfigFile()">💾 ENREGISTRER LE FICHIER</button>
          <span style="font-size:.65rem;color:var(--text3);margin-left:.5rem;" id="config-save-msg"></span>
        </div>
      </div>

      <!-- ══════ SITE INFO PAGE ══════ -->
      <div class="page" id="page-siteinfo">
        <div class="section-head">ÉDITEUR DES INFOS DU SITE</div>
        <div class="editor-toolbar">
          <select class="file-select" id="json-file-sel" onchange="loadJsonFile()"></select>
          <button class="btn btn-blue" onclick="loadJsonFile()">↻ RECHARGER</button>
        </div>
        <div class="tab-bar">
          <div class="tab active" onclick="switchJsonTab('form',this)">FORMULAIRE</div>
          <div class="tab" onclick="switchJsonTab('raw',this)">JSON BRUT</div>
        </div>
        <div class="tab-pane active" id="json-form-pane">
          <div id="json-form-fields" style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;"></div>
          <div style="margin-top:.8rem;display:flex;gap:.5rem;">
            <button class="btn btn-green" onclick="saveJsonForm()">💾 ENREGISTRER LES MODIFICATIONS</button>
            <span id="json-save-msg" style="font-size:.65rem;color:var(--text3);margin-left:.5rem;"></span>
          </div>
        </div>
        <div class="tab-pane" id="json-raw-pane">
          <textarea class="code" id="json-raw-editor" rows="25" spellcheck="false"></textarea>
          <div style="margin-top:.5rem;">
            <button class="btn btn-green" onclick="saveJsonRaw()">💾 ENREGISTRER LE JSON BRUT</button>
          </div>
        </div>
      </div>

      <!-- ══════ MARKERS PAGE ══════ -->
      <div class="page" id="page-markers">
        <div class="section-head">ÉDITEUR DES MARQUEURS DE FRÉQUENCE</div>
        <div style="margin-bottom:.8rem;display:flex;gap:.5rem;flex-wrap:wrap;">
          <button class="btn btn-green" onclick="addMarker()">+ AJOUTER UN MARQUEUR</button>
          <button class="btn btn-amber" onclick="saveMarkers()">💾 ENREGISTRER LES MARQUEURS</button>
          <button class="btn btn-blue" onclick="loadMarkers()">↻ RECHARGER</button>
          <span id="markers-save-msg" style="font-size:.65rem;color:var(--text3);margin:auto 0;"></span>
        </div>
        <div class="card" style="overflow-x:auto;">
          <table class="markers">
            <thead>
              <tr>
                <th>FRÉQUENCE (Hz)</th><th>NOM</th><th>MODE</th><th>COULEUR</th><th>ACTION</th>
              </tr>
            </thead>
            <tbody id="markers-tbody"></tbody>
          </table>
        </div>
        <div style="margin-top:.8rem;">
          <div class="card-header"><div class="dot"></div>APERÇU DU JSON BRUT</div>
          <textarea class="code" id="markers-raw" rows="10" readonly style="opacity:.7;"></textarea>
        </div>
      </div>

      <!-- ══════ SPOT REPORTING PAGE ══════ -->
      <div class="page" id="page-reporting">
        <div class="section-head">ENVOI DES SPOTS &#183; AUTORUN</div>

        <div class="card" style="margin-bottom:.9rem;">
          <div class="card-header"><div class="dot" id="ar-dot"></div><span id="ar-state">&#8212;</span></div>
          <div id="ar-status" style="font-size:.7rem;color:var(--text2);line-height:1.7;">&#8212;</div>
          <div style="margin-top:.8rem;display:flex;gap:.5rem;flex-wrap:wrap;">
            <button class="btn btn-green" onclick="autorunStart()">&#9654; DÉMARRER</button>
            <button class="btn btn-red" onclick="autorunStop()">&#9632; ARRÊT</button>
            <button class="btn btn-amber" onclick="autorunSave()">&#128190; ENREGISTRER LA CONFIG</button>
            <button class="btn btn-blue" onclick="autorunLoad()">&#8635; RECHARGER</button>
            <button class="btn btn-red" onclick="autorunFreeAll()">&#10005; LIBÉRER TOUS LES SLOTS</button>
            <span id="ar-msg" style="font-size:.65rem;color:var(--text3);margin:auto 0;"></span>
          </div>
        </div>

        <!-- Per-decoder spot tally.  The aggregate PSK Reporter figure above
             cannot separate FT8, FT4 and JS8 (they share one upload queue), so
             the daemon counts them separately and reports them here. -->
        <div class="card" style="margin-bottom:.9rem;">
          <div class="card-header"><div class="dot"></div>SPOTS ENVOYÉS PAR DÉCODEUR</div>
          <div class="grid grid-4" id="ar-spots-grid">
            <div class="ar-spot-tile">
              <div class="ar-spot-mode">FT8</div>
              <div class="ar-spot-count" id="ar-up-ft8">&#8212;</div>
              <div class="ar-spot-sub" id="ar-sub-ft8">&#8212;</div>
            </div>
            <div class="ar-spot-tile">
              <div class="ar-spot-mode">FT4</div>
              <div class="ar-spot-count" id="ar-up-ft4">&#8212;</div>
              <div class="ar-spot-sub" id="ar-sub-ft4">&#8212;</div>
            </div>
            <div class="ar-spot-tile">
              <div class="ar-spot-mode">JS8</div>
              <div class="ar-spot-count" id="ar-up-js8">&#8212;</div>
              <div class="ar-spot-sub" id="ar-sub-js8">&#8212;</div>
            </div>
            <div class="ar-spot-tile">
              <div class="ar-spot-mode">WSPR</div>
              <div class="ar-spot-count" id="ar-up-wspr">&#8212;</div>
              <div class="ar-spot-sub" id="ar-sub-wspr">&#8212;</div>
            </div>
          </div>
          <p style="color:var(--text3);font-size:.65rem;margin-top:.6rem;" id="ar-spots-note">
            Compteurs depuis le dernier démarrage du démon &#8212; Arrêt/Démarrage les remet à zéro.</p>
        </div>

        <div class="card" style="margin-bottom:.9rem;">
          <div class="card-header"><div class="dot"></div>IDENTITÉ DE LA STATION</div>
          <p style="color:var(--text2);font-size:.68rem;margin:.2rem 0 .7rem;">
            Les spots sont envoyés sous cet indicatif/locator. Valeurs par défaut issues des Infos du site (siteSysop /
            siteGridSquare, 6 premiers caractères). Modifiable &#8212; mettez votre propre indicatif avant d'activer l'envoi.</p>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;">
            <div class="field"><label>INDICATIF</label><input id="ar-call" type="text" placeholder="SV1BTL"></div>
            <div class="field"><label>LOCATOR (6 CAR.)</label><input id="ar-grid" type="text" maxlength="6" placeholder="KM17VX"></div>
          </div>
        </div>

        <div class="card" style="margin-bottom:.9rem;">
          <div class="card-header"><div class="dot"></div>DESTINATIONS D'ENVOI</div>
          <label style="display:flex;align-items:center;gap:.5rem;font-size:.72rem;margin:.4rem 0;">
            <input type="checkbox" id="ar-psk"> PSK Reporter <span style="color:var(--text3)">&#8212; FT8 &amp; FT4 &#8594; report.pskreporter.info</span></label>
          <label style="display:flex;align-items:center;gap:.5rem;font-size:.72rem;margin:.4rem 0;">
            <input type="checkbox" id="ar-wspr"> wsprnet <span style="color:var(--text3)">&#8212; WSPR &#8594; wsprnet.org</span></label>
          <p style="color:var(--amber);font-size:.65rem;margin-top:.5rem;">L'envoi est DÉSACTIVÉ par défaut. Rien n'est envoyé tant que vous n'avez pas coché une destination, enregistré puis démarré.</p>
        </div>

        <div class="card">
          <div class="card-header"><div class="dot"></div>BANDES &amp; MODES
            <span style="margin-left:auto;font-size:.62rem;color:var(--text3);">SLOTS MAX
              <input id="ar-max" type="number" min="1" max="64" onchange="autorunCount()" style="width:3.4rem;margin-left:.3rem;background:#071007;border:1px solid var(--border);color:var(--green);padding:.15rem;"></span>
          </div>
          <div style="overflow-x:auto;"><table class="markers" id="ar-matrix"></table></div>
          <p style="color:var(--text3);font-size:.62rem;margin-top:.5rem;" id="ar-count">&#8212;</p>
          <p style="color:var(--text3);font-size:.62rem;margin-top:.3rem;display:none;" id="ar-slot-note">
            Le nombre à côté de chaque case est le total <b>cumulé</b> de spots envoyés pour cette bande+mode, conservé entre
            les redémarrages. <span style="color:var(--amber)">En ambre avec un point (&#183;123)</span> : décodages pas
            encore envoyés &#8212; normal entre deux envois ; un simple
            <span style="color:var(--amber)">0</span> : activé mais rien décodé pour l'instant (le WSPR peut prendre
            plusieurs minutes &#8212; cycle de 2 minutes). Survolez pour le détail.</p>
        </div>
      </div>

      <!-- ══════ LOG VIEWER PAGE ══════ -->
      <div class="page" id="page-logs">
        <div class="section-head">JOURNAUX</div>
        <div style="display:flex;gap:.5rem;margin-bottom:.7rem;flex-wrap:wrap;">
          <button class="btn btn-blue" onclick="loadCurrentLogTab()">↻ ACTUALISER</button>
          <button class="btn btn-green" id="auto-refresh-btn" onclick="toggleAutoRefresh()">⏵ ACTUALISATION AUTO</button>
          <button class="btn btn-red" onclick="clearLogView()">✕ VIDER LES JOURNAUX</button>
        </div>
        <div class="tab-bar" style="margin-bottom:.6rem;">
          <div class="tab log-tab active" data-log-name="logwebsdr.txt" onclick="switchLogTab('logwebsdr.txt', this)">LOGWEBSDR</div>
          <div class="tab log-tab" data-log-name="spectrumserver.log" onclick="switchLogTab('spectrumserver.log', this)">SPECTRUMSERVER</div>
          <div class="tab log-tab" data-log-name="admin.log" onclick="switchLogTab('admin.log', this)">ADMIN</div>
          <div class="tab log-tab" data-log-name="rade.log" onclick="switchLogTab('rade.log', this)">RADE</div>
          <div class="tab log-tab" data-log-name="crash.log" onclick="switchLogTab('crash.log', this)">CRASH</div>
          <div class="tab log-tab" data-log-name="autorun.log" onclick="switchLogTab('autorun.log', this)">AUTORUN</div>
          <div class="tab log-tab" data-log-name="proxy.log" onclick="switchLogTab('proxy.log', this)">PROXY</div>
        </div>
        <div class="tab-pane log-tab-pane active" id="log-pane-logwebsdr">
          <div class="log-box" id="main-log-logwebsdr" style="height:550px;"></div>
        </div>
        <div class="tab-pane log-tab-pane" id="log-pane-spectrumserver">
          <div class="log-box" id="main-log-spectrumserver" style="height:550px;"></div>
        </div>
        <div class="tab-pane log-tab-pane" id="log-pane-admin">
          <div class="log-box" id="main-log-admin" style="height:550px;"></div>
        </div>
        <div class="tab-pane log-tab-pane" id="log-pane-rade">
          <div class="log-box" id="main-log-rade" style="height:550px;"></div>
        </div>
        <div class="tab-pane log-tab-pane" id="log-pane-crash">
          <div class="log-box" id="main-log-crash" style="height:550px;"></div>
        </div>
        <div class="tab-pane log-tab-pane" id="log-pane-autorun">
          <div class="log-box" id="main-log-autorun" style="height:550px;"></div>
        </div>
        <div class="tab-pane log-tab-pane" id="log-pane-proxy">
          <div class="log-box" id="main-log-proxy" style="height:550px;"></div>
        </div>
      </div>

      <!-- ══════ CHAT HISTORY PAGE ══════ -->
      <div class="page" id="page-chat">
        <div class="section-head">HISTORIQUE DU CHAT</div>
        <div style="display:flex;gap:.5rem;margin-bottom:.7rem;">
          <button class="btn btn-blue" onclick="loadChat()">↻ ACTUALISER</button>
        </div>
        <div class="chat-log" id="chat-log">Chargement…</div>
      </div>

      <!-- ══════ SETTINGS PAGE ══════ -->
      <!-- Pages ajoutées par admin_extras (contenu rendu par /admin/extras.js) -->
      <div class="page" id="page-map"><div id="x-map"></div></div>
      <div class="page" id="page-signal"><div id="x-signal"></div></div>
      <div class="page" id="page-health"><div id="x-health"></div></div>
      <div class="page" id="page-update"><div id="x-update"></div></div>
      <div class="page" id="page-backup"><div id="x-backup"></div></div>

      <div class="page" id="page-settings">
        <div class="section-head">RÉGLAGES ADMIN</div>
        <div class="grid grid-2" style="margin-bottom:1rem;">
          <div class="card">
            <div class="card-header"><div class="dot"></div>CHANGER LE MOT DE PASSE</div>
            <form onsubmit="changePassword(event)">
              <div style="margin-bottom:.6rem;">
                <label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">MOT DE PASSE ACTUEL</label>
                <input type="password" id="old-pwd" style="width:100%;">
              </div>
              <div style="margin-bottom:.6rem;">
                <label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">NOUVEAU MOT DE PASSE</label>
                <input type="password" id="new-pwd" style="width:100%;">
              </div>
              <div style="margin-bottom:.8rem;">
                <label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">CONFIRMER LE NOUVEAU MOT DE PASSE</label>
                <input type="password" id="new-pwd2" style="width:100%;">
              </div>
              <button type="submit" class="btn btn-green">🔑 MODIFIER LE MOT DE PASSE</button>
            </form>
          </div>
          <div class="card">
            <div class="card-header"><div class="dot"></div>RÉPERTOIRE DE BASE SDR</div>
            <p style="color:var(--text2);font-size:.75rem;margin-bottom:.6rem;">Chemin de l'installation PhantomSDR-Plus :</p>
            <input type="text" id="sdr-dir" style="width:100%;margin-bottom:1rem;" placeholder="/chemin/vers/PhantomSDR-Plus">
            <div class="card-header" style="margin:.4rem 0;">
              <div class="dot" style="background:var(--blue);box-shadow:0 0 6px var(--blue);"></div>
              PORT SPECTRUMSERVER (INTERNE)
            </div>
            <p style="color:var(--text2);font-size:.7rem;margin-bottom:.4rem;">Le port sur lequel spectrumserver écoute lui-même (port de la section [server] de sa config). Ce n'est pas le port public des auditeurs quand proxy.py est devant — n'indiquez jamais le port du proxy ici.</p>
            <input type="number" id="public-port" style="width:100%;margin-bottom:1rem;" placeholder="8900" min="1" max="65535">
            <div class="card-header" style="margin:.4rem 0;">
              <div class="dot" style="background:var(--green);box-shadow:0 0 6px var(--green);"></div>
              SCRIPT DE DÉMARRAGE PAR DÉFAUT
            </div>
            <select class="script-select" id="default-start-sel" style="width:100%;margin-bottom:.8rem;"></select>
            <div class="card-header" style="margin:.4rem 0;">
              <div class="dot" style="background:var(--red);box-shadow:0 0 6px var(--red);"></div>
              SCRIPT D'ARRÊT PAR DÉFAUT
            </div>
            <select class="script-select" id="default-stop-sel" style="width:100%;margin-bottom:.8rem;"></select>
            <button class="btn btn-amber" onclick="saveSettings()">💾 ENREGISTRER LES RÉGLAGES</button>
            <div id="settings-msg" style="margin-top:.5rem;font-size:.7rem;color:var(--text3);"></div>
          </div>
        </div>

        <!-- ══════ GARDE THERMIQUE SETTINGS ══════ -->
        <div class="section-head">GARDE THERMIQUE</div>
        <div class="card" style="margin-bottom:1rem;">
          <p style="color:var(--text2);font-size:.75rem;margin-bottom:.6rem;">
            Protège la machine quand le CPU surchauffe. Un champ de température vide signifie
            <b>auto</b> — calculé depuis le seuil critique propre à cette machine
            (<span id="tg-cfg-crit">--</span>), donc juste pour Intel, AMD comme Pi.
            Chaque palier doit durer son temps de maintien : un pic bref ne déclenche rien.
            <b>Commencez en mode = log</b> quelque temps et lisez les résultats dans le journal CRASH.
          </p>
          <div class="field-row" style="margin-bottom:.7rem;">
            <div>
              <label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">MODE</label>
              <select id="tg-cfg-mode" style="width:100%;">
                <option value="log">log — enregistre seulement, aucune action (défaut sûr)</option>
                <option value="throttle">throttle — baisse la fréquence CPU, sans jamais arrêter</option>
                <option value="stop">stop — bride, puis arrête le serveur</option>
                <option value="stop+restart">stop+restart — et redémarre une fois refroidi</option>
              </select>
            </div>
            <div>
              <label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">ACTIVÉ</label>
              <select id="tg-cfg-enabled" style="width:100%;">
                <option value="1">yes</option><option value="0">no</option>
              </select>
            </div>
          </div>
          <div class="grid grid-4" style="gap:.6rem;margin-bottom:.7rem;">
            <div><label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">ALERTE °C</label>
                 <input type="number" step="0.5" id="tg-cfg-warn" style="width:100%;" placeholder="auto"></div>
            <div><label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">BRIDAGE °C</label>
                 <input type="number" step="0.5" id="tg-cfg-throttle" style="width:100%;" placeholder="auto"></div>
            <div><label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">ARRÊT °C</label>
                 <input type="number" step="0.5" id="tg-cfg-stop" style="width:100%;" placeholder="auto"></div>
            <div><label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">REPRISE °C</label>
                 <input type="number" step="0.5" id="tg-cfg-resume" style="width:100%;" placeholder="auto"></div>
          </div>
          <div class="grid grid-4" style="gap:.6rem;margin-bottom:.7rem;">
            <div><label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">MAINTIEN ARRÊT (s)</label>
                 <input type="number" id="tg-cfg-sustain" style="width:100%;" placeholder="60"></div>
            <div><label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">MAINTIEN ALERTE (s)</label>
                 <input type="number" id="tg-cfg-warnsustain" style="width:100%;" placeholder="30"></div>
            <div><label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">MAINTIEN REPRISE (s)</label>
                 <input type="number" id="tg-cfg-resumes" style="width:100%;" placeholder="300"></div>
            <div><label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">ARRÊTS MAX / HEURE</label>
                 <input type="number" id="tg-cfg-maxstops" style="width:100%;" placeholder="2"></div>
          </div>
          <div style="margin-bottom:.7rem;">
            <label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">
              TEMPÉRATURE DE TEST °C — injecte une fausse mesure pour vérifier toute la chaîne, vide = désactivé</label>
            <input type="number" step="0.5" id="tg-cfg-test" style="width:100%;" placeholder="vide = capteur réel">
          </div>
          <button class="btn btn-amber" onclick="saveThermal()">💾 ENREGISTRER LA GARDE THERMIQUE</button>
          <div id="tg-cfg-msg" style="margin-top:.5rem;font-size:.7rem;color:var(--text3);"></div>
        </div>
      </div>

      <!-- ══════ USERS PAGE ══════ -->
      <!-- ══════ GRAPHS PAGE ══════ -->
      <div class="page" id="page-graphs">
        <div class="section-head">GRAPHIQUES SYSTÈME</div>
        <div style="display:flex;gap:.5rem;margin-bottom:.8rem;flex-wrap:wrap;align-items:center;">
          <button class="btn btn-green graph-range active" data-range="900"  onclick="graphSetRange(900,this)">15 MIN</button>
          <button class="btn graph-range" data-range="3600" onclick="graphSetRange(3600,this)">1 HEURE</button>
          <button class="btn graph-range" data-range="14400" onclick="graphSetRange(14400,this)">4 HEURES</button>
          <button class="btn graph-range" data-range="43200" onclick="graphSetRange(43200,this)">12 HEURES</button>
          <button class="btn graph-range" data-range="86400" onclick="graphSetRange(86400,this)">24 HEURES</button>
          <span style="font-size:.78rem;color:var(--text3);margin-left:.4rem;" id="graph-info-label"></span>
        </div>

        <!-- Current values.  Each graph panel below is titled and scaled on its
             own, so these tiles carry the exact reading the curves only imply. -->
        <div class="grid grid-4" style="margin-bottom:1rem;">
          <div class="card">
            <div class="card-header"><div class="dot"></div>FRÉQUENCE CPU</div>
            <div class="stat-val" id="g-cur-freq">--</div>
            <div class="stat-label" id="g-sub-freq">GHz en moyenne</div>
          </div>
          <div class="card">
            <div class="card-header"><div class="dot"></div>CHARGE CPU</div>
            <div class="stat-val" id="g-cur-load">--</div>
            <div class="stat-label">percent</div>
          </div>
          <div class="card">
            <div class="card-header"><div class="dot"></div>TEMPÉRATURE CPU</div>
            <div class="stat-val" id="g-cur-temp">--</div>
            <div class="stat-label" id="g-sub-temp">degrés C</div>
          </div>
          <div class="card">
            <div class="card-header"><div class="dot"></div>AUDITEURS EN LIGNE</div>
            <div class="stat-val" id="g-cur-users">--</div>
            <div class="stat-label">connectés maintenant</div>
          </div>
        </div>

        <div class="card" style="padding:.6rem .4rem .2rem .4rem;">
          <!-- Four stacked panels sharing one time axis.  Deliberately NOT one
               chart with several y-scales: GHz, %, °C and a head-count have no
               common scale, and overlaying them would invent relationships that
               are not in the data. -->
          <div id="graph-empty" style="display:none;color:var(--text3);font-size:.72rem;text-align:center;padding:2rem .6rem;"></div>
          <canvas id="graph-canvas" style="width:100%;display:block;cursor:crosshair;"></canvas>
          <div id="graph-tooltip" style="display:none;position:absolute;z-index:50;pointer-events:none;
               background:#071007;border:1px solid var(--border);border-radius:3px;padding:.45rem .6rem;
               font-size:.8rem;line-height:1.5;color:var(--text);white-space:nowrap;box-shadow:0 4px 14px #000a;"></div>
        </div>
      </div>

      <div class="page" id="page-users">
        <div class="section-head">AUDITEURS CONNECTÉS</div>
        <div style="display:flex;gap:.5rem;margin-bottom:.8rem;flex-wrap:wrap;align-items:center;">
          <button class="btn btn-blue" onclick="loadUsers()">&#8635; ACTUALISER</button>
          <button class="btn btn-green" id="users-auto-btn" onclick="toggleUsersAutoRefresh()">&#9654; AUTO</button>
          <span style="font-size:.65rem;color:var(--text3);margin-left:.4rem;" id="users-info-label"></span>
        </div>
        <div id="users-error" style="display:none;background:rgba(255,64,64,.08);border:1px solid rgba(255,64,64,.3);border-radius:3px;color:var(--red);padding:.5rem .9rem;font-size:.72rem;margin-bottom:.6rem;"></div>
        <div class="card" style="overflow-x:auto;padding:0;">
          <table style="width:100%;border-collapse:collapse;font-size:.75rem;">
            <thead>
              <tr>
                <th style="color:var(--text3);font-weight:normal;letter-spacing:.1em;padding:.4rem .6rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">IP / LIEU</th>
                <th id="users-rx-th" style="display:none;color:var(--text3);font-weight:normal;letter-spacing:.1em;padding:.4rem .6rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">RÉCEPTEUR</th>
                <th style="color:var(--text3);font-weight:normal;letter-spacing:.1em;padding:.4rem .6rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">FRÉQUENCE</th>
                <th style="color:var(--text3);font-weight:normal;letter-spacing:.1em;padding:.4rem .6rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">MODE</th>
                <th style="color:var(--text3);font-weight:normal;letter-spacing:.1em;padding:.4rem .6rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">DURÉE</th>
                <th style="color:var(--text3);font-weight:normal;letter-spacing:.1em;padding:.4rem .6rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">ACTION</th>
              </tr>
            </thead>
            <tbody id="users-tbody">
              <tr><td colspan="5" style="color:var(--text3);text-align:center;padding:.8rem;">Cliquez sur ACTUALISER pour charger</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ══════ WATERFALL MESSAGE PAGE ══════ -->
      <div class="page" id="page-listeners">
        <div class="section-head">ANALYSE AUDITEURS — EN DIRECT</div>
        <div style="font-size:.65rem;color:var(--text3);margin-bottom:.6rem;">Données privées, visibles uniquement ici. Détail conservé 90 jours, résumés quotidiens sans limite. Lieu, FAI et type de réseau : ip-api.com (VPN/proxy, datacenter, mobile).</div>
        <div style="display:flex;gap:.5rem;margin-bottom:.8rem;flex-wrap:wrap;align-items:center;">
          <button class="btn btn-blue" onclick="liLoadAll()">&#8635; ACTUALISER</button>
          <button class="btn btn-green" id="li-auto-btn" onclick="liToggleAuto()">&#9654; AUTO</button>
          <span style="font-size:.65rem;color:var(--text3);" id="li-live-label"></span>
        </div>
        <div class="card" style="overflow-x:auto;padding:0;margin-bottom:1.2rem;">
          <table style="width:100%;border-collapse:collapse;font-size:.72rem;">
            <thead><tr><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">IP</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">LIEU</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">FAI / RÉSEAU</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">TYPE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">FRÉQ.</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">MODE / BANDE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">DÉCODEUR</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">NAVIGATEUR</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">LANGUE / FUSEAU</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">PROVENANCE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">DEPUIS</th></tr></thead>
            <tbody id="li-live-tbody"><tr><td colspan="11" style="color:var(--text3);text-align:center;padding:.8rem;">Chargement…</td></tr></tbody>
          </table>
        </div>
        <div class="section-head">STATISTIQUES</div>
        <div style="display:flex;gap:.4rem;margin-bottom:.8rem;flex-wrap:wrap;" id="li-period-btns">
          <button class="btn btn-blue" onclick="liStats(1,this)">AUJOURD'HUI</button>
          <button class="btn" onclick="liStats(7,this)">7 J</button>
          <button class="btn" onclick="liStats(30,this)">30 J</button>
          <button class="btn" onclick="liStats(90,this)">90 J</button>
          <button class="btn" onclick="liStats(365,this)">1 AN</button>
          <button class="btn" onclick="liStats(3650,this)">TOUT</button>
        </div>
        <div id="li-kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.5rem;margin-bottom:.8rem;"></div>
        <div id="li-days" class="card" style="margin-bottom:.8rem;"></div>
        <div id="li-tops" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.6rem;margin-bottom:1.2rem;"></div>
        <div class="section-head">SESSIONS DES 7 DERNIERS JOURS</div>
        <div class="card" style="overflow-x:auto;padding:0;">
          <table style="width:100%;border-collapse:collapse;font-size:.7rem;">
            <thead><tr><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">DÉBUT (UTC)</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">DURÉE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">LIEU</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">FAI</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">TYPE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">BANDES</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">MODES</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">DÉCODEURS</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">NAV.</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">PROVENANCE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">ID</th></tr></thead>
            <tbody id="li-sess-tbody"></tbody>
          </table>
        </div>
        <div class="section-head" style="margin-top:1.2rem;">SÉCURITÉ — TENTATIVES ANORMALES</div>
        <div style="font-size:.65rem;color:var(--text3);margin-bottom:.6rem;">Tout le trafic web passe par le proxy : recherches de failles, remontées de dossiers, méthodes inhabituelles, actions interdites, rafales de 404, échecs de connexion au panneau (verrouillage 30 min après 5 échecs en 15 min). Les IP bannies reçoivent un refus sur tout le site et sont coupées de l'audio.</div>
        <div style="display:flex;gap:.4rem;margin-bottom:.8rem;flex-wrap:wrap;align-items:center;" id="sec-period-btns">
          <button class="btn" onclick="secLoad(1,this)">AUJOURD'HUI</button>
          <button class="btn btn-blue" onclick="secLoad(7,this)">7 J</button>
          <button class="btn" onclick="secLoad(30,this)">30 J</button>
          <button class="btn" onclick="secLoad(90,this)">90 J</button>
          <span style="flex:1"></span>
          <button class="btn btn-amber" onclick="secClear()" title="Efface tout le journal des tentatives ; les IP bannies restent bannies">🗑 VIDER LE JOURNAL</button>
        </div>
        <div class="card" style="margin-bottom:.8rem;">
          <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.4rem;">
            <span style="font-size:.65rem;color:var(--text3);letter-spacing:.1em;">LISTE DE BANNISSEMENT</span>
            <span id="sec-ban-count" style="font-size:.65rem;color:var(--text2);"></span>
            <span style="flex:1"></span>
            <input id="sec-ban-filter" placeholder="Filtrer…" style="width:9rem;" oninput="secRenderBans()">
            <button class="btn btn-amber" onclick="secKiwiImport()" title="Importer (ou mettre à jour) la liste noire officielle des KiwiSDR : robots, hébergeurs abusifs, VPN. Les entrées gardent le motif « KiwiSDR » et sont remplacées à chaque import ; votre IP et la liste blanche restent protégées.">⬇ LISTE KIWISDR</button>
            <a class="btn btn-blue" href="/admin/api/security/banlist.txt" title="Télécharger la liste (réimportable)">⬇ EXPORTER</a>
          </div>
          <div style="display:grid;grid-template-columns:1fr auto;gap:.5rem;align-items:start;margin-bottom:.5rem;">
            <textarea id="sec-ban-bulk" rows="3" placeholder="Une IP ou une plage par ligne (ex. 203.0.113.7 ou 198.51.100.0/24) — # pour un commentaire. On peut coller une liste entière." style="width:100%;font-family:monospace;font-size:.68rem;"></textarea>
            <div style="display:flex;flex-direction:column;gap:.3rem;">
              <input id="sec-ban-reason" placeholder="Motif (facultatif)" style="width:11rem;">
              <div style="display:flex;gap:.3rem;">
                <button class="btn" style="color:var(--red);border-color:var(--red);" onclick="secBanBulk(24)">BANNIR 24 H</button>
                <button class="btn" style="color:var(--red);border-color:var(--red);" onclick="secBanBulk(0)">DÉFINITIF</button>
              </div>
            </div>
          </div>
          <div id="sec-bans" style="max-height:16rem;overflow-y:auto;"></div>
        </div>
        <div class="card" style="margin-bottom:.8rem;">
          <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.4rem;">
            <span style="font-size:.65rem;color:var(--text3);letter-spacing:.1em;">LISTE BLANCHE</span>
            <span id="sec-allow-count" style="font-size:.65rem;color:var(--text2);"></span>
            <span style="flex:1"></span>
            <span style="font-size:.65rem;color:var(--text2);">Votre IP actuelle : <b id="sec-myip" style="font-family:monospace;color:var(--green);">—</b></span>
            <button class="btn btn-blue" onclick="secAllowMe()" title="Ajouter votre IP actuelle à la liste blanche">+ MON IP</button>
          </div>
          <div style="font-size:.62rem;color:var(--text3);margin-bottom:.4rem;">Ces adresses ne sont jamais bloquées, même si elles tombent dans une plage bannie (une liste importée, par exemple). Sont aussi protégés automatiquement : le réseau local et toute IP qui s'est connectée avec succès au panneau d'administration dans les 90 derniers jours. Le panneau refuse de bannir une plage qui contient votre propre IP.</div>
          <div style="display:grid;grid-template-columns:1fr auto;gap:.5rem;align-items:start;margin-bottom:.5rem;">
            <textarea id="sec-allow-bulk" rows="2" placeholder="Une IP ou une plage par ligne — # pour un commentaire" style="width:100%;font-family:monospace;font-size:.68rem;"></textarea>
            <div style="display:flex;flex-direction:column;gap:.3rem;">
              <input id="sec-allow-note" placeholder="Note (ex. indicatif)" style="width:11rem;">
              <button class="btn" style="color:var(--green);border-color:var(--green);" onclick="secAllowBulk()">AJOUTER</button>
            </div>
          </div>
          <div id="sec-allow" style="max-height:10rem;overflow-y:auto;"></div>
        </div>
        <div id="sec-kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:.5rem;margin-bottom:.8rem;"></div>
        <div class="card" style="overflow-x:auto;padding:0;margin-bottom:.8rem;">
          <table style="width:100%;border-collapse:collapse;font-size:.7rem;">
            <thead><tr><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">DANGER</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">IP</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">REVERSE DNS</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">LIEU / FAI</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">TYPE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">ÉVÉNEMENTS</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">CATÉGORIES</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">EXEMPLES DE CHEMINS</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">DERNIER</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">ACTION</th></tr></thead>
            <tbody id="sec-ips-tbody"></tbody>
          </table>
        </div>
        <div class="card" style="overflow-x:auto;padding:0;">
          <table style="width:100%;border-collapse:collapse;font-size:.68rem;">
            <thead><tr><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">HEURE (UTC)</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">IP</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">CATÉGORIE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">REQUÊTE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">CODE</th><th style="color:var(--text3);font-weight:normal;letter-spacing:.08em;padding:.4rem .5rem;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap;">NAVIGATEUR / OUTIL</th></tr></thead>
            <tbody id="sec-ev-tbody"></tbody>
          </table>
        </div>
      </div>
      <div class="page" id="page-wfmsg">
        <div class="section-head">📢 MESSAGE SUR LE WATERFALL</div>
        <div class="grid grid-2">

          <div class="card">
            <div class="card-header">
              <div class="dot" style="background:var(--amber);box-shadow:0 0 6px var(--amber)"></div>
              RÉDACTION &amp; DIFFUSION
            </div>

            <div style="margin-bottom:.6rem;">
              <label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">MESSAGE (200 car. max)</label>
              <textarea id="wfmsg-text"
                style="width:100%;background:#030803;border:1px solid var(--border);
                       color:var(--text);font-family:'Share Tech Mono',monospace;
                       font-size:.85rem;padding:.5rem .7rem;border-radius:3px;
                       resize:vertical;height:80px;outline:none;transition:.15s;"
                placeholder="QRT dans 10 min — 73 de F1NSK !" maxlength="200"
                onfocus="this.style.borderColor='var(--amber)'"
                onblur="this.style.borderColor='var(--border)'"></textarea>
              <div id="wfmsg-charcount" style="font-size:.6rem;color:var(--text3);text-align:right;margin-top:.2rem;">0 / 200</div>
            </div>

            <div style="margin-bottom:.8rem;">
              <label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">COULEUR DU TEXTE</label>
              <select id="wfmsg-color"
                style="width:100%;background:#071207;border:1px solid var(--border);
                       color:var(--text);font-family:'Share Tech Mono',monospace;
                       font-size:.8rem;padding:.4rem .6rem;border-radius:2px;outline:none;">
                <option value="#ffffff">⬜ Blanc</option>
                <option value="#ffff00">🟡 Jaune</option>
                <option value="#00ffff">🩵 Cyan</option>
                <option value="#00ff41">🟢 Vert</option>
                <option value="#ffb000">🟠 Ambre</option>
              </select>
            </div>

            <div style="margin-bottom:.8rem;">
              <label style="font-size:.65rem;color:var(--text3);display:block;margin-bottom:.3rem;">DURÉE D'AFFICHAGE</label>
              <div style="display:flex;gap:.5rem;flex-wrap:wrap;">
                <select id="wfmsg-dur" onchange="document.getElementById('wfmsg-until').style.display = this.value==='custom' ? '' : 'none'"
                  style="flex:1;min-width:10rem;background:#071207;border:1px solid var(--border);
                         color:var(--text);font-family:'Share Tech Mono',monospace;
                         font-size:.8rem;padding:.4rem .6rem;border-radius:2px;outline:none;">
                  <option value="0">Jusqu'à effacement manuel</option>
                  <option value="1800">30 minutes</option>
                  <option value="3600">1 heure</option>
                  <option value="7200">2 heures</option>
                  <option value="21600">6 heures</option>
                  <option value="86400">24 heures</option>
                  <option value="custom">Jusqu'au… (date et heure)</option>
                </select>
                <input type="datetime-local" id="wfmsg-until" style="display:none;flex:1;min-width:12rem;background:#071207;border:1px solid var(--border);
                       color:var(--text);font-family:'Share Tech Mono',monospace;font-size:.8rem;padding:.35rem .5rem;border-radius:2px;color-scheme:dark;">
              </div>
            </div>

            <div style="display:flex;gap:.5rem;">
              <button class="btn btn-amber" onclick="sendWfMsg()" style="flex:1;">📢 DIFFUSER</button>
              <button class="btn btn-red" onclick="clearWfMsg()">✕ EFFACER</button>
            </div>
            <div id="wfmsg-status" style="margin-top:.6rem;font-size:.7rem;color:var(--text3);min-height:1.4em;padding:.2rem 0;"></div>
          </div>

          <div class="card">
            <div class="card-header"><div class="dot"></div>ÉTAT &amp; NOTES</div>
            <div style="font-size:.75rem;color:var(--text2);line-height:2;">
              <p>Le message s'affiche dans un <span style="color:var(--green)">bandeau sombre fixe en haut du waterfall</span> pour tous les auditeurs connectés.</p>
              <br>
              <p>&#9679; Reste visible jusqu'à un clic sur <strong style="color:var(--red)">EFFACER</strong>, ou jusqu'à l'heure de fin choisie (DURÉE D'AFFICHAGE).</p>
              <p>&#9679; Les navigateurs interrogent toutes les 10 s — le message apparaît dans les 10 s après DIFFUSER.</p>
              <p>&#9679; Disparaît dans les 10 s après EFFACER.</p>
              <p>&#9679; Les auditeurs connectés après EFFACER ne le voient jamais.</p>
              <p>&#9679; Aucun rechargement de page nécessaire, ni d'un côté ni de l'autre.</p>
            </div>

            <div style="margin-top:1rem;padding:.6rem .8rem;border-radius:3px;border:1px solid var(--border);background:#030803;">
              <div style="font-size:.6rem;color:var(--text3);letter-spacing:.15em;margin-bottom:.4rem;">MESSAGE ACTUELLEMENT AFFICHÉ</div>
              <div id="wfmsg-active" style="font-size:.85rem;color:var(--text3);word-break:break-word;min-height:1.4em;">—</div>
            </div>

            <div style="margin-top:.8rem;display:flex;gap:.5rem;">
              <button class="btn btn-blue" onclick="loadWfMsgStatus()" style="flex:1;">↻ ACTUALISER L'ÉTAT</button>
            </div>
          </div>

        </div>
      </div>
      <!-- /WATERFALL MESSAGE PAGE -->

    </div><!-- /content -->
  </div><!-- /main -->
</div><!-- /layout -->

<!-- Mobile bottom navigation bar -->
<nav class="bottom-nav" id="bottom-nav">
  <a href="#" onclick="showPage('dashboard',this);return false;" class="active" data-page="dashboard">
    <span class="bi">⬡</span><span>ACCUEIL</span>
  </a>
  <a href="#" onclick="showPage('config',this);return false;" data-page="config">
    <span class="bi">⚙</span><span>CONFIG</span>
  </a>
  <a href="#" onclick="showPage('markers',this);return false;" data-page="markers">
    <span class="bi">◉</span><span>MARQUEURS</span>
  </a>
  <a href="#" onclick="showPage('logs',this);return false;" data-page="logs">
    <span class="bi">▤</span><span>JOURNAUX</span>
  </a>
  <a href="#" onclick="showPage('graphs',this);return false;" data-page="graphs">
    <span class="bi">📈</span><span>Graphiques</span>
  </a>
  <a href="#" onclick="showPage('users',this);return false;" data-page="users">
    <span class="bi">👥</span><span>AUDITEURS</span>
  </a>
  <a href="#" onclick="showPage('wfmsg',this);return false;" data-page="wfmsg">
    <span class="bi">📢</span><span>MSG</span>
  </a>
  <a href="#" onclick="showPage('settings',this);return false;" data-page="settings">
    <span class="bi">◧</span><span>PLUS</span>
  </a>
</nav>

<div id="toast"></div>

<script>
// ─── State ──────────────────────────────────────────────────────────────────
let currentPage = 'dashboard';
let autoRefresh = false;
let autoRefreshTimer = null;
let statusTimer = null;
let currentLogTab = 'logwebsdr.txt';

const LOG_TAB_TARGETS = {
  'logwebsdr.txt': 'main-log-logwebsdr',
  'spectrumserver.log': 'main-log-spectrumserver',
  'admin.log': 'main-log-admin',
  'rade.log': 'main-log-rade',
  'crash.log': 'main-log-crash',
  'autorun.log': 'main-log-autorun',
  'proxy.log': 'main-log-proxy',
};

const LOG_TAB_PANES = {
  'logwebsdr.txt': 'log-pane-logwebsdr',
  'spectrumserver.log': 'log-pane-spectrumserver',
  'admin.log': 'log-pane-admin',
  'rade.log': 'log-pane-rade',
  'crash.log': 'log-pane-crash',
  'autorun.log': 'log-pane-autorun',
  'proxy.log': 'log-pane-proxy',
};

// ─── Page navigation ────────────────────────────────────────────────────────
// ─── Analyse auditeurs (statistiques privées) ───────────────────────────────
let liAutoTimer = null, liDays = 1;
const LI_NET = {vpn:['VPN/PROXY','var(--red)'], datacenter:['DATACENTER','var(--amber)'],
  mobile:['MOBILE','var(--blue)'], fixe:['FIXE','var(--green)'], local:['LOCAL','var(--text3)'], '?':['?','var(--text3)']};
function liEsc(v){ return String(v==null?'':v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function liFlag(cc){ if(!cc||cc.length!==2) return ''; return String.fromCodePoint(...[...cc.toUpperCase()].map(c => 0x1F1E6 + c.charCodeAt(0) - 65)); }
function liBadge(n){ const b = LI_NET[n] || LI_NET['?']; return `<span style="border:1px solid ${b[1]};color:${b[1]};border-radius:3px;padding:0 .3rem;font-size:.62rem;white-space:nowrap;">${b[0]}</span>`; }
function liDur(s){ s = +s||0; const h = Math.floor(s/3600), m = Math.floor(s%3600/60); return h ? `${h} h ${String(m).padStart(2,'0')}` : `${m} min`; }
const liTd = 'style="padding:.35rem .5rem;border-bottom:1px solid var(--border);vertical-align:top;"';
async function liLoadAll(){ liLive(); liStats(liDays); liSessions(); secLoad(secDays); }
function liToggleAuto(){
  const b = document.getElementById('li-auto-btn');
  if (liAutoTimer){ clearInterval(liAutoTimer); liAutoTimer = null; b.innerHTML = '&#9654; AUTO'; }
  else { liAutoTimer = setInterval(() => { if (currentPage === 'listeners') liLive(); }, 10000); b.innerHTML = '&#9632; STOP'; liLive(); }
}
async function liLive(){
  const tb = document.getElementById('li-live-tbody');
  try {
    const d = await (await fetch('/admin/api/listeners/live', {cache:'no-store'})).json();
    const u = d.users || [];
    document.getElementById('li-live-label').textContent = `${u.length} auditeur(s) — ${new Date().toLocaleTimeString('fr-FR')}`;
    if (!u.length){ tb.innerHTML = `<tr><td colspan="11" ${liTd} style="text-align:center;color:var(--text3);">Aucun auditeur connecté</td></tr>`; return; }
    tb.innerHTML = u.map(x => `<tr>
      <td ${liTd}><span style="font-family:monospace;">${liEsc(x.ip)}</span>${x.returning?'<br><span style="color:var(--green);font-size:.6rem;">FIDÈLE</span>':'<br><span style="color:var(--amber);font-size:.6rem;">NOUVEAU</span>'}</td>
      <td ${liTd}>${liFlag(x.cc)} ${liEsc(x.city)}<br><span style="color:var(--text3);">${liEsc(x.region)}${x.region?', ':''}${liEsc(x.country)}</span>${x.lat!=null?`<br><a href="https://www.openstreetmap.org/?mlat=${x.lat}&mlon=${x.lon}&zoom=9" target="_blank" style="font-size:.6rem;color:var(--blue);">carte ≈</a>`:''}</td>
      <td ${liTd}>${liEsc(x.isp)}<br><span style="color:var(--text3);">${liEsc(x.as)}</span>${x.rdns?`<br><span style="color:var(--blue);font-family:monospace;font-size:.62rem;">${liEsc(x.rdns)}</span>`:''}</td>
      <td ${liTd}>${liBadge(x.net)}${x.https?'<br><span style="font-size:.6rem;color:var(--green);">HTTPS</span>':'<br><span style="font-size:.6rem;color:var(--text3);">http</span>'}</td>
      <td ${liTd}>${x.freq_khz!=null?(+x.freq_khz).toFixed(2)+' kHz':''}</td>
      <td ${liTd}>${liEsc(x.mode)}<br><span style="color:var(--text3);">${liEsc(x.band)}</span></td>
      <td ${liTd}>${x.decoder?`<b style="color:var(--amber);">${liEsc(x.decoder)}</b>`:'—'}${x.decoders_used.length?`<br><span style="color:var(--text3);font-size:.6rem;">utilisés : ${liEsc(x.decoders_used.join(', '))}</span>`:''}</td>
      <td ${liTd} title="${liEsc(x.ua)}">${liEsc(x.browser)} / ${liEsc(x.os)}<br><span style="color:var(--text3);">${liEsc(x.device)} ${liEsc(x.screen)}</span></td>
      <td ${liTd}>${liEsc(x.lang)}<br><span style="color:var(--text3);">${liEsc(x.tz_browser)}${x.tz_browser&&x.tz_ip&&x.tz_browser!==x.tz_ip?' <span style="color:var(--red);" title="Fuseau du navigateur différent de celui de l’IP (indice de VPN)">≠ IP</span>':''}</span></td>
      <td ${liTd}>${x.src?liEsc(x.src):'<span style="color:var(--text3);">direct / inconnu</span>'}</td>
      <td ${liTd}>${liEsc(x.duration)}</td></tr>`).join('');
  } catch(e){ tb.innerHTML = `<tr><td colspan="11" ${liTd} style="color:var(--red);">Erreur : ${liEsc(e.message)}</td></tr>`; }
}
function liTop(title, obj, n){
  const arr = Object.entries(obj||{}).sort((a,b) => b[1]-a[1]).slice(0, n||12);
  const max = arr.length ? arr[0][1] : 1, sum = Object.values(obj||{}).reduce((a,b)=>a+b,0) || 1;
  return `<div class="card"><div style="font-size:.65rem;color:var(--text3);letter-spacing:.1em;margin-bottom:.4rem;">${liEsc(title)}</div>` +
    (arr.length ? arr.map(([k,v]) => `<div style="display:flex;align-items:center;gap:.4rem;font-size:.7rem;margin:.15rem 0;">
      <span style="flex:0 0 42%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${liEsc(k)}">${liEsc(k)}</span>
      <span style="flex:1;background:var(--border);height:.5rem;border-radius:2px;"><span style="display:block;height:100%;width:${Math.max(2,v/max*100)}%;background:var(--green2);border-radius:2px;"></span></span>
      <span style="flex:0 0 3.6rem;text-align:right;color:var(--text2);">${v} · ${Math.round(v/sum*100)}%</span></div>`).join('')
      : '<div style="font-size:.7rem;color:var(--text3);">—</div>') + '</div>';
}
function liKpi(label, val, sub){ return `<div class="card" style="padding:.6rem;"><div style="font-size:.6rem;color:var(--text3);letter-spacing:.1em;">${liEsc(label)}</div><div style="font-size:1.2rem;color:var(--green);">${liEsc(val)}</div>${sub?`<div style="font-size:.6rem;color:var(--text3);">${liEsc(sub)}</div>`:''}</div>`; }
async function liStats(days, btn){
  liDays = days;
  if (btn){ document.querySelectorAll('#li-period-btns .btn').forEach(b => b.classList.remove('btn-blue')); btn.classList.add('btn-blue'); }
  try {
    const d = await (await fetch('/admin/api/listeners/stats?days=' + days, {cache:'no-store'})).json();
    const t = d.total || {}, net = t.net || {};
    const lis = Object.values(net).reduce((a,b)=>a+b,0) || 0;
    const pct = (a,b) => b ? Math.round(a/b*100) + ' %' : '—';
    document.getElementById('li-kpis').innerHTML = [
      liKpi('AUDITEURS', t.unique_listeners!=null ? t.unique_listeners : (t.listeners||0), t.unique_listeners!=null ? 'uniques sur la période' : 'somme des auditeurs / jour'),
      liKpi('SESSIONS', t.sessions||0, (t.sessions? 'durée moy. ' + liDur((t.listen_s||0)/t.sessions):'')),
      liKpi("TEMPS D'ÉCOUTE", liDur(t.listen_s||0)),
      liKpi('VISITES DE LA PAGE', t.visits||0, pct(t.returning||0, t.visits||0) + ' de fidèles'),
      liKpi('VIA HTTPS', pct(t.https||0, t.visits||0)),
      liKpi('VPN / PROXY', pct(net.vpn||0, lis), (net.datacenter||0) + ' datacenter'),
      liKpi('MOBILE', pct(net.mobile||0, lis)),
      liKpi('UTILISENT UN DÉCODEUR', t.decoder_users||0, pct(t.decoder_users||0, t.unique_listeners||t.listeners||0) + ' des auditeurs'),
    ].join('');
    const pd = d.per_day || [];
    const mx = Math.max(1, ...pd.map(x => x.listeners));
    document.getElementById('li-days').innerHTML = pd.length > 1
      ? `<div style="font-size:.65rem;color:var(--text3);letter-spacing:.1em;margin-bottom:.4rem;">AUDITEURS PAR JOUR</div><div style="display:flex;align-items:flex-end;gap:2px;height:80px;">` +
        pd.map(x => `<div title="${x.date} : ${x.listeners} auditeurs, ${x.sessions} sessions" style="flex:1;background:var(--green2);min-width:2px;height:${Math.max(2, x.listeners/mx*100)}%;"></div>`).join('') + '</div>'
      : '';
    const hours = {}; for (let h = 0; h < 24; h++){ const k = String(h).padStart(2,'0'); hours[k+' h UTC'] = (t.hours||{})[k] || 0; }
    document.getElementById('li-tops').innerHTML = [
      liTop('PAYS', t.countries), liTop('VILLES', t.cities, 15), liTop("FOURNISSEURS D'ACCÈS", t.isps, 15),
      liTop('TYPE DE RÉSEAU', t.net), liTop('DÉCODEURS (activations)', t.decoders), liTop('BANDES', t.bands, 15),
      liTop('MODES', t.modes), liTop('PROVENANCE (site précédent)', t.sources), liTop('NAVIGATEURS', t.browsers),
      liTop('SYSTÈMES', t.os), liTop('APPAREILS', t.devices), liTop('LANGUES', t.langs),
      liTop('SESSIONS PAR HEURE', Object.fromEntries(Object.entries(hours).filter(e => e[1])), 24),
    ].join('');
  } catch(e){ document.getElementById('li-kpis').innerHTML = `<div style="color:var(--red);">Erreur : ${liEsc(e.message)}</div>`; }
}
async function liSessions(){
  const tb = document.getElementById('li-sess-tbody');
  try {
    const d = await (await fetch('/admin/api/listeners/sessions?days=7', {cache:'no-store'})).json();
    const r = d.sessions || [];
    tb.innerHTML = r.length ? r.map(x => `<tr>
      <td ${liTd}>${liEsc((x.start||'').replace('T',' ').replace('Z',''))}</td>
      <td ${liTd}>${liDur(x.dur)}</td>
      <td ${liTd}>${liFlag(x.cc)} ${liEsc(x.city)}${x.country?', '+liEsc(x.country):''}</td>
      <td ${liTd} title="${liEsc(x.rdns)}">${liEsc(x.isp)}${x.rdns?`<br><span style="color:var(--blue);font-family:monospace;font-size:.6rem;">${liEsc(x.rdns)}</span>`:''}</td>
      <td ${liTd}>${liBadge(x.net)}</td>
      <td ${liTd}>${liEsc(x.bands.join(', '))}</td>
      <td ${liTd}>${liEsc(x.modes.join(', '))}</td>
      <td ${liTd}>${x.decoders.length?`<span style="color:var(--amber);">${liEsc(x.decoders.join(', '))}</span>`:'—'}</td>
      <td ${liTd}>${liEsc(x.browser)} ${liEsc(x.os)}</td>
      <td ${liTd}>${x.src?liEsc(x.src):'<span style="color:var(--text3);">direct / inconnu</span>'}</td>
      <td ${liTd} style="font-family:monospace;color:var(--text3);" title="Identifiant anonyme de l’auditeur : même IP = même ID pendant 90 jours">${liEsc(x.iph)}</td></tr>`).join('')
      : `<tr><td colspan="11" ${liTd} style="text-align:center;color:var(--text3);">Aucune session</td></tr>`;
  } catch(e){ tb.innerHTML = `<tr><td colspan="11" ${liTd} style="color:var(--red);">Erreur : ${liEsc(e.message)}</td></tr>`; }
}

let secDays = 7;
const SEC_COL = {scan:'var(--amber)', traversal:'var(--red)', method:'var(--amber)', forbidden:'var(--red)',
  burst404:'var(--amber)', admin_login_fail:'var(--red)', admin_login_ok:'var(--green)', admin_locked:'var(--red)', admin_global_lock:'var(--red)', admin_country:'var(--amber)', blocked:'var(--text3)'};
function secCat(c, n){ return `<span style="border:1px solid ${SEC_COL[c]||'var(--text3)'};color:${SEC_COL[c]||'var(--text3)'};border-radius:3px;padding:0 .3rem;font-size:.6rem;white-space:nowrap;margin:0 .15rem .15rem 0;display:inline-block;">${liEsc(c)}${n!=null?' ×'+n:''}</span>`; }
async function secLoad(days, btn){
  secDays = days;
  if (btn){ document.querySelectorAll('#sec-period-btns .btn').forEach(b => b.classList.remove('btn-blue')); btn.classList.add('btn-blue'); }
  try {
    const d = await (await fetch('/admin/api/security?days=' + days, {cache:'no-store'})).json();
    const L = d.labels || {};
    const order = ['admin_login_fail','admin_locked','admin_global_lock','admin_country','scan','traversal','forbidden','method','burst404','blocked','admin_login_ok'];
    document.getElementById('sec-kpis').innerHTML = order.map(c => `<div class="card" style="padding:.55rem;" title="${liEsc(L[c]||c)}"><div style="font-size:.58rem;color:var(--text3);">${liEsc(L[c]||c)}</div><div style="font-size:1.15rem;color:${(d.cats||{})[c]?(SEC_COL[c]||'var(--green)'):'var(--text3)'};">${(d.cats||{})[c]||0}</div></div>`).join('');
    secBans = d.bans || [];
    secRenderBans();
    secAllow = d.allow || []; secMyIp = d.myip || '';
    secRenderAllow();
    const ips = d.ips || [];
    document.getElementById('sec-ips-tbody').innerHTML = ips.length ? ips.map(x => `<tr>
      <td ${liTd} style="min-width:15rem;">${secDanger(x)}</td>
      <td ${liTd} style="font-family:monospace;">${liEsc(x.ip)}</td>
      <td ${liTd} style="font-family:monospace;color:var(--blue);font-size:.62rem;">${liEsc(x.rdns||'—')}</td>
      <td ${liTd}>${liFlag(x.countryCode)} ${liEsc(x.city||'')}${x.country?', '+liEsc(x.country):''}<br><span style="color:var(--text3);">${liEsc(x.isp||'')} ${liEsc(x.as||'')}</span></td>
      <td ${liTd}>${liBadge(x.net||'?')}</td>
      <td ${liTd}>${x.count}</td>
      <td ${liTd}>${Object.entries(x.cats).map(([c,n]) => secCat(c,n)).join('')}</td>
      <td ${liTd} style="font-family:monospace;font-size:.6rem;color:var(--text2);">${x.paths.map(liEsc).join('<br>')}</td>
      <td ${liTd}>${liEsc((x.last||'').replace('T',' ').replace('Z',''))}</td>
      <td ${liTd}>${x.banned?`<button class="btn" style="font-size:.6rem;" onclick="secUnban('${liEsc(x.ip)}')">DÉBANNIR</button>`:`<button class="btn" style="font-size:.6rem;color:var(--red);border-color:var(--red);" onclick="secBan('${liEsc(x.ip)}',24)">24 H</button> <button class="btn" style="font-size:.6rem;color:var(--red);border-color:var(--red);" onclick="secBan('${liEsc(x.ip)}',0)">DÉFINITIF</button>`}</td></tr>`).join('')
      : `<tr><td colspan="10" ${liTd} style="text-align:center;color:var(--text3);">Aucune tentative anormale sur la période</td></tr>`;
    const ev = d.events || [];
    document.getElementById('sec-ev-tbody').innerHTML = ev.length ? ev.slice(0,200).map(e => `<tr>
      <td ${liTd}>${liEsc((e.ts||'').replace('T',' ').replace('Z',''))}</td>
      <td ${liTd} style="font-family:monospace;" title="${liEsc(e.rdns||'')}">${liEsc(e.ip)}</td>
      <td ${liTd}>${secCat(e.cat)}</td>
      <td ${liTd} style="font-family:monospace;font-size:.6rem;word-break:break-all;">${liEsc(e.method)} ${liEsc(e.path)}</td>
      <td ${liTd}>${liEsc(e.status)}</td>
      <td ${liTd} style="font-size:.6rem;color:var(--text3);">${liEsc((e.ua||'').slice(0,90))}</td></tr>`).join('')
      : `<tr><td colspan="6" ${liTd} style="text-align:center;color:var(--text3);">—</td></tr>`;
  } catch(e){ document.getElementById('sec-kpis').innerHTML = `<div style="color:var(--red);">Erreur : ${liEsc(e.message)}</div>`; }
}
const SEC_LVL = {'faible':'var(--green)', 'moyen':'var(--amber)', 'élevé':'var(--red)', 'critique':'#ff2a2a'};
function secDanger(x){
  const c = SEC_LVL[x.level] || 'var(--text3)';
  const why = (x.why || []).map(w => `<li>${liEsc(w)}</li>`).join('');
  return `<div><span style="border:1px solid ${c};color:${c};border-radius:3px;padding:0 .35rem;font-size:.62rem;font-weight:bold;text-transform:uppercase;letter-spacing:.06em;">${liEsc(x.level||'?')}</span> <span style="color:var(--text3);font-size:.6rem;">score ${x.score||0}</span></div>` +
    (why ? `<ul style="margin:.25rem 0 .2rem 1rem;padding:0;font-size:.62rem;color:var(--text2);">${why}</ul>` : '') +
    `<div style="font-size:.6rem;color:${c};">${liEsc(x.advice||'')}</div>`;
}
let secAllow = [], secMyIp = '';
function secRenderAllow(){
  document.getElementById('sec-myip').textContent = secMyIp || '—';
  document.getElementById('sec-allow-count').textContent = secAllow.length ? `${secAllow.length} entrée${secAllow.length>1?'s':''}` : 'vide';
  document.getElementById('sec-allow').innerHTML = secAllow.length ? `<table style="width:100%;border-collapse:collapse;font-size:.68rem;">` + secAllow.map(b => `<tr>
      <td ${liTd} style="font-family:monospace;color:var(--green);">${liEsc(b.ip)}${b.ip===secMyIp?' <span style="color:var(--text3);">(vous)</span>':''}</td>
      <td ${liTd} style="color:var(--text2);">${liEsc(b.note||'')}</td>
      <td ${liTd} style="color:var(--text3);white-space:nowrap;">${b.since?new Date(b.since*1000).toLocaleDateString():''}</td>
      <td ${liTd}><button class="btn" style="font-size:.6rem;padding:0 .4rem;" onclick="secAllowRemove('${liEsc(b.ip)}')">RETIRER</button></td></tr>`).join('') + '</table>'
    : `<div style="font-size:.68rem;color:var(--text3);padding:.3rem;">Aucune entrée.</div>`;
}
async function secAllowPost(body){
  const d = await (await fetch('/admin/api/security/allow', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)})).json();
  toast(d.msg || (d.ok ? 'OK' : 'Erreur'), d.ok ? 'ok' : 'err');
  secLoad(secDays);
  return d;
}
function secAllowMe(){ if (secMyIp) secAllowPost({text: secMyIp, note: 'administrateur'}); }
async function secAllowBulk(){
  const ta = document.getElementById('sec-allow-bulk');
  const text = (ta.value || '').trim(); if (!text) return;
  const d = await secAllowPost({text, note: document.getElementById('sec-allow-note').value || ''});
  if (d.ok) ta.value = '';
}
function secAllowRemove(ip){ if (confirm(`Retirer ${ip} de la liste blanche ?`)) secAllowPost({ip, remove: true}); }
let secBans = [];
function secRenderBans(){
  const box = document.getElementById('sec-bans');
  const q = ((document.getElementById('sec-ban-filter')||{}).value || '').trim().toLowerCase();
  const list = secBans.filter(b => !q || (b.ip + ' ' + (b.reason||'')).toLowerCase().includes(q));
  document.getElementById('sec-ban-count').textContent = secBans.length ? `${secBans.length} entrée${secBans.length>1?'s':''}` : 'vide';
  box.innerHTML = list.length ? `<table style="width:100%;border-collapse:collapse;font-size:.68rem;">` + list.map(b => `<tr>
      <td ${liTd} style="font-family:monospace;">${liEsc(b.ip)}</td>
      <td ${liTd} style="color:var(--text2);">${liEsc(b.reason||'')}</td>
      <td ${liTd} style="color:var(--text3);white-space:nowrap;">${b.since?new Date(b.since*1000).toLocaleDateString():''}</td>
      <td ${liTd} style="white-space:nowrap;">${b.until?'jusqu’au '+new Date(b.until*1000).toLocaleString():'définitif'}</td>
      <td ${liTd}><button class="btn" style="font-size:.6rem;padding:0 .4rem;" onclick="secUnban('${liEsc(b.ip)}')">DÉBANNIR</button></td></tr>`).join('') + '</table>'
    : `<div style="font-size:.68rem;color:var(--text3);padding:.3rem;">${secBans.length ? 'Aucune entrée ne correspond.' : 'Aucune IP bannie.'}</div>`;
}
async function secBanBulk(hours){
  const ta = document.getElementById('sec-ban-bulk');
  const text = (ta.value || '').trim(); if (!text) return;
  const reason = document.getElementById('sec-ban-reason').value || 'liste';
  if (!confirm(`Bannir ${hours ? hours + ' h' : 'définitivement'} les adresses saisies ?`)) return;
  const d = await (await fetch('/admin/api/security/ban_bulk', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, hours, reason})})).json();
  toast(d.msg || (d.ok ? 'OK' : 'Erreur'), d.ok ? 'ok' : 'err');
  if (d.ok) ta.value = '';
  secLoad(secDays);
}
async function secKiwiImport(){
  if (!confirm('Importer la liste noire KiwiSDR (environ 130 adresses et plages, dont de grandes plages cloud Amazon / Google / Alibaba) ? Un nouvel import remplace le précédent.')) return;
  const d = await (await fetch('/admin/api/security/kiwi_import', {method:'POST'})).json();
  toast(d.msg || (d.ok ? 'OK' : 'Erreur'), d.ok ? 'ok' : 'err');
  secLoad(secDays);
}
async function secClear(){
  if (!confirm('Vider tout le journal des tentatives anormales ? Les IP bannies restent bannies.')) return;
  const d = await (await fetch('/admin/api/security/clear', {method:'POST'})).json();
  toast(d.msg || (d.ok ? 'OK' : 'Erreur'), d.ok ? 'ok' : 'err'); secLoad(secDays);
}
async function secBan(ip, hours){
  ip = (ip||'').trim(); if (!ip) return;
  if (!confirm(`Bannir ${ip} ${hours ? hours + ' h' : 'définitivement'} ?`)) return;
  const d = await (await fetch('/admin/api/security/ban', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ip, hours, reason:'panneau'})})).json();
  toast(d.msg || (d.ok ? 'OK' : 'Erreur'), d.ok ? 'ok' : 'err'); secLoad(secDays);
}
async function secUnban(ip){
  const d = await (await fetch('/admin/api/security/ban', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ip, unban:true})})).json();
  toast(d.msg || (d.ok ? 'OK' : 'Erreur'), d.ok ? 'ok' : 'err'); secLoad(secDays);
}

function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  el.classList.add('active');
  // Get label from either sidebar nav-item or bottom-nav link
  const labelEl = el.querySelector('span:last-child') || el.querySelector('span.bi + span') || el;
  document.getElementById('page-title').textContent = (labelEl.textContent || name).toUpperCase();
  currentPage = name;
  // Sync bottom nav active state
  document.querySelectorAll('.bottom-nav a').forEach(a => {
    a.classList.toggle('active', a.dataset.page === name);
  });
  if (name === 'dashboard') { loadDashboard(); }
  if (name === 'config') { loadConfigList(); }
  if (name === 'siteinfo') { loadJsonList(); }
  if (name === 'markers') { loadMarkers(); }
  if (name === 'reporting') { autorunLoad(); }
  if (name === 'logs') { loadCurrentLogTab(); }
  if (name === 'chat') { loadChat(); }
  if (name === 'settings') { loadSettingsPage(); }
  if (name === 'graphs')   { initGraphs(); }
  if (name === 'users')    { loadUsers(); }
  if (name === 'listeners') { liLoadAll(); }
  if (name === 'wfmsg')    { loadWfMsgStatus(); }
  if (window.extrasShow) { window.extrasShow(name); }
  return false;
}

// ─── Toast ───────────────────────────────────────────────────────────────────
function toast(msg, type='ok') {
  const t = document.getElementById('toast');
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = (type==='ok'?'✓ ':'✗ ') + msg;
  t.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ─── Clock ───────────────────────────────────────────────────────────────────
function updateClock() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('fr-FR');
}
setInterval(updateClock, 1000); updateClock();

// ─── Status polling ──────────────────────────────────────────────────────────
async function updateStatus() {
  try {
    const r = await fetch('/admin/api/status');
    const d = await r.json();
    const pill = document.getElementById('sdr-status');
    const dot  = pill ? pill.querySelector('.status-dot') : null;
    if (pill && dot) {
      if (d.process && d.process.running) {
        pill.className = 'status-pill online'; dot.className = 'status-dot online';
        pill.querySelector('span').textContent = 'EN LIGNE';
        document.getElementById('stat-status').textContent = 'EN MARCHE';
        document.getElementById('stat-status').style.color = 'var(--green)';
      } else {
        pill.className = 'status-pill offline'; dot.className = 'status-dot offline';
        pill.querySelector('span').textContent = 'HORS LIGNE';
        document.getElementById('stat-status').textContent = 'ARRÊTÉ';
        document.getElementById('stat-status').style.color = 'var(--red)';
      }
    }
    const pidEl = document.getElementById('stat-pid');
    if (pidEl && d.process) pidEl.textContent = 'PID: ' + (d.process.pid || '--');
    const s = d.system;
    if (s && s.cpu !== undefined && s.cpu !== 'N/A') {
      document.getElementById('stat-cpu').textContent  = s.cpu + '%';
      setBar('bar-cpu', s.cpu);
      const memEl = document.getElementById('stat-mem');
      memEl.textContent = s.mem_used + ' / ' + s.mem_total + ' GB';
      memEl.style.color = s.mem_pct > 80 ? 'var(--stat-bad)' : '';
      setBar('bar-mem', s.mem_pct);
      document.getElementById('stat-disk').textContent = s.disk_used + ' / ' + s.disk_total + ' GB';
      setBar('bar-disk', s.disk_pct);
      const tempEl = document.getElementById('stat-temp');
      if (tempEl) {
        if (s.temp !== null && s.temp !== undefined) {
          tempEl.textContent = s.temp + '\u00b0C';
          tempEl.style.color = s.temp >= 80 ? 'var(--stat-bad)'
                             : s.temp >= 70 ? 'var(--stat-warn)' : '';
          setBar('bar-temp', Math.min(100, Math.max(0, (s.temp - 20) / 80 * 100)));
        } else { tempEl.textContent = 'N/A'; tempEl.style.color = ''; }
      }
    }
    const tbody = document.getElementById('top-procs-tbody');
    if (tbody) {
      if (d.top_procs && d.top_procs.length > 0) {
        tbody.innerHTML = '';
        d.top_procs.forEach(proc => {
          const cc = proc.cpu > 80 ? 'cpu-hi' : proc.cpu > 50 ? 'cpu-med' : 'cpu-ok';
          const tr = document.createElement('tr');
          tr.innerHTML =
            `<td style="color:var(--text3)">${proc.pid}</td>` +
            `<td style="color:var(--text)">${proc.name}</td>` +
            `<td style="color:var(--text3)">${proc.user||''}</td>` +
            `<td class="${cc}">${proc.cpu}%</td>` +
            `<td class="mem-col">${proc.mem}%</td>`;
          tbody.appendChild(tr);
        });
      } else {
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text3);text-align:center;">Aucune donnée</td></tr>';
      }
    }
  } catch(e) { console.error('updateStatus:', e); }
}

// ─── Thermal guard ───────────────────────────────────────────────────────────
async function updateThermal() {
  try {
    const t = await fetch('/admin/api/thermal').then(r => r.json());
    const card = document.getElementById('thermal-card');
    const sub  = document.getElementById('stat-temp-guard');
    if (!t.available) {
      if (card) card.style.display = 'none';
      if (sub) sub.textContent = 'GARDE : indisponible';
      return;
    }
    if (card) card.style.display = '';
    const th = t.thresholds || {};
    let state, color;
    if (!t.enabled)      { state = 'DÉSACTIVÉE'; color = 'var(--text3)'; }
    else if (t.locked)   { state = 'BLOQUÉE'; color = 'var(--red)'; }
    else if (!t.armed)   { state = 'NON ARMÉE'; color = 'var(--amber)'; }
    else if (t.stage === 'stopped')  { state = 'NIVEAU ARRÊT'; color = 'var(--red)'; }
    else if (t.stage === 'throttle') { state = 'BRIDAGE'; color = 'var(--amber)'; }
    else if (t.stage === 'warn')     { state = 'CHAUD'; color = 'var(--amber)'; }
    else                 { state = 'ARMÉE'; color = 'var(--green)'; }
    const set = (id, txt) => { const e = document.getElementById(id); if (e) e.textContent = txt; };
    set('tg-state', state);
    const st = document.getElementById('tg-state'); if (st) st.style.color = color;
    const dot = document.getElementById('tg-dot');
    if (dot) { dot.style.background = color; dot.style.boxShadow = '0 0 6px ' + color; }
    set('tg-mode', t.mode + (t.mode === 'log' ? ' (aucune action)' : ''));
    set('tg-stop',   th.stop   !== undefined ? th.stop + '°C' : '--');
    set('tg-resume', th.resume !== undefined ? th.resume + '°C' : '--');
    set('tg-sensor', (t.sensor || 'aucun capteur') +
        (t.crit ? '  crit ' + t.crit + '°C' : '') +
        (t.throttle_supported ? '' : '  cpufreq: n/a'));
    let reason = t.reason || '';
    if (t.test_temp !== null && t.test_temp !== undefined)
      reason += '   [MODE TEST : mesure forcée à ' + t.test_temp + '°C]';
    if (t.giveup) reason += '   [limite atteinte : redémarrage auto désactivé]';
    set('tg-reason', reason);
    set('tg-last', t.last_event || '');
    if (sub) sub.textContent = 'GARDE : ' + state +
      (th.stop !== undefined && t.enabled ? ' · arrêt ' + th.stop + '°C' : '');
  } catch(e) { console.error('updateThermal:', e); }
}

async function thermalReset() {
  if (!confirm('Lever le blocage thermique et la limite de redémarrages ?' +
               String.fromCharCode(10) +
               'Si le CPU est encore trop chaud, la garde arrêtera simplement le serveur à nouveau.')) return;
  const d = await fetch('/admin/api/thermal', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({action: 'reset'})
  }).then(r => r.json());
  toast(d.msg || (d.ok ? 'Levé' : 'Échec'), d.ok ? '' : 'err');
  updateThermal();
}

// ─── WebSDR diversity relay ──────────────────────────────────────────────────
async function updateRelay() {
  try {
    const d = await fetch('/admin/api/websdr-relay').then(r => r.json());
    const card = document.getElementById('relay-card');
    if (!card) return;
    // Not set up at all: say nothing rather than show a permanently red card
    // on the many receivers that will never use this.
    if (!d.configured) { card.style.display = 'none'; return; }
    card.style.display = '';

    const set = (id, txt) => { const e = document.getElementById(id); if (e) e.textContent = txt; };
    const state = d.running ? 'EN MARCHE' : 'ARRÊTÉ';
    const color = d.running ? 'var(--green)' : 'var(--red)';
    set('rl-state', state);
    const st = document.getElementById('rl-state'); if (st) st.style.color = color;
    const dot = document.getElementById('rl-dot');
    if (dot) { dot.style.background = color; dot.style.boxShadow = '0 0 6px ' + color; }

    set('rl-port', d.port !== undefined ? String(d.port) : '--');
    set('rl-cap', (d.max_per_host !== undefined && d.max_per_host !== null)
                  ? d.max_per_host + ' / site' : '--');

    const sess = (d.sessions && d.sessions.hosts) ? d.sessions.hosts : {};
    const total = (d.sessions && d.sessions.total !== undefined) ? d.sessions.total : 0;
    set('rl-sessions', d.running ? (total + (d.max_total ? ' / ' + d.max_total : '')) : '--');

    // Which WebSDRs this station is currently relaying to, and how many
    // listeners on each. Empty is the normal resting state.
    const names = Object.keys(sess);
    const hosts = document.getElementById('rl-hosts');
    if (hosts) {
      if (!d.running) hosts.textContent = '';
      else if (!names.length) hosts.textContent = 'Aucune session active.';
      else hosts.textContent = names.map(h => h + '  \u00d7' + sess[h]).join('     ');
    }

    // The User-Agent is what WebSDR operators see. Showing it here is the
    // quickest way to notice it still says "your-receiver.example".
    set('rl-ua', d.user_agent || d.site || '');
    set('rl-reason', d.running ? '' : (d.reason || ''));
  } catch(e) { console.error('updateRelay:', e); }
}

function setBar(id, pct) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.width = pct + '%';
  el.className = 'bar-fill' + (pct>80?' danger':pct>50?' warn':'');
}

statusTimer = setInterval(updateStatus, 3000);
updateStatus();
setInterval(updateThermal, 5000);
updateThermal();
setInterval(updateRelay, 10000);
updateRelay();

// ─── Dashboard & Terminal ────────────────────────────────────────────────────
let _dashLogTimer = null;
let _termCwd  = '';
let _termHist = [];
let _termIdx  = -1;

async function loadDashboard() {
  updateStatus();
  updateThermal();
  loadLogs('dash-log', 'logwebsdr.txt');
  if (_dashLogTimer) clearInterval(_dashLogTimer);
  _dashLogTimer = setInterval(() => {
    if (currentPage === 'dashboard') loadLogs('dash-log', 'logwebsdr.txt');
    else { clearInterval(_dashLogTimer); _dashLogTimer = null; }
  }, 5000);
  // Set terminal cwd to sdr base dir
  if (!_termCwd) {
    try {
      const cfg = await fetch('/admin/api/settings').then(r => r.json());
      _termCwd = cfg.sdr_base_dir || '.';
    } catch(e) { _termCwd = '.'; }
    termUpdatePrompt();
  }
}

function termUpdatePrompt() {
  const el = document.getElementById('term-cwd');
  if (el && _termCwd) {
    const parts = _termCwd.replace(/\\/+$/, '').split('/');
    el.textContent = parts.slice(-2).join('/') || _termCwd;
  }
}

function termPrint(text, cls) {
  const out = document.getElementById('term-output');
  if (!out) return;
  if (text === '__CLEAR__') { out.innerHTML = ''; return; }
  const div = document.createElement('div');
  if (cls === 'cmd') {
    div.style.cssText = 'color:var(--amber);margin-top:.3rem;font-weight:bold;';
  } else if (cls === 'err') {
    div.style.cssText = 'color:#ff6666;';
  } else {
    div.style.cssText = 'color:var(--text);';
  }
  div.textContent = text;
  out.appendChild(div);
  out.scrollTop = out.scrollHeight;
}

function termClear() {
  const out = document.getElementById('term-output');
  if (out) out.innerHTML = '';
}

// Commande en cours (tâche de fond côté serveur) : sortie relevée en direct,
// la ligne tapée pendant qu'elle tourne est envoyée à son entrée standard
// (réponses aux menus des scripts), Ctrl+C ou STOP l'interrompt.
let _termJob = null;      // { id, pos, div, timer }

function termSetRunning(on) {
  const stop = document.getElementById('term-stop');
  const run  = document.getElementById('term-run');
  const inp  = document.getElementById('term-input');
  if (stop) stop.style.display = on ? '' : 'none';
  if (run)  run.style.display  = on ? 'none' : '';
  if (inp)  inp.placeholder = on
    ? 'commande en cours : tapez une réponse + Entrée, Ctrl+C pour interrompre'
    : 'tapez une commande puis Entrée';
}

function termAppend(text) {
  if (!_termJob || !text) return;
  const out = document.getElementById('term-output');
  if (!_termJob.div) {
    _termJob.div = document.createElement('div');
    _termJob.div.style.cssText = 'color:var(--text);';
    out.appendChild(_termJob.div);
  }
  const atBottom = out.scrollHeight - out.scrollTop - out.clientHeight < 40;
  _termJob.div.appendChild(document.createTextNode(text));
  if (atBottom) out.scrollTop = out.scrollHeight;
  _termJob.tail = ((_termJob.tail || '') + text).slice(-200);
  termPasswordMode(/(assword|mot de passe)[^:]*: *$/i.test(_termJob.tail));
}

// Mot de passe demandé (sudo…) : saisie masquée, rien n'est réaffiché.
function termPasswordMode(on) {
  const inp = document.getElementById('term-input');
  if (inp) inp.type = on ? 'password' : 'text';
}

async function termPoll() {
  if (!_termJob) return;
  const job = _termJob;
  try {
    const r = await fetch('/admin/api/terminal/poll?id=' + encodeURIComponent(job.id) + '&pos=' + job.pos);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    if (d.lost) termPrint('… (début de sortie tronqué)', 'err');
    termAppend(d.output);
    job.pos = d.pos;
    if (d.done) {
      _termJob = null;
      termSetRunning(false);
      termPasswordMode(false);
      if (d.gone) termPrint('(commande introuvable sur le serveur)', 'err');
      else if (d.rc !== 0) termPrint('[code de sortie ' + d.rc + ']', 'err');
      else if (job.pos === 0) termPrint('(no output)', '');
      return;
    }
    job.fails = 0;
  } catch (ex) {
    job.fails = (job.fails || 0) + 1;
    if (job.fails === 5) termPrint('Connexion perdue, nouvel essai… (' + ex.message + ')', 'err');
  }
  job.timer = setTimeout(termPoll, 400);
}

async function termKill() {
  if (!_termJob) return;
  termPrint('^C', 'cmd');
  try {
    await fetch('/admin/api/terminal/kill', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: _termJob.id})
    });
  } catch (ex) {}
}

async function termRun() {
  const inp = document.getElementById('term-input');
  if (!inp) return;
  const cmd = inp.value;
  // Commande en cours : la ligne part vers son entrée standard
  if (_termJob) {
    inp.value = '';
    const secret = inp.type === 'password';
    termPasswordMode(false);
    _termJob.tail = '';
    termAppend((secret ? '********' : cmd) + String.fromCharCode(10));
    _termJob.div = null;
    try {
      await fetch('/admin/api/terminal/input', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: _termJob.id, text: cmd})
      });
    } catch (ex) { termPrint('Network error: ' + ex.message, 'err'); }
    return;
  }
  if (!cmd.trim()) return;
  inp.value = '';
  _termHist.unshift(cmd.trim());
  if (_termHist.length > 100) _termHist.pop();
  _termIdx = -1;
  termPrint('$ ' + cmd.trim(), 'cmd');
  try {
    const r = await fetch('/admin/api/terminal/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cmd: cmd.trim(), cwd: _termCwd})
    });
    if (!r.ok) { termPrint('Erreur HTTP : ' + r.status, 'err'); return; }
    const d = await r.json();
    if (d.cwd && d.cwd !== _termCwd) {
      _termCwd = d.cwd;
      termUpdatePrompt();
    }
    if (d.id) {
      _termJob = { id: d.id, pos: 0, div: null, timer: null };
      termSetRunning(true);
      termPoll();
      return;
    }
    if (d.output) termPrint(d.output, d.ok ? '' : 'err');
  } catch(ex) {
    termPrint('Network error: ' + ex.message, 'err');
  }
}

function termCopy() {
  const out = document.getElementById('term-output');
  if (!out) return;
  const sel = window.getSelection ? String(window.getSelection()) : '';
  const text = sel || out.innerText;
  const done = () => toast(sel ? 'Sélection copiée' : 'Sortie du terminal copiée', 'ok');
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done, () => termCopyFallback(text, done));
  } else termCopyFallback(text, done);
}

function termCopyFallback(text, done) {
  const ta = document.createElement('textarea');
  ta.value = text; ta.style.cssText = 'position:fixed;left:-9999px;top:0;';
  document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy'); done(); } catch (e) { toast('Copie impossible', 'err'); }
  ta.remove();
}

function termKey(e) {
  const inp = document.getElementById('term-input');
  if (!inp) return;
  if (e.key === 'Enter') {
    e.preventDefault(); termRun();
  } else if ((e.key === 'c' || e.key === 'C') && e.ctrlKey && _termJob && !inp.selectionEnd) {
    e.preventDefault(); termKill();
  } else if (e.key === 'ArrowUp' && !_termJob) {
    e.preventDefault();
    if (_termIdx < _termHist.length - 1) { _termIdx++; inp.value = _termHist[_termIdx]; }
  } else if (e.key === 'ArrowDown' && !_termJob) {
    e.preventDefault();
    if (_termIdx > 0) { _termIdx--; inp.value = _termHist[_termIdx]; }
    else { _termIdx = -1; inp.value = ''; }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const out = document.getElementById('term-output');
  // Clic dans la sortie → focus sur la saisie, sauf si l'on vient de
  // sélectionner du texte (sinon la sélection disparaît et rien n'est copiable).
  if (out) out.addEventListener('click', () => {
    if (window.getSelection && String(window.getSelection())) return;
    const inp = document.getElementById('term-input');
    if (inp) inp.focus();
  });
});


// ─── File Editor ─────────────────────────────────────────────────────────────
let configFiles = {};

async function loadConfigList(notify) {
  const sel = document.getElementById('config-file-sel');
  const prev = sel.value;                       // preserve current selection across a rescan
  const r = await fetch('/admin/api/editable-files');
  const nextFiles = await r.json();
  if (notify) {
    const before = Object.keys(configFiles);
    const after  = Object.keys(nextFiles);
    const added   = after.filter(f => !before.includes(f)).length;
    const removed = before.filter(f => !after.includes(f)).length;
    toast('Rescan : ' + after.length + ' fichiers (+' + added + ' / -' + removed + ')');
  }
  configFiles = nextFiles;
  sel.innerHTML = '<option value="">-- Choisir un fichier --</option>';
  // Group by extension
  const groups = {};
  Object.keys(configFiles).forEach(rel => {
    const ext = rel.split('.').pop().toLowerCase();
    if (!groups[ext]) groups[ext] = [];
    groups[ext].push(rel);
  });
  const order = ['toml','sh','json','html','cpp','h','txt'];
  [...order, ...Object.keys(groups).filter(e => !order.includes(e))].forEach(ext => {
    if (!groups[ext]) return;
    const og = document.createElement('optgroup');
    og.label = '.' + ext.toUpperCase();
    groups[ext].forEach(rel => {
      const o = document.createElement('option');
      o.value = rel; o.textContent = rel;
      og.appendChild(o);  // ← append to optgroup, not directly to select
    });
    sel.appendChild(og);
  });
  if (prev && configFiles[prev]) sel.value = prev;   // keep selection if the file still exists
}

async function loadConfigFile() {
  const sel = document.getElementById('config-file-sel');
  const name = sel.value;
  if (!name) return;
  document.getElementById('config-filepath').textContent = configFiles[name] || name;
  const r = await fetch('/admin/api/read-file?path=' + encodeURIComponent(configFiles[name]));
  const d = await r.json();
  document.getElementById('config-editor').value = d.content || '';
}

async function saveConfigFile() {
  const sel = document.getElementById('config-file-sel');
  const name = sel.value;
  const content = document.getElementById('config-editor').value;
  const r = await fetch('/admin/api/write-file', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({path: configFiles[name], content})
  });
  const d = await r.json();
  const msg = document.getElementById('config-save-msg');
  if (d.ok) { toast('Configuration enregistrée'); msg.textContent = '✓ Enregistré à ' + new Date().toLocaleTimeString('fr-FR'); msg.style.color = 'var(--green)'; }
  else { toast(d.msg, 'err'); msg.textContent = '✗ ' + d.msg; msg.style.color = 'var(--red)'; }
}

// ─── JSON / Site Info Editor ─────────────────────────────────────────────────
let jsonFiles = {};
let currentJsonData = {};
let currentJsonPath = '';

async function loadJsonList() {
  const r = await fetch('/admin/api/json-files');
  jsonFiles = await r.json();
  const sel = document.getElementById('json-file-sel');
  sel.innerHTML = '';
  Object.keys(jsonFiles).forEach(name => {
    const o = document.createElement('option');
    o.value = name; o.textContent = name;
    sel.appendChild(o);
  });
  if (Object.keys(jsonFiles).length > 0) loadJsonFile();
}

async function loadJsonFile() {
  const sel = document.getElementById('json-file-sel');
  const name = sel.value;
  if (!name) return;
  currentJsonPath = jsonFiles[name];
  const r = await fetch('/admin/api/read-file?path=' + encodeURIComponent(currentJsonPath));
  const d = await r.json();
  const raw = d.content || '{}';
  document.getElementById('json-raw-editor').value = raw;
  try {
    currentJsonData = JSON.parse(raw);
    renderJsonForm(currentJsonData);
  } catch(e) {
    document.getElementById('json-form-fields').innerHTML = '<p style="color:var(--red)">JSON invalide : ' + e.message + '</p>';
  }
}

function renderJsonForm(data) {
  const container = document.getElementById('json-form-fields');
  container.innerHTML = '';
  Object.entries(data).forEach(([key, val]) => {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;gap:.2rem;';
    const label = document.createElement('label');
    label.style.cssText = 'font-size:.6rem;color:var(--text3);letter-spacing:.1em;';
    label.textContent = key.toUpperCase();

    let input;
    if (typeof val === 'boolean') {
      input = document.createElement('select');
      input.className = 'script-select';
      input.style.marginBottom = '0';
      input.innerHTML = `<option value="true" ${val?'selected':''}>true</option><option value="false" ${!val?'selected':''}>false</option>`;
    } else if (typeof val === 'number') {
      input = document.createElement('input');
      input.type = 'number'; input.value = val;
      input.style.width = '100%';
    } else if (typeof val === 'object') {
      input = document.createElement('textarea');
      input.className = 'code';
      input.style.minHeight = '60px';
      input.style.width = '100%';
      input.value = JSON.stringify(val, null, 2);
    } else {
      input = document.createElement('input');
      input.type = 'text'; input.value = val;
      input.style.width = '100%';
    }
    input.dataset.key = key;
    wrap.appendChild(label);
    wrap.appendChild(input);
    container.appendChild(wrap);
  });
}

function getJsonFormData() {
  const container = document.getElementById('json-form-fields');
  const result = {};
  container.querySelectorAll('[data-key]').forEach(el => {
    const key = el.dataset.key;
    const orig = currentJsonData[key];
    if (typeof orig === 'boolean') result[key] = el.value === 'true';
    else if (typeof orig === 'number') result[key] = Number(el.value);
    else if (typeof orig === 'object') { try { result[key] = JSON.parse(el.value); } catch { result[key] = el.value; } }
    else result[key] = el.value;
  });
  return result;
}

function switchJsonTab(tab, el) {
  document.querySelectorAll('#page-siteinfo .tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('#page-siteinfo .tab-pane').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('json-' + tab + '-pane').classList.add('active');
  if (tab === 'raw') {
    // Sync form → raw
    try {
      const d = getJsonFormData();
      document.getElementById('json-raw-editor').value = JSON.stringify(d, null, 2);
    } catch(e) {}
  }
}

async function saveJsonForm() {
  const data = getJsonFormData();
  const content = JSON.stringify(data, null, 2);
  const r = await fetch('/admin/api/write-file', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({path: currentJsonPath, content})
  });
  const d = await r.json();
  const msg = document.getElementById('json-save-msg');
  if (d.ok) { toast('JSON enregistré'); msg.textContent = '✓ Enregistré'; msg.style.color = 'var(--green)'; }
  else { toast(d.msg, 'err'); msg.textContent = '✗ ' + d.msg; msg.style.color = 'var(--red)'; }
}

async function saveJsonRaw() {
  const content = document.getElementById('json-raw-editor').value;
  try { JSON.parse(content); } catch(e) { toast('JSON invalide : ' + e.message, 'err'); return; }
  const r = await fetch('/admin/api/write-file', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({path: currentJsonPath, content})
  });
  const d = await r.json();
  if (d.ok) toast('JSON saved'); else toast(d.msg, 'err');
}

// ─── Markers Editor ──────────────────────────────────────────────────────────
let markersData = [];
let markersPath = '';

async function loadMarkers() {
  const r = await fetch('/admin/api/markers');
  const d = await r.json();
  markersData = d.data || [];
  markersPath = d.path || '';
  renderMarkersTable();
}

function renderMarkersTable() {
  const tbody = document.getElementById('markers-tbody');
  tbody.innerHTML = '';
  markersData.forEach((m, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="text" value="${m.frequency||m.freq||''}" data-i="${i}" data-f="frequency"></td>
      <td><input type="text" value="${m.name||m.label||''}" data-i="${i}" data-f="name"></td>
      <td><input type="text" value="${m.mode||m.modulation||''}" data-i="${i}" data-f="mode"></td>
      <td><input type="text" value="${m.color||''}" data-i="${i}" data-f="color" style="width:80px"></td>
      <td><button class="btn btn-red" style="padding:.2rem .5rem;font-size:.7rem;" onclick="deleteMarker(${i})">✕</button></td>
    `;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('input', () => {
      const i = parseInt(inp.dataset.i);
      const f = inp.dataset.f;
      if (!markersData[i]) return;
      markersData[i][f] = f === 'frequency' ? (isNaN(Number(inp.value)) ? inp.value : Number(inp.value)) : inp.value;
      document.getElementById('markers-raw').value = JSON.stringify(markersData, null, 2);
    });
  });
  document.getElementById('markers-raw').value = JSON.stringify(markersData, null, 2);
}

function addMarker() {
  markersData.push({frequency: 0, name: "Nouveau marqueur", mode: "AM", color: "#00ff41"});
  renderMarkersTable();
}

function deleteMarker(i) {
  markersData.splice(i, 1);
  renderMarkersTable();
}

async function saveMarkers() {
  const r = await fetch('/admin/api/markers', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({data: markersData})
  });
  const d = await r.json();
  const msg = document.getElementById('markers-save-msg');
  if (d.ok) { toast('Marqueurs enregistrés'); msg.textContent = '✓ Enregistré'; msg.style.color = 'var(--green)'; }
  else { toast(d.msg, 'err'); msg.textContent = '✗ ' + d.msg; msg.style.color = 'var(--red)'; }
}

// ─── Spot Reporting (autorun) ─────────────────────────────────────────────────
let AR_BANDS = [], AR_MODES = {}, AR_POLL = null;

async function autorunLoad() {
  try {
    const d = await fetch('/admin/api/autorun/config').then(r => r.json());
    AR_BANDS = d.bands; AR_MODES = d.modes;
    const c = d.config;
    document.getElementById('ar-call').value = c.identity.callsign || '';
    document.getElementById('ar-grid').value = c.identity.grid || '';
    document.getElementById('ar-psk').checked = !!c.reporting.pskreporter;
    document.getElementById('ar-wspr').checked = !!c.reporting.wsprnet;
    document.getElementById('ar-max').value = c.maxSlots || 12;
    const enabled = new Set((c.slots || []).filter(s => s.enabled).map(s => s.mode + ':' + s.band));
    autorunBuildMatrix(enabled);
    autorunPoll();
    if (!AR_POLL) AR_POLL = setInterval(autorunPoll, 5000);
  } catch (e) { toast('échec du chargement : ' + e.message, 'err'); }
}

function autorunBuildMatrix(enabledSet) {
  const modes = Object.keys(AR_MODES);
  // The badge is filled by autorunPoll; it is empty (and hidden) until the
  // daemon reports a count, so a rebuild never shows a stale number.
  let h = '<thead><tr><th>BANDE</th>' + modes.map(m =>
    '<th>' + m.toUpperCase() + '<span class="ar-hdr-badge" id="ar-hdr-' + m + '"></span></th>').join('') +
    '</tr></thead><tbody>';
  for (const band of AR_BANDS) {
    h += '<tr><td style="color:var(--amber)">' + band + '</td>';
    for (const m of modes) {
      const key = m + ':' + band;
      if (AR_MODES[m].includes(band)) {
        h += '<td style="white-space:nowrap;"><input type="checkbox" data-key="' + key +
             '" onchange="autorunCount()"' + (enabledSet.has(key) ? ' checked' : '') + '>' +
             '<span class="ar-slot-tot" data-slot="' + key + '"></span></td>';
      } else {
        h += '<td><span style="color:var(--text3)">&#8211;</span></td>';
      }
    }
    h += '</tr>';
  }
  document.getElementById('ar-matrix').innerHTML = h + '</tbody>';
  autorunCount();
}

function autorunGatherSlots() {
  const slots = [];
  document.querySelectorAll('#ar-matrix input[type=checkbox]').forEach(cb => {
    const [mode, band] = cb.dataset.key.split(':');
    slots.push({ band, mode, enabled: cb.checked });
  });
  return slots;
}

function autorunCount() {
  const n = document.querySelectorAll('#ar-matrix input:checked').length;
  const max = parseInt(document.getElementById('ar-max').value || '12', 10);
  const el = document.getElementById('ar-count');
  el.textContent = n + ' slot(s) activé(s) (limite ' + max + ')';
  el.style.color = n > max ? 'var(--red)' : 'var(--text3)';
}

async function autorunSave() {
  const body = {
    identity: { callsign: document.getElementById('ar-call').value.trim(), grid: document.getElementById('ar-grid').value.trim() },
    reporting: { pskreporter: document.getElementById('ar-psk').checked, wsprnet: document.getElementById('ar-wspr').checked },
    maxSlots: parseInt(document.getElementById('ar-max').value || '12', 10),
    slots: autorunGatherSlots(),
  };
  const d = await fetch('/admin/api/autorun/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json());
  toast(d.ok ? 'Configuration enregistrée' : d.msg, d.ok ? 'ok' : 'err');
  document.getElementById('ar-msg').textContent = d.ok ? '✓ enregistré' : '✗ ' + d.msg;
  return d.ok;
}

async function autorunStart() {
  if (!(await autorunSave())) return;
  const d = await fetch('/admin/api/autorun/start', { method: 'POST' }).then(r => r.json());
  toast(d.msg, d.ok ? 'ok' : 'err'); setTimeout(autorunPoll, 800);
}
async function autorunStop() {
  const d = await fetch('/admin/api/autorun/stop', { method: 'POST' }).then(r => r.json());
  toast(d.msg, d.ok ? 'ok' : 'err'); setTimeout(autorunPoll, 500);
}
async function autorunFreeAll() {
  // Spell out the counter loss: the all-time totals are the one thing here
  // that a restart cannot bring back.
  if (!confirm('Décocher toutes les bandes/modes, arrêter le démon et effacer les ' +
               'compteurs cumulés de spots de chaque bande ?\\n\\n' +
               'Les compteurs ne pourront pas être récupérés.')) return;
  document.querySelectorAll('#ar-matrix input:checked').forEach(cb => cb.checked = false);
  document.getElementById('ar-psk').checked = false;
  document.getElementById('ar-wspr').checked = false;
  autorunCount();
  await autorunSave();
  // The endpoint stops the daemon itself and waits for it to exit before
  // deleting, because the daemon rewrites its totals on the way out.
  const d = await fetch('/admin/api/autorun/totals/reset', { method: 'POST' })
                    .then(r => r.json()).catch(e => ({ok: false, msg: e.message}));
  toast(d.ok ? 'Slots libérés, compteurs remis à zéro' : d.msg, d.ok ? 'ok' : 'err');
  autorunRenderSlotTotals({});          // clear the numbers without waiting for a poll
  setTimeout(autorunPoll, 600);
}

async function autorunPoll() {
  try {
    const d = await fetch('/admin/api/autorun/status').then(r => r.json());
    const dot = document.getElementById('ar-dot');
    if (!dot) return;
    dot.style.background = d.running ? 'var(--green)' : 'var(--text3)';
    document.getElementById('ar-state').textContent = d.running ? ('EN MARCHE (PID ' + (d.pids || []).join(',') + ')') : 'ARRÊTÉ';
    const s = d.status || {}, cn = s.counts || {}, rep = s.reporting || {};
    const fmt = t => t ? new Date(t * 1000).toLocaleTimeString('fr-FR') : '—';
    const pending = (q, sent) => Math.max(0, (q || 0) - (sent || 0));
    document.getElementById('ar-status').innerHTML =
      'Envoi : PSK Reporter <b>' + (rep.pskreporter ? 'ACTIF' : 'inactif') + '</b> &#183; wsprnet <b>' + (rep.wsprnet ? 'ACTIF' : 'inactif') + '</b>' + (s.dryRun ? ' &#183; <span style="color:var(--amber)">SIMULATION</span>' : '') + '<br>' +
      'Décodages : ' + (cn.decodes || 0) + '<br>' +
      'PSK Reporter : <b>' + (cn.pskSent || 0) + '</b> envoyés, ' + pending(cn.pskQueued, cn.pskSent) + ' en attente <span style="color:var(--text3)">(envoi toutes les 5 min)</span><br>' +
      'wsprnet : <b>' + (cn.wsprSent || 0) + '</b> envoyés, ' + pending(cn.wsprQueued, cn.wsprSent) + ' en attente <span style="color:var(--text3)">(toutes les 2 min)</span><br>' +
      'Dernier décodage : ' + fmt(s.lastDecodeAt) + ' &#183; Dernier envoi : ' + fmt(s.lastUploadAt) + ' ' + (s.lastUploadMsg || '');
    autorunRenderSpots(s, d.running, rep);
    autorunRenderSlotTotals(d.totals || {});
  } catch (e) { /* ignore */ }
}

// All-time spots per band+mode, written next to that slot's checkbox.
// These come from autorun-totals.json, which the daemon keeps across restarts,
// so unlike the tiles above they are NOT reset by Stop/Start.
function autorunRenderSlotTotals(totals) {
  var any = false;
  document.querySelectorAll('.ar-slot-tot').forEach(function(el) {
    var t = totals[el.dataset.slot];
    var up = t ? (t.uploaded || 0) : 0;
    var dec = t ? (t.decodes || 0) : 0;
    // No entry at all = the daemon has never run this slot, so nothing to say.
    // An entry that is still all zeros DOES get a 0: the daemon seeds every
    // enabled slot at startup, and a blank cell there reads as a broken
    // counter rather than as "nothing heard yet". WSPR sits at zero for
    // minutes after a start — its cycle is 2 minutes — while FT8 is already
    // in the hundreds.
    if (!t) { el.textContent = ''; el.title = ''; return; }
    any = true;
    if (!up && !dec) {
      el.textContent = '0';
      el.classList.add('none');
      el.title = 'Activé, rien décodé pour l’instant — le WSPR en particulier peut prendre ' +
                 'plusieurs minutes, il émet sur un cycle de 2 minutes.';
      return;
    }
    // Uploaded is the headline; decodes explain a slot that hears plenty but
    // uploads nothing because its destination is off.
    el.textContent = up ? String(up) : '·' + dec;
    el.classList.toggle('none', !up);
    el.title = up + ' spots envoyés, ' + dec + ' décodages — cumul pour cette bande et ce mode' +
               (t.lastSpotAt ? '\\ndernier envoi ' + new Date(t.lastSpotAt * 1000).toLocaleString('fr-FR') : '');
  });
  var note = document.getElementById('ar-slot-note');
  if (note) note.style.display = any ? 'block' : 'none';
}

// Fill the per-decoder tiles and the badges in the bands/modes header.
function autorunRenderSpots(s, running, rep) {
  const bm = (s && s.byMode) || {};
  // Which destination carries each decoder — a mode whose destination is off
  // decodes but never uploads, and saying "0" without that context reads as a
  // fault rather than a setting.
  const dest = {ft8: 'pskreporter', ft4: 'pskreporter', js8: 'pskreporter', wspr: 'wsprnet'};
  ['ft8', 'ft4', 'js8', 'wspr'].forEach(function(m) {
    const t   = bm[m] || null;
    const el  = document.getElementById('ar-up-' + m);
    const sub = document.getElementById('ar-sub-' + m);
    const hdr = document.getElementById('ar-hdr-' + m);
    if (!el) return;
    const up      = t ? (t.uploaded || 0) : 0;
    const dec     = t ? (t.decodes  || 0) : 0;
    const pending = t ? Math.max(0, (t.queued || 0) - up) : 0;
    const on      = !!(rep || {})[dest[m]];

    el.textContent = t ? up : '—';
    el.classList.toggle('idle', !t || up === 0);
    if (sub) {
      if (!t)              sub.textContent = running ? 'aucun slot activé' : 'démon arrêté';
      else if (!on)        sub.innerHTML = dec + ' décodages · <span style="color:var(--amber)">envoi désactivé</span>';
      else                 sub.textContent = dec + ' décodages · ' + pending + ' en attente';
    }
    // Badge shows uploads only, and only once there are some — an empty badge
    // is hidden by CSS, keeping the header clean before the first upload.
    if (hdr) {
      hdr.textContent = (t && up) ? String(up) : '';
      hdr.title = (t && up) ? (up + ' spots envoyés depuis le démarrage du démon') : '';
    }
  });
}

// ─── Logs ────────────────────────────────────────────────────────────────────
function getLogTargetId(logName) {
  return LOG_TAB_TARGETS[logName] || 'main-log-logwebsdr';
}

async function loadLogs(targetId, logName) {
  const id = targetId || 'dash-log';
  const name = logName || 'logwebsdr.txt';
  const r = await fetch('/admin/api/logs?name=' + encodeURIComponent(name));
  const d = await r.json();
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = '';
  (d.lines || []).forEach(line => {
    const div = document.createElement('div');
    div.className = line.match(/error|fail|crash/i) ? 'log-line-err' :
                    line.match(/warn/i) ? 'log-line-warn' :
                    line.match(/ok|success|started/i) ? 'log-line-ok' : '';
    div.textContent = line;
    el.appendChild(div);
  });
  if (!(d.lines || []).length) {
    const div = document.createElement('div');
    div.textContent = 'Aucune ligne dans ce journal.';
    el.appendChild(div);
  }
  el.scrollTop = el.scrollHeight;
}

function switchLogTab(logName, el) {
  currentLogTab = logName;
  document.querySelectorAll('.log-tab').forEach(tab => tab.classList.remove('active'));
  document.querySelectorAll('.log-tab-pane').forEach(pane => pane.classList.remove('active'));
  if (el) el.classList.add('active');
  const paneId = LOG_TAB_PANES[logName];
  const pane = document.getElementById(paneId);
  if (pane) pane.classList.add('active');
  loadLogs(getLogTargetId(logName), logName);
}

function loadCurrentLogTab() {
  loadLogs(getLogTargetId(currentLogTab), currentLogTab);
}

async function clearLogView() {
  if (autoRefresh) toggleAutoRefresh();
  let d = {};
  try {
    const r = await fetch('/admin/api/logs/clear', {method: 'POST'});
    d = await r.json();
  } catch (e) {
    toast('Échec du vidage : ' + e, 'err');
    return;
  }
  const failed  = d.failed  || [];
  const skipped = d.skipped || [];
  const cleared = d.cleared || [];
  // Blank only the panes whose file was actually emptied. A pane blanked over a
  // file that is still on disk fills again at the next refresh, which reads as
  // the button being broken — so a log the server kept or could not write keeps
  // its lines on screen. CLEAR_EXCLUDE is empty now, so in practice this only
  // covers failures, but it stays correct if a log is ever excluded again.
  const keptPanes = new Set(skipped.concat(failed.map(f => f.name))
                                   .map(n => LOG_TAB_TARGETS[n]));
  ['dash-log', ...Object.values(LOG_TAB_TARGETS)].forEach(id => {
    if (keptPanes.has(id)) return;
    const el = document.getElementById(id);
    if (el) el.innerHTML = '';
  });
  // Say which files were actually emptied: a silent "Logs cleared" over a pane
  // that still has lines in it is what made this look broken.
  if (failed.length) {
    toast('Impossible de vider ' + failed.map(f => f.name + ' (' + f.error + ')').join(', '), 'err');
  } else {
    let msg = 'Cleared ' + (cleared.length ? cleared.join(', ') : 'nothing');
    if (skipped.length) msg += ' — kept ' + skipped.join(', ') + ' (excluded)';
    toast(msg);
  }
}

function toggleAutoRefresh() {
  autoRefresh = !autoRefresh;
  const btn = document.getElementById('auto-refresh-btn');
  if (autoRefresh) {
    btn.textContent = '⏸ ARRÊTER AUTO';
    btn.className = 'btn btn-red';
    autoRefreshTimer = setInterval(() => loadCurrentLogTab(), 3000);
  } else {
    btn.textContent = '⏵ ACTUALISATION AUTO';
    btn.className = 'btn btn-green';
    clearInterval(autoRefreshTimer);
  }
}

// ─── Chat ────────────────────────────────────────────────────────────────────
async function loadChat() {
  const r = await fetch('/admin/api/chat');
  const d = await r.json();
  const el = document.getElementById('chat-log');
  el.innerHTML = '';
  (d.messages || []).forEach(m => {
    const div = document.createElement('div');
    div.className = 'chat-msg';

    const txt = document.createElement('span');
    txt.className = 'chat-msg-text';
    const rxTag = (d.multi && m.rx) ? `<span class="chat-time">${escHtml(m.rx)}</span> ` : '';
    txt.innerHTML = `${rxTag}<span class="chat-time">[${m.time||'?'}]</span> <span class="chat-nick">&lt;${m.nick||'?'}&gt;</span> ${escHtml(m.msg||'')}`;

    const delBtn = document.createElement('button');
    delBtn.className = 'chat-del-btn';
    delBtn.title = 'Supprimer ce message';
    delBtn.textContent = '✕ SUPPR.';
    delBtn.onclick = async function() {
      if (!confirm('Supprimer ce message ?\\n\\n' + (m.time ? '[' + m.time + '] ' : '') + '<' + m.nick + '> ' + m.msg)) return;
      try {
        const res = await fetch('/admin/api/chat/delete', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({line: m.raw, rx: m.rx || ''})
        });
        const rd = await res.json();
        if (rd.ok) { div.remove(); toast('Message supprimé'); }
        else toast(rd.msg || 'Échec de la suppression', 'err');
      } catch(e) { toast('Network error: ' + e.message, 'err'); }
    };

    div.appendChild(txt);
    div.appendChild(delBtn);
    el.appendChild(div);
  });
  if (!d.messages?.length) el.textContent = 'Aucun historique de chat.';
  el.scrollTop = el.scrollHeight;
}

async function clearChat() {
  if (!confirm('Effacer l’historique du chat ?')) return;
  const r = await fetch('/admin/api/chat/clear', {method:'POST'});
  const d = await r.json();
  if (d.ok) { toast('Chat effacé'); loadChat(); } else toast(d.msg, 'err');
}

// ─── Settings ────────────────────────────────────────────────────────────────
async function loadSettingsPage() {
  const r = await fetch('/admin/api/settings');
  const d = await r.json();
  document.getElementById('sdr-dir').value = d.sdr_base_dir || '';
  const ppEl = document.getElementById('public-port');
  if (ppEl) ppEl.value = d.public_port || 8900;
  // Populate start/stop script selectors
  const sh = await fetch('/admin/api/scripts').then(r => r.json());
  const all = sh.all || [];
  ['default-start-sel','default-stop-sel'].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = '<option value="">-- Aucun --</option>';
    all.forEach(s => {
      const o = document.createElement('option');
      o.value = s; o.textContent = s;
      sel.appendChild(o);
    });
  });
  if (document.getElementById('default-start-sel'))
    document.getElementById('default-start-sel').value = d.start_script || '';
  if (document.getElementById('default-stop-sel'))
    document.getElementById('default-stop-sel').value = d.stop_script || '';
  loadThermalSettings(d);
}

// ─── Thermal guard settings ──────────────────────────────────────────────────
const TG_FIELDS = {
  'tg-cfg-warn':        'thermal_warn',
  'tg-cfg-throttle':    'thermal_throttle',
  'tg-cfg-stop':        'thermal_stop',
  'tg-cfg-resume':      'thermal_resume',
  'tg-cfg-sustain':     'thermal_sustain_s',
  'tg-cfg-warnsustain': 'thermal_warn_sustain_s',
  'tg-cfg-resumes':     'thermal_resume_s',
  'tg-cfg-maxstops':    'thermal_max_stops_hour',
  'tg-cfg-test':        'thermal_test_temp',
};

function loadThermalSettings(d) {
  const mode = document.getElementById('tg-cfg-mode');
  if (!mode) return;
  if (d.thermal_mode === undefined) return;   // guard not loaded server-side
  mode.value = d.thermal_mode || 'log';
  const en = document.getElementById('tg-cfg-enabled');
  if (en) en.value = (d.thermal_enabled === false) ? '0' : '1';
  for (const [id, key] of Object.entries(TG_FIELDS)) {
    const el = document.getElementById(id);
    if (el) el.value = (d[key] === null || d[key] === undefined) ? '' : d[key];
  }
  fetch('/admin/api/thermal').then(r => r.json()).then(t => {
    const c = document.getElementById('tg-cfg-crit');
    if (!c) return;
    if (!t.available)   { c.textContent = 'garde non chargée'; return; }
    if (!t.sensor)      { c.textContent = 'aucun capteur CPU fiable trouvé'; return; }
    c.textContent = t.crit ? (t.sensor + ', crit ' + t.crit + '°C')
                           : (t.sensor + ', pas de seuil critique publié — réglez ARRÊT à la main');
  }).catch(() => {});
}

async function saveThermal() {
  const body = {
    thermal_mode: document.getElementById('tg-cfg-mode').value,
    thermal_enabled: document.getElementById('tg-cfg-enabled').value === '1',
  };
  for (const [id, key] of Object.entries(TG_FIELDS)) {
    const el = document.getElementById(id);
    if (!el) continue;
    const v = el.value.trim();
    body[key] = (v === '') ? null : parseFloat(v);
  }
  const d = await fetch('/admin/api/settings', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body)
  }).then(r => r.json());
  if (d.ok) {
    toast('Garde thermique enregistrée');
    document.getElementById('tg-cfg-msg').textContent =
      'Enregistré — appliqué à la prochaine mesure (sous quelques secondes), sans redémarrage';
    loadSettingsPage();
    updateThermal();
  } else toast(d.msg || 'Échec', 'err');
}

async function saveSettings() {
  const dir   = document.getElementById('sdr-dir').value.trim();
  const start = document.getElementById('default-start-sel')?.value || '';
  const stop  = document.getElementById('default-stop-sel')?.value || '';
  const pp    = parseInt(document.getElementById('public-port')?.value || '8900', 10);
  const r = await fetch('/admin/api/settings', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({sdr_base_dir: dir, start_script: start, stop_script: stop, public_port: pp})
  });
  const d = await r.json();
  if (d.ok) {
    toast('Réglages enregistrés');
    document.getElementById('settings-msg').textContent = 'Enregistré';
  } else toast(d.msg, 'err');
}

async function changePassword(e) {
  e.preventDefault();
  const old = document.getElementById('old-pwd').value;
  const n = document.getElementById('new-pwd').value;
  const n2 = document.getElementById('new-pwd2').value;
  if (n !== n2) { toast('Les mots de passe ne correspondent pas', 'err'); return; }
  if (n.length < 12) { toast('Mot de passe trop court (12 min.)', 'err'); return; }
  const r = await fetch('/admin/api/change-password', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({old, new_pwd: n})
  });
  const d = await r.json();
  if (d.ok) { toast('Mot de passe modifié'); document.getElementById('old-pwd').value=''; document.getElementById('new-pwd').value=''; document.getElementById('new-pwd2').value=''; }
  else toast(d.msg, 'err');
}
function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function isLocalIp(ip) {
  if (!ip) return false;
  var raw = ip.startsWith('::ffff:') ? ip.slice(7) : ip;
  if (raw === '::1' || raw === 'localhost') return true;
  return /^127\\./.test(raw) || /^10\\./.test(raw) || /^192\\.168\\./.test(raw) ||
         /^172\\.(1[6-9]|2\\d|3[01])\\./.test(raw) || /^fc/i.test(raw) || /^fd/i.test(raw);
}

// ─── Users / Kick ────────────────────────────────────────────────────────────
let _usersAutoTimer = null;

var _uConnTimes = {};

function _uFmtFreq(khz) {
  if (khz == null || isNaN(khz)) return '--';
  if (khz >= 50) return (khz / 1000).toFixed(3) + ' MHz';
  return khz.toFixed(3) + ' kHz';
}

function _uFmtDur(ms) {
  var s  = Math.floor(ms / 1000);
  var h  = Math.floor(s / 3600);
  var m  = Math.floor((s % 3600) / 60);
  var ss = s % 60;
  if (h > 0) return h + ':' + String(m).padStart(2,'0') + ':' + String(ss).padStart(2,'0');
  return m + ':' + String(ss).padStart(2,'0');
}

function _uTickDurations() {
  var now = Date.now();
  document.querySelectorAll('td.u-dur-cell[data-uid]').forEach(function(td) {
    var t = _uConnTimes[td.dataset.uid];
    if (t) td.textContent = _uFmtDur(now - t);
  });
}

setInterval(function(){ if (currentPage === 'users') _uTickDurations(); }, 1000);

// ─── Graphs page ─────────────────────────────────────────────────────────────
// Four measures with four different units (GHz, %, degC, a head-count).  They
// are drawn as four stacked panels sharing one time axis rather than as one
// chart with several y-scales: a shared scale would imply the curves are
// comparable, and the crossings it produced would be an artefact of the scaling.
var _gPoints   = [];      // full history, oldest first
var _gRange    = 900;     // visible window, seconds
var _gLast     = 0;       // newest sample timestamp we hold
var _gMeta     = {interval: 2, freq_limit: null, cores: null, coarse: false};
var _gTimer    = null;
var _gHover    = null;    // index under the pointer, or null

var GRAPH_PANELS = [
  {key:'f', title:'FRÉQUENCE CPU', unit:'GHz', dec:2},
  {key:'l', title:'CHARGE CPU',      unit:'%',   dec:0},
  {key:'c', title:'TEMPÉRATURE CPU', unit:'°C', dec:1},
  {key:'u', title:'AUDITEURS EN LIGNE',  unit:'',    dec:0, step:true}
];

// One hue for every panel: each panel holds a single series that its own title
// names, so colour is not carrying identity here and four competing hues would
// only add noise.  Colour is kept in reserve for temperature, where it means
// something specific.
var G_LINE = '#00ff41', G_FILL = 'rgba(0,255,65,0.10)';
var G_WARN = '#ffb000', G_CRIT = '#ff4040';
var TEMP_WARN = 70, TEMP_CRIT = 80;

function graphTempColor(v) {
  if (v === null || v === undefined) return G_LINE;
  if (v >= TEMP_CRIT) return G_CRIT;
  if (v >= TEMP_WARN) return G_WARN;
  return G_LINE;
}

function graphSetRange(sec, el) {
  _gRange = sec;
  document.querySelectorAll('.graph-range').forEach(function(b) {
    b.classList.toggle('active', b === el);
  });
  // Ranges are served from different tiers (2s live, 30s averages beyond an
  // hour), so the held points are not interchangeable — refetch rather than
  // splice two resolutions into one series.
  _gPoints = []; _gLast = 0;
  loadGraphs(false);
}

async function loadGraphs(incremental) {
  var want = _gRange;
  try {
    var url = '/admin/api/graph-stats?range=' + want +
              (incremental && _gLast ? '&since=' + _gLast : '');
    var r = await fetch(url, {cache: 'no-store'});
    var d = await r.json();
    if (!d.ok) return;
    // A slow reply that lands after the range changed again would mix
    // resolutions; drop it and let the newer request stand.
    if (want !== _gRange) return;
    var restart = _gMeta.interval && d.interval !== _gMeta.interval;
    _gMeta = {interval: d.interval, freq_limit: d.freq_limit, cores: d.cores, coarse: d.coarse};
    var pts = d.points || [];
    if (incremental && _gLast) {
      if (pts.length) _gPoints = _gPoints.concat(pts);
    } else {
      _gPoints = pts;
    }
    if (_gPoints.length) _gLast = _gPoints[_gPoints.length - 1].t;
    // Drop anything older than the window so the buffer here cannot grow
    // without bound over a long-lived session.
    var cutoff = _gLast - want;
    _gPoints = _gPoints.filter(function(p) { return p.t >= cutoff; });
    // Poll on the tier's cadence: 2s on the live view, no faster than new
    // points appear on the aggregated ones.
    if (restart) graphSchedulePoll();
    drawGraphs();
  } catch (e) { /* transient fetch error: keep what we have and retry next tick */ }
}

function graphSchedulePoll() {
  if (_gTimer) clearInterval(_gTimer);
  _gTimer = setInterval(function() {
    if (currentPage === 'graphs' && !document.hidden) loadGraphs(true);
  }, (_gMeta.interval || 2) * 1000);
}

function graphVisible() {
  var cut = (_gPoints.length ? _gPoints[_gPoints.length - 1].t : 0) - _gRange;
  return _gPoints.filter(function(p) { return p.t >= cut; });
}

function graphFmt(v, p) {
  if (v === null || v === undefined) return '--';
  return v.toFixed(p.dec) + (p.unit ? ' ' + p.unit : '');
}

// Top of a panel's y-scale.  Single source of truth: the plot and the hover
// markers must agree, and computing it twice is how they stop agreeing.
// Every scale starts at zero, so curve height stays proportional to the value.
function graphTop(p, pts) {
  var vals = pts.map(function(q) { return q[p.key]; })
                .filter(function(v) { return v !== null && v !== undefined; });
  if (p.key === 'l') return 100;
  if (p.key === 'f') return _gMeta.freq_limit ||
                            (vals.length ? Math.max.apply(null, vals) * 1.15 : 1);
  if (p.key === 'c') return Math.max(80, vals.length
                            ? Math.ceil(Math.max.apply(null, vals) / 10) * 10 : 80);
  return Math.ceil(Math.max(4, vals.length ? Math.max.apply(null, vals) : 1));
}

function drawGraphs() {
  var cv = document.getElementById('graph-canvas');
  var empty = document.getElementById('graph-empty');
  if (!cv) return;
  var pts = graphVisible();

  var info = document.getElementById('graph-info-label');
  if (info) {
    // Say plainly when a view is averaged: a 30s mean and a 2s reading are not
    // the same measurement, and the peaks differ between them.
    info.textContent = (_gMeta.coarse ? _gMeta.interval + 's de moyenne' : 'mesure toutes les ' + _gMeta.interval + 's') +
      ' · ' + pts.length + ' points affichés' + (_gMeta.cores ? ' · ' + _gMeta.cores + ' cœurs' : '');
  }

  // Current-value tiles always reflect the newest sample, not the hover.
  var last = _gPoints.length ? _gPoints[_gPoints.length - 1] : null;
  var setTile = function(id, val, p) {
    var el = document.getElementById(id);
    if (el) el.textContent = (val === null || val === undefined) ? '--' : val.toFixed(p);
  };
  setTile('g-cur-freq', last ? last.f : null, 2);
  setTile('g-cur-load', last ? last.l : null, 0);
  setTile('g-cur-temp', last ? last.c : null, 1);
  setTile('g-cur-users', last ? last.u : null, 0);
  var tempEl = document.getElementById('g-cur-temp');
  if (tempEl && last) tempEl.style.color = graphTempColor(last.c);
  var fsub = document.getElementById('g-sub-freq');
  if (fsub) fsub.textContent = 'GHz en moyenne' + (last && last.fm ? ' · cœur max ' + last.fm.toFixed(2) : '');
  var tsub = document.getElementById('g-sub-temp');
  if (tsub && last && last.c !== null && last.c !== undefined) {
    tsub.textContent = last.c >= TEMP_CRIT ? 'degrés C · CRITIQUE'
                     : last.c >= TEMP_WARN ? 'degrés C · CHAUD' : 'degrés C';
  }

  if (pts.length < 2) {
    cv.style.display = 'none';
    if (empty) {
      empty.style.display = 'block';
      empty.textContent = _gMeta.coarse
        ? 'Collecte en cours — cette vue trace des moyennes sur ' + _gMeta.interval + ' s, elle se remplit tant que le panneau tourne.'
        : 'Collecte en cours — une mesure toutes les ' + _gMeta.interval + ' s, la première courbe apparaît sous quelques secondes.';
    }
    return;
  }
  cv.style.display = 'block';
  if (empty) empty.style.display = 'none';

  // ── geometry ──
  var dpr = window.devicePixelRatio || 1;
  var cssW = cv.clientWidth || 800;
  // Type sizes are named once here: the panel geometry is sized around them,
  // so bumping a size and leaving the padding behind is not possible.
  var F_TITLE = '600 13px Orbitron, monospace';          // panel heading
  var F_AXIS  = '12px "Share Tech Mono", monospace';     // tick + min/max labels
  var F_NOTE  = '11px "Share Tech Mono", monospace';     // threshold legend
  var PANEL_H = 100, GAP = 36, PAD_L = 64, PAD_R = 14, PAD_T = 22, AXIS_H = 28;
  var cssH = PAD_T + GRAPH_PANELS.length * (PANEL_H + GAP) + AXIS_H;
  cv.style.height = cssH + 'px';
  cv.width = Math.round(cssW * dpr);
  cv.height = Math.round(cssH * dpr);
  var ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  var narrow = cssW < 680;
  var t0 = pts[0].t, t1 = pts[pts.length - 1].t;
  if (t1 === t0) t1 = t0 + 1;
  var plotW = cssW - PAD_L - PAD_R;
  var xOf = function(t) { return PAD_L + (t - t0) / (t1 - t0) * plotW; };

  GRAPH_PANELS.forEach(function(p, pi) {
    var top = PAD_T + pi * (PANEL_H + GAP);
    var bot = top + PANEL_H;
    var vals = pts.map(function(q) { return q[p.key]; })
                  .filter(function(v) { return v !== null && v !== undefined; });

    var hi = graphTop(p, pts);
    var yOf = function(v) { return bot - (v / hi) * PANEL_H; };

    // ── panel title + range label ──
    ctx.font = F_TITLE;
    ctx.fillStyle = '#7ab87a';
    ctx.textAlign = 'left';
    ctx.fillText(p.title, PAD_L, top - 8);
    if (p.key === 'c' && !narrow) {
      // The threshold legend lives in the title row.  In the plot the two
      // guides can end up ~9px apart, where their labels would collide with
      // each other and with this title.  On a phone the row is only wide
      // enough for the title and the min/max, so the legend is dropped there
      // and the dashed guides speak for themselves.
      var tw = ctx.measureText(p.title).width;
      ctx.font = F_NOTE;
      ctx.fillStyle = G_WARN; ctx.fillText('– – ' + TEMP_WARN + '° warm', PAD_L + tw + 12, top - 8);
      var ww = ctx.measureText('– – ' + TEMP_WARN + '° warm').width;
      ctx.fillStyle = G_CRIT; ctx.fillText('– – ' + TEMP_CRIT + '° critical', PAD_L + tw + ww + 24, top - 8);
    }
    if (vals.length) {
      ctx.font = F_AXIS;
      ctx.fillStyle = '#4a8a4a';
      ctx.textAlign = 'right';
      var lo = Math.min.apply(null, vals), up = Math.max.apply(null, vals);
      // On a narrow canvas the spelled-out form runs into the panel title, so
      // it collapses to a range: same two numbers, roughly half the width.
      ctx.fillText(narrow ? (lo.toFixed(p.dec) + ' – ' + graphFmt(up, p))
                          : ('min ' + graphFmt(lo, p) + '   max ' + graphFmt(up, p)),
                   cssW - PAD_R, top - 8);
    }

    // ── recessive grid: baseline plus mid and top gridlines only ──
    ctx.strokeStyle = 'rgba(26,58,26,0.9)';
    ctx.lineWidth = 1;
    ctx.font = F_AXIS;
    ctx.textAlign = 'right';
    [0, hi / 2, hi].forEach(function(gv) {
      var y = Math.round(yOf(gv)) + 0.5;
      ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(cssW - PAD_R, y); ctx.stroke();
      ctx.fillStyle = '#4a8a4a';
      var lbl = (p.key === 'u') ? String(Math.round(gv)) : gv.toFixed(p.dec === 2 ? 1 : 0);
      ctx.fillText(lbl, PAD_L - 8, y + 4);
    });

    if (!vals.length) {
      ctx.font = F_AXIS;
      ctx.fillStyle = '#4a8a4a';
      ctx.textAlign = 'center';
      ctx.fillText('non disponible sur ce système', PAD_L + plotW / 2, top + PANEL_H / 2);
      return;
    }

    // ── segments: a null reading breaks the line instead of being bridged,
    // so a gap in the data never looks like a measured value. ──
    var segs = [], cur = [];
    pts.forEach(function(q) {
      var v = q[p.key];
      if (v === null || v === undefined) { if (cur.length) { segs.push(cur); cur = []; } }
      else cur.push(q);
    });
    if (cur.length) segs.push(cur);

    segs.forEach(function(seg) {
      // continueFrom: append to the current subpath instead of starting a new
      // one.  The fill has already moved to the baseline, and a moveTo there
      // would break the polygon into two subpaths and fill the space between.
      var trace = function(continueFrom) {
        seg.forEach(function(q, i) {
          var x = xOf(q.t), y = yOf(q[p.key]);
          if (i === 0) {
            if (continueFrom) ctx.lineTo(x, y); else ctx.moveTo(x, y);
            return;
          }
          if (p.step) ctx.lineTo(x, yOf(seg[i - 1][p.key]));   // hold, then move
          ctx.lineTo(x, y);
        });
      };
      if (seg.length > 1) {
        ctx.beginPath();
        ctx.moveTo(xOf(seg[0].t), bot);
        trace(true);
        ctx.lineTo(xOf(seg[seg.length - 1].t), bot);
        ctx.closePath();
        ctx.fillStyle = G_FILL;
        ctx.fill();
      }
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      if (p.key === 'c') {
        // Colour tracks each reading, so the line changes hue exactly where it
        // crosses a threshold.  Colouring the whole run by one value would
        // paint cool history as if it had been hot.
        for (var i = 1; i < seg.length; i++) {
          ctx.beginPath();
          ctx.moveTo(xOf(seg[i - 1].t), yOf(seg[i - 1].c));
          ctx.lineTo(xOf(seg[i].t), yOf(seg[i].c));
          ctx.strokeStyle = graphTempColor(Math.max(seg[i].c, seg[i - 1].c));
          ctx.stroke();
        }
      } else {
        ctx.beginPath();
        trace(false);
        ctx.strokeStyle = G_LINE;
        ctx.stroke();
      }
      if (seg.length === 1) {   // a lone sample still deserves to be visible
        ctx.beginPath();
        ctx.arc(xOf(seg[0].t), yOf(seg[0][p.key]), 2.5, 0, Math.PI * 2);
        ctx.fillStyle = (p.key === 'c') ? graphTempColor(seg[0].c) : G_LINE;
        ctx.fill();
      }
    });

    // Temperature thresholds are the one place colour means something, so the
    // line it refers to is drawn and labelled rather than left implicit.
    if (p.key === 'c') {
      [[TEMP_WARN, 'rgba(255,176,0,', 'warm'], [TEMP_CRIT, 'rgba(255,64,64,', 'critical']]
        .forEach(function(th) {
          if (hi < th[0]) return;
          var ty = Math.round(yOf(th[0])) + 0.5;
          ctx.save();
          ctx.setLineDash([3, 3]);
          ctx.strokeStyle = th[1] + '0.45)';
          ctx.beginPath(); ctx.moveTo(PAD_L, ty); ctx.lineTo(cssW - PAD_R, ty); ctx.stroke();
          ctx.restore();
        });
    }
  });

  // ── shared time axis ──
  var axisY = PAD_T + GRAPH_PANELS.length * (PANEL_H + GAP) - GAP + 14;
  ctx.font = F_AXIS;
  ctx.fillStyle = '#4a8a4a';
  ctx.textAlign = 'center';
  var TICKS = Math.max(2, Math.min(6, Math.floor(plotW / 130)));
  for (var i = 0; i <= TICKS; i++) {
    var tt = t0 + (t1 - t0) * i / TICKS;
    var lbl = new Date(tt * 1000).toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit'});
    var x = xOf(tt);
    ctx.textAlign = (i === 0) ? 'left' : (i === TICKS ? 'right' : 'center');
    ctx.fillText(lbl, x, axisY);
  }

  // ── crosshair + tooltip ──
  if (_gHover !== null && _gHover >= 0 && _gHover < pts.length) {
    var hp = pts[_gHover];
    var hx = xOf(hp.t);
    ctx.save();
    ctx.setLineDash([2, 3]);
    ctx.strokeStyle = 'rgba(200,255,200,0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(hx + 0.5, PAD_T - 8);
    ctx.lineTo(hx + 0.5, PAD_T + GRAPH_PANELS.length * (PANEL_H + GAP) - GAP);
    ctx.stroke();
    ctx.restore();
    GRAPH_PANELS.forEach(function(p, pi) {
      var v = hp[p.key];
      if (v === null || v === undefined) return;
      var top = PAD_T + pi * (PANEL_H + GAP), bot = top + PANEL_H;
      var y = bot - (v / graphTop(p, pts)) * PANEL_H;
      ctx.beginPath();
      ctx.arc(hx, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = (p.key === 'c') ? graphTempColor(v) : G_LINE;
      ctx.fill();
      ctx.lineWidth = 2;                       // surface ring keeps the marker
      ctx.strokeStyle = '#0a150a';             // readable on top of the line
      ctx.stroke();
    });
  }
}

function graphHover(ev) {
  var cv = document.getElementById('graph-canvas');
  var tip = document.getElementById('graph-tooltip');
  if (!cv || !tip) return;
  var pts = graphVisible();
  if (pts.length < 2) return;
  var rect = cv.getBoundingClientRect();
  var x = ev.clientX - rect.left;
  var PAD_L = 52, PAD_R = 12;
  var plotW = rect.width - PAD_L - PAD_R;
  var t0 = pts[0].t, t1 = pts[pts.length - 1].t;
  var frac = Math.max(0, Math.min(1, (x - PAD_L) / plotW));
  var want = t0 + frac * (t1 - t0);
  var best = 0, bestD = Infinity;
  pts.forEach(function(p, i) {
    var d = Math.abs(p.t - want);
    if (d < bestD) { bestD = d; best = i; }
  });
  _gHover = best;
  var p = pts[best];
  var rows = GRAPH_PANELS.map(function(pl) {
    var v = p[pl.key];
    return '<div style="display:flex;gap:.8rem;justify-content:space-between;">' +
           '<span style="color:var(--text3);">' + pl.title + '</span>' +
           '<span style="color:' + ((pl.key === 'c') ? graphTempColor(v) : 'var(--text)') + ';">' +
           graphFmt(v === undefined ? null : v, pl) + '</span></div>';
  }).join('');
  tip.innerHTML = '<div style="color:var(--green);margin-bottom:.25rem;">' +
    new Date(p.t * 1000).toLocaleTimeString('fr-FR') + '</div>' + rows;
  tip.style.display = 'block';
  // Flip the tooltip to the other side near the right edge so it never
  // overflows the card it lives in.
  var card = cv.parentElement;
  var cardRect = card.getBoundingClientRect();
  var tw = tip.offsetWidth || 150;
  var left = ev.clientX - cardRect.left + 14;
  if (left + tw > cardRect.width) left = ev.clientX - cardRect.left - tw - 14;
  tip.style.left = Math.max(4, left) + 'px';
  tip.style.top  = (ev.clientY - cardRect.top + 12) + 'px';
  drawGraphs();
}

function graphLeave() {
  _gHover = null;
  var tip = document.getElementById('graph-tooltip');
  if (tip) tip.style.display = 'none';
  drawGraphs();
}

function initGraphs() {
  var cv = document.getElementById('graph-canvas');
  if (cv && !cv._wired) {
    cv._wired = true;
    cv.parentElement.style.position = 'relative';
    cv.addEventListener('mousemove', graphHover);
    cv.addEventListener('mouseleave', graphLeave);
    window.addEventListener('resize', function() { if (currentPage === 'graphs') drawGraphs(); });
  }
  loadGraphs(false);
  graphSchedulePoll();
}

async function loadUsers() {
  var tbody = document.getElementById('users-tbody');
  var info  = document.getElementById('users-info-label');
  var errEl = document.getElementById('users-error');
  var CL = 'padding:.38rem .6rem;border-bottom:1px solid var(--border);vertical-align:middle;';
  function msgRow(msg, color) {
    tbody.innerHTML = '';
    var tr = document.createElement('tr'); var td = document.createElement('td');
    td.colSpan = 6;
    td.style.cssText = 'color:' + (color||'var(--text3)') + ';text-align:center;padding:.8rem;';
    td.textContent = msg; tr.appendChild(td); tbody.appendChild(tr);
  }
  if (tbody) msgRow('Chargement…', 'var(--text3)');
  try {
    // Through the admin API, not /users: proxy.py would route that by the rx
    // cookie and show only the receiver last opened with ?rx=.
    var r = await fetch('/admin/api/sdr-users', {cache: 'no-store'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    var data = await r.json();
    if (!data.ok) throw new Error(data.error || 'aucun récepteur n’a répondu');
    var users = data.users || [];
    var multi = !!data.multi;
    var rxTh = document.getElementById('users-rx-th');
    if (rxTh) rxTh.style.display = multi ? '' : 'none';
    if (errEl) errEl.style.display = 'none';
    if (info)  info.textContent = users.length + ' connected';
    if (!tbody) return;
    if (!users.length) { msgRow('Aucun auditeur connecté', ''); return; }
    var now = Date.now();
    tbody.innerHTML = '';
    users.forEach(function(u) {
      if (!_uConnTimes[u.id])
        _uConnTimes[u.id] = now - (u.duration_s || 0) * 1000;
      var tr = document.createElement('tr');
      // IP / location
      var tdGeo = document.createElement('td');
      tdGeo.style.cssText = CL + 'color:var(--green);';
      if (isLocalIp(u.ip) || u.geo === 'Local') {
        tdGeo.textContent = 'Local';
      } else if (u.geo && u.geo !== u.ip) {
        tdGeo.textContent = u.geo;
        tdGeo.title = u.ip;
      } else {
        tdGeo.textContent = u.ip || '--';
      }
      tr.appendChild(tdGeo);
      // Receiver (only with several receivers)
      if (multi) {
        var tdRx = document.createElement('td');
        tdRx.style.cssText = CL + 'color:var(--text2);font-size:.7rem;';
        tdRx.textContent = u.rx || '--';
        tr.appendChild(tdRx);
      }
      // Frequency
      var tdF = document.createElement('td');
      tdF.style.cssText = CL + 'color:var(--amber);';
      tdF.textContent = _uFmtFreq(u.freq_khz);
      tr.appendChild(tdF);
      // Mode
      var tdM = document.createElement('td');
      tdM.style.cssText = CL + 'color:var(--text2);font-size:.7rem;';
      tdM.textContent = (u.mode || '--').toUpperCase();
      tr.appendChild(tdM);
      // Duration (live ticking)
      var tdDur = document.createElement('td');
      tdDur.className = 'u-dur-cell';
      tdDur.dataset.uid = u.id;
      tdDur.style.cssText = CL + 'color:var(--blue);font-variant-numeric:tabular-nums;';
      tdDur.textContent = _uFmtDur(now - _uConnTimes[u.id]);
      tr.appendChild(tdDur);
      // Kick button
      var tdK = document.createElement('td');
      tdK.style.cssText = CL;
      var rawIp = (u.ip||'').replace(/^::ffff:/,'');
      if (rawIp && rawIp !== '127.0.0.1' && rawIp !== '::1') {
        var btn = document.createElement('button');
        btn.className = 'btn btn-red';
        btn.style.cssText = 'padding:.25rem .6rem;font-size:.65rem;';
        btn.textContent = '⚡ EXPULSER';
        btn.onclick = (function(ip){ return function(){ kickUser(ip); }; })(rawIp);
        tdK.appendChild(btn);
      }
      tr.appendChild(tdK);
      tbody.appendChild(tr);
    });
    var liveIds = new Set(users.map(function(u){ return u.id; }));
    Object.keys(_uConnTimes).forEach(function(id){
      if (!liveIds.has(id)) delete _uConnTimes[id];
    });
  } catch(e) {
    if (errEl) { errEl.textContent = 'Impossible de lire la liste des auditeurs : ' + e.message; errEl.style.display = 'block'; }
    if (tbody)  msgRow('Erreur : ' + e.message, 'var(--red)');
  }
}

async function kickUser(ip) {
  if (!confirm('Expulser ' + ip + ' ? Toutes ses connexions seront coupées.')) return;
  try {
    var r = await fetch('/admin/api/kick', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ip: ip})
    });
    var d = await r.json();
    if (d.ok) { toast('Kicked ' + ip); setTimeout(loadUsers, 1800); }
    else toast(d.msg || 'Échec de l’expulsion', 'err');
  } catch(e) {
    toast('Expulsion envoyée — actualisation…', 'ok');
    setTimeout(loadUsers, 2000);
  }
}

function toggleUsersAutoRefresh() {
  var btn = document.getElementById('users-auto-btn');
  if (_usersAutoTimer) {
    clearInterval(_usersAutoTimer); _usersAutoTimer = null;
    if (btn) { btn.textContent = '▶ AUTO'; btn.classList.replace('btn-amber','btn-green'); }
  } else {
    loadUsers();
    _usersAutoTimer = setInterval(function(){
      if (currentPage === 'users') loadUsers();
      else { clearInterval(_usersAutoTimer); _usersAutoTimer = null; }
    }, 5000);
    if (btn) { btn.textContent = '⏸ AUTO ACTIF'; btn.classList.replace('btn-green','btn-amber'); }
  }
}

// ── Waterfall Message ─────────────────────────────────────────────────────────
document.getElementById('wfmsg-text')?.addEventListener('input', function() {
  var n = this.value.length;
  var el = document.getElementById('wfmsg-charcount');
  if (el) { el.textContent = n + ' / 200'; el.style.color = n > 180 ? 'var(--amber)' : 'var(--text3)'; }
});

function wfUntil() {
  var v = document.getElementById('wfmsg-dur')?.value || '0';
  if (v === 'custom') {
    var dt = document.getElementById('wfmsg-until')?.value;
    return dt ? Math.floor(new Date(dt).getTime() / 1000) : 0;
  }
  var sec = parseInt(v, 10) || 0;
  return sec ? Math.floor(Date.now() / 1000) + sec : 0;
}
function wfUntilText(u) {
  if (!u) return '';
  var d = new Date(u * 1000);
  return " (jusqu'au " + d.toLocaleDateString('fr-FR') + ' ' + d.toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'}) + ')';
}
async function sendWfMsg() {
  var text  = (document.getElementById('wfmsg-text')?.value || '').trim();
  var color = document.getElementById('wfmsg-color')?.value || '#ffffff';
  var el    = document.getElementById('wfmsg-status');
  if (!text) { el.textContent = '⚠ Le message ne peut pas être vide.'; el.style.color = 'var(--red)'; return; }
  el.textContent = 'Diffusion…'; el.style.color = 'var(--text3)';
  try {
    var r = await fetch('/admin/api/wf-message', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: text, color: color, until: wfUntil()})
    });
    var d = await r.json();
    if (d.ok) {
      el.textContent = '✓ En ligne ! Tous les auditeurs le verront sous 10 s.';
      el.style.color = 'var(--green)';
      var a = document.getElementById('wfmsg-active');
      if (a) { a.textContent = text + wfUntilText(wfUntil()); a.style.color = 'var(--green)'; }
      toast('Message waterfall diffusé');
    } else {
      el.textContent = '✗ ' + (d.msg || 'Erreur'); el.style.color = 'var(--red)';
    }
  } catch(e) { el.textContent = '✗ Erreur réseau : ' + e.message; el.style.color = 'var(--red)'; }
}

async function clearWfMsg() {
  var el = document.getElementById('wfmsg-status');
  el.textContent = 'Effacement…'; el.style.color = 'var(--text3)';
  try {
    await fetch('/admin/api/wf-message', {method: 'DELETE'});
    el.textContent = '✓ Effacé. Le bandeau disparaît sous 10 s.';
    el.style.color = 'var(--text3)';
    var a = document.getElementById('wfmsg-active');
    if (a) { a.textContent = '—'; a.style.color = 'var(--text3)'; }
    toast('Message waterfall effacé');
  } catch(e) { el.textContent = '✗ Erreur réseau'; el.style.color = 'var(--red)'; }
}

async function loadWfMsgStatus() {
  try {
    var r = await fetch('/admin/api/wf-message');
    var d = await r.json();
    var a = document.getElementById('wfmsg-active');
    if (!a) return;
    a.textContent = d.text ? d.text + wfUntilText(d.until) : '—';
    a.style.color  = d.text ? 'var(--green)' : 'var(--text3)';
  } catch(_) {}
}

// ─── Init ────────────────────────────────────────────────────────────────────
loadDashboard();
</script>
<script src="/admin/extras.js"></script>
</body>
</html>"""

# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route("/admin")
@app.route("/admin/")
def login():
    if session.get("authenticated"):
        return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_HTML, error=None)

@app.route("/admin", methods=["POST"])
@app.route("/admin/", methods=["POST"])
def login_post():
    pwd = request.form.get("password", "")
    if check_password(pwd):
        session["authenticated"] = True
        session.permanent = True
        if is_first_run():
            return redirect(url_for("setup"))
        return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_HTML, error="Code d'accès invalide. Réessayez.")

@app.route("/admin/dashboard")
@login_required
def dashboard():
    from flask import make_response
    resp = make_response(render_template_string(MAIN_HTML, fork_origin=fork_origin(),
                                                origin_repo=ORIGIN_REPO))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin/setup")
def setup():
    if not session.get("authenticated"):
        return redirect(url_for("login"))
    if not is_first_run():
        return redirect(url_for("dashboard"))
    from flask import make_response
    resp = make_response(render_template_string(SETUP_HTML))
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.route("/admin/api/autodetect")
def api_autodetect():
    if not session.get("authenticated"):
        return jsonify({"ok": False}), 403
    return jsonify({"ok": True, "candidates": auto_detect_sdr_candidates()})

@app.route("/admin/api/setup", methods=["POST"])
def api_setup():
    if not session.get("authenticated"):
        return jsonify({"ok": False, "msg": "Non authentifié"}), 403
    if not is_first_run():
        return jsonify({"ok": False, "msg": "Configuration déjà effectuée"})
    data = request.get_json(silent=True) or {}
    sdr_dir   = data.get("sdr_base_dir", "").strip()
    proc_name = (data.get("sdr_process_name", "spectrumserver") or "spectrumserver").strip()
    try:
        public_port = int(data.get("public_port", 8900))
    except (ValueError, TypeError):
        public_port = 8900
    new_password = data.get("new_password", "")
    if not sdr_dir:
        return jsonify({"ok": False, "msg": "Le répertoire de base SDR est obligatoire"})
    if len(new_password) < MIN_PASSWORD_LEN or new_password.lower() == "admin":
        return jsonify({"ok": False, "msg": f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LEN} caractères"})
    cfg = load_admin_config()
    if cfg.get("proxy_port") and public_port == int(cfg["proxy_port"]):
        return jsonify({"ok": False, "msg": f"Port {public_port} est le port public du proxy. "
                        "Indiquez le port propre à spectrumserver (port de [server] dans sa config)."})
    cfg["sdr_base_dir"]     = sdr_dir
    cfg["sdr_process_name"] = proc_name
    cfg["public_port"]      = public_port
    cfg["password_hash"]    = hash_password(new_password)
    cfg["setup_complete"]   = True
    save_admin_config(cfg)
    return jsonify({"ok": True})


# ── API: Status ──────────────────────────────────────────────────────────────
@app.route("/admin/api/status")
@login_required
def api_status():
    try:
        return jsonify({"process": get_process_status(),
                        "system": get_system_stats(),
                        "top_procs": get_top_processes()})
    except Exception as e:
        return jsonify({"process": {"running": False, "pid": None, "name": None,
                                    "cpu": 0, "mem": 0, "uptime": None, "error": str(e)},
                        "system": {}, "top_procs": []})

# ── API: Scripts ─────────────────────────────────────────────────────────────
@app.route("/admin/api/scripts")
@login_required
def api_scripts():
    sh = get_allowed_scripts()
    return jsonify({"start": [k for k in sh if "start" in k.lower()],
                    "stop":  [k for k in sh if "stop"  in k.lower()],
                    "all":   sorted(sh.keys()), "paths": sh})

@app.route("/admin/api/scripts/all-discovered")
@login_required
def api_scripts_all():
    sh     = find_sh_files()
    result = [{"label": k, "path": v, "enabled": True} for k, v in sh.items()]
    return jsonify({"scripts": result})

@app.route("/admin/api/scripts/debug")
@login_required
def api_scripts_debug():
    """Shows exactly which scripts were found and where it looked."""
    base = get_sdr_dir()
    sh = find_sh_files()
    freq_dir = base / "frequencylist"
    return jsonify({
        "base_dir": str(base),
        "frequencylist_exists": freq_dir.exists(),
        "frequencylist_contents": [str(f.name) for f in sorted(freq_dir.glob("*"))] if freq_dir.exists() else [],
        "found_scripts": sh,
    })

# ── API: Server control ───────────────────────────────────────────────────────
def _is_plain_cd(cmd):
    """Un « cd » seul est géré par le panneau (le dossier courant est mémorisé) ;
    « cd X && commande », « cd X; commande »… part au shell tel quel."""
    if not (cmd == "cd" or cmd.startswith("cd ") or cmd == "cd~"):
        return False
    return not any(op in cmd for op in ("&", ";", "|", ">", "<", "`", "$("))


@login_required
@app.route("/admin/api/terminal/exec", methods=["POST"])
def api_terminal_exec():
    data = request.get_json(silent=True) or {}
    cmd  = (data.get("cmd") or "").strip()
    # Use sdr_base_dir as default cwd, fallback to /tmp
    default_cwd = str(get_sdr_dir())
    cwd = (data.get("cwd") or "").strip() or default_cwd
    if not os.path.isdir(cwd):
        cwd = default_cwd
    if not cmd:
        return jsonify({"ok": True, "output": "", "cwd": cwd})
    if _is_plain_cd(cmd):
        target = cmd[2:].strip() or "~"
        # Expand ~ and env vars
        target = os.path.expanduser(target)
        target = os.path.expandvars(target)
        if target == "-":
            target = os.environ.get("OLDPWD", cwd)
        new_dir = os.path.realpath(os.path.join(cwd, target) if not os.path.isabs(target) else target)
        if os.path.isdir(new_dir):
            return jsonify({"ok": True, "output": "", "cwd": new_dir})
        return jsonify({"ok": False, "output": "cd: no such directory: " + target, "cwd": cwd})
    if cmd.strip() in ("clear", "cls"):
        return jsonify({"ok": True, "output": "__CLEAR__", "cwd": cwd})
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=300, env={**os.environ, "TERM": "xterm"}
        )
        return jsonify({"ok": result.returncode == 0, "output": result.stdout or "(no output)", "cwd": cwd})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "output": "(command timed out after 300s)", "cwd": cwd})
    except Exception as ex:
        return jsonify({"ok": False, "output": str(ex), "cwd": cwd})

# ── Terminal : commandes longues en tâche de fond (sortie en direct) ─────────
# /terminal/exec attend la fin de la commande dans une seule requête HTTP ; or
# proxy.py coupe toute requête vers le panneau au bout de 60 s (ClientTimeout),
# d'où le « HTTP error: 500 » sur ./recompile.sh --frontend alors que la
# commande, elle, continue et réussit. Ici la commande tourne en tâche de fond :
# le navigateur la lance (start), relève la sortie par petites requêtes (poll),
# peut répondre aux questions d'un script (input) et l'interrompre (kill).
# Plus de limite de durée, sortie affichée au fil de l'eau.
_TERM_JOBS = {}
_TERM_LOCK = threading.Lock()
_TERM_MAX_OUT = 2 * 1024 * 1024          # sortie gardée par commande (octets)
_TERM_KEEP_S  = 600                      # une commande finie est oubliée après 10 min
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\x1b[()][A-Z0-9]")

def _term_reader(job):
    fd = job["fd"]
    while True:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        text = chunk.decode("utf-8", "replace")
        text = _ANSI_RE.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
        with job["lock"]:
            job["out"] += text
            if len(job["out"]) > _TERM_MAX_OUT:
                cut = len(job["out"]) - _TERM_MAX_OUT
                job["out"] = job["out"][cut:]
                job["base"] += cut
    rc = job["proc"].wait()
    try:
        os.close(fd)
    except OSError:
        pass
    with job["lock"]:
        job["rc"] = rc
        job["done"] = True
        job["ended"] = time.time()

def _term_gc():
    now = time.time()
    with _TERM_LOCK:
        for jid in [j for j, v in _TERM_JOBS.items()
                    if v["done"] and now - v["ended"] > _TERM_KEEP_S]:
            _TERM_JOBS.pop(jid, None)

@app.route("/admin/api/terminal/start", methods=["POST"])
@login_required
def api_terminal_start():
    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").strip()
    default_cwd = str(get_sdr_dir())
    cwd = (data.get("cwd") or "").strip() or default_cwd
    if not os.path.isdir(cwd):
        cwd = default_cwd
    # cd, clear et commande vide : réponse immédiate, comme /terminal/exec
    if not cmd or cmd in ("clear", "cls") or _is_plain_cd(cmd):
        return api_terminal_exec()
    _term_gc()
    env = {**os.environ, "TERM": "dumb", "PYTHONUNBUFFERED": "1", "NO_COLOR": "1",
           "COLUMNS": "160", "LINES": "50"}
    # Pseudo-terminal : les scripts se croient dans un vrai terminal, donc
    # « read -p » affiche sa question, la sortie arrive ligne par ligne au lieu
    # d'être retenue en tampon, et sudo peut demander son mot de passe.
    import pty, termios, fcntl, struct
    master, slave = pty.openpty()
    try:
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~termios.ECHO            # le navigateur affiche déjà la saisie
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 160, 0, 0))
    except Exception:
        pass
    def _ctty():
        os.setsid()
        try:
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        except Exception:
            pass
    try:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=cwd, executable="/bin/bash",
            stdin=slave, stdout=slave, stderr=slave,
            env=env, preexec_fn=_ctty, close_fds=True,
        )
    except Exception as ex:
        os.close(master); os.close(slave)
        return jsonify({"ok": False, "output": str(ex), "cwd": cwd})
    os.close(slave)
    jid = "%d-%d" % (int(time.time() * 1000), proc.pid)
    job = {"proc": proc, "fd": master, "out": "", "base": 0, "done": False, "rc": None,
           "ended": 0, "lock": threading.Lock(), "cmd": cmd}
    with _TERM_LOCK:
        _TERM_JOBS[jid] = job
    threading.Thread(target=_term_reader, args=(job,), daemon=True).start()
    return jsonify({"ok": True, "id": jid, "cwd": cwd})

@app.route("/admin/api/terminal/poll")
@login_required
def api_terminal_poll():
    job = _TERM_JOBS.get(request.args.get("id", ""))
    if not job:
        return jsonify({"ok": False, "gone": True, "output": "", "pos": 0, "done": True})
    try:
        pos = int(request.args.get("pos", "0"))
    except ValueError:
        pos = 0
    with job["lock"]:
        start = max(pos - job["base"], 0)
        out = job["out"][start:]
        newpos = job["base"] + len(job["out"])
        lost = pos < job["base"]
        return jsonify({"ok": True, "output": out, "pos": newpos, "lost": lost,
                        "done": job["done"], "rc": job["rc"]})

@app.route("/admin/api/terminal/input", methods=["POST"])
@login_required
def api_terminal_input():
    data = request.get_json(silent=True) or {}
    job = _TERM_JOBS.get(data.get("id", ""))
    if not job or job["done"]:
        return jsonify({"ok": False, "msg": "commande terminée"})
    try:
        os.write(job["fd"], (str(data.get("text", "")) + "\n").encode("utf-8"))
    except Exception as ex:
        return jsonify({"ok": False, "msg": str(ex)})
    return jsonify({"ok": True})

@app.route("/admin/api/terminal/kill", methods=["POST"])
@login_required
def api_terminal_kill():
    data = request.get_json(silent=True) or {}
    job = _TERM_JOBS.get(data.get("id", ""))
    if not job or job["done"]:
        return jsonify({"ok": False})
    pid = job["proc"].pid
    def _kill():
        for sig, wait in ((signal.SIGINT, 3), (signal.SIGTERM, 3), (signal.SIGKILL, 0)):
            try:
                os.killpg(pid, sig)
            except Exception:
                return
            t0 = time.time()
            while time.time() - t0 < wait:
                if job["done"]:
                    return
                time.sleep(0.2)
    threading.Thread(target=_kill, daemon=True).start()
    return jsonify({"ok": True})

# ── API: Config files ─────────────────────────────────────────────────────────
@app.route("/admin/api/config-files")
@login_required
def api_config_files():
    return jsonify(get_allowed_configs())

@app.route("/admin/api/editable-files")
@login_required
def api_editable_files():
    return jsonify(find_editable_files())

@app.route("/admin/api/config-files/all-discovered")
@login_required
def api_config_files_all():
    cf     = find_config_files_all()
    result = [{"label": k, "path": v, "enabled": True} for k, v in cf.items()]
    return jsonify({"configs": result})

@app.route("/admin/api/json-files")
@login_required
def api_json_files():
    return jsonify(find_json_files())

@app.route("/admin/api/read-file")
@login_required
def api_read_file():
    path = request.args.get("path", "")
    if not path:
        return jsonify({"content": ""})
    # Security: must be within base dir
    base = get_sdr_dir()
    try:
        p = Path(path).resolve()
        p.relative_to(base)  # raises if outside
    except (ValueError, Exception):
        return jsonify({"error": "Accès refusé"}), 403
    content = read_file_safe(path)
    return jsonify({"content": content})

@app.route("/admin/api/write-file", methods=["POST"])
@login_required
def api_write_file():
    data = request.get_json(silent=True) or {}
    path = data.get("path", "")
    content = data.get("content", "")
    base = get_sdr_dir()
    try:
        p = Path(path).resolve()
        p.relative_to(base)
    except (ValueError, Exception):
        return jsonify({"ok": False, "msg": "Accès refusé"}), 403
    ok, msg = write_file_safe(path, content)
    return jsonify({"ok": ok, "msg": msg})

# ── API: Markers ──────────────────────────────────────────────────────────────
@app.route("/admin/api/markers", methods=["GET", "POST"])
@login_required
def api_markers():
    base = get_sdr_dir()
    markers_file = base / "markers.json"
    if request.method == "GET":
        try:
            raw = json.loads(read_file_safe(markers_file))
            # Support both {"markers": [...]} and plain [...] formats
            if isinstance(raw, dict) and "markers" in raw:
                data = raw["markers"]
            elif isinstance(raw, list):
                data = raw
            else:
                data = []
        except Exception:
            data = []
        return jsonify({"data": data, "path": str(markers_file)})
    else:
        req = request.get_json(silent=True) or {}
        data = req.get("data", [])
        # Preserve the {"markers": [...]} wrapper format
        output = json.dumps({"markers": data}, indent=2)
        ok, msg = write_file_safe(markers_file, output)
        return jsonify({"ok": ok, "msg": msg})

# ── API: Autorun spot reporting ───────────────────────────────────────────────
# Band/mode matrix mirrors autorun/bandplan.js (kept here so the UI can render
# without importing the JS). 6m is absent: RX888 at 60 MHz → 30 MHz Nyquist.
AUTORUN_BANDS = ["2200m", "630m", "160m", "80m", "80mEU", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"]
AUTORUN_MODES = {
    "ft8":  ["160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"],
    "ft4":  ["80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"],
    # JS8 Normal (15 s) only -- the calling speed, where heartbeats and CQs are.
    "js8":  ["160m", "80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"],
    "wspr": ["2200m", "630m", "160m", "80m", "80mEU", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"],
}

def _autorun_paths():
    base = get_sdr_dir()
    return base, base / "autorun.json", base / "autorun-status.json", base / "autorun.log"


def _autorun_totals():
    """All-time per-slot spot totals, or {} if the daemon has never run.

    Written by the daemon and deliberately NOT deleted on shutdown, unlike the
    status file — these totals are cumulative across restarts.
    """
    path = get_sdr_dir() / "autorun-totals.json"
    try:
        if path.exists():
            d = json.loads(read_file_safe(path))
            return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}

def _resolve_node():
    import shutil as _sh
    n = _sh.which("node")
    if n:
        return n
    for p in sorted(glob.glob(str(Path.home() / ".nvm/versions/node/*/bin/node")), reverse=True):
        return p
    return "node"

def _reporter_grid(g):
    """The locator PSK Reporter and WSPRnet accept: 4 or 6 characters. A finer
    one (KM17VX69JA) is cut to its square; anything else gives ""."""
    s = str(g or "").strip()
    for n in (6, 4):
        if len(s) >= n and re.fullmatch(r"[A-Ra-r]{2}[0-9]{2}([A-Xa-x]{2})?", s[:n]):
            return s[:n]
    return ""

def _autorun_default_identity():
    base = get_sdr_dir()
    call, grid = "", ""
    try:
        si = json.loads(read_file_safe(base / "frontend" / "site_information.json"))
        call = (si.get("siteSysop") or "")
        grid = _reporter_grid(si.get("siteGridSquare"))
    except Exception:
        pass
    return call, grid

def _autorun_running():
    try:
        r = subprocess.run(["pgrep", "-f", r"node .*autorun/index\.js"],
                           capture_output=True, text=True, timeout=3)
        pids = [p for p in r.stdout.split() if p.strip()]
        return (len(pids) > 0), pids
    except Exception:
        return False, []

@app.route("/admin/api/autorun/config", methods=["GET", "POST"])
@login_required
def api_autorun_config():
    base, cfg_path, _, _ = _autorun_paths()
    if request.method == "GET":
        cfg = {}
        if cfg_path.exists():
            try:
                cfg = json.loads(read_file_safe(cfg_path))
            except Exception:
                cfg = {}
        def_call, def_grid = _autorun_default_identity()
        ident = cfg.get("identity") or {}
        rep = cfg.get("reporting") or {}
        return jsonify({
            "config": {
                "identity": {
                    "callsign": ident.get("callsign") or def_call,
                    "grid": ident.get("grid") or def_grid,
                },
                "reporting": {"pskreporter": bool(rep.get("pskreporter", False)),
                              "wsprnet": bool(rep.get("wsprnet", False))},
                "maxSlots": int(cfg.get("maxSlots", 12)),
                "slots": cfg.get("slots", []),
            },
            "defaults": {"callsign": def_call, "grid": def_grid},
            "bands": AUTORUN_BANDS,
            "modes": AUTORUN_MODES,
        })
    req = request.get_json(silent=True) or {}
    slots = []
    for s in (req.get("slots") or []):
        band, mode = s.get("band"), s.get("mode")
        if mode in AUTORUN_MODES and band in AUTORUN_MODES[mode]:
            slots.append({"band": band, "mode": mode, "enabled": bool(s.get("enabled"))})
    try:
        max_slots = max(1, min(64, int(req.get("maxSlots", 12))))
    except Exception:
        max_slots = 12
    enabled_count = sum(1 for s in slots if s["enabled"])
    if enabled_count > max_slots:
        return jsonify({"ok": False, "msg": f"{enabled_count} slots activés dépassent la limite de {max_slots}"})
    ident = req.get("identity") or {}
    call = (ident.get("callsign") or "").strip().upper()
    grid_in = (ident.get("grid") or "").strip()
    grid = _reporter_grid(grid_in)
    if not re.match(r'^[A-Z0-9/]{3,12}$', call):
        return jsonify({"ok": False, "msg": "format d'indicatif invalide"})
    # The reporters refuse spots with any other locator, so it is 4 or 6
    # characters (KM17 or KM17VX) or nothing.
    if grid_in and not grid:
        return jsonify({"ok": False, "msg": "le locator doit faire 4 ou 6 caractères, ex. IN93 ou IN93KS"})
    rep = req.get("reporting") or {}
    out = {
        "identity": {"callsign": call, "grid": grid},
        "reporting": {"pskreporter": bool(rep.get("pskreporter", False)),
                      "wsprnet": bool(rep.get("wsprnet", False))},
        "maxSlots": max_slots,
        "slots": slots,
    }
    # Optional manual CPU-pin override (advanced; usually absent). Accept a
    # taskset core list or none/off/unpinned, else drop it. Preserve any value
    # already in autorun.json when the request doesn't carry one, so hand-edits
    # and the env/auto paths keep working across a Save.
    cores = req.get("cores")
    if cores is None and cfg_path.exists():
        try:
            cores = (json.loads(read_file_safe(cfg_path)) or {}).get("cores")
        except Exception:
            cores = None
    if cores is not None:
        cores = str(cores).strip()
        if cores.lower() in ("none", "off", "unpinned"):
            out["cores"] = "none"
        elif _CORELIST_RE.match(cores):
            out["cores"] = cores
        # anything else: silently omit (invalid)
    ok, msg = write_file_safe(cfg_path, json.dumps(out, indent=2))
    return jsonify({"ok": ok, "msg": msg if not ok else "enregistré"})

@app.route("/admin/api/autorun/status")
@login_required
def api_autorun_status():
    _, _, status_path, _ = _autorun_paths()
    running, pids = _autorun_running()
    status = {}
    if status_path.exists():
        try:
            status = json.loads(read_file_safe(status_path))
        except Exception:
            status = {}
    return jsonify({"running": running, "pids": pids, "status": status,
                    "totals": _autorun_totals()})

_CORELIST_RE = re.compile(r'^\d+([-,]\d+)*$')  # e.g. "2-3", "0,2,4", "0-2,5"

def _autorun_cores_override():
    """Manual core override for the autorun pin, or None if not set.

    Precedence: AUTORUN_CORES env var, else the "cores" field in autorun.json.
    Useful on CPUs where the auto-derived range isn't ideal (AMD CCX/CCD, ARM
    big.LITTLE, interleaved SMT). Accepts a taskset -c list ("2-3", "0,2,4") or
    one of none/off/unpinned to force no pinning. Malformed values are ignored
    (falls back to auto) so a typo can't stop the daemon from launching.
    """
    val = os.environ.get("AUTORUN_CORES")
    if val is None:
        try:
            _, cfg_path, _, _ = _autorun_paths()
            if cfg_path.exists():
                val = (json.loads(read_file_safe(cfg_path)) or {}).get("cores")
        except Exception:
            val = None
    if val is None:
        return None
    val = str(val).strip()
    if val.lower() in ("none", "off", "unpinned", ""):
        return ""  # explicit "do not pin"
    return val if _CORELIST_RE.match(val) else None

def _autorun_taskset_prefix():
    """taskset prefix (list) pinning the autorun daemon to the top CPU cores.

    A manual override (see _autorun_cores_override) wins if set: a core list
    pins there, an empty override forces unpinned. Otherwise auto-derive:
    returns [] (unpinned) when taskset is unavailable or the machine is too
    small to segregate — a 4-core i5 shares all cores with spectrumserver, and
    naming cores that don't exist would make taskset fail to launch. Otherwise
    reserves the top few cores for the daemon: 4 on a >=12-thread CPU (the E-cores
    on a 4P+HT/4E part -> 8-11, matching the original hardcode), fewer on smaller
    CPUs. spectrumserver is pinned to 0-7 by xgo.sh, so the top cores stay clear.
    """
    import shutil as _sh
    if not _sh.which("taskset"):
        return []
    override = _autorun_cores_override()
    if override is not None:
        return ["taskset", "-c", override] if override else []
    n = os.cpu_count() or 0
    if n <= 4:
        return []  # can't segregate — let the scheduler balance across cores
    count = 4 if n >= 12 else max(1, n // 4)
    lo, hi = n - count, n - 1
    spec = f"{lo}-{hi}" if count > 1 else str(lo)
    return ["taskset", "-c", spec]

@app.route("/admin/api/autorun/start", methods=["POST"])
@login_required
def api_autorun_start():
    base, cfg_path, _, log_path = _autorun_paths()
    running, _ = _autorun_running()
    if running:
        return jsonify({"ok": False, "msg": "déjà en marche"})
    if not cfg_path.exists():
        return jsonify({"ok": False, "msg": "enregistrez d'abord la configuration"})
    try:
        cfg = json.loads(read_file_safe(cfg_path))
        if not any(s.get("enabled") for s in cfg.get("slots", [])):
            return jsonify({"ok": False, "msg": "aucune bande/mode activé"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"configuration invalide : {e}"})
    index_js = base / "autorun" / "index.js"
    if not index_js.exists():
        return jsonify({"ok": False, "msg": "autorun/index.js introuvable"})
    node = _resolve_node()
    # Pin the daemon to the top CPU cores so decode bursts stay off the lower
    # cores spectrumserver prefers (xgo.sh pins it to 0-7). Config-aware: on a
    # 4P+HT/4E box this yields the E-cores (8-11), on smaller CPUs it shrinks the
    # range, and on a 4-core (or fewer) machine it launches unpinned rather than
    # naming cores that don't exist (which would make taskset fail to start).
    cmd = _autorun_taskset_prefix() + [node, str(index_js)]
    try:
        logf = open(log_path, "a")
        proc = subprocess.Popen(cmd, cwd=str(base), stdout=logf,
                                stderr=subprocess.STDOUT, start_new_session=True)
        return jsonify({"ok": True, "msg": f"démarré (PID {proc.pid})", "pid": proc.pid})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route("/admin/api/autorun/totals/reset", methods=["POST"])
@login_required
def api_autorun_totals_reset():
    """Clear the all-time per-slot spot totals.

    The daemon holds these in memory and rewrites the file every 15s and again
    on shutdown, so deleting it under a live daemon just brings the numbers
    straight back. Stop first, wait for the process to actually exit — its
    shutdown handler writes the totals one last time — and only then delete.
    """
    running, pids = _autorun_running()
    if running:
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass
        deadline = time.time() + 15
        while time.time() < deadline:
            time.sleep(0.5)
            if not _autorun_running()[0]:
                break
        else:
            return jsonify({"ok": False, "msg": "le démon ne s'est pas arrêté ; compteurs conservés"})

    path = get_sdr_dir() / "autorun-totals.json"
    try:
        if path.exists():
            path.unlink()
        return jsonify({"ok": True, "msg": "compteurs remis à zéro", "was_running": running})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"impossible de remettre les compteurs à zéro : {e}"})


@app.route("/admin/api/autorun/stop", methods=["POST"])
@login_required
def api_autorun_stop():
    running, pids = _autorun_running()
    if not running:
        return jsonify({"ok": False, "msg": "pas en marche"})
    killed = []
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGTERM)
            killed.append(pid)
        except Exception:
            pass
    return jsonify({"ok": True, "msg": f"PID arrêté(s) : {','.join(killed)}"})

# ── API: Logs ─────────────────────────────────────────────────────────────────
@app.route("/admin/api/logs")
@login_required
def api_logs():
    log_name = request.args.get("name", "logwebsdr.txt")
    if log_name not in LOG_FILES:
        return jsonify({"ok": False, "msg": "Journal inconnu", "available": list(LOG_FILES.keys()), "lines": []}), 400
    lines = tail_log(150, log_name)
    return jsonify({"ok": True, "name": log_name, "available": list(LOG_FILES.keys()), "lines": lines})

@app.route("/admin/api/logs/clear", methods=["POST"])
@login_required
def api_logs_clear():
    global log_buffer
    # Clear in-memory buffer
    with log_lock:
        log_buffer.clear()
    # Truncate the log files defined in LOG_FILES, except CLEAR_EXCLUDE
    base = get_sdr_dir()
    cleared = []
    skipped = []
    failed = []
    for log_name, log_path in LOG_FILES.items():
        if log_name in CLEAR_EXCLUDE:
            skipped.append(log_name)
            continue
        lf = base / log_path
        if not lf.exists():
            continue
        try:
            # Truncate in place rather than unlink: systemd holds these open
            # with StandardOutput=append: (O_APPEND), so a deleted file would
            # keep filling an unlinked inode until the service restarts.
            with open(lf, "r+") as f:
                f.truncate(0)
            cleared.append(log_name)
        except Exception as e:
            failed.append({"name": log_name, "error": str(e)})
    return jsonify({"ok": not failed, "cleared": cleared,
                    "skipped": skipped, "failed": failed})

# ── Chat admin IPC ────────────────────────────────────────────────────────────
# Communicates with the Unix domain socket started by ChatClient::start_admin_listener()
# inside spectrumserver.  This lets the admin panel send real-time commands
# (currently: DELETE) to the running C++ process without restarting it.

import socket as _socket

CHAT_ADMIN_SOCK = "/tmp/phantomsdr_chat.sock"

def _send_chat_admin_cmd(cmd: str, sock_path: str = CHAT_ADMIN_SOCK):
    """Send a single newline-terminated command to spectrumserver's chat socket.

    Returns (True, "ok") on success, or (False, error_message) on failure.
    """
    try:
        with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(sock_path)
            s.sendall((cmd + "\n").encode())
        return True, "ok"
    except FileNotFoundError:
        return False, "Socket admin du chat introuvable — spectrumserver est-il lancé ?"
    except _socket.timeout:
        return False, "Délai dépassé en se connectant au socket admin du chat"
    except Exception as e:
        return False, str(e)


# ── API: Chat ─────────────────────────────────────────────────────────────────
def _chat_sources():
    """(label, chat_history.txt, admin socket) for every receiver. Each
    spectrumserver writes chat_history.txt in its own working directory: the
    main receiver in the base dir, a named instance in instances/<name>/, with
    its admin socket at /tmp/phantomsdr_chat-<name>.sock (spectrumserver.cpp)."""
    base = get_sdr_dir()
    rxs = _receivers_toml().get("receiver", [])
    main_label = ""
    out = []
    for r in rxs:
        inst = str(r.get("instance") or "").strip()
        label = str(r.get("id") or inst).upper()
        if not inst or inst == "main":
            main_label = label
            continue
        out.append((label, base / "instances" / inst / "chat_history.txt",
                    "/tmp/phantomsdr_chat-%s.sock" % inst))
    return [(main_label, base / "chat_history.txt", CHAT_ADMIN_SOCK)] + out

def _chat_source(rx):
    """The _chat_sources() entry for label rx; the main receiver when empty."""
    srcs = _chat_sources()
    for src in srcs:
        if src[0] == (rx or "").upper():
            return src
    return srcs[0] if not rx else None

def _parse_chat_line(line):
    # Try parse: [time] <nick> msg  or  nick: msg
    m = re.match(r'\[([^\]]+)\]\s+<([^>]+)>\s+(.*)', line)
    if m:
        return {"time": m.group(1), "nick": m.group(2), "msg": m.group(3), "raw": line}
    m2 = re.match(r'(\S+):\s+(.*)', line)
    if m2:
        return {"time": "", "nick": m2.group(1), "msg": m2.group(2), "raw": line}
    return {"time": "", "nick": "system", "msg": line, "raw": line}

@app.route("/admin/api/chat")
@login_required
def api_chat():
    """Every receiver's chat history, each message tagged with its receiver."""
    messages = []
    srcs = _chat_sources()
    for label, chat_file, _sock in srcs:
        if not chat_file.exists():
            continue
        try:
            with open(chat_file, encoding="utf-8", errors="replace") as f:
                for line in f.readlines()[-200:]:
                    line = line.strip()
                    if line:
                        m = _parse_chat_line(line)
                        m["rx"] = label
                        messages.append(m)
        except Exception as e:
            messages.append({"time": "", "nick": "error", "msg": "%s: %s" % (label or "chat", e), "rx": label})
    # The lines start with "YYYY-MM-DD HH:MM:SS", so a stable sort on the raw
    # text interleaves the receivers in time order.
    if len(srcs) > 1:
        messages.sort(key=lambda m: m.get("raw", ""))
    return jsonify({"messages": messages, "multi": len(srcs) > 1})

@app.route("/admin/api/chat/clear", methods=["POST"])
@login_required
def api_chat_clear():
    data = request.get_json(silent=True) or {}
    src = _chat_source(data.get("rx", ""))
    if not src:
        return jsonify({"ok": False, "msg": "Récepteur inconnu"})
    try:
        with open(src[1], "w") as f:
            f.write("")
        return jsonify({"ok": True, "msg": "Historique du chat effacé"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route("/admin/api/chat/delete", methods=["POST"])
@login_required
def api_chat_delete():
    """Delete a single chat message in real time.

    Expects JSON body: {"line": "<full formatted message string>"}
    The 'line' value must match exactly what is stored in chat_history.txt
    (i.e. the 'raw' field returned by /admin/api/chat).

    Sends a DELETE command to spectrumserver via the admin Unix socket.
    spectrumserver removes the message from its in-memory deque, rewrites
    chat_history.txt, and broadcasts a __CHAT_DELETE__ frame to all connected
    chat clients so their UI updates instantly.
    """
    data = request.get_json(silent=True) or {}
    line = data.get("line", "").strip()
    if not line:
        return jsonify({"ok": False, "msg": "Aucune ligne indiquée"})
    # Each receiver has its own spectrumserver and its own admin socket.
    src = _chat_source(data.get("rx", ""))
    if not src:
        return jsonify({"ok": False, "msg": "Récepteur inconnu"})
    ok, msg = _send_chat_admin_cmd("DELETE:" + line, src[2])
    return jsonify({"ok": ok, "msg": msg})

# ── Waterfall Message — static file helper ─────────────────────────────────────
# The message is written as wf-message.json into the frontend/dist directory
# (the same folder spectrumserver already serves statically).
# The browser fetches /wf-message.json directly from spectrumserver — no proxy,
# no auth, no routing issues whatsoever.

def _wf_write_file(text: str, color: str, until: float = 0) -> str:
    """Write wf-message.json to every likely web-root location.
    Returns a summary string of files written (for logging).
    """
    import json as _json
    obj = {"text": text, "color": color}
    if until:
        obj["until"] = int(until)        # epoch (s) : le message disparaît seul
    payload = _json.dumps(obj)
    candidates = [
        BASE_DIR / "frontend" / "dist",
        BASE_DIR / "frontend" / "public",
        BASE_DIR / "public",
        BASE_DIR / "dist",
        get_sdr_dir() / "frontend" / "dist",
        get_sdr_dir() / "frontend" / "public",
        get_sdr_dir() / "public",
    ]
    written = []
    seen = set()
    for d in candidates:
        d = d.resolve()
        if d in seen or not d.is_dir():
            continue
        seen.add(d)
        try:
            target = d / "wf-message.json"
            target.write_text(payload, encoding="utf-8")
            written.append(str(target))
        except Exception as e:
            print(f"[wf-msg] Could not write {d}/wf-message.json: {e}")
    return ", ".join(written) if written else "nowhere (no candidate dir found)"


def _wf_expiry_loop():
    """Efface le message à sa date de fin, y compris après un redémarrage du
    panneau (la date est relue dans wf-message.json)."""
    import json as _json
    while True:
        time.sleep(20)
        try:
            with _wf_message_lock:
                until = _wf_message.get("until", 0)
            if not until:
                f = BASE_DIR / "frontend" / "dist" / "wf-message.json"
                if f.is_file():
                    d = _json.loads(f.read_text(encoding="utf-8") or "{}")
                    if d.get("text") and d.get("until"):
                        until = d["until"]
                        with _wf_message_lock:
                            _wf_message.update({"text": d["text"], "color": d.get("color", "#ffffff"),
                                                "until": until})
            if until and time.time() >= until:
                with _wf_message_lock:
                    _wf_message.update({"text": "", "color": "#ffffff", "until": 0})
                print(f"[wf-msg] EXPIRED → {_wf_write_file('', '#ffffff')}")
        except Exception as e:
            print(f"[wf-msg] expiry check: {e}")


threading.Thread(target=_wf_expiry_loop, daemon=True, name="wf-expiry").start()


# ── API: Waterfall Message ─────────────────────────────────────────────────────
@app.route("/admin/api/wf-message", methods=["GET"])
def api_wf_message_get():
    """Public fallback — no @login_required.  The frontend normally reads the
    static /wf-message.json; this endpoint is kept for diagnostics.
    """
    with _wf_message_lock:
        m = dict(_wf_message)
    return jsonify({"text": m.get("text", ""), "color": m.get("color", "#ffffff"),
                    "until": m.get("until", 0)})


@app.route("/admin/api/wf-message", methods=["POST"])
@login_required
def api_wf_message_post():
    """Set the waterfall message (admin only).
    Body JSON: {"text": "...", "color": "#ffffff"}
    """
    data  = request.get_json(silent=True) or {}
    text  = (data.get("text") or "").strip()[:200]
    color = data.get("color", "#ffffff")
    if not text:
        return jsonify({"ok": False, "msg": "Message vide"})
    try:
        until = float(data.get("until") or 0)
    except (TypeError, ValueError):
        until = 0
    if until and until <= time.time():
        return jsonify({"ok": False, "msg": "La date de fin est déjà passée"})
    with _wf_message_lock:
        _wf_message.update({"text": text, "color": color, "until": until})
    written = _wf_write_file(text, color, until)
    print(f"[wf-msg] SET '{text}' → {written}")
    return jsonify({"ok": True, "written": written})


@app.route("/admin/api/wf-message", methods=["DELETE"])
@login_required
def api_wf_message_delete():
    """Clear the waterfall message (admin only)."""
    with _wf_message_lock:
        _wf_message.update({"text": "", "color": "#ffffff", "until": 0})
    written = _wf_write_file("", "#ffffff")
    print(f"[wf-msg] CLEARED → {written}")
    return jsonify({"ok": True})


# ── API: Settings ─────────────────────────────────────────────────────────────
@app.route("/admin/api/settings", methods=["GET", "POST"])
@login_required
def api_settings():
    cfg = load_admin_config()
    if request.method == "GET":
        out = {
            "sdr_base_dir":  cfg.get("sdr_base_dir", str(BASE_DIR)),
            "start_script":  cfg.get("start_script", ""),
            "stop_script":   cfg.get("stop_script", ""),
            "public_port":   cfg.get("public_port", 8900),
        }
        if HAS_THERMAL:
            for k, v in thermal_guard.DEFAULTS.items():
                out[k] = cfg.get(k, v)
        return jsonify(out)
    data = request.get_json(silent=True) or {}
    if HAS_THERMAL:
        # Temperatures are floats and may be left blank ("auto" = derive from the
        # machine's own critical trip point); the rest are whole seconds/counts.
        temp_keys = {"thermal_warn", "thermal_throttle", "thermal_stop",
                     "thermal_resume", "thermal_test_temp"}
        for k in thermal_guard.DEFAULTS:
            if k not in data:
                continue
            v = data[k]
            if k == "thermal_enabled":
                cfg[k] = bool(v)
            elif k == "thermal_mode":
                if str(v) in thermal_guard.MODE_RANK:
                    cfg[k] = str(v)
            elif v in (None, "", "auto"):
                cfg[k] = None
            else:
                try:
                    cfg[k] = float(v) if k in temp_keys else int(v)
                except (TypeError, ValueError):
                    pass
    if "sdr_base_dir" in data:
        cfg["sdr_base_dir"] = data["sdr_base_dir"]
    if "start_script" in data:
        cfg["start_script"] = data["start_script"]
    if "stop_script" in data:
        cfg["stop_script"] = data["stop_script"]
    if "public_port" in data:
        try:
            pp = int(data["public_port"])
        except (ValueError, TypeError):
            pp = None
        if pp is not None:
            if cfg.get("proxy_port") and pp == int(cfg["proxy_port"]):
                return jsonify({"ok": False, "msg": f"Port {pp} est le port public du proxy. "
                                "Indiquez le port propre à spectrumserver (port de [server] dans sa config)."})
            cfg["public_port"] = pp
    save_admin_config(cfg)
    return jsonify({"ok": True})

# ── API: WebSDR diversity relay ──────────────────────────────────────────────
# The relay is a separate process (websdr_relay.py) that lets receive diversity
# use a WebSDR as the second receiver. It is optional and often not installed,
# so every failure here is reported as a state to show, never as an error: a
# missing config file means "not set up", a refused connection means "not
# running", and both are normal.
@app.route("/admin/api/websdr-relay")
@login_required
def api_websdr_relay():
    import urllib.request
    import urllib.error

    cfg_path = BASE_DIR / "websdr_relay.json"
    if not cfg_path.exists():
        return jsonify({"configured": False,
                        "reason": "websdr_relay.json not found — "
                                  "run ./setup_websdr_relay.sh"})
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return jsonify({"configured": False, "reason": f"websdr_relay.json: {e}"})

    port = int(cfg.get("port", 8898))
    out = {"configured": True, "port": port, "running": False,
           "site": cfg.get("site", ""), "operator": cfg.get("operator", ""),
           "max_per_host": cfg.get("max_per_host"), "max_total": cfg.get("max_total")}

    # Always loopback: the relay binds every interface, but asking it through
    # the public address would depend on the router's hairpin NAT and could
    # report "down" for a relay that is perfectly healthy.
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2) as r:
            live = json.loads(r.read().decode("utf-8"))
        out["running"] = True
        out["user_agent"] = live.get("user_agent", "")
        out["sessions"] = live.get("sessions", {})
        # The live values win: someone may have edited the config without
        # restarting, and what the relay is actually enforcing is what matters.
        for k in ("max_per_host", "max_total"):
            if live.get(k) is not None:
                out[k] = live[k]
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as e:
        out["reason"] = str(getattr(e, "reason", e))

    return jsonify(out)


@app.route("/admin/api/thermal", methods=["GET", "POST"])
@login_required
def api_thermal():
    if not HAS_THERMAL:
        return jsonify({"available": False, "reason": "thermal_guard.py not loaded"})
    if request.method == "POST":
        act = (request.get_json(silent=True) or {}).get("action")
        if act == "reset":
            thermal_guard.reset()
            return jsonify({"ok": True, "msg": "Blocage thermique levé"})
        return jsonify({"ok": False, "msg": "Action inconnue"})
    st = thermal_guard.status()
    st["available"] = True
    return jsonify(st)


@app.route("/admin/api/change-password", methods=["POST"])
@login_required
def api_change_password():
    data = request.get_json(silent=True) or {}
    old = data.get("old", "")
    new_pwd = data.get("new_pwd", "")
    if not check_password(old):
        return jsonify({"ok": False, "msg": "Mot de passe actuel incorrect"})
    if len(new_pwd) < MIN_PASSWORD_LEN or new_pwd.lower() == "admin":
        return jsonify({"ok": False, "msg": f"Mot de passe trop court (minimum {MIN_PASSWORD_LEN} caractères)"})
    cfg = load_admin_config()
    cfg["password_hash"] = hash_password(new_pwd)
    save_admin_config(cfg)
    return jsonify({"ok": True})

# ── API: Stats history (Graphs page) ──────────────────────────────────────────
@app.route("/admin/api/graph-stats")
@login_required
def api_graph_stats():
    """Sampled CPU/user history for the Graphs page.

    ?since=<epoch> returns only newer points so the page polls incrementally
    instead of re-downloading the whole buffer every tick.
    """
    def _arg(name, default):
        try:
            return int(request.args.get(name, default))
        except (TypeError, ValueError):
            return default

    since = _arg("since", 0)
    rng   = max(60, min(GRAPH_HISTORY_S, _arg("range", GRAPH_FINE_S)))

    # A range the fine tier cannot cover in full has to come from the coarse
    # tier, otherwise the plot would silently stop at the fine tier's horizon
    # and look like the server had been down.
    coarse = rng > GRAPH_FINE_S
    interval = GRAPH_COARSE_INTERVAL_S if coarse else GRAPH_INTERVAL_S
    cutoff = int(time.time()) - rng

    with _graph_lock:
        src = _graph_coarse if coarse else _graph_history
        pts = [p for p in src if p["t"] >= cutoff and p["t"] > since]

    _, _, limit = get_cpu_frequency()
    return jsonify({
        "ok": True,
        "interval": interval,
        "retention": rng,
        "coarse": coarse,
        "freq_limit": limit,
        "cores": (psutil.cpu_count() if HAS_PSUTIL else os.cpu_count()),
        "points": pts,
    })


# ── API: Connected users / Kick ───────────────────────────────────────────────
def _get_public_port():
    """Return the PUBLIC port users connect to for 'ss' connection counting.

    When running behind proxy.py this must be proxy_port (e.g. 8902), because
    all connections to spectrumserver's internal port (public_port, e.g. 8900)
    come from 127.0.0.1 (the proxy itself) — real client IPs are invisible there.
    Falls back to public_port for standalone (no-proxy) deployments.
    """
    cfg = load_admin_config()
    return int(cfg.get("proxy_port") or cfg.get("public_port", 8900))

@app.route("/admin/api/sdr-users")
@login_required
def api_sdr_users():
    """Every receiver's /users list merged into one, each listener tagged with
    its receiver. Asked of each spectrumserver directly on loopback: the page
    used to fetch /users through proxy.py, which routes by the listener's rx
    cookie — so after the sysop once opened ?rx=vhf the panel kept showing the
    2 m listeners, even back on HF."""
    import urllib.request
    labels = {}
    for r in _receivers_toml().get("receiver", []):
        try:
            labels[int(r.get("port"))] = str(r.get("id") or "").upper()
        except (TypeError, ValueError):
            continue
    users, seen, errors = [], 0, []
    for port in _sdr_ports():
        label = labels.get(port, "")
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/users" % port, timeout=2) as r:
                d = json.loads(r.read().decode())
        except Exception as e:
            errors.append("%s: %s" % (label or port, e))
            continue
        seen += 1
        for u in d.get("users", []):
            u = dict(u)
            u["rx"] = label
            # Session ids are per server; keep them unique across receivers.
            u["id"] = "%d:%s" % (port, u.get("id", ""))
            users.append(u)
    if not seen:
        return jsonify({"ok": False, "users": [], "error": "; ".join(errors) or "aucun récepteur"})
    return jsonify({"ok": True, "users": users, "multi": len(labels) > 1, "errors": errors})

@app.route("/admin/api/users")
@login_required
def api_users():
    """Return IPs with active connections to the WebSDR.

    Scans BOTH the proxy port (proxy.py) AND the public spectrumserver port,
    because in practice most clients connect straight to spectrumserver and
    bypass the proxy — their real IPs appear as the peer on the SDR port.
    Uses 'ss -tn sport = :PORT' (no -p flag; no privilege needed).

    Loopback and the proxy's own relay IP (sdr_host) are filtered out so the
    proxy's upstream connections to spectrumserver aren't listed as a "user".
    """
    cfg = load_admin_config()
    proxy_port  = int(cfg.get("proxy_port") or 0)
    public_port = int(cfg.get("public_port", 8900))
    # With receivers.toml the listeners' sockets end on its [front] port (the
    # proxy now owns the public port), so that one is scanned as well.
    front_port  = int((_receivers_toml().get("front") or {}).get("port") or 0)
    ports = [p for p in {proxy_port, public_port, front_port} if p]
    # Connections the proxy itself opens to spectrumserver originate from
    # sdr_host — never a real client, so drop them.
    relay_ip = (cfg.get("sdr_host") or "").strip()
    exclude = {"127.0.0.1", "::1", "*", "", relay_ip}
    try:
        ips = {}
        for port in ports:
            # sport and = and :PORT must be SEPARATE argv tokens — a single
            # string like "sport = :8900" is silently ignored by ss execvp.
            r = subprocess.run(
                ["ss", "-tn", "sport", "=", ":%d" % port],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.splitlines()[1:]:   # skip header row
                parts = line.split()
                if len(parts) < 5:
                    continue
                # Column layout: State  Recv-Q  Send-Q  Local:Port  Peer:Port
                peer = parts[4]
                # Handle IPv6-mapped IPv4 like [::ffff:1.2.3.4]:PORT
                ip = peer.rsplit(":", 1)[0].strip("[]")
                if ip.startswith("::ffff:"):
                    ip = ip[7:]
                if ip not in exclude:
                    ips[ip] = ips.get(ip, 0) + 1
        users = [{"ip": ip, "connections": cnt} for ip, cnt in sorted(ips.items())]
        return jsonify({"ok": True, "users": users, "ports": ports})
    except Exception as e:
        return jsonify({"ok": False, "users": [], "error": str(e)})


# ── API : Analyse auditeurs (statistiques privées — panneau admin uniquement) ─
_LI_MAINT = {"t": 0.0}


def _li_maintain():
    if time.time() - _LI_MAINT["t"] > 3600:
        _LI_MAINT["t"] = time.time()
        try:
            LI.maintain()
        except Exception as e:
            print("[WARN] listener stats maintenance: %s" % e, file=sys.stderr)


def _li_recent_usage(days=2):
    """Événements récents de logs/usage_*.jsonl, par auditeur (iph)."""
    by = {}
    for i in range(days - 1, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        for e in LI.read_jsonl(LI.LOGS / ("usage_%s.jsonl" % d)):
            st = by.setdefault(e.get("iph", "?"), {})
            ev = e.get("ev")
            if ev == "visit":
                st["visit"] = e
            elif ev == "hello":
                st["hello"] = e
            elif ev == "decoder":
                st["decoder"] = e
                used = st.setdefault("decoders_used", [])
                dec = (e.get("decoder") or "").upper()
                if dec and dec != "NONE" and dec not in used:
                    used.append(dec)
    return by


@app.route("/admin/api/listeners/live")
@login_required
def api_listeners_live():
    import urllib.request
    usage = _li_recent_usage(2)
    rows, errors = [], []
    for port in _sdr_ports():
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/users" % port, timeout=2) as r:
                d = json.loads(r.read().decode())
        except Exception as e:
            errors.append("%s: %s" % (port, e))
            continue
        for u in d.get("users", []):
            ip = LI.norm_ip(u.get("ip", ""))
            iph = LI.ip_hash(ip)
            g = LI.geo(ip)
            st = usage.get(iph, {})
            vis, hel, dec = st.get("visit", {}), st.get("hello", {}), st.get("decoder", {})
            cur_dec = (dec.get("decoder") or "none")
            rows.append({
                "ip": ip, "iph": iph,
                "city": g.get("city", ""), "region": g.get("regionName", ""),
                "country": g.get("country", ""), "cc": g.get("countryCode", ""),
                "lat": g.get("lat"), "lon": g.get("lon"), "tz_ip": g.get("timezone", ""),
                "isp": g.get("isp", ""), "org": g.get("org", ""), "as": g.get("as", ""),
                "rdns": g.get("rdns", ""), "net": LI.net_kind(g),
                "freq_khz": u.get("freq_khz"), "mode": (u.get("mode") or "").upper(),
                "band": LI.band_of(u.get("freq_hz")),
                "duration": u.get("duration", ""), "duration_s": u.get("duration_s", 0),
                "decoder": "" if cur_dec == "none" else cur_dec.upper(),
                "decoders_used": st.get("decoders_used", []),
                "browser": vis.get("browser") or hel.get("browser", ""),
                "os": vis.get("os") or hel.get("os", ""),
                "device": vis.get("device") or hel.get("device", ""),
                "lang": hel.get("lang") or (vis.get("accept_lang", "")[:5]),
                "tz_browser": hel.get("tz", ""), "screen": hel.get("screen", ""),
                "src": vis.get("src") or hel.get("src", ""),
                "https": bool(vis.get("https") or hel.get("https")),
                "returning": bool(vis.get("returning")),
                "ua": vis.get("ua", ""),
                "port": port,
            })
    LI.flush()
    return jsonify({"ok": True, "users": rows, "errors": errors})


def _li_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict):
            sub = dst.setdefault(k, {})
            for kk, vv in v.items():
                sub[kk] = sub.get(kk, 0) + vv
        elif isinstance(v, (int, float)):
            dst[k] = dst.get(k, 0) + v


@app.route("/admin/api/listeners/stats")
@login_required
def api_listeners_stats():
    _li_maintain()
    try:
        days = max(1, min(3650, int(request.args.get("days", 30))))
    except ValueError:
        days = 30
    agg = LI.load_aggregates()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    start = (datetime.utcnow() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    total, per_day, uniq = {}, [], set()
    have_detail_all = True
    for i in range(days - 1, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        day = LI.aggregate_day(d) if d == today else agg.get(d)
        if day is None:
            continue
        _li_merge(total, day)
        per_day.append({"date": d, "listeners": day.get("listeners", 0),
                        "sessions": day.get("sessions", 0), "listen_s": day.get("listen_s", 0)})
        f = LI.LOGS / ("users_%s.jsonl" % d)
        if f.exists():
            for e in LI.read_jsonl(f):
                uniq.add(LI.ip_hash(e.get("ip", "")))
        else:
            have_detail_all = False
    LI.flush()
    total["unique_listeners"] = len(uniq) if have_detail_all else None
    return jsonify({"ok": True, "days": days, "from": start, "to": today,
                    "total": total, "per_day": per_day,
                    "retention_days": LI.RETENTION_DAYS})


@app.route("/admin/api/listeners/sessions")
@login_required
def api_listeners_sessions():
    try:
        days = max(1, min(LI.RETENTION_DAYS, int(request.args.get("days", 7))))
    except ValueError:
        days = 7
    usage = _li_recent_usage(days)
    sess = {}
    for i in range(days - 1, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        for e in LI.read_jsonl(LI.LOGS / ("users_%s.jsonl" % d)):
            sid = "%s:%s" % (d, e.get("id") or e.get("ip"))
            s = sess.get(sid)
            if s is None:
                ip = e.get("ip", "")
                s = sess[sid] = {"start": e.get("ts", ""), "iph": LI.ip_hash(ip), "_ip": ip,
                                 "dur": 0, "bands": [], "modes": [], "end": ""}
            if e.get("event") == "tune":
                b = LI.band_of(e.get("freq_hz"))
                if b not in s["bands"]:
                    s["bands"].append(b)
                m = (e.get("mode") or "").upper()
                if m and m not in s["modes"]:
                    s["modes"].append(m)
            elif e.get("event") == "disconnect":
                s["dur"] = max(s["dur"], int(e.get("duration_s") or 0))
                s["end"] = e.get("ts", "")
    rows = []
    for s in sorted(sess.values(), key=lambda x: x["start"], reverse=True)[:500]:
        g = LI.geo(s.pop("_ip"), allow_lookup=False)
        st = usage.get(s["iph"], {})
        vis = st.get("visit", {})
        s.update({"city": g.get("city", ""), "country": g.get("country", ""),
                  "cc": g.get("countryCode", ""), "isp": g.get("isp", ""),
                  "rdns": g.get("rdns", ""),
                  "net": LI.net_kind(g), "decoders": st.get("decoders_used", []),
                  "browser": vis.get("browser", ""), "os": vis.get("os", ""),
                  "src": vis.get("src", ""), "returning": bool(vis.get("returning"))})
        rows.append(s)
    return jsonify({"ok": True, "sessions": rows})


# ── Analyse du danger d'une IP (ORSAT) ────────────────────────────────────────
# Poids par catégorie d'événement (plafonnés par IP), puis signatures reconnues
# dans les chemins demandés : chaque élément retenu donne une explication en clair.
_SEC_WEIGHT = {"traversal": (30, 45), "admin_login_fail": (12, 50), "admin_locked": (40, 40),
               "admin_global_lock": (40, 40), "forbidden": (12, 30), "scan": (4, 25),
               "method": (6, 15), "burst404": (5, 15), "admin_country": (8, 20), "blocked": (1, 5)}
_SEC_WHY = {
    "traversal": "a tenté de sortir du site pour lire d'autres fichiers du serveur (../)",
    "admin_login_fail": "a essayé des mots de passe sur le panneau d'administration",
    "admin_locked": "a fait verrouiller le panneau après des échecs répétés",
    "admin_global_lock": "fait partie d'une attaque qui a suspendu le panneau pour tous",
    "forbidden": "a demandé des actions réservées (kick, contrôle du proxy…)",
    "scan": "a demandé des pages typiques de logiciels vulnérables",
    "method": "a utilisé des méthodes HTTP inhabituelles (PUT, DELETE, CONNECT…)",
    "burst404": "a balayé le site en rafale (beaucoup de pages introuvables)",
    "admin_country": "a voulu ouvrir le panneau depuis un pays non autorisé",
    "blocked": "est déjà bannie et continue d'insister",
}
_SEC_SIGS = [
    (re.compile(r"phpunit|eval-stdin|/cgi-bin/|/bin/sh|cmd=|shell|\$\{jndi", re.I), 25,
     "tente d'exécuter du code sur le serveur via une faille connue"),
    (re.compile(r"/etc/passwd|/proc/self|win\.ini", re.I), 25, "tente de lire des fichiers système"),
    (re.compile(r"\.env|\.git|\.aws|config\.json|credentials|\.htpasswd|id_rsa", re.I), 15,
     "cherche des fichiers de configuration contenant mots de passe ou clés"),
    (re.compile(r"containers/json|api/v1/pods|/docker", re.I), 15, "cherche un Docker ou un Kubernetes exposé"),
    (re.compile(r"phpmyadmin|/pma|adminer|mysql|\.sql", re.I), 10, "cherche une base de données ou son interface d'administration"),
    (re.compile(r"/remote/login|sslvpn|dana-na|global-protect|/owa/|/ecp/|autodiscover", re.I), 10,
     "cherche un VPN ou une messagerie d'entreprise vulnérable"),
    (re.compile(r"/actuator|/solr|jenkins|druid|geoserver|telescope|/console|/debug", re.I), 10,
     "cherche une application serveur exposée (Java, Jenkins…)"),
    (re.compile(r"backup|\.bak|\.zip|\.tar", re.I), 8, "cherche des sauvegardes à télécharger"),
    (re.compile(r"wp-login|wp-admin|xmlrpc|wordpress|wp-content", re.I), 3,
     "robot qui cherche un site WordPress à pirater (sans effet ici)"),
]
_SEC_RESEARCH = re.compile(r"shodan|censys|shadowserver|binaryedge|internet-measurement|stretchoid|"
                           r"recyber|onyphe|criminalip|leakix|netcraft|rapid7|internettl|projectdiscovery", re.I)
_SEC_LEVELS = [(15, "faible", "Aucune action nécessaire : le proxy a déjà refusé ces requêtes."),
               (40, "moyen", "À surveiller ; bannir 24 h si cela continue."),
               (80, "élevé", "Bannissement conseillé."),
               (10 ** 9, "critique", "Bannir définitivement.")]


def _sec_assess(x: dict) -> None:
    score, why = 0, []
    for c, n in sorted(x["cats"].items(), key=lambda kv: -kv[1]):
        w, cap = _SEC_WEIGHT.get(c, (0, 0))
        score += min(cap, w * n)
        if c in _SEC_WHY:
            why.append(_SEC_WHY[c] + (" (%d fois)" % n if n > 1 else ""))
    seen = set()
    for pth in x.get("paths", []):
        for rx, bonus, txt in _SEC_SIGS:
            if txt not in seen and rx.search(pth):
                seen.add(txt)
                score += bonus
                why.append(txt)
    if x["count"] >= 200:
        score += 20
        why.append("volume très élevé : %d requêtes suspectes" % x["count"])
    elif x["count"] >= 50:
        score += 10
        why.append("volume élevé : %d requêtes suspectes" % x["count"])
    if x.get("net") in ("datacenter", "vpn"):
        score += 5
        why.append("vient d'un hébergeur ou d'un VPN, pas d'un particulier : typique des robots")
    research = bool(_SEC_RESEARCH.search(x.get("rdns") or ""))
    if research:
        score = min(score, 14)
        why.insert(0, "scanner de recherche connu (il recense Internet) : en général inoffensif")
    for limit, lvl, advice in _SEC_LEVELS:
        if score < limit:
            x["level"], x["advice"] = lvl, advice
            break
    x["score"], x["why"], x["research"] = int(score), why, research


@app.route("/admin/api/security/clear", methods=["POST"])
@login_required
def api_security_clear():
    """Vide le journal des tentatives anormales (la liste des IP bannies est conservée)."""
    n = 0
    for f in LI.LOGS.glob("security_*.jsonl"):
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return jsonify({"ok": True, "msg": "Journal vidé (%d fichier%s). Les bannissements sont conservés." % (n, "s" if n > 1 else "")})


def _sec_norm_target(raw: str):
    """IP ou plage CIDR publique, normalisée ; None si invalide ou locale."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        if "/" in raw:
            net = ipaddress.ip_network(raw, strict=False)
            if net.is_private or net.is_loopback or net.prefixlen < (8 if net.version == 4 else 24):
                return None
            return str(net)
        ip = LI.norm_ip(raw)
        a = ipaddress.ip_address(ip)
        if LI.is_private(ip) or a.is_loopback:
            return None
        return str(a)
    except ValueError:
        return None


@app.route("/admin/api/security/ban_bulk", methods=["POST"])
@login_required
def api_security_ban_bulk():
    """Ajoute une liste d'IP / plages CIDR (une par ligne, # pour commenter)."""
    data = request.get_json(silent=True) or {}
    try:
        hours = float(data.get("hours", 0))
    except (TypeError, ValueError):
        hours = 0
    reason = str(data.get("reason", "liste"))[:120]
    until = None if hours <= 0 else time.time() + hours * 3600
    bl = dict(LI.load_blocklist())
    added, bad, skipped = 0, [], []
    for line in str(data.get("text", "")).splitlines()[:5000]:
        tok = line.split("#", 1)[0].replace(",", " ").replace(";", " ").split()
        for t in tok:
            k = _sec_norm_target(t)
            if not k:
                bad.append(t)
                continue
            why = _sec_protected(k)
            if why:
                skipped.append("%s (%s)" % (k, why))
                continue
            if k not in bl:
                added += 1
            bl[k] = {"until": until, "since": time.time(), "reason": reason}
    LI.save_blocklist(bl)
    msg = "%d entrée%s ajoutée%s" % (added, "s" if added > 1 else "", "s" if added > 1 else "")
    if skipped:
        msg += " — %d non bannie%s : %s" % (len(skipped), "s" if len(skipped) > 1 else "", ", ".join(skipped[:3]))
    if bad:
        msg += " — %d ignorée%s (invalide ou locale) : %s" % (len(bad), "s" if len(bad) > 1 else "", ", ".join(bad[:5]))
    return jsonify({"ok": True, "msg": msg, "added": added})


@app.route("/admin/api/security/banlist.txt")
@login_required
def api_security_banlist_export():
    """Liste des bannissements, au format texte réimportable."""
    now = time.time()
    lines = ["# Liste de bannissement ORSAT — %s" % datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")]
    for k, v in sorted(LI.load_blocklist().items()):
        if v.get("until") and v["until"] <= now:
            continue
        lines.append("%s  # %s%s" % (k, v.get("reason") or "", "" if not v.get("until") else
                     " (jusqu'au %s UTC)" % datetime.utcfromtimestamp(v["until"]).strftime("%Y-%m-%d %H:%M")))
    resp = Response("\n".join(lines) + "\n")
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=orsat-banlist.txt"
    return resp


@app.route("/admin/api/security")
@login_required
def api_security():
    """Tentatives anormales vues par proxy.py (logs/security_*.jsonl)."""
    _li_maintain()
    try:
        days = max(1, min(LI.RETENTION_DAYS, int(request.args.get("days", 7))))
    except ValueError:
        days = 7
    events, per_ip, cats = [], {}, {}
    for i in range(days - 1, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        for e in LI.read_jsonl(LI.LOGS / ("security_%s.jsonl" % d)):
            events.append(e)
            c = e.get("cat", "?")
            cats[c] = cats.get(c, 0) + 1
            ip = e.get("ip", "?")
            x = per_ip.setdefault(ip, {"ip": ip, "count": 0, "cats": {}, "first": e.get("ts", ""),
                                       "last": "", "paths": []})
            x["count"] += 1
            x["cats"][c] = x["cats"].get(c, 0) + 1
            x["last"] = e.get("ts", "")
            for k in ("city", "country", "countryCode", "isp", "as", "net", "rdns"):
                if e.get(k):
                    x[k] = e[k]
            pth = e.get("path", "")
            if pth and pth not in x["paths"] and len(x["paths"]) < 8:
                x["paths"].append(pth)
    bl = LI.load_blocklist()
    now = time.time()
    for x in per_ip.values():
        b = bl.get(x["ip"])
        x["banned_until"] = b.get("until") if b and (not b.get("until") or b["until"] > now) else None
        x["banned"] = bool(b) and (not b.get("until") or b["until"] > now)
    for x in per_ip.values():
        _sec_assess(x)
    ips = sorted(per_ip.values(), key=lambda x: (x["score"], x["count"]), reverse=True)[:100]
    bans = sorted(({"ip": k, **v} for k, v in bl.items() if not v.get("until") or v["until"] > now),
                  key=lambda b: b.get("since") or 0, reverse=True)
    allow = sorted(({"ip": k, **v} for k, v in LI.load_allowlist().items()),
                   key=lambda b: b.get("since") or 0, reverse=True)
    LI.flush()
    return jsonify({"ok": True, "days": days, "cats": cats, "labels": LI.SEC_LABELS,
                    "ips": ips, "events": events[-300:][::-1], "bans": bans,
                    "allow": allow, "myip": LI.norm_ip(request.remote_addr or "")})


def _sec_protected(target: str):
    """Raison pour laquelle une IP / plage ne doit pas être bannie, ou None."""
    me = LI.norm_ip(request.remote_addr or "")
    try:
        net = ipaddress.ip_network(target, strict=False)
        if me and ipaddress.ip_address(me) in net:
            return "contient votre propre IP (%s)" % me
    except ValueError:
        return None
    if "/" not in target and LI.is_allowed(target):
        return "en liste blanche"
    return None


# ── Liste noire KiwiSDR ─────────────────────────────────────────────────────
# La liste officielle des KiwiSDR (robots, hébergeurs abusifs, VPN…). Copie
# embarquée dans security/ (dépôt jks-prv/Beagle_SDR_GPS) ; à l'import on tente
# d'abord la version à jour servie par kiwisdr.com. Les entrées gardent le
# motif « KiwiSDR » : un nouvel import remplace les anciennes. Les exceptions
# « +IP » de la liste vont en liste blanche.
KIWI_BL_URL = "http://kiwisdr.com/ip_blacklist/ip_blacklist3.cjson"
KIWI_BL_FILE = BASE_DIR / "security" / "kiwisdr_ip_blacklist3.cjson"
KIWI_REASON = "KiwiSDR"


def _kiwi_parse(text: str):
    body = "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("//"))
    items = [x.strip() for x in json.loads(body) if isinstance(x, str)]
    ban, allow = [], []
    for x in items:
        plus = x.startswith("+")
        ip, _, pfx = x.lstrip("+").partition("/")
        try:
            ip = ".".join(str(int(o)) for o in ip.split("."))      # « 194.00 » → « 194.0 »
        except ValueError:
            pass
        (allow if plus else ban).append(ip + ("/" + pfx if pfx else ""))
    return ban, allow


def kiwi_import(fetch: bool = True, me: str = "") -> dict:
    src, text = None, None
    if fetch:
        try:
            import urllib.request
            with urllib.request.urlopen(KIWI_BL_URL, timeout=8) as r:
                text = r.read(1_000_000).decode("utf-8", "replace")
            _kiwi_parse(text)
            src = "kiwisdr.com (à jour)"
        except Exception:
            text = None
    if text is None:
        text = KIWI_BL_FILE.read_text(encoding="utf-8")
        src = "copie embarquée (déc. 2024)"
    ban, allow = _kiwi_parse(text)
    bl = {k: v for k, v in LI.load_blocklist().items() if v.get("reason") != KIWI_REASON}
    al = dict(LI.load_allowlist())
    now = time.time()
    n_ban, skipped = 0, []
    for raw in ban:
        k = _sec_norm_target(raw)
        if not k:
            continue
        if me:
            try:
                if ipaddress.ip_address(me) in ipaddress.ip_network(k, strict=False):
                    skipped.append(k)
                    continue
            except ValueError:
                pass
        if k not in bl:
            bl[k] = {"until": None, "since": now, "reason": KIWI_REASON}
            n_ban += 1
    n_allow = 0
    for raw in allow:
        k = _sec_norm_target(raw)
        if k and k not in al:
            al[k] = {"since": now, "note": KIWI_REASON + " (exception de la liste)"}
            n_allow += 1
    LI.save_blocklist(bl)
    LI.save_allowlist(al)
    try:
        (LI.LOGS / "kiwisdr_import.json").write_text(json.dumps({"ts": now, "src": src, "ban": n_ban}))
    except OSError:
        pass
    msg = "Liste KiwiSDR importée depuis %s : %d entrées bannies, %d exception%s en liste blanche" % (
        src, n_ban, n_allow, "s" if n_allow > 1 else "")
    if skipped:
        msg += " — non bannie%s car %s votre IP : %s" % ("s" if len(skipped) > 1 else "",
                                                          "elles contiennent" if len(skipped) > 1 else "elle contient", ", ".join(skipped))
    return {"ok": True, "msg": msg, "ban": n_ban, "allow": n_allow, "src": src}


@app.route("/admin/api/security/kiwi_import", methods=["POST"])
@login_required
def api_security_kiwi_import():
    try:
        return jsonify(kiwi_import(True, LI.norm_ip(request.remote_addr or "")))
    except Exception as e:
        return jsonify({"ok": False, "msg": "Import impossible : %s" % e})


def _kiwi_auto_import():
    """Premier démarrage après la mise à jour : importe la liste une fois."""
    try:
        if (LI.LOGS / "kiwisdr_import.json").exists():
            return
        r = kiwi_import(True, "")
        print("[PhantomSDR Admin] " + r["msg"])
    except Exception as e:
        print("[PhantomSDR Admin] Import KiwiSDR impossible : %s" % e)


@app.route("/admin/api/security/allow", methods=["POST"])
@login_required
def api_security_allow():
    """Liste blanche : ajout (texte, une IP / plage par ligne) ou retrait ({ip, remove})."""
    data = request.get_json(silent=True) or {}
    al = dict(LI.load_allowlist())
    if data.get("remove"):
        raw = str(data.get("ip", "")).strip()
        al.pop(raw, None)
        al.pop(LI.norm_ip(raw), None)
        LI.save_allowlist(al)
        return jsonify({"ok": True, "msg": "%s retirée de la liste blanche" % raw})
    note = str(data.get("note", ""))[:120]
    added, bad = 0, []
    for line in str(data.get("text", "")).splitlines()[:2000]:
        for t in line.split("#", 1)[0].replace(",", " ").replace(";", " ").split():
            k = _sec_norm_target(t)
            if not k:
                bad.append(t)
                continue
            if k not in al:
                added += 1
            al[k] = {"since": time.time(), "note": note}
    LI.save_allowlist(al)
    msg = "%d entrée%s ajoutée%s à la liste blanche" % (added, "s" if added > 1 else "", "s" if added > 1 else "")
    if bad:
        msg += " — %d ignorée%s (invalide ou locale) : %s" % (len(bad), "s" if len(bad) > 1 else "", ", ".join(bad[:5]))
    return jsonify({"ok": True, "msg": msg, "added": added})


@app.route("/admin/api/security/ban", methods=["POST"])
@login_required
def api_security_ban():
    data = request.get_json(silent=True) or {}
    raw = str(data.get("ip", "")).strip()
    bl = dict(LI.load_blocklist())
    if data.get("unban"):
        bl.pop(raw, None)
        bl.pop(LI.norm_ip(raw), None)
        LI.save_blocklist(bl)
        return jsonify({"ok": True, "msg": "%s débannie" % raw})
    ip = _sec_norm_target(raw)
    if not ip:
        return jsonify({"ok": False, "msg": "IP ou plage invalide, ou locale"})
    why = _sec_protected(ip)
    if why:
        return jsonify({"ok": False, "msg": "%s non bannie : %s" % (ip, why)})
    try:
        hours = float(data.get("hours", 24))
    except (TypeError, ValueError):
        hours = 24
    until = None if hours <= 0 else time.time() + hours * 3600
    bl[ip] = {"until": until, "since": time.time(), "reason": str(data.get("reason", ""))[:120]}
    LI.save_blocklist(bl)
    # Coupe aussi l'audio en cours, et bannit côté spectrumserver pour la même durée.
    try:
        if "/" not in ip:
            _proxy_kick(ip)
            _server_kick(ip, ban_s=int(hours * 3600) if hours > 0 else 10 * 365 * 86400)
    except Exception:
        pass
    return jsonify({"ok": True, "msg": "%s bannie %s" % (ip, "définitivement" if until is None else "%g h" % hours)})

def _proxy_kick(ip):
    """Ask proxy.py to close all WebSockets from `ip`.

    proxy.py owns every client WebSocket, so it disconnects the user by closing
    the socket from inside its own process — no CAP_NET_ADMIN / 'ss -K' needed.
    Returns (ok: bool, count: int|None, err: str|None). count is None when the
    proxy is unreachable (standalone deployment → caller falls back to ss -K).
    """
    import urllib.request
    cfg = load_admin_config()
    proxy_port = cfg.get("proxy_port")
    if not proxy_port:
        return (False, None, "no proxy_port configured")
    url = "http://127.0.0.1:%d/__proxy_control/kick" % int(proxy_port)
    body = json.dumps({"ip": ip}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            d = json.loads(resp.read().decode())
        return (bool(d.get("ok")), int(d.get("count", 0)), None)
    except Exception as e:
        # Connection refused / timeout ⇒ no proxy running ⇒ signal fallback.
        return (False, None, str(e))


def _server_kick(ip, ban_s=0):
    """Ask spectrumserver itself to disconnect and ban `ip`.

    This is the one that actually works on a normal station. Listeners reach
    spectrumserver directly on public_port, so proxy.py never sees their
    sockets, and 'ss -K' only destroys the TCP connection — which every page
    treats as a network drop and reconnects from. spectrumserver closes with
    code 4001, which the browser knows not to retry.

    ban_s is 0: a kick disconnects, it does not lock anyone out. Someone who
    wants back in reloads the page and is a normal listener again.

    Returns (ok: bool, count: int|None, err: str|None); count is None when the
    endpoint is unreachable (an older spectrumserver has no /~~kick).
    """
    import urllib.request, urllib.parse
    cfg = load_admin_config()
    if not cfg.get("public_port"):
        return (False, None, "no public_port configured")
    # Every receiver: the listener may be on any of them, or on several.
    query = urllib.parse.urlencode({"ip": ip, "secs": int(ban_s)})
    ok, count, err = False, None, None
    for port in _sdr_ports():
        url = "http://127.0.0.1:%d/~~kick?%s" % (port, query)
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                d = json.loads(resp.read().decode())
        except Exception as e:
            err = err or str(e)
            continue
        ok = ok or bool(d.get("ok"))
        count = (count or 0) + int(d.get("count", 0))
    return (ok, count, None if count is not None else err)


@app.route("/admin/api/kick", methods=["POST"])
@login_required
def api_kick():
    """Disconnect all connections from a given IP.

    Most clients connect straight to spectrumserver (a separate C++ process),
    so the only way to drop those sockets from here is 'ss -K', which requires
    CAP_NET_ADMIN on the ss binary ('setcap cap_net_admin+ep <ss>'). We also
    ask proxy.py to close any WebSockets it owns (privilege-free) so users who
    DO go through the proxy are covered even when ss lacks the capability.
    """
    data = request.get_json(silent=True) or {}
    ip = data.get("ip", "").strip()
    if not re.match(r'^[\d.a-fA-F:]+$', ip) or ip in ("127.0.0.1", "::1", ""):
        return jsonify({"ok": False, "msg": "IP invalide ou non autorisée"})
    if ip.startswith("::ffff:"):
        ip = ip[7:]  # normalize IPv4-mapped IPv6 so it matches ss / proxy keys

    # ── Privilege-free part: close WebSockets proxy.py owns (proxy users) ─────
    _pok, proxy_count, _perr = _proxy_kick(ip)
    proxy_count = proxy_count or 0

    # ── The real kick: spectrumserver closes its own sockets, with a close
    # code the browser does not reconnect from. No ban — a kick is a
    # disconnect, and coming back is the listener's own move. ────────────────
    _sok, server_count, _serr = _server_kick(ip)
    server_count = server_count or 0
    if server_count or proxy_count:
        total = server_count + proxy_count
        return jsonify({
            "ok": True,
            "msg": "%s expulsé — %d connexion%s fermée%s" % (
                ip, total, *(("s", "s") if total != 1 else ("", ""))),
        })

    import shutil as _shutil
    ss_bin = _shutil.which("ss") or "/usr/bin/ss"
    try:
        # Count ALL of this IP's connections (direct 8900 + proxied 8899).
        before = subprocess.run([ss_bin, "-tn", "dst", ip],
                                capture_output=True, text=True, timeout=3)
        count_before = max(0, len(before.stdout.strip().splitlines()) - 1)

        if count_before == 0 and proxy_count == 0:
            return jsonify({"ok": False,
                            "msg": "Aucune connexion active depuis %s" % ip})

        # 'ss -K' (SOCK_DESTROY) needs CAP_NET_ADMIN. Without it the kernel
        # replies "Operation not permitted" but ss still exits 0, so the kick
        # silently no-ops. Verify the capability directly (never by killing the
        # target socket — that could drop the admin's own connection).
        has_perm = (os.geteuid() == 0)
        if not has_perm:
            real_ss = os.path.realpath(ss_bin)
            getcap_bin = (_shutil.which("getcap") or "/usr/sbin/getcap")
            try:
                cap = subprocess.run([getcap_bin, real_ss],
                                     capture_output=True, text=True, timeout=3)
                has_perm = "cap_net_admin" in (cap.stdout or "").lower()
            except FileNotFoundError:
                has_perm = True  # can't verify; let ss attempt it

        if not has_perm:
            # Direct spectrumserver connections cannot be closed without the
            # capability. Report the proxy streams we DID close (if any) and
            # tell the operator exactly how to enable full kicks.
            if proxy_count:
                return jsonify({
                    "ok": True,
                    "msg": ("%d flux proxy fermé%s pour %s. Les connexions "
                            "directes nécessitent encore : sudo setcap "
                            "cap_net_admin+ep %s" % (
                                proxy_count, "s" if proxy_count != 1 else "",
                                ip, os.path.realpath(ss_bin))),
                })
            return jsonify({
                "ok": False,
                "msg": ("Expulsion sans effet — ces auditeurs sont connectés directement à "
                        "spectrumserver et fermer ces sockets exige "
                        "CAP_NET_ADMIN. À lancer une fois : sudo setcap cap_net_admin+ep "
                        "%s  (aucun redémarrage nécessaire — effet immédiat)"
                        % os.path.realpath(ss_bin)),
            })

        # Deferred so the admin browser receives the response before ss -K can
        # terminate the admin's own connection (if it shares the kicked IP/NAT).
        def _kick_later():
            import time
            time.sleep(0.3)
            try:
                subprocess.run([ss_bin, "-K", "dst", ip],
                               capture_output=True, timeout=5)
            except Exception:
                pass

        threading.Thread(target=_kick_later, daemon=True).start()
        total = max(count_before, proxy_count)
        return jsonify({
            "ok":  True,
            "msg": "%s expulsé — %d connexion%s coupée%s" % (
                ip, total, *(("s", "s") if total != 1 else ("", ""))),
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# ── Access-log noise filter ───────────────────────────────────────────────────
# The dashboard polls these paths every 3-5s for as long as a browser tab is
# open, so werkzeug's access log fills admin.log with hundreds of identical
# successful GETs an hour and buries the entries worth reading (logins, POSTed
# actions, errors). Successful polls are dropped; anything that is not a plain
# 200 still gets logged, so failures on these paths remain visible. proxy.py
# filters the same traffic on its own side (see QuietPollFilter there) — this
# is the second half of that, for requests reaching Flask directly.
# /admin/api/logs/clear is here for a different reason than the pollers: its own
# access line is written to admin.log *after* the truncate, so a successful clear
# always left one fresh line behind and the pane looked like it had not cleared.
_QUIET_PATHS = ("/admin/api/status", "/admin/api/thermal", "/admin/api/logs",
                "/admin/api/logs/clear",
                "/admin/api/autorun/status", "/admin/api/users", "/admin/api/sdr-users",
                "/admin/api/graph-stats", "/admin/api/chat")
_ACCESS_RE = re.compile(r'"[A-Z]+ (?P<path>[^ ?"]+)[^"]*" (?P<status>\d{3})')


class QuietPollFilter(logging.Filter):
    def filter(self, record):
        m = _ACCESS_RE.search(record.getMessage())
        if not m or m.group("status") != "200":
            return True
        return m.group("path") not in _QUIET_PATHS


# ─── Startup ───────────────────────────────────────────────────────────────────
# ── Fonctions supplémentaires (mise à jour, sauvegardes, santé, signal, carte)
try:
    import admin_extras as _extras
    _extras.init(app, globals())
except Exception as _e:
    print(f"[WARN] admin_extras indisponible : {_e}")

if __name__ == "__main__":
    if not ADMIN_CONFIG_FILE.exists():
        save_admin_config(DEFAULT_CONFIG)
        print("[PhantomSDR Admin] Created admin_config.json with default password 'admin'")

    threading.Thread(target=_kiwi_auto_import, daemon=True).start()

    cfg = load_admin_config()
    port = cfg.get("port", ADMIN_PORT)
    bind = ADMIN_BIND
    proxy_port = cfg.get("proxy_port", PUBLIC_PORT)
    sdr_port = cfg.get("public_port", PUBLIC_PORT)

    print("=" * 60)
    print("  PhantomSDR-Plus Admin Panel  [INTERNAL SERVICE]")
    print(f"  Listening : http://{bind}:{port}/admin")
    print(f"  Public URL: via proxy.py -> http://SERVER_IP:{proxy_port}/admin")
    print(f"  Password  : admin  (CHANGE THIS IMMEDIATELY)")
    print(f"  Dir       : {BASE_DIR}")
    print("=" * 60)
    print("  NOTE: Run proxy.py separately to share the main SDR port.")
    print(f"        spectrumserver must use port {sdr_port} in your .toml")
    print("=" * 60)

    # Arm the thermal guard before the sampler that ticks it.
    if start_thermal_guard():
        _tg = thermal_guard.status()
        _tt = thermal_guard.read_cpu_temp()
        print("  Thermal   : %s, mode=%s, sensor=%s" % (
            "enabled" if _tg.get("enabled") else "disabled",
            _tg.get("mode"), (_tt[2] if _tt else "NONE — guard cannot act")))
        if _tt and _tt[1]:
            print("              crit=%.0fC -> stop at %.0fC (override in Settings)"
                  % (_tt[1], _tt[1] - thermal_guard.OFF_STOP))
    else:
        print("  Thermal   : guard unavailable (thermal_guard.py missing)")

    # Start sampling immediately, not on first visit to the Graphs page, so the
    # page opens onto existing history rather than an empty plot.
    start_graph_sampler()
    print(f"  Graphs    : sampling every {GRAPH_INTERVAL_S}s, "
          f"{GRAPH_HISTORY_S // 3600}h history (in memory)")

    if not HAS_PSUTIL:
        print("[WARN] psutil not installed - system stats limited. pip3 install psutil")
    if tomllib is None:
        print("[WARN] tomllib unavailable - TOML editing is text-only")

    logging.getLogger("werkzeug").addFilter(QuietPollFilter())

    app.run(host=bind, port=port, debug=False, threaded=True)
