#!/usr/bin/env python3
"""
Nova CLI — Agents that answer for themselves.
Zero dependencies. Python 3.8+.
"""

import sys, os, json, time, urllib.request, urllib.error
import urllib.parse, hashlib, argparse, textwrap, random
import threading, re
from datetime import datetime, timezone

# Force UTF-8 on Windows (PowerShell uses cp1252 by default)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.system("chcp 65001 >nul 2>&1")

# ══════════════════════════════════════════════════════════════════
# COLOR SYSTEM
# ══════════════════════════════════════════════════════════════════

USE_COLOR = (
    not os.environ.get("NO_COLOR") and
    (os.environ.get("FORCE_COLOR") or
     (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()))
)
DEBUG = os.environ.get("NOVA_DEBUG", "").lower() in ("1", "true", "yes")

def _e(code): return "\033[" + code + "m" if USE_COLOR else ""


class C:
    """
    Color palette for nova CLI.
    Rule: G3 (240) is the ABSOLUTE DARKEST for any visible text.
    """
    R    = _e("0")
    BOLD = _e("1")
    DIM  = _e("2")

    # Blues — midnight to electric (LOGO gradient B1→B7)
    B1 = _e("38;5;18")
    B2 = _e("38;5;19")
    B4 = _e("38;5;21")
    B5 = _e("38;5;27")
    B6 = _e("38;5;33")   # nova accent — interactive elements
    B7 = _e("38;5;39")   # bright blue — commands, links

    # Text hierarchy (NEVER darker than G3)
    W  = _e("38;5;255")  # primary — titles, values
    G1 = _e("38;5;252")  # secondary — descriptions
    G2 = _e("38;5;246")  # tertiary — hints, labels
    G3 = _e("38;5;240")  # subtle — separators (MINIMUM)

    # Semantic
    GRN = _e("38;5;84")
    YLW = _e("38;5;220")
    RED = _e("38;5;196")
    ORG = _e("38;5;208")
    MGN = _e("38;5;141")  # magenta — special accents
    CYN = _e("38;5;87")   # cyan — informational


def q(color, text, bold=False):
    b = C.BOLD if bold else ""
    return b + color + str(text) + C.R


def debug(msg):
    if DEBUG:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
        print("  " + q(C.G3, "[" + ts + "]") + " " + q(C.G2, msg))


# ══════════════════════════════════════════════════════════════════
# LOGO + BRANDING
# ══════════════════════════════════════════════════════════════════

_NOVA = [
    "  ███╗   ██╗  ██████╗  ██╗   ██╗  █████╗  ",
    "  ████╗  ██║ ██╔═══██╗ ██║   ██║ ██╔══██╗ ",
    "  ██╔██╗ ██║ ██║   ██║ ██║   ██║ ███████║ ",
    "  ██║╚██╗██║ ██║   ██║ ╚██╗ ██╔╝ ██╔══██║ ",
    "  ██║ ╚████║ ╚██████╔╝  ╚████╔╝  ██║  ██║ ",
    "  ╚═╝  ╚═══╝  ╚═════╝    ╚═══╝   ╚═╝  ╚═╝ ",
]
_NOVA_COLORS = [C.B1, C.B2, C.B4, C.B5, C.B6, C.B7]

_CLI = [
    " ██████╗██╗     ██╗",
    "██╔════╝██║     ██║",
    "██║     ██║     ██║",
    "██║     ██║     ██║",
    "╚██████╗███████╗██║",
    " ╚═════╝╚══════╝╚═╝",
]

_TAGLINES = [
    "Agents that answer for themselves.",
    "The layer between intent and chaos.",
    "Your agents, accountable.",
    "What your agents do. Provably.",
    "Where intent becomes law.",
    "Intelligence with limits. Actions with proof.",
    "Every action, signed. Every intent, provable.",
    "The nervous system for autonomous agents.",
    "Trust, but verify. Automatically.",
    "Control without constraint.",
    "The firewall for AI agents.",
    "Governance at machine speed.",
    "What stands between your agent and the world.",
    "Actions speak. nova listens.",
    "Because 'it seemed like a good idea' isn't an audit trail.",
    "Sleep well. Your agents are supervised.",
]
_tagline = random.choice(_TAGLINES)

NOVA_VERSION = "3.0.0"

# Command aliases
ALIASES = {
    "s": "status", "v": "validate", "a": "agent",
    "c": "config", "l": "ledger",   "m": "memory",
    "w": "watch",  "i": "init",     "h": "help",
    "t": "test",   "sk": "skill",   "e": "export",
}


def print_logo(tagline=True, compact=False):
    print()
    if compact:
        print("  " + q(C.B6, "✦", bold=True) + "  " + q(C.W, "nova", bold=True) +
              q(C.G2, "  ·  CLI " + NOVA_VERSION))
    else:
        for i in range(6):
            nova_part = _NOVA_COLORS[i] + C.BOLD + _NOVA[i] + C.R
            cli_part  = C.W + C.BOLD + _CLI[i] + C.R
            print(nova_part + cli_part)
        if tagline:
            print()
            print("  " + q(C.G2, _tagline))
            print("  " + q(C.G3, "─" * 54))
    print()


def _step_header(n, total, title):
    bar = q(C.B6, "█" * n, bold=True) + q(C.G3, "░" * (total - n))
    print()
    print("  " + bar + "  " + q(C.G2, str(n) + "/" + str(total)) +
          "  " + q(C.W, title, bold=True))
    print("  " + q(C.G3, "─" * 54))
    print()


def _pause(label="continue"):
    print()
    print("  " + q(C.W, "Press Enter to " + label) + "  " + q(C.G2, "↵"), end="", flush=True)
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print()
    print()


# ══════════════════════════════════════════════════════════════════
# ANIMATED SPINNER (threaded, zero deps)
# ══════════════════════════════════════════════════════════════════

_SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

class Spinner:
    """Threaded animated spinner. Usage:
        with Spinner("Loading..."):
            do_work()
    """
    def __init__(self, msg, color=None):
        self.msg   = msg
        self.color = color or C.B5
        self.stop  = threading.Event()
        self.thread = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.finish()

    def start(self):
        def run():
            i = 0
            while not self.stop.is_set():
                frame = _SPIN_FRAMES[i % len(_SPIN_FRAMES)]
                sys.stdout.write("\r  " + q(self.color, frame) + "  " + q(C.G1, self.msg))
                sys.stdout.flush()
                time.sleep(0.08)
                i += 1
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def finish(self, final_msg=None):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)
        clear_line()
        if final_msg:
            print("  " + final_msg)

    def update(self, msg):
        self.msg = msg


# ══════════════════════════════════════════════════════════════════
# ARROW-KEY SELECTOR  (zero deps, cross-platform)
# ══════════════════════════════════════════════════════════════════

def _select(options, title="", default=0):
    """
    Arrow-key selector. Zero deps. Cross-platform.
    Options must be plain strings — no ANSI codes.
    """
    is_tty = False
    try:
        is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        pass

    if not is_tty:
        if title:
            print("  " + q(C.G2, title))
        print()
        for i, opt in enumerate(options):
            marker = q(C.B6, "▸", bold=True) if i == default else "  "
            label  = q(C.W, opt, bold=True) if i == default else q(C.G2, opt)
            print("  " + marker + "  " + label)
        print()
        print("  " + q(C.G2, "Select [1-" + str(len(options)) + "]:") + "  ",
              end="", flush=True)
        try:
            v = input().strip()
            if v.isdigit():
                idx = int(v) - 1
                if 0 <= idx < len(options):
                    return idx
        except (EOFError, KeyboardInterrupt):
            pass
        return default

    def _draw(current, first=False):
        out = []
        if not first:
            n = (1 if title else 0) + 1 + len(options) + 1
            out.append("\033[" + str(n) + "A\033[J")
        if title:
            out.append("  " + q(C.G2, title) + "\n")
        out.append("\n")
        for i, opt in enumerate(options):
            if i == current:
                out.append("  " + q(C.B6, "▸", bold=True) + "  " +
                           q(C.W, opt, bold=True) + "\n")
            else:
                out.append("     " + q(C.G2, opt) + "\n")
        out.append("\n")
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    # Windows
    if sys.platform == "win32":
        import msvcrt
        current = default
        _draw(current, first=True)
        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                return current
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                if   ch2 == "H": current = (current - 1) % len(options)
                elif ch2 == "P": current = (current + 1) % len(options)
            elif ch == "\x03":
                raise KeyboardInterrupt
            _draw(current)
        return current

    # Unix
    import termios, tty
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)

    def _read_key():
        tty.setraw(fd)
        try:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    if   ch3 == "A": return "UP"
                    elif ch3 == "B": return "DOWN"
                    return ch3
                return ch2
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    current = default
    _draw(current, first=True)

    while True:
        key = _read_key()
        if key in ("\r", "\n"):
            return current
        elif key == "\x03":
            raise KeyboardInterrupt
        elif key in ("UP",   "k", "K"):
            current = (current - 1) % len(options)
        elif key in ("DOWN", "j", "J"):
            current = (current + 1) % len(options)
        _draw(current)


def _select_lang():
    print()
    print()
    print("  " + q(C.W, "Select your language", bold=True) +
          "  " + q(C.G3, "/ Selecciona tu idioma"))
    print()
    idx = _select(["English", "Español"], default=0)
    return "en" if idx == 0 else "es"


# ══════════════════════════════════════════════════════════════════
# CONNECT ANIMATION
# ══════════════════════════════════════════════════════════════════

def _animate_connect(url):
    host = url.replace("http://", "").replace("https://", "").split(":")[0][:20]
    pad  = max(0, 20 - len(host))
    srv  = host + " " * pad

    frames = [
        ("  CLI                    " + srv,      C.G3),
        ("   ○                          ○",      C.G2),
        ("   │                          │",      C.G2),
        ("   │  ──── identify ────────► │",      C.G2),
        ("   │                          │",      C.G2),
        ("   │  ◄─── challenge ───────  │",      C.B5),
        ("   │                          │",      C.G2),
        ("   │  ──── intent token ────► │",      C.G2),
        ("   │                          │",      C.G2),
        ("   │  ◄─── access granted ──  │",      C.B6),
        ("   │                          │",      C.G2),
        ("   ●                          ●",      C.GRN),
    ]

    delays = [0.05, 0.08, 0.04, 0.18, 0.04, 0.22,
              0.04, 0.20, 0.04, 0.24, 0.04, 0.10]

    print()
    for (line, color), delay in zip(frames, delays):
        print("  " + q(color, line))
        time.sleep(delay)
    print()


# ══════════════════════════════════════════════════════════════════
# CONFIG — ~/.nova/config.json
# ══════════════════════════════════════════════════════════════════

NOVA_DIR    = os.path.expanduser("~/.nova")
CONFIG_FILE = os.path.join(NOVA_DIR, "config.json")
QUEUE_FILE  = os.path.join(NOVA_DIR, "offline_queue.json")

DEFAULTS = {
    "api_url":       "http://localhost:8000",
    "api_key":       "",
    "default_token": "",
    "version":       NOVA_VERSION,
    "lang":          "",
    "user_name":     "",
}


def load_config():
    os.makedirs(NOVA_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            return dict(DEFAULTS, **json.load(open(CONFIG_FILE)))
        except Exception:
            pass
    return dict(DEFAULTS)


def save_config(cfg):
    os.makedirs(NOVA_DIR, exist_ok=True)
    json.dump(cfg, open(CONFIG_FILE, "w"), indent=2)


def validate_config(cfg):
    """Check config integrity, return list of issues."""
    issues = []
    url = cfg.get("api_url", "")
    if not url:
        issues.append("api_url is not set")
    elif not url.startswith(("http://", "https://")):
        issues.append("api_url must start with http:// or https://")
    key = cfg.get("api_key", "")
    if key and len(key) < 8:
        issues.append("api_key seems too short (less than 8 characters)")
    return issues


# ══════════════════════════════════════════════════════════════════
# API CLIENT — pure urllib, zero deps, retry with backoff
# ══════════════════════════════════════════════════════════════════

class NovaAPI:
    def __init__(self, url, key):
        self.url = url.rstrip("/")
        self.key = key

    def _req(self, method, path, data=None, retries=0):
        url  = self.url + path
        hdrs = {"Content-Type": "application/json", "x-api-key": self.key}
        body = json.dumps(data).encode() if data else None
        debug(method + " " + url)
        if data:
            debug("Body: " + json.dumps(data)[:120])

        last_err = None
        attempts = 1 + retries
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
                with urllib.request.urlopen(req, timeout=15) as r:
                    result = json.loads(r.read().decode())
                    debug("Response OK")
                    return result
            except urllib.error.HTTPError as e:
                try:
                    detail = json.loads(e.read().decode()).get("detail", str(e))
                except Exception:
                    detail = "HTTP " + str(e.code)
                last_err = {"error": detail}
                # Don't retry client errors (4xx)
                if 400 <= e.code < 500:
                    return last_err
            except urllib.error.URLError:
                last_err = {"error": "Cannot connect to " + self.url + " — run: docker ps"}
            except Exception as e:
                last_err = {"error": str(e)}

            if attempt < attempts - 1:
                wait = (2 ** attempt) + random.random() * 0.5
                debug("Retry " + str(attempt + 1) + "/" + str(retries) + " in " + str(round(wait, 1)) + "s")
                time.sleep(wait)

        return last_err or {"error": "Unknown error"}

    def get(self, p, **kw):              return self._req("GET",    p, **kw)
    def post(self, p, d, **kw):          return self._req("POST",   p, d, **kw)
    def delete(self, p, **kw):           return self._req("DELETE", p, **kw)
    def patch(self, p, d=None, **kw):    return self._req("PATCH",  p, d or {}, **kw)


def _api(cfg=None):
    """Shortcut to create API client from config."""
    cfg = cfg or load_config()
    return NovaAPI(cfg["api_url"], cfg["api_key"]), cfg


# ══════════════════════════════════════════════════════════════════
# UI PRIMITIVES
# ══════════════════════════════════════════════════════════════════

def ok(msg):   print("  " + q(C.GRN, "✓") + "  " + q(C.W,  msg))
def fail(msg): print("  " + q(C.RED, "✗") + "  " + q(C.W,  msg))
def warn(msg): print("  " + q(C.YLW, "!") + "  " + q(C.G1, msg))
def info(msg): print("  " + q(C.B6,  "·") + "  " + q(C.G1, msg))
def dim(msg):  print("       " + q(C.G2, msg))
def nl():      print()


def section(title, subtle=""):
    sub = "  " + q(C.G2, subtle) if subtle else ""
    print()
    print("  " + q(C.W, title, bold=True) + sub)
    print("  " + q(C.G3, "─" * (len(title) + 2)))


def kv(key, val, vc=None):
    vc = vc or C.W
    print("  " + q(C.G2, key.ljust(20)) + "  " + q(vc, str(val)))


def loading(msg):
    print("  " + q(C.B5, "○") + "  " + q(C.G1, msg), end="", flush=True)


def clear_line():
    print("\r\033[K", end="", flush=True)


def score_bar(score, width=18):
    filled = max(0, int((score / 100) * width))
    empty  = width - filled
    c = C.GRN if score >= 70 else (C.YLW if score >= 40 else C.RED)
    bar = c + C.BOLD + ("█" * filled) + C.R + q(C.G3, "░" * empty)
    num = q(c, str(score), bold=True)
    return q(C.G2, "[") + bar + q(C.G2, "]") + " " + num


def progress_bar(current, total, width=30, label=""):
    pct = current / max(total, 1)
    filled = int(width * pct)
    bar = q(C.B6, "█" * filled) + q(C.G3, "░" * (width - filled))
    sys.stdout.write("\r  " + bar + "  " + q(C.W, str(int(pct*100)) + "%") +
                     "  " + q(C.G2, label))
    sys.stdout.flush()


def sparkline(values, width=None):
    """Render a sparkline from a list of numbers."""
    if not values:
        return q(C.G3, "no data")
    blocks = "▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    line = ""
    for v in values:
        idx = min(int((v - mn) / rng * (len(blocks) - 1)), len(blocks) - 1)
        line += blocks[idx]
    return q(C.B6, line)


def verdict_badge(v):
    m = {
        "APPROVED":  (C.GRN, "✓", "APPROVED"),
        "BLOCKED":   (C.RED, "✗", "BLOCKED"),
        "ESCALATED": (C.YLW, "⚠", "ESCALATED"),
        "DUPLICATE": (C.ORG, "⊘", "DUPLICATE"),
    }
    c, sym, label = m.get(v, (C.G2, "·", v))
    return q(c, sym) + "  " + q(c, label, bold=True)


def time_ago(iso_str):
    """Convert ISO timestamp to human-readable relative time."""
    if not iso_str:
        return ""
    try:
        s = iso_str.replace("Z", "+00:00")
        # Handle naive datetimes
        if "+" not in s and s.count("-") <= 2:
            dt = datetime.fromisoformat(s)
            now = datetime.now()
        else:
            dt = datetime.fromisoformat(s)
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                now = datetime.now()
        delta = now - dt
        secs = int(delta.total_seconds())
        if secs < 0:
            return "just now"
        if secs < 60:
            return "just now"
        if secs < 3600:
            m = secs // 60
            return str(m) + "m ago"
        if secs < 86400:
            h = secs // 3600
            return str(h) + "h ago"
        days = delta.days
        if days < 7:
            return str(days) + "d ago"
        if days < 30:
            return str(days // 7) + "w ago"
        if days < 365:
            return str(days // 30) + "mo ago"
        return str(days // 365) + "y ago"
    except Exception:
        return iso_str[:16] if len(iso_str) > 16 else iso_str


def box(lines, color=None, title=""):
    bc = color or C.G3
    inner_w = max((len(l) for l in lines), default=30) + 4
    w = max(inner_w, len(title) + 6)
    if title:
        tpad = max(0, w - len(title) - 4)
        print("  " + q(bc, "┌─ ") + q(C.G1, title) + " " + q(bc, "─" * tpad + "┐"))
    else:
        print("  " + q(bc, "┌" + "─" * w + "┐"))
    for line in lines:
        pad = max(0, w - len(line) - 2)
        print("  " + q(bc, "│") + " " + q(C.G1, line) + " " * pad + " " + q(bc, "│"))
    print("  " + q(bc, "└" + "─" * w + "┘"))


def table(headers, rows, colors=None):
    """Formatted table with aligned columns."""
    if not rows:
        return
    col_count = len(headers)
    widths = []
    for i in range(col_count):
        max_w = len(str(headers[i]))
        for row in rows:
            if i < len(row):
                max_w = max(max_w, len(str(row[i])))
        widths.append(min(max_w, 40))

    header_line = "  "
    for i, h in enumerate(headers):
        header_line += q(C.G3, str(h).ljust(widths[i])) + "  "
    print(header_line)
    print("  " + q(C.G3, "─" * (sum(widths) + col_count * 2)))

    for row in rows:
        line = "  "
        for i in range(col_count):
            val = str(row[i]) if i < len(row) else ""
            c = colors[i] if colors and i < len(colors) else C.G1
            line += q(c, val[:widths[i]].ljust(widths[i])) + "  "
        print(line)


def prompt(label, default=""):
    hint = " " + q(C.G3, "(" + default + ")") if default else ""
    print("  " + q(C.B6, "?") + "  " + q(C.G1, label) + hint + "  ", end="", flush=True)
    val = input().strip()
    return val or default


def prompt_list(label, hint="empty line to finish"):
    print("  " + q(C.B6, "?") + "  " + q(C.G1, label) + "  " + q(C.G3, "(" + hint + ")"))
    items = []
    while True:
        print("    " + q(C.G3, "+  "), end="", flush=True)
        v = input().strip()
        if not v:
            break
        items.append(v)
    return items


def confirm(label, default=True):
    hint = q(C.G3, "Y/n" if default else "y/N")
    print("  " + q(C.B6, "?") + "  " + q(C.G1, label) + "  " + hint + "  ", end="", flush=True)
    v = input().strip().lower()
    return default if not v else v in ("y", "yes", "s", "si", "sí")


def print_error(r):
    fail(r.get("error", "Unknown error"))


# ══════════════════════════════════════════════════════════════════
# OFFLINE QUEUE — actions queued when server is unreachable
# ══════════════════════════════════════════════════════════════════

def queue_action(action_data):
    """Queue an action for later sync."""
    queue = []
    if os.path.exists(QUEUE_FILE):
        try:
            queue = json.load(open(QUEUE_FILE))
        except Exception:
            queue = []
    queue.append({
        "data": action_data,
        "queued_at": datetime.now().isoformat(),
    })
    json.dump(queue, open(QUEUE_FILE, "w"), indent=2)
    return len(queue)


def get_queue():
    if os.path.exists(QUEUE_FILE):
        try:
            return json.load(open(QUEUE_FILE))
        except Exception:
            pass
    return []


def clear_queue():
    if os.path.exists(QUEUE_FILE):
        os.remove(QUEUE_FILE)


# ══════════════════════════════════════════════════════════════════
# VERSION CHECK
# ══════════════════════════════════════════════════════════════════

def check_version():
    """Check for newer version (non-blocking, 2s timeout)."""
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/Santiagorubioads/nova-os/releases/latest",
            headers={"User-Agent": "nova-cli/" + NOVA_VERSION}
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.loads(r.read().decode())
            latest = data.get("tag_name", "").lstrip("v")
            if latest and latest != NOVA_VERSION:
                return latest
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════
# INTERNATIONALIZATION
# ══════════════════════════════════════════════════════════════════

def _i18n(lang="en"):
    strings = {
        "en": {
            "tagline":    random.choice(_TAGLINES),
            "welcome":    "Welcome to nova.",
            "intro1":     "nova sits between your agents and the real world.",
            "intro2":     "Before anything executes, nova asks one question:",
            "question":   "Should this happen?",
            "p_continue": "continue",
            "h_howworks": "How nova works",
            "how1":       "Your agent wants to do something",
            "how_ev":     "nova evaluates it in <5ms — no AI for 90% of cases",
            "approved":   "Approved · runs",
            "escalated":  "Escalated · you decide",
            "blocked":    "Blocked · logged forever",
            "ledger_desc":"Every decision lands in the Intent Ledger.",
            "ledger_sub": "Cryptographic. Auditable. Permanent.",
            "h_risks":    "Before we continue",
            "risk_title": "nova is not a sandbox.",
            "risk_sub":   "It makes real decisions about real actions in production.",
            "r1":         "nova may block actions your agents try to execute",
            "r2":         "every validation is recorded permanently in the ledger",
            "r3":         "you define the rules — you own the consequences",
            "r4":         "misconfigured rules can block legitimate work",
            "r5":         "the ledger cannot be deleted or modified",
            "terms_label":"Terms:",
            "terms_q":    "Do you understand and accept?",
            "accept":     "Yes, I accept",
            "decline":    "No, exit",
            "cancelled":  "Setup cancelled. Run",
            "h_who":      "Who are you?",
            "who_sub":    "This personalizes your nova experience.",
            "your_name":  "Your name or organization",
            "h_server":   "Connect to your server",
            "server_sub": "nova CLI talks to a nova server. Self-hosted or cloud.",
            "server_opts":"How do you want to connect?",
            "srv_local":  "Local server (http://localhost:8000)",
            "srv_remote": "Enter a custom URL",
            "srv_already":"Use saved config",
            "using":      "Using",
            "server_url": "Server URL",
            "h_connecting":"Connecting",
            "testing":    "Testing connection...",
            "srv_ok":     "Server responding",
            "key_ok":     "API key accepted",
            "srv_fail":   "Could not connect",
            "saved_anyway":"Config saved. Fix server then run",
            "youre_in":   "You're in",
            "ready":      "is ready.",
            "next_steps": "What to do next:",
            "n1":         "Create your first agent",
            "n2":         "System health & metrics",
            "n3":         "Skills, server, preferences",
            "n4":         "Browse available integrations",
        },
        "es": {
            "tagline":    random.choice(_TAGLINES),
            "welcome":    "Bienvenido a nova.",
            "intro1":     "nova se sienta entre tus agentes y el mundo real.",
            "intro2":     "Antes de que algo se ejecute, nova hace una pregunta:",
            "question":   "¿Debería pasar esto?",
            "p_continue": "continuar",
            "h_howworks": "Cómo funciona nova",
            "how1":       "Tu agente quiere hacer algo",
            "how_ev":     "nova lo evalúa en <5ms — sin IA en el 90% de casos",
            "approved":   "Aprobado · se ejecuta",
            "escalated":  "Escalado · tú decides",
            "blocked":    "Bloqueado · registrado para siempre",
            "ledger_desc":"Cada decisión queda en el Intent Ledger.",
            "ledger_sub": "Criptográfico. Auditable. Permanente.",
            "h_risks":    "Antes de continuar",
            "risk_title": "nova no es un sandbox.",
            "risk_sub":   "Toma decisiones reales sobre acciones reales en producción.",
            "r1":         "nova puede bloquear acciones que tus agentes intentan ejecutar",
            "r2":         "cada validación se registra permanentemente en el ledger",
            "r3":         "tú defines las reglas — tú eres responsable de las consecuencias",
            "r4":         "reglas mal configuradas pueden bloquear trabajo legítimo",
            "r5":         "el ledger no puede eliminarse ni modificarse",
            "terms_label":"Términos:",
            "terms_q":    "¿Entiendes y aceptas?",
            "accept":     "Sí, acepto",
            "decline":    "No, salir",
            "cancelled":  "Setup cancelado. Ejecuta",
            "h_who":      "¿Quién eres?",
            "who_sub":    "Esto personaliza tu experiencia con nova.",
            "your_name":  "Tu nombre u organización",
            "h_server":   "Conecta tu servidor",
            "server_sub": "nova CLI habla con un servidor nova. Self-hosted o cloud.",
            "server_opts":"¿Cómo quieres conectar?",
            "srv_local":  "Servidor local (http://localhost:8000)",
            "srv_remote": "Ingresar URL personalizada",
            "srv_already":"Usar configuración guardada",
            "using":      "Usando",
            "server_url": "URL del servidor",
            "h_connecting":"Conectando",
            "testing":    "Probando conexión...",
            "srv_ok":     "Servidor respondiendo",
            "key_ok":     "API key aceptada",
            "srv_fail":   "No se puede conectar",
            "saved_anyway":"Config guardada. Arregla el servidor y ejecuta",
            "youre_in":   "Estás dentro",
            "ready":      "está listo.",
            "next_steps": "Qué hacer ahora:",
            "n1":         "Crea tu primer agente",
            "n2":         "Estado del sistema y métricas",
            "n3":         "Skills, servidor, preferencias",
            "n4":         "Ver integraciones disponibles",
        }
    }
    return strings.get(lang, strings["en"])


# ══════════════════════════════════════════════════════════════════
# RULE TEMPLATES — pre-built agent configurations
# ══════════════════════════════════════════════════════════════════

RULE_TEMPLATES = {
    "email-safety": {
        "label": "Email Safety",
        "desc":  "Block external sends, protect inbox integrity",
        "can_do": [
            "send email to verified contacts",
            "read inbox",
            "draft emails",
            "reply to existing threads",
        ],
        "cannot_do": [
            "send email to external domains",
            "delete emails",
            "forward to personal accounts",
            "modify email rules",
        ],
    },
    "database-readonly": {
        "label": "Database Read-Only",
        "desc":  "SELECT only — no mutations allowed",
        "can_do": [
            "SELECT queries",
            "read schemas",
            "list tables",
            "explain query plans",
        ],
        "cannot_do": [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "CREATE",
        ],
    },
    "social-media": {
        "label": "Social Media Manager",
        "desc":  "Draft and schedule, never auto-publish",
        "can_do": [
            "read posts and analytics",
            "draft content",
            "schedule posts for review",
            "reply to comments",
        ],
        "cannot_do": [
            "publish without approval",
            "delete posts",
            "change account settings",
            "DM users directly",
        ],
    },
    "payment-guard": {
        "label": "Payment Guard",
        "desc":  "Verify and read — never initiate charges",
        "can_do": [
            "read transaction history",
            "verify payment status",
            "list subscriptions",
            "check balance",
        ],
        "cannot_do": [
            "create charges",
            "issue refunds over $100",
            "modify subscriptions",
            "update payment methods",
            "transfer funds",
        ],
    },
    "devops-safe": {
        "label": "DevOps Safe Mode",
        "desc":  "Monitor and report, no destructive ops",
        "can_do": [
            "read logs",
            "check service status",
            "list deployments",
            "run health checks",
            "view metrics",
        ],
        "cannot_do": [
            "deploy to production",
            "scale down services",
            "delete resources",
            "modify secrets",
            "change DNS",
            "rollback without approval",
        ],
    },
    "crm-assistant": {
        "label": "CRM Assistant",
        "desc":  "Read and update contacts, no deletions",
        "can_do": [
            "read contacts",
            "update notes on existing contacts",
            "search leads",
            "log activities",
        ],
        "cannot_do": [
            "delete contacts",
            "export all data",
            "modify deal amounts",
            "send mass emails",
            "change pipeline stages without note",
        ],
    },
}


# ══════════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════════

def cmd_init(args):
    """First-run setup wizard."""
    cfg = load_config()

    lang = cfg.get("lang", "")
    if not lang:
        try:
            lang = _select_lang()
        except KeyboardInterrupt:
            print(); return
        cfg["lang"] = lang
        save_config(cfg)

    L = _i18n(lang)

    # ── SPLASH
    print()
    print()
    for i in range(6):
        print(_NOVA_COLORS[i] + C.BOLD + _NOVA[i] + C.R + C.W + C.BOLD + _CLI[i] + C.R)
        time.sleep(0.06)

    print()
    print("  " + q(C.G2, L["tagline"]))
    print("  " + q(C.G3, "─" * 54))
    print()
    time.sleep(0.3)

    print("  " + q(C.W, L["welcome"], bold=True))
    print()
    print("  " + q(C.G1, L["intro1"]))
    print("  " + q(C.G1, L["intro2"]))
    print()
    print("  " + q(C.B7, "  " + L["question"], bold=True))
    print()
    _pause(L["p_continue"])

    # ── [1/5] HOW IT WORKS
    _step_header(1, 5, L["h_howworks"])
    print("  " + q(C.G2,  "  ┌─  " + L["how1"]))
    print("  " + q(C.G3,  "  │"))
    print("  " + q(C.G1,  "  │   " + L["how_ev"]))
    print("  " + q(C.G3,  "  │"))
    print("  " + q(C.G3,  "  ├─  ") + q(C.GRN, "Score >= 70", bold=True) +
          q(C.G2, "  →  ✓  " + L["approved"]))
    print("  " + q(C.G3,  "  ├─  ") + q(C.YLW, "Score 40-70", bold=True) +
          q(C.G2, "  →  ⚠  " + L["escalated"]))
    print("  " + q(C.G3,  "  └─  ") + q(C.RED, "Score < 40", bold=True) +
          q(C.G2, "   →  ✗  " + L["blocked"]))
    print()
    print("  " + q(C.G1, "  " + L["ledger_desc"]))
    print("  " + q(C.G2, "  " + L["ledger_sub"]))
    print()
    _pause(L["p_continue"])

    # ── [2/5] RISKS + T&C
    _step_header(2, 5, L["h_risks"])
    print("  " + q(C.YLW, "  !") + "  " + q(C.W, L["risk_title"], bold=True))
    print("  " + q(C.G1, "     " + L["risk_sub"]))
    print()

    for r in [L["r1"], L["r2"], L["r3"], L["r4"], L["r5"]]:
        print("  " + q(C.G3, "     ◦  ") + q(C.G1, r))
    print()
    print("  " + q(C.G3, "     " + L["terms_label"] + "  ") + q(C.B7, "https://nova-os.com/terms"))
    print()

    print("  " + q(C.G2, "  " + L["terms_q"]))
    print()
    try:
        idx = _select([L["accept"], L["decline"]], default=0)
    except KeyboardInterrupt:
        print(); return

    if idx != 0:
        print()
        warn(L["cancelled"] + "  nova init")
        print()
        return

    # ── [3/5] PERSONALIZATION
    _step_header(3, 5, L["h_who"])
    print("  " + q(C.G1, "  " + L["who_sub"]))
    print()
    try:
        name = prompt("  " + L["your_name"], cfg.get("user_name", ""))
        name = name or "Explorer"
    except (EOFError, KeyboardInterrupt):
        name = "Explorer"

    # ── [4/5] SERVER
    _step_header(4, 5, L["h_server"])
    print("  " + q(C.G1, "  " + L["server_sub"]))
    print()
    print("  " + q(C.G3, "  Docs: ") + q(C.B7, "https://github.com/Santiagorubioads/nova-os"))
    print()
    print("  " + q(C.G2, "  " + L["server_opts"]))
    print()

    try:
        srv_idx = _select([L["srv_local"], L["srv_remote"], L["srv_already"]], default=0)
    except KeyboardInterrupt:
        print(); return

    if srv_idx == 0:
        url = "http://localhost:8000"
        print()
        info(L["using"] + " http://localhost:8000")
    elif srv_idx == 1:
        print()
        try:
            url = prompt("  " + L["server_url"], cfg.get("api_url", "http://localhost:8000"))
        except (EOFError, KeyboardInterrupt):
            url = cfg.get("api_url", "http://localhost:8000")
    else:
        url = cfg.get("api_url", "http://localhost:8000")
        print()
        info(L["using"] + " " + url)

    print()
    try:
        import getpass
        print("  " + q(C.B6, "?") + "  " + q(C.G1, "  API Key") + "  ", end="", flush=True)
        key = getpass.getpass("").strip() or cfg.get("api_key", "")
    except (EOFError, KeyboardInterrupt):
        key = cfg.get("api_key", "")

    # ── [5/5] CONNECT
    _step_header(5, 5, L["h_connecting"])
    _animate_connect(url)

    loading(L["testing"])
    api    = NovaAPI(url, key)
    health = api.get("/health")
    clear_line()

    connected = "error" not in health
    srv_ver   = health.get("version", "online") if connected else "—"

    if connected:
        ok(L["srv_ok"] + "  · " + q(C.G3, srv_ver))
        ok(L["key_ok"])
    else:
        fail(health.get("error", L["srv_fail"]))
        print()
        warn(L["saved_anyway"] + "  " + q(C.B7, "nova status"))

    cfg.update({"api_url": url, "api_key": key, "user_name": name, "lang": lang,
                "version": NOVA_VERSION})
    save_config(cfg)

    # ── SUCCESS
    print()
    print("  " + q(C.G3, "═" * 54))
    print()
    first = name.split()[0] if name and name != "Explorer" else ""
    greeting = L["youre_in"] + (", " + first + "." if first else ".")
    print("  " + q(C.GRN, "✓", bold=True) + "  " + q(C.W, greeting, bold=True))
    print()
    print("     " + q(C.G1, "nova CLI " + NOVA_VERSION + " " + L["ready"]))
    print()
    print("  " + q(C.G3, "═" * 54))
    print()

    print("  " + q(C.G2, L["next_steps"]))
    print()
    for cmd, desc in [
        ("nova agent create",  L["n1"]),
        ("nova status",        L["n2"]),
        ("nova config",        L["n3"]),
        ("nova skill",         L["n4"]),
    ]:
        print("    " + q(C.B7, cmd.ljust(22), bold=True) + q(C.G2, desc))
    print()


def cmd_status(args):
    """System status dashboard."""
    print_logo()
    api, cfg = _api()

    with Spinner("Loading dashboard...") as sp:
        stats  = api.get("/stats")
        health = api.get("/health")

    if "error" in health:
        fail("Nova not responding at " + q(C.G3, cfg["api_url"]))
        print()
        dim("Check: docker compose -f ~/nova-os/docker-compose.yml up -d")
        print()
        # Show queued actions if any
        queue = get_queue()
        if queue:
            warn(str(len(queue)) + " actions queued offline. Run " +
                 q(C.B7, "nova sync") + " when server is back.")
        print()
        return

    section("Server")
    kv("URL",     cfg["api_url"], C.B7)
    kv("Status",  "Operational",  C.GRN)
    ver = health.get("version", "")
    if ver:
        kv("Version", ver, C.G2)

    if "error" not in stats:
        section("Activity")
        t = stats.get("total_actions", 0)
        a = stats.get("approved", 0)
        b = stats.get("blocked", 0)
        d = stats.get("duplicates_blocked", 0)
        rate = stats.get("approval_rate", 0)

        kv("Total actions",       str(t))
        kv("Approved",            str(a), C.GRN)
        kv("Blocked",             str(b), C.RED if b > 0 else C.G2)
        kv("Duplicates avoided",  str(d), C.ORG if d > 0 else C.G2)
        kv("Approval rate",       str(rate) + "%")
        if t > 0:
            print()
            print("  " + q(C.G2, "Distribution") + "   " + score_bar(rate, 24))

        section("Resources")
        alr = stats.get("alerts_pending", 0)
        kv("Active agents",    str(stats.get("active_agents", 0)),  C.B7)
        kv("Memories stored",  str(stats.get("memories_stored", 0)), C.B6)
        kv("Avg score",        str(stats.get("avg_score", 0)))
        kv("Pending alerts",   str(alr), C.YLW if alr > 0 else C.G2)

        # Score trend sparkline if available
        trend = stats.get("score_trend")
        if trend and isinstance(trend, list) and len(trend) > 1:
            print()
            kv("Score trend (7d)", sparkline(trend))

    # Offline queue check
    queue = get_queue()
    if queue:
        print()
        warn(str(len(queue)) + " actions queued offline")
        dim("Run " + q(C.B7, "nova sync") + " to process them")

    # Version check (non-blocking)
    new_ver = check_version()
    if new_ver:
        print()
        info("Nova " + q(C.B7, new_ver) + " available. Run: " +
             q(C.B7, "pip install --upgrade nova-cli"))
    print()


def cmd_agent_create(args):
    """Create a new agent with intent rules."""
    section("New Agent")
    print("  " + q(C.G2, "Define the behavior rules for your agent."))
    print()

    api, cfg = _api()

    # Ask if they want to start from a template
    print("  " + q(C.G2, "Start from a template or create from scratch?"))
    print()
    try:
        mode = _select(["From template (recommended)", "From scratch"], default=0)
    except KeyboardInterrupt:
        print(); return

    can  = []
    cant = []

    if mode == 0:
        # Template picker
        print()
        print("  " + q(C.W, "Choose a template:", bold=True))
        print()
        tpl_keys = list(RULE_TEMPLATES.keys())
        tpl_opts = []
        for k in tpl_keys:
            t = RULE_TEMPLATES[k]
            tpl_opts.append(t["label"] + "  —  " + t["desc"])

        try:
            tpl_idx = _select(tpl_opts, default=0)
        except KeyboardInterrupt:
            print(); return

        chosen = RULE_TEMPLATES[tpl_keys[tpl_idx]]
        can  = list(chosen["can_do"])
        cant = list(chosen["cannot_do"])

        print()
        ok("Template loaded: " + q(C.B7, chosen["label"]))
        print()

        # Show pre-filled rules
        print("  " + q(C.GRN, "●", bold=True) + "  " + q(C.W, "ALLOWED:"))
        for c in can:
            print("    " + q(C.G2, "  + " + c))
        print()
        print("  " + q(C.RED, "●", bold=True) + "  " + q(C.W, "FORBIDDEN:"))
        for c in cant:
            print("    " + q(C.G2, "  - " + c))
        print()

        if confirm("Customize these rules?", default=False):
            print()
            print("  " + q(C.G2, "Add more ALLOWED actions (empty to skip):"))
            extra_can = prompt_list("Additional allowed actions")
            can.extend(extra_can)

            print("  " + q(C.G2, "Add more FORBIDDEN actions (empty to skip):"))
            extra_cant = prompt_list("Additional forbidden actions")
            cant.extend(extra_cant)
    else:
        pass

    name = prompt("Agent name", "My Agent")
    desc = prompt("Brief description (optional)", "")
    auth = prompt("Authorized by", cfg.get("user_name", "admin@company.com"))
    print()

    if mode == 1:
        print("  " + q(C.GRN, "●", bold=True) + "  " + q(C.W, "ALLOWED actions:"))
        can = prompt_list("One per line")
        print()
        print("  " + q(C.RED, "●", bold=True) + "  " + q(C.W, "FORBIDDEN actions:"))
        cant = prompt_list("One per line")
        print()

    can_preview  = (", ".join(can[:2])  + ("..." if len(can)  > 2 else "")) if can  else "none"
    cant_preview = (", ".join(cant[:2]) + ("..." if len(cant) > 2 else "")) if cant else "none"
    box([
        "  Agent      " + name,
        "  Can do     " + can_preview,
        "  Forbidden  " + cant_preview,
        "  By         " + auth,
    ], C.B5, title="Summary")
    print()

    if not confirm("Create this agent?"):
        warn("Cancelled.")
        return

    with Spinner("Signing Intent Token..."):
        result = api.post("/tokens", {
            "agent_name": name, "description": desc,
            "can_do": can, "cannot_do": cant, "authorized_by": auth,
        })

    if "error" in result:
        print_error(result)
        return

    tid = result.get("token_id", "")
    ok("Agent created — token signed")
    print()
    kv("Token ID",  tid, C.B7)
    kv("Signature", result.get("signature", "")[:24] + "...", C.G3)
    print()

    cfg["default_token"] = tid
    save_config(cfg)

    webhook = cfg["api_url"] + "/webhook/" + cfg["api_key"]
    section("Webhook ready for n8n")
    box([
        "  POST  " + webhook,
        "",
        '  Body:  {"action": "{{$json.texto}}", "token_id": "' + tid[:16] + '..."}',
    ], C.B5)
    print()


def cmd_agent_list(args):
    """List all active agents."""
    api, cfg = _api()

    with Spinner("Loading agents..."):
        result = api.get("/tokens")

    if "error" in result:
        print_error(result)
        return
    if not result:
        warn("No active agents.")
        info("Create one with:  " + q(C.B7, "nova agent create"))
        return

    default_id = cfg.get("default_token", "")
    section("Active Agents", str(len(result)) + " total")

    for t in result:
        is_def = str(t["id"]) == default_id
        badge  = "  " + q(C.B6, "default") if is_def else ""
        st     = q(C.GRN, "● active") if t.get("active") else q(C.G2, "○ inactive")
        print()
        print("  " + q(C.W, t["agent_name"], bold=True) + "  " + st + badge)
        kv("  ID", str(t["id"])[:22] + "...", C.G3)
        created = t.get("created_at", "")
        if created:
            kv("  Created", time_ago(created), C.G2)
        if t.get("can_do"):
            preview = ", ".join(t["can_do"][:3]) + ("..." if len(t["can_do"]) > 3 else "")
            kv("  Can do",    preview, C.GRN)
        if t.get("cannot_do"):
            preview = ", ".join(t["cannot_do"][:3]) + ("..." if len(t["cannot_do"]) > 3 else "")
            kv("  Forbidden", preview, C.RED)
    print()


def cmd_validate(args):
    """Validate an action and get verdict."""
    api, cfg = _api()
    tid    = args.token or cfg.get("default_token", "")
    action = args.action or prompt("Action to validate")
    ctx    = args.context or ""
    dry    = getattr(args, "dry_run", False)

    if not tid:
        fail("No token set. Pass --token or create an agent first.")
        return

    payload = {
        "token_id": tid, "action": action, "context": ctx,
        "generate_response": True, "check_duplicates": True,
    }
    if dry:
        payload["dry_run"] = True

    t0 = time.time()
    with Spinner("Validating..."):
        result = api.post("/validate", payload)
    ms = int((time.time() - t0) * 1000)

    if "error" in result:
        # Offer to queue if offline
        if "Cannot connect" in result.get("error", ""):
            print()
            fail("Server unreachable.")
            if confirm("Queue this action for later?", default=True):
                n = queue_action(payload)
                ok("Action queued (" + str(n) + " pending). Run " +
                   q(C.B7, "nova sync") + " when server is back.")
            return
        print_error(result)
        return

    verdict = result.get("verdict", "?")
    score   = result.get("score", 0)
    reason  = result.get("reason", "")
    resp    = result.get("response")
    dup     = result.get("duplicate_of")
    factors = result.get("score_factors")

    if dry:
        print()
        warn("DRY RUN — not recorded to ledger")

    print()
    print("  " + verdict_badge(verdict) + "   " + score_bar(score) + "   " + q(C.G3, str(ms) + "ms"))
    print()
    kv("Reason",         reason, C.G2)
    kv("Agent",          result.get("agent_name", ""), C.W)
    kv("Ledger",         "#" + str(result.get("ledger_id", "?")), C.G3)
    kv("Memories used",  str(result.get("memories_used", 0)), C.B6)

    # Score breakdown
    if factors and isinstance(factors, dict):
        print()
        print("  " + q(C.G2, "Score Breakdown"))
        print("  " + q(C.G3, "─" * 32))
        for factor, impact in factors.items():
            c = C.GRN if impact > 0 else C.RED if impact < 0 else C.G2
            sign = "+" if impact > 0 else ""
            print("  " + q(c, (sign + str(impact)).rjust(5)) + "  " + q(C.G1, factor))
        print("  " + q(C.G3, "─" * 32))
        print("  " + q(C.W, str(score).rjust(5), bold=True) + "  " + q(C.G2, "Final score"))

    if dup:
        print()
        dup_action = dup.get("action", "")
        dup_short  = dup_action[:52] + ("…" if len(dup_action) > 52 else "")
        box([
            "  Duplicate of record #" + str(dup.get("ledger_id")),
            "  Similarity  " + str(int(dup.get("similarity", 0) * 100)) + "%",
            "  Original    " + dup_short,
        ], C.ORG, title="Duplicate Detected")

    if resp:
        print()
        section("Generated Response")
        print()
        for line in textwrap.wrap(resp, width=64):
            print("  " + q(C.G1, line))

    print()
    h = result.get("hash", "")[:20]
    if h:
        print("  " + q(C.G3, "hash  " + h + "..."))
    print()


def cmd_test(args):
    """Dry-run validation — test without recording."""
    args.dry_run = True
    cmd_validate(args)


def cmd_memory_save(args):
    """Save a memory to an agent's context."""
    api, cfg = _api()
    agent = args.agent or prompt("Agent")
    key   = args.key   or prompt("Key", "important_data")
    value = args.value or prompt("Value")
    imp   = int(getattr(args, "importance", None) or "5")

    with Spinner("Saving memory..."):
        r = api.post("/memory", {
            "agent_name": agent, "key": key, "value": value,
            "importance": imp, "tags": ["manual"],
        })

    if "error" in r:
        print_error(r)
        return
    ok("Memory saved — ID " + str(r.get("id")) + "  importance " + str(imp) + "/10")
    print()


def cmd_memory_list(args):
    """List memories for an agent."""
    api, cfg = _api()
    agent = args.agent or prompt("Agent")

    with Spinner("Loading memories..."):
        result = api.get("/memory/" + urllib.parse.quote(agent))

    if "error" in result:
        print_error(result)
        return
    if not result:
        warn("'" + agent + "' has no memories.")
        cmd_hint = 'nova memory save --agent "' + agent + '"'
        info("Save with:  " + q(C.B7, cmd_hint))
        return

    section("Memories of " + agent, str(len(result)) + " entries")
    for m in result:
        imp = m.get("importance", 5)
        bar = q(C.B6, "█" * imp) + q(C.G3, "░" * (10 - imp))
        src = q(C.G3, m.get("source", "manual"))
        ts  = time_ago(m.get("created_at", ""))
        print()
        print("  " + q(C.W, m["key"], bold=True) + "  " + bar + "  " + src +
              ("  " + q(C.G3, ts) if ts else ""))
        for line in textwrap.wrap(m["value"], width=62):
            print("    " + q(C.G2, line))
    print()


def cmd_ledger(args):
    """View the cryptographic action ledger."""
    api, cfg = _api()
    limit   = getattr(args, "limit", 10) or 10
    verdict = getattr(args, "verdict", "") or ""
    url     = "/ledger?limit=" + str(limit) + ("&verdict=" + verdict.upper() if verdict else "")

    with Spinner("Loading ledger..."):
        result = api.get(url)

    if "error" in result:
        print_error(result)
        return

    section("Ledger", str(len(result)) + " entries")
    vc_map = {
        "APPROVED": C.GRN, "BLOCKED": C.RED,
        "ESCALATED": C.YLW, "DUPLICATE": C.ORG,
    }
    for e in result:
        v   = e.get("verdict", "?")
        s   = e.get("score", 0)
        vc  = vc_map.get(v, C.G2)
        act = e.get("action", "")
        ts  = time_ago(e.get("executed_at", ""))
        print()
        short = act[:56] + ("…" if len(act) > 56 else "")
        print("  " + q(vc, "■") + "  " + q(C.W, short))
        print("     " + q(vc, v.ljust(10)) + "  score " + score_bar(s, 10) +
              "  " + q(C.G3, ts) + "  " + q(C.G3, e.get("agent_name", "")[:22]))
    print()


def cmd_verify(args):
    """Verify ledger cryptographic integrity."""
    api, cfg = _api()

    with Spinner("Verifying cryptographic chain..."):
        r = api.get("/ledger/verify")

    if "error" in r:
        print_error(r)
        return
    print()
    if r.get("verified"):
        ok("Chain intact — " + str(r.get("total_records", 0)) + " records verified")
        kv("Status", "No modifications detected", C.GRN)
        h = r.get("chain_hash", "")
        if h:
            kv("Chain hash", h[:32] + "...", C.G3)
    else:
        fail("Chain compromised at record #" + str(r.get("broken_at")))
        warn("A ledger record has been tampered with.")
    print()


def cmd_alerts(args):
    """View pending alerts."""
    api, cfg = _api()

    with Spinner("Loading alerts..."):
        r = api.get("/alerts")

    if "error" in r:
        print_error(r)
        return

    pending = [a for a in r if not a.get("resolved")]
    if not pending:
        ok("No pending alerts.")
        print()
        return

    section("Pending Alerts", str(len(pending)))
    for a in pending:
        s  = a.get("score", 0)
        ac = C.RED if s < 40 else C.YLW
        ts = time_ago(a.get("created_at", ""))
        print()
        print("  " + q(ac, "▲") + "  " + q(C.W, a.get("message", "")[:62]))
        print("     " + q(C.G2, "Score ") + q(ac, str(s), bold=True) +
              "   " + q(C.G3, a.get("agent_name", "")) +
              "   " + q(C.G3, str(a["id"])[:12]) +
              ("   " + q(C.G3, ts) if ts else ""))
    print()
    dim("Resolve:  nova alerts resolve <id>")
    print()


def cmd_seed(args):
    """Seed demo data for testing."""
    api, cfg = _api()

    warn("This will insert demo agents and actions.")
    if not confirm("Continue?"):
        return

    with Spinner("Seeding demo data..."):
        r = api.post("/demo/seed", {})

    if "error" in r:
        print_error(r)
        return
    ok("Demo data loaded.")
    kv("Agents",   str(r.get("tokens", 0)),   C.B7)
    kv("Actions",  str(r.get("actions", 0)))
    kv("Memories", str(r.get("memories", 0)), C.B6)
    print()
    info("Explore with:  " + q(C.B7, "nova status"))
    print()


# ══════════════════════════════════════════════════════════════════
# WATCH — Live tail of ledger
# ══════════════════════════════════════════════════════════════════

def cmd_watch(args):
    """Live stream of ledger entries."""
    api, cfg = _api()
    interval = getattr(args, "interval", 3) or 3

    print_logo(compact=True)
    print("  " + q(C.W, "Watching ledger...", bold=True) + "  " + q(C.G3, "Ctrl+C to stop"))
    print("  " + q(C.G3, "─" * 54))
    print()

    seen = set()
    vc_map = {
        "APPROVED": C.GRN, "BLOCKED": C.RED,
        "ESCALATED": C.YLW, "DUPLICATE": C.ORG,
    }

    try:
        while True:
            result = api.get("/ledger?limit=10")
            if isinstance(result, list):
                for e in reversed(result):
                    eid = e.get("id", "")
                    if eid and eid not in seen:
                        seen.add(eid)
                        v   = e.get("verdict", "?")
                        vc  = vc_map.get(v, C.G2)
                        act = e.get("action", "")[:52]
                        ts  = time_ago(e.get("executed_at", ""))
                        s   = e.get("score", 0)
                        print("  " + q(vc, "■") + "  " + q(C.W, act) + "  " +
                              q(vc, v) + "  " + score_bar(s, 8) + "  " + q(C.G3, ts))
            time.sleep(interval)
    except KeyboardInterrupt:
        print()
        info("Stopped watching.")
        print()


# ══════════════════════════════════════════════════════════════════
# REPLAY — Re-evaluate past action with current rules
# ══════════════════════════════════════════════════════════════════

def cmd_replay(args):
    """Re-evaluate a past action with current rules."""
    api, cfg = _api()
    ledger_id = args.subcommand or args.third or ""
    if not ledger_id:
        ledger_id = prompt("Ledger entry ID")

    with Spinner("Loading original entry..."):
        entries = api.get("/ledger?limit=100")

    if "error" in entries:
        print_error(entries)
        return

    # Find entry
    entry = None
    for e in entries:
        if str(e.get("id", "")) == str(ledger_id):
            entry = e
            break

    if not entry:
        fail("Ledger entry #" + str(ledger_id) + " not found.")
        return

    print()
    section("Replaying entry #" + str(ledger_id))
    kv("Action",    entry.get("action", "")[:50], C.W)
    kv("Original",  entry.get("verdict", "?"), C.G2)
    kv("Score",     str(entry.get("score", 0)), C.G2)

    with Spinner("Re-evaluating with current rules..."):
        result = api.post("/validate", {
            "token_id": entry.get("token_id", cfg.get("default_token", "")),
            "action": entry.get("action", ""),
            "context": entry.get("context", ""),
            "dry_run": True,
        })

    if "error" in result:
        print_error(result)
        return

    new_verdict = result.get("verdict", "?")
    new_score   = result.get("score", 0)

    print()
    section("Original vs Current")
    old_v = entry.get("verdict", "?")
    vc_map = {"APPROVED": C.GRN, "BLOCKED": C.RED, "ESCALATED": C.YLW, "DUPLICATE": C.ORG}
    kv("Original verdict", old_v, vc_map.get(old_v, C.G2))
    kv("Current verdict",  new_verdict, vc_map.get(new_verdict, C.G2))
    kv("Original score",   str(entry.get("score", 0)))
    kv("Current score",    str(new_score))

    if old_v != new_verdict:
        print()
        warn("Verdict changed! Rules have been modified since original validation.")
    else:
        print()
        ok("Verdict is consistent — rules unchanged.")
    print()


# ══════════════════════════════════════════════════════════════════
# DIFF — Compare two agents
# ══════════════════════════════════════════════════════════════════

def cmd_diff(args):
    """Compare rules between two agents."""
    api, cfg = _api()

    with Spinner("Loading agents..."):
        tokens = api.get("/tokens")

    if "error" in tokens:
        print_error(tokens)
        return
    if not tokens or len(tokens) < 2:
        warn("Need at least 2 agents to compare.")
        return

    # Let user pick two agents
    names = [t["agent_name"] for t in tokens]
    print()
    print("  " + q(C.W, "Select first agent:", bold=True))
    print()
    try:
        idx1 = _select(names, default=0)
    except KeyboardInterrupt:
        print(); return

    print("  " + q(C.W, "Select second agent:", bold=True))
    print()
    remaining = [n for i, n in enumerate(names) if i != idx1]
    if not remaining:
        fail("Need at least 2 agents.")
        return
    try:
        idx2_r = _select(remaining, default=0)
    except KeyboardInterrupt:
        print(); return

    t1 = tokens[idx1]
    # Find t2 in original list
    chosen_name = remaining[idx2_r]
    t2 = next(t for t in tokens if t["agent_name"] == chosen_name)

    section("Diff: " + t1["agent_name"] + " vs " + t2["agent_name"])

    can1  = set(t1.get("can_do", []))
    can2  = set(t2.get("can_do", []))
    cant1 = set(t1.get("cannot_do", []))
    cant2 = set(t2.get("cannot_do", []))

    print()
    print("  " + q(C.W, "ALLOWED actions:", bold=True))
    for x in sorted(can1 - can2):
        print("    " + q(C.RED, "-") + "  " + q(C.G1, x) + "  " + q(C.G3, "(only " + t1["agent_name"] + ")"))
    for x in sorted(can2 - can1):
        print("    " + q(C.GRN, "+") + "  " + q(C.G1, x) + "  " + q(C.G3, "(only " + t2["agent_name"] + ")"))
    for x in sorted(can1 & can2):
        print("    " + q(C.G3, " ") + "  " + q(C.G3, x))
    if not (can1 | can2):
        print("    " + q(C.G3, "(none)"))

    print()
    print("  " + q(C.W, "FORBIDDEN actions:", bold=True))
    for x in sorted(cant1 - cant2):
        print("    " + q(C.RED, "-") + "  " + q(C.G1, x) + "  " + q(C.G3, "(only " + t1["agent_name"] + ")"))
    for x in sorted(cant2 - cant1):
        print("    " + q(C.GRN, "+") + "  " + q(C.G1, x) + "  " + q(C.G3, "(only " + t2["agent_name"] + ")"))
    for x in sorted(cant1 & cant2):
        print("    " + q(C.G3, " ") + "  " + q(C.G3, x))
    if not (cant1 | cant2):
        print("    " + q(C.G3, "(none)"))
    print()


# ══════════════════════════════════════════════════════════════════
# EXPORT — Export ledger to JSON/CSV
# ══════════════════════════════════════════════════════════════════

def cmd_export(args):
    """Export ledger entries to JSON or CSV."""
    api, cfg = _api()
    fmt    = getattr(args, "format", "json") or "json"
    limit  = getattr(args, "limit", 1000) or 1000
    output = getattr(args, "output", "") or ""

    with Spinner("Exporting ledger..."):
        entries = api.get("/ledger?limit=" + str(limit))

    if "error" in entries:
        print_error(entries)
        return
    if not entries:
        warn("No ledger entries to export.")
        return

    if not output:
        ext = "csv" if fmt == "csv" else "json"
        output = "nova-ledger-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "." + ext

    if fmt == "csv":
        # CSV export without importing csv module (zero deps)
        if entries:
            fields = list(entries[0].keys())
            lines = [",".join(fields)]
            for e in entries:
                row = []
                for f in fields:
                    val = str(e.get(f, "")).replace('"', '""')
                    if "," in val or '"' in val or "\n" in val:
                        val = '"' + val + '"'
                    row.append(val)
                lines.append(",".join(row))
            with open(output, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
    else:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    ok("Exported " + str(len(entries)) + " entries to " + q(C.B7, output))
    kv("Format", fmt.upper(), C.G2)
    kv("Size",   str(os.path.getsize(output)) + " bytes", C.G2)
    print()


# ══════════════════════════════════════════════════════════════════
# SIMULATE — Batch validate from file
# ══════════════════════════════════════════════════════════════════

def cmd_simulate(args):
    """Batch-validate actions from a file or interactive list."""
    api, cfg = _api()
    tid = args.token or cfg.get("default_token", "")

    if not tid:
        fail("No token set. Pass --token or create an agent first.")
        return

    file_path = getattr(args, "file", "") or ""
    actions = []

    if file_path and os.path.exists(file_path):
        with open(file_path) as f:
            actions = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    else:
        print()
        print("  " + q(C.W, "Enter actions to simulate", bold=True) +
              "  " + q(C.G3, "(one per line, empty line to run)"))
        print()
        actions = prompt_list("Actions")

    if not actions:
        warn("No actions to simulate.")
        return

    print()
    section("Simulating " + str(len(actions)) + " actions", "dry run")
    print()

    results = {"APPROVED": 0, "BLOCKED": 0, "ESCALATED": 0, "DUPLICATE": 0}
    scores = []
    vc_map = {"APPROVED": C.GRN, "BLOCKED": C.RED, "ESCALATED": C.YLW, "DUPLICATE": C.ORG}

    for i, action in enumerate(actions):
        progress_bar(i + 1, len(actions), label=action[:30])
        r = api.post("/validate", {
            "token_id": tid, "action": action, "dry_run": True,
        })
        v = r.get("verdict", "?")
        s = r.get("score", 0)
        results[v] = results.get(v, 0) + 1
        scores.append(s)

    print()  # newline after progress bar
    print()

    # Results
    section("Simulation Results")
    print()
    for v in ["APPROVED", "BLOCKED", "ESCALATED", "DUPLICATE"]:
        count = results.get(v, 0)
        if count > 0:
            c = vc_map.get(v, C.G2)
            pct = int(count / len(actions) * 100)
            bar_w = int(count / len(actions) * 20)
            print("  " + q(c, v.ljust(12)) + "  " + q(c, str(count).rjust(3)) +
                  "  " + q(c, "█" * bar_w) + q(C.G3, "░" * (20 - bar_w)) +
                  "  " + q(C.G2, str(pct) + "%"))

    if scores:
        avg = sum(scores) / len(scores)
        print()
        kv("Average score", str(int(avg)), C.W)
        kv("Score range",   str(min(scores)) + " — " + str(max(scores)), C.G2)
        kv("Distribution",  sparkline(scores))
    print()


# ══════════════════════════════════════════════════════════════════
# SYNC — Process offline queue
# ══════════════════════════════════════════════════════════════════

def cmd_sync(args):
    """Process actions queued while offline."""
    api, cfg = _api()
    queue = get_queue()

    if not queue:
        ok("No pending actions in queue.")
        print()
        return

    section("Syncing " + str(len(queue)) + " queued actions")
    print()

    success, failed = 0, 0
    for i, item in enumerate(queue):
        progress_bar(i + 1, len(queue), label="Syncing...")
        result = api.post("/validate", item["data"])
        if "error" not in result:
            success += 1
        else:
            failed += 1

    print()
    print()

    if success > 0:
        ok(str(success) + " actions synced successfully")
    if failed > 0:
        fail(str(failed) + " actions failed")

    clear_queue()
    print()


# ══════════════════════════════════════════════════════════════════
# AUDIT — Generate signed audit report
# ══════════════════════════════════════════════════════════════════

def cmd_audit(args):
    """Generate a signed audit report."""
    api, cfg = _api()

    with Spinner("Generating audit report..."):
        stats  = api.get("/stats")
        verify = api.get("/ledger/verify")
        recent = api.get("/ledger?limit=5")

    if "error" in stats:
        print_error(stats)
        return

    report = {
        "report_type": "nova_audit",
        "generated_at": datetime.now().isoformat(),
        "cli_version": NOVA_VERSION,
        "server_url": cfg["api_url"],
        "stats": stats if "error" not in stats else {},
        "chain_verified": verify.get("verified", False) if "error" not in verify else None,
        "chain_records": verify.get("total_records", 0) if "error" not in verify else 0,
        "chain_hash": verify.get("chain_hash", "") if "error" not in verify else "",
        "recent_entries": recent if isinstance(recent, list) else [],
    }

    # Sign the report
    report_json = json.dumps(report, sort_keys=True)
    report["signature"] = hashlib.sha256(report_json.encode()).hexdigest()

    filename = "nova-audit-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    ok("Audit report generated")
    print()
    kv("File",       filename, C.B7)
    kv("Records",    str(report["chain_records"]))
    kv("Chain",      "Verified" if report["chain_verified"] else "Unverified",
       C.GRN if report["chain_verified"] else C.RED)
    kv("Signature",  report["signature"][:32] + "...", C.G3)
    kv("Size",       str(os.path.getsize(filename)) + " bytes", C.G2)
    print()


# ══════════════════════════════════════════════════════════════════
# WHOAMI — Current config summary
# ══════════════════════════════════════════════════════════════════

def cmd_whoami(args):
    """Show current configuration identity."""
    cfg = load_config()
    api_key = cfg.get("api_key", "")
    key_display = ("*" * 8 + api_key[-4:]) if len(api_key) >= 4 else ("not set" if not api_key else api_key)

    print_logo(compact=True)
    print()
    kv("User",     cfg.get("user_name", "not set"), C.W)
    kv("Server",   cfg.get("api_url", "not set"), C.B7)
    kv("API Key",  key_display, C.G2)
    kv("Agent",    (cfg.get("default_token", "")[:20] + "...") if cfg.get("default_token") else "none", C.G3)
    kv("Language", "English" if cfg.get("lang", "en") == "en" else "Español", C.G2)
    kv("Config",   CONFIG_FILE, C.G3)
    kv("Version",  NOVA_VERSION, C.B6)

    # Config validation
    issues = validate_config(cfg)
    if issues:
        print()
        for issue in issues:
            warn(issue)

    # Installed skills
    installed = [k for k in SKILLS if skill_status(k) == "installed"]
    if installed:
        print()
        kv("Skills", ", ".join(installed), C.GRN)

    # Queue
    queue = get_queue()
    if queue:
        print()
        kv("Queued actions", str(len(queue)), C.YLW)
    print()


# ══════════════════════════════════════════════════════════════════
# WEBHOOK TEST
# ══════════════════════════════════════════════════════════════════

def cmd_webhook_test(args):
    """Test webhook connectivity."""
    cfg = load_config()
    url = cfg["api_url"] + "/webhook/" + cfg["api_key"]

    test_payload = {
        "action": "test action from nova CLI",
        "token_id": cfg.get("default_token", "test"),
        "_test": True,
    }

    with Spinner("Sending test webhook..."):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(test_payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                status = r.status
                body = r.read().decode()[:200]
        except urllib.error.HTTPError as e:
            status = e.code
            body = str(e)
        except Exception as e:
            status = 0
            body = str(e)

    if 200 <= status < 300:
        ok("Webhook responding (" + str(status) + ")")
        if body:
            print()
            print("  " + q(C.G2, "Response:"))
            print("  " + q(C.G1, body))
    else:
        fail("Webhook failed" + (" (" + str(status) + ")" if status else "") + ": " + body)
    print()


# ══════════════════════════════════════════════════════════════════
# COMPLETION — Shell autocompletion
# ══════════════════════════════════════════════════════════════════

def cmd_completion(args):
    """Generate shell completion script."""
    shell = args.subcommand or ""
    if not shell:
        # Try to detect shell
        shell_path = os.environ.get("SHELL", "")
        if "zsh" in shell_path:
            shell = "zsh"
        elif "fish" in shell_path:
            shell = "fish"
        else:
            shell = "bash"

    commands = "init status config agent validate memory ledger skill help " \
               "watch replay diff export simulate sync audit whoami test " \
               "seed alerts verify webhook completion"
    sub_agent  = "create list"
    sub_memory = "save list"
    sub_skill  = "add remove info list"

    if shell == "bash":
        print("""
# nova CLI bash completion
# Add to ~/.bashrc: eval "$(nova completion bash)"
_nova_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    case "$prev" in
        agent)  COMPREPLY=($(compgen -W \"""" + sub_agent + """\" -- "$cur"));;
        memory) COMPREPLY=($(compgen -W \"""" + sub_memory + """\" -- "$cur"));;
        skill)  COMPREPLY=($(compgen -W \"""" + sub_skill + """\" -- "$cur"));;
        *)      COMPREPLY=($(compgen -W \"""" + commands + """\" -- "$cur"));;
    esac
}
complete -F _nova_completions nova
""".strip())
    elif shell == "zsh":
        print("""
# nova CLI zsh completion
# Add to ~/.zshrc: eval "$(nova completion zsh)"
_nova() {
    local -a commands=(
        'init:First-run setup'
        'status:System health and metrics'
        'config:Skills, server, preferences'
        'agent:Agent management'
        'validate:Validate an action'
        'test:Dry-run validation'
        'memory:Agent memory'
        'ledger:Action history'
        'skill:Skill catalog'
        'watch:Live ledger tail'
        'replay:Re-evaluate past action'
        'diff:Compare agents'
        'export:Export ledger'
        'simulate:Batch testing'
        'sync:Process offline queue'
        'audit:Generate audit report'
        'whoami:Current config'
        'help:Show help'
    )
    _describe 'commands' commands
}
compdef _nova nova
""".strip())
    elif shell == "fish":
        print("""
# nova CLI fish completion
# Save to ~/.config/fish/completions/nova.fish
complete -c nova -n __fish_use_subcommand -a init -d 'First-run setup'
complete -c nova -n __fish_use_subcommand -a status -d 'System health'
complete -c nova -n __fish_use_subcommand -a config -d 'Configuration'
complete -c nova -n __fish_use_subcommand -a agent -d 'Agent management'
complete -c nova -n __fish_use_subcommand -a validate -d 'Validate action'
complete -c nova -n __fish_use_subcommand -a test -d 'Dry-run validation'
complete -c nova -n __fish_use_subcommand -a memory -d 'Agent memory'
complete -c nova -n __fish_use_subcommand -a ledger -d 'Action history'
complete -c nova -n __fish_use_subcommand -a skill -d 'Skill catalog'
complete -c nova -n __fish_use_subcommand -a watch -d 'Live ledger tail'
complete -c nova -n __fish_use_subcommand -a export -d 'Export ledger'
complete -c nova -n __fish_use_subcommand -a whoami -d 'Current config'
complete -c nova -n __fish_use_subcommand -a help -d 'Show help'
""".strip())
    else:
        fail("Unknown shell: " + shell)
        info("Supported: bash, zsh, fish")


# ══════════════════════════════════════════════════════════════════
# CONFIG HUB
# ══════════════════════════════════════════════════════════════════

def cmd_config(args):
    """Interactive configuration hub."""
    while True:
        cfg       = load_config()
        api_url   = cfg.get("api_url", "http://localhost:8000")
        api_key   = cfg.get("api_key", "")
        installed = [k for k in SKILLS if skill_status(k) == "installed"]

        connected = False
        try:
            h = NovaAPI(api_url, api_key).get("/health")
            connected = "error" not in h
        except Exception:
            pass

        key_display = ("*" * 8 + api_key[-4:]) if len(api_key) >= 4 else ("not set" if not api_key else api_key)
        srv_status  = ("connected" if connected else "unreachable")
        skill_count = str(len(installed)) + "/" + str(len(SKILLS)) + " installed"

        print_logo(compact=True)
        print("  " + q(C.G3, "─" * 52))
        print()
        kv("  Server",  api_url[:38], C.B7 if connected else C.YLW)
        kv("  Status",  srv_status,   C.GRN if connected else C.YLW)
        kv("  API Key", key_display,  C.G2)
        kv("  Skills",  skill_count,  C.GRN if installed else C.G2)
        print()

        # Config validation warnings
        issues = validate_config(cfg)
        if issues:
            for issue in issues:
                warn(issue)
            print()

        print("  " + q(C.G3, "─" * 52))
        print()

        opts = [
            "Server        — update URL",
            "API Key       — update credentials",
            "Skills        — install integrations",
            "Templates     — pre-built agent rules",
            "Preferences   — language",
            "About         — version, docs",
            "Reset         — clear all settings",
            "Exit",
        ]

        try:
            choice = _select(opts, default=0)
        except KeyboardInterrupt:
            print(); break

        if choice == 7:  # Exit
            break

        if choice == 0:  # Server
            print()
            section("Server")
            kv("URL", api_url, C.B7)
            kv("Status", "Connected" if connected else "Unreachable",
               C.GRN if connected else C.RED)
            print()
            try:
                new_url = prompt("New URL (Enter to keep)", api_url)
                if new_url and new_url != api_url:
                    cfg["api_url"] = new_url
                    save_config(cfg)
                    ok("Server URL updated.")
            except (EOFError, KeyboardInterrupt):
                pass

        elif choice == 1:  # API Key
            print()
            section("API Key")
            kv("Current", key_display, C.G2)
            print()
            try:
                import getpass
                print("  " + q(C.B6, "?") + "  " + q(C.G1, "New API Key (Enter to keep)") +
                      "  ", end="", flush=True)
                new_key = getpass.getpass("").strip()
                if new_key:
                    cfg["api_key"] = new_key
                    save_config(cfg)
                    ok("API Key updated.")
            except (EOFError, KeyboardInterrupt):
                pass

        elif choice == 2:  # Skills
            _config_skills_hub()

        elif choice == 3:  # Templates
            _config_templates_hub()

        elif choice == 4:  # Preferences
            print()
            section("Preferences")
            lang = cfg.get("lang", "en")
            kv("Language", "English" if lang == "en" else "Español", C.W)
            print()
            try:
                lang_idx = _select(["English", "Español"],
                                   default=0 if lang == "en" else 1)
                cfg["lang"] = "en" if lang_idx == 0 else "es"
                save_config(cfg)
                ok("Saved.")
            except (EOFError, KeyboardInterrupt):
                pass

        elif choice == 5:  # About
            print()
            section("About nova")
            kv("Version", NOVA_VERSION, C.B6)
            kv("Config",  CONFIG_FILE,  C.G2)
            kv("Skills",  skill_count,  C.G2)
            kv("Docs",    "https://github.com/Santiagorubioads/nova-os", C.B7)
            kv("Support", "https://nova-os.com/support", C.B7)
            print()
            # Show changelog highlights
            print("  " + q(C.G2, "What's new in " + NOVA_VERSION + ":"))
            for item in [
                "Animated spinners for all async operations",
                "Rule templates for quick agent setup",
                "Live ledger watch mode",
                "Batch simulation from file",
                "Offline queue with automatic sync",
                "Shell autocompletion (bash/zsh/fish)",
                "Audit report generation with signatures",
                "Agent diff comparison",
                "Sparkline visualizations",
            ]:
                print("    " + q(C.B6, "·") + "  " + q(C.G1, item))
            print()
            _pause("go back")

        elif choice == 6:  # Reset
            print()
            warn("This will erase all local nova config and installed skills.")
            print()
            try:
                idx = _select(["Cancel", "Yes, reset everything"], default=0)
                if idx == 1:
                    import shutil
                    shutil.rmtree(NOVA_DIR, ignore_errors=True)
                    ok("nova reset. Run " + q(C.B7, "nova init") + " to start fresh.")
                    print()
                    break
            except (EOFError, KeyboardInterrupt):
                pass
        print()


def _config_templates_hub():
    """Browse and preview rule templates."""
    print()
    section("Rule Templates")
    print("  " + q(C.G1, "Pre-built rule sets for common agent patterns."))
    print("  " + q(C.G2, "Use them with  " + q(C.B7, "nova agent create")))
    print()

    for key, tpl in RULE_TEMPLATES.items():
        print("  " + q(C.B6, "●") + "  " + q(C.W, tpl["label"], bold=True) +
              "  " + q(C.G2, tpl["desc"]))
        can_preview = ", ".join(tpl["can_do"][:2]) + ("..." if len(tpl["can_do"]) > 2 else "")
        cant_preview = ", ".join(tpl["cannot_do"][:2]) + ("..." if len(tpl["cannot_do"]) > 2 else "")
        print("       " + q(C.GRN, "✓ ") + q(C.G2, can_preview))
        print("       " + q(C.RED, "✗ ") + q(C.G2, cant_preview))
        print()

    _pause("go back")


def _config_skills_hub():
    """Skills hub — arrow-key browsable catalog."""
    while True:
        all_keys = list(SKILLS.keys())

        print()
        print_logo(compact=True)
        print("  " + q(C.W, "Skills  ", bold=True) + q(C.B6, "✦") +
              "  " + q(C.G2, "The Constellation"))
        print("  " + q(C.G3, "─" * 52))
        print()
        print("  " + q(C.G1, "  Skills give nova real-world context before every decision."))
        print("  " + q(C.G2, "  Install what you need. Nothing else runs."))
        print()

        opts = []
        for k in all_keys:
            s   = SKILLS[k]
            st  = skill_status(k)
            tag = " [installed]" if st == "installed" else ""
            opts.append(s["icon"] + "  " + s["name"].ljust(14) + tag + "  " + s["desc"][:28])
        opts.append("Back")

        try:
            idx = _select(opts, default=0)
        except KeyboardInterrupt:
            print(); break

        if idx == len(opts) - 1:
            break

        name = all_keys[idx]
        fake = type("A", (), {"third": name, "subcommand": "add",
                              "agent": "", "reconfigure": False})()
        cmd_skill_add(fake)


# ══════════════════════════════════════════════════════════════════
# SKILLS CATALOG
# ══════════════════════════════════════════════════════════════════

SKILLS = {
    "gmail": {
        "name": "Gmail",
        "category": "Communication",
        "icon": "✉",
        "color": "RED",
        "desc": "Verify sent emails, detect duplicates, read inbox",
        "what": "nova checks your Gmail before approving any send action",
        "fields": [
            ("service_account_json", "Path to Service Account JSON file", False),
            ("delegated_email",      "Your Google account email",         False),
        ],
        "docs": "https://console.cloud.google.com/iam-admin/serviceaccounts",
        "mcp":  "gmail-mcp",
    },
    "sheets": {
        "name": "Google Sheets",
        "category": "Data",
        "icon": "⊞",
        "color": "GRN",
        "desc": "Read and write your spreadsheets in real time",
        "what": "nova checks your Sheet before executing actions",
        "fields": [
            ("service_account_json", "Path to Service Account JSON file", False),
            ("spreadsheet_id",       "Main Spreadsheet ID",               False),
        ],
        "docs": "https://console.cloud.google.com/iam-admin/serviceaccounts",
        "mcp":  "google-sheets-mcp",
    },
    "slack": {
        "name": "Slack",
        "category": "Communication",
        "icon": "◈",
        "color": "YLW",
        "desc": "Send alerts, read channels, verify sent messages",
        "what": "nova notifies Slack when it blocks or escalates an action",
        "fields": [
            ("bot_token",   "Bot Token (xoxb-...)",        False),
            ("channel",     "Default channel (#general)",  False),
        ],
        "docs": "https://api.slack.com/apps",
        "mcp":  "slack-mcp-server",
    },
    "whatsapp": {
        "name": "WhatsApp",
        "category": "Communication",
        "icon": "◉",
        "color": "GRN",
        "desc": "Verify sent messages, prevent spam, manage contacts",
        "what": "nova checks WhatsApp history before approving messages",
        "fields": [
            ("evolution_api_url", "Evolution API URL",   False),
            ("evolution_api_key", "Evolution API Key",   True),
            ("instance_name",     "Instance name",       False),
        ],
        "docs": "https://doc.evolution-api.com",
        "mcp":  "whatsapp-mcp",
    },
    "telegram": {
        "name": "Telegram",
        "category": "Communication",
        "icon": "◎",
        "color": "B6",
        "desc": "Read & send messages, manage bots, verify channels",
        "what": "nova can receive commands and send alerts via Telegram",
        "fields": [
            ("bot_token",  "Bot Token from @BotFather", True),
            ("chat_id",    "Main Chat ID",              False),
        ],
        "docs": "https://core.telegram.org/bots",
        "mcp":  "telegram-mcp",
    },
    "notion": {
        "name": "Notion",
        "category": "Productivity",
        "icon": "◻",
        "color": "W",
        "desc": "Read databases, create pages, update records",
        "what": "nova can query and update your Notion as source of truth",
        "fields": [
            ("api_key",     "Integration Token (secret_...)", True),
            ("database_id", "Main database ID",               False),
        ],
        "docs": "https://www.notion.so/my-integrations",
        "mcp":  "notion-mcp",
    },
    "airtable": {
        "name": "Airtable",
        "category": "Data",
        "icon": "◈",
        "color": "ORG",
        "desc": "CRM, leads database, inventory — check before acting",
        "what": "nova verifies Airtable records before executing",
        "fields": [
            ("api_key",  "Personal Access Token", True),
            ("base_id",  "Base ID (app...)",      False),
        ],
        "docs": "https://airtable.com/create/tokens",
        "mcp":  "airtable-mcp",
    },
    "github": {
        "name": "GitHub",
        "category": "Development",
        "icon": "◯",
        "color": "W",
        "desc": "Create issues, review PRs, verify code before deploy",
        "what": "nova can block deploys if critical issues are open",
        "fields": [
            ("token",  "Personal Access Token (ghp_...)", True),
            ("repo",   "Default repo (owner/repo)",       False),
        ],
        "docs": "https://github.com/settings/tokens",
        "mcp":  "github-mcp",
    },
    "stripe": {
        "name": "Stripe",
        "category": "Payments",
        "icon": "◈",
        "color": "B7",
        "desc": "Verify charges, detect fraud, approve transactions",
        "what": "nova validates payments and blocks suspicious transactions",
        "fields": [
            ("secret_key", "Secret Key (sk_live_... or sk_test_...)", True),
        ],
        "docs": "https://dashboard.stripe.com/apikeys",
        "mcp":  "stripe-mcp",
    },
    "hubspot": {
        "name": "HubSpot",
        "category": "CRM",
        "icon": "◉",
        "color": "ORG",
        "desc": "Query contacts, deals, communication history",
        "what": "nova checks if a lead was already contacted before approving",
        "fields": [
            ("api_key", "Private App Token", True),
        ],
        "docs": "https://developers.hubspot.com/docs/api/private-apps",
        "mcp":  "hubspot-mcp",
    },
    "supabase": {
        "name": "Supabase",
        "category": "Database",
        "icon": "◈",
        "color": "GRN",
        "desc": "Query your Postgres database in real time",
        "what": "nova can verify any table before executing actions",
        "fields": [
            ("url",         "Project URL (https://xxx.supabase.co)", False),
            ("service_key", "Service Role Key",                      True),
        ],
        "docs": "https://app.supabase.com/project/_/settings/api",
        "mcp":  "supabase-mcp",
    },
    "postgres": {
        "name": "PostgreSQL",
        "category": "Database",
        "icon": "◉",
        "color": "B6",
        "desc": "Direct connection to your PostgreSQL database",
        "what": "nova queries your DB before every critical validation",
        "fields": [
            ("connection_string", "postgresql://user:pass@host:5432/db", True),
        ],
        "docs": "https://www.postgresql.org/docs/current/libpq-connect.html",
        "mcp":  "postgres-mcp",
    },
}

SKILL_CATEGORIES = ["Communication", "Data", "Productivity", "Development", "CRM", "Payments", "Database"]
SKILLS_DIR = os.path.join(NOVA_DIR, "skills")


def load_skill(name):
    path = os.path.join(SKILLS_DIR, name + ".json")
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except:
            pass
    return None


def save_skill(name, data):
    os.makedirs(SKILLS_DIR, exist_ok=True)
    json.dump(data, open(os.path.join(SKILLS_DIR, name + ".json"), "w"), indent=2)


def skill_status(name):
    d = load_skill(name)
    if not d:
        return "not_installed"
    return d.get("status", "installed")


def _skill_color(skill_def):
    color_map = {
        "RED": C.RED, "GRN": C.GRN, "YLW": C.YLW,
        "W": C.W, "B6": C.B6, "B7": C.B7, "ORG": C.ORG,
    }
    return color_map.get(skill_def.get("color", "W"), C.W)


def cmd_skill_list(args):
    """List all available skills."""
    print_logo(tagline=False)
    print("  " + q(C.W, "Available Skills", bold=True) + "  " + q(C.G3, "· connect nova to the world"))
    print("  " + q(C.G3, "─" * 54))
    print()

    print("  " + q(C.B5, "✦") + "  " + q(C.G2, "nova is a new star. Skills are its constellation."))
    print("       " + q(C.G2, "Install what you need — each one expands what nova can see."))
    print()

    for cat in SKILL_CATEGORIES:
        cat_skills = [(k, v) for k, v in SKILLS.items() if v["category"] == cat]
        if not cat_skills:
            continue

        print("  " + q(C.G3, cat.upper()))
        print()

        for name, s in cat_skills:
            st   = skill_status(name)
            sc   = _skill_color(s)
            icon = s["icon"]

            if st == "installed":
                badge = q(C.GRN, " installed", bold=True)
                dot   = q(C.GRN, "●")
            else:
                badge = ""
                dot   = q(C.G2, "○")

            print("  " + dot + "  " + q(sc, icon + " " + s["name"], bold=True) +
                  badge + "  " + q(C.G2, s["desc"]))
        print()

    print("  " + q(C.G3, "─" * 54))
    print()
    print("  " + q(C.B7, "nova skill add <name>", bold=True) + "     " + q(C.G2, "install a skill"))
    print("  " + q(C.B7, "nova skill info <name>") + "    " + q(C.G2, "view details"))
    print("  " + q(C.B7, "nova skill remove <name>") + "  " + q(C.G2, "uninstall"))
    print()


def cmd_skill_info(args):
    """Show detailed information about a skill."""
    name = getattr(args, "third", "") or args.subcommand or args.agent or ""
    if name in ("info", "add", "list", "remove", ""):
        name = getattr(args, "third", "") or args.agent or ""

    if not name or name not in SKILLS:
        fail("Skill not found: " + (name or "?"))
        print()
        info("Available skills: " + ", ".join(SKILLS.keys()))
        return

    s  = SKILLS[name]
    sc = _skill_color(s)
    st = skill_status(name)
    data = load_skill(name)

    print()
    print("  " + q(sc, s["icon"] + "  " + s["name"], bold=True) +
          "  " + q(C.G3, s["category"]))
    print()
    kv("Description",  s["desc"])
    kv("What it does", s["what"], C.G2)
    kv("MCP",          s["mcp"], C.G3)
    kv("Docs",         s["docs"], C.B7)
    kv("Status",       ("✓ installed" if st == "installed" else "not installed"),
       C.GRN if st == "installed" else C.G2)

    if data and data.get("installed_at"):
        kv("Installed", time_ago(data["installed_at"]), C.G3)

    section("Required Fields")
    for field, label, secret in s["fields"]:
        val = ""
        if data and data.get(field):
            v = data[field]
            val = q(C.GRN, ("*" * 8) if secret else v[:32])
        else:
            val = q(C.G2, "not configured")
        kv("  " + field, val if val else label)

    print()
    if st != "installed":
        info("Install:  " + q(C.B7, "nova skill add " + name))
    else:
        info("Reconfigure:  " + q(C.B7, "nova skill add " + name + " --reconfigure"))
    print()


def cmd_skill_add(args):
    """Install or reconfigure a skill."""
    raw = getattr(args, "third", "") or args.subcommand or args.agent or ""
    if raw in ("add", "remove", "list", "info", "install", ""):
        raw = getattr(args, "third", "") or args.agent or ""
    name = raw.lower().strip()

    if not name:
        print()
        print("  " + q(C.W, "Which skill do you want to install?", bold=True))
        print()
        for i, (k, s) in enumerate(SKILLS.items()):
            sc = _skill_color(s)
            st = "  " + q(C.GRN, "✓") if skill_status(k) == "installed" else ""
            print("  " + q(C.G2, str(i+1).rjust(2) + ".") + "  " +
                  q(sc, s["icon"] + " " + s["name"], bold=True) + st +
                  "  " + q(C.G2, s["desc"][:48]))
        print()
        print("  ", end="")
        try:
            choice = input(q(C.B6, "Number or name: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print(); return

        if choice.isdigit():
            idx = int(choice) - 1
            keys = list(SKILLS.keys())
            if 0 <= idx < len(keys):
                name = keys[idx]
        else:
            name = choice.lower()

    if name not in SKILLS:
        fail("Skill '" + name + "' not found.")
        info("Available skills: " + ", ".join(SKILLS.keys()))
        return

    s   = SKILLS[name]
    sc  = _skill_color(s)
    st  = skill_status(name)
    existing = load_skill(name) or {}
    reconfigure = getattr(args, "reconfigure", False) or st == "installed"

    print()
    print("  " + q(sc, s["icon"] + "  " + s["name"], bold=True) + "  " + q(C.G3, "skill"))
    print("  " + q(C.G3, "─" * 40))
    print()
    print("  " + q(C.G2, s["what"]))
    print()

    if st == "installed" and not reconfigure:
        ok("Already installed.")
        info("To reconfigure:  " + q(C.B7, "nova skill add " + name + " --reconfigure"))
        print()
        return

    print("  " + q(C.B6, "✦") + "  " + q(C.W, "Step 1 of 2 — Get your credentials", bold=True))
    print()
    print("  " + q(C.G2, "Set up access at:"))
    print("  " + q(C.B7, "  " + s["docs"]))
    print()
    if not confirm("Do you have the credentials ready?", default=False):
        print()
        info("Once ready, come back with:  " + q(C.B7, "nova skill add " + name))
        print()
        return

    print()
    print("  " + q(C.B6, "✦") + "  " + q(C.W, "Step 2 of 2 — Configure the skill", bold=True))
    print()

    data = dict(existing)

    for field, label, secret in s["fields"]:
        current = existing.get(field, "")
        display_current = ("***" if secret and current else current[:20] if current else "")
        hint = display_current or ""
        print("  " + q(C.B6, "?") + "  " + q(C.G1, label) +
              ("  " + q(C.G3, "(" + hint + ")") if hint else "") + "  ", end="", flush=True)
        try:
            if secret:
                import getpass
                val = getpass.getpass("").strip()
            else:
                val = input().strip()
        except (EOFError, KeyboardInterrupt):
            val = ""
        data[field] = val or current

    print()
    with Spinner("Verifying skill..."):
        time.sleep(0.6)

    missing = [f for f, _, _ in s["fields"] if not data.get(f)]
    if missing:
        warn("Missing fields: " + ", ".join(missing))
        warn("Saved as incomplete. Reconfigure with:  nova skill add " + name)
        data["status"] = "incomplete"
    else:
        ok(s["name"] + " skill configured")
        data["status"] = "installed"

    data["installed_at"] = datetime.now().isoformat()
    data["version"] = "1.0.0"
    save_skill(name, data)

    print()
    box([
        "  " + s["icon"] + "  " + s["name"] + " connected to nova",
        "",
        "  " + s["what"],
    ], sc, title=s["category"])
    print()
    info("View details:  " + q(C.B7, "nova skill info " + name))
    print()


def cmd_skill_remove(args):
    """Remove an installed skill."""
    name = (args.subcommand or args.agent or "").lower()
    if name in ("remove", ""):
        name = args.agent or ""

    if not name or name not in SKILLS:
        fail("Specify a valid skill name.")
        return

    if skill_status(name) != "installed":
        warn(name + " is not installed.")
        return

    warn("This will remove credentials for " + SKILLS[name]["name"] + " from this machine.")
    if not confirm("Continue?", default=False):
        return

    path = os.path.join(SKILLS_DIR, name + ".json")
    if os.path.exists(path):
        os.remove(path)
    ok(SKILLS[name]["name"] + " uninstalled.")
    print()


def cmd_skill_health(args):
    """Check connectivity of all installed skills."""
    installed = [k for k in SKILLS if skill_status(k) == "installed"]

    if not installed:
        warn("No skills installed.")
        info("Install skills with:  " + q(C.B7, "nova skill add <name>"))
        return

    section("Skill Health Check", str(len(installed)) + " installed")
    print()

    for name in installed:
        s = SKILLS[name]
        sc = _skill_color(s)
        data = load_skill(name)

        # Check if all required fields are configured
        missing = [f for f, _, _ in s["fields"] if not data.get(f)]
        if missing:
            print("  " + q(C.YLW, "!") + "  " + q(sc, s["icon"] + " " + s["name"]) +
                  "  " + q(C.YLW, "incomplete") + "  " + q(C.G3, "missing: " + ", ".join(missing)))
        else:
            installed_at = data.get("installed_at", "")
            print("  " + q(C.GRN, "✓") + "  " + q(sc, s["icon"] + " " + s["name"]) +
                  "  " + q(C.GRN, "configured") +
                  ("  " + q(C.G3, time_ago(installed_at)) if installed_at else ""))
    print()


# ══════════════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════════════

def cmd_help(args=None):
    """Display help information."""
    print_logo()

    print("  " + q(C.G1, "Governance infrastructure for AI agents."))
    print()
    print("  " + q(C.G3, "─" * 54))
    print()

    sections_data = [
        ("Getting Started", [
            ("init",              "First-run setup, T&C, server connection"),
            ("status",            "System health, metrics, active agents"),
            ("config",            "Skills, server, preferences"),
            ("whoami",            "Current identity and config summary"),
        ]),
        ("Agents", [
            ("agent create",      "Create agent with rules (or from template)"),
            ("agent list",        "List all active agents"),
            ("diff",              "Compare rules between two agents"),
        ]),
        ("Validation", [
            ("validate",          "Validate an action — verdict + response"),
            ("test",              "Dry-run — validate without recording"),
            ("simulate",          "Batch-validate from a file"),
        ]),
        ("Memory", [
            ("memory save",       "Store context in an agent's memory"),
            ("memory list",       "Read an agent's memories"),
        ]),
        ("Ledger", [
            ("ledger",            "Full cryptographic action history"),
            ("ledger verify",     "Verify chain integrity"),
            ("watch",             "Live tail — stream new entries"),
            ("replay <id>",       "Re-evaluate past action with current rules"),
            ("alerts",            "Blocked & escalated action alerts"),
        ]),
        ("Data", [
            ("export",            "Export ledger to JSON or CSV"),
            ("audit",             "Generate signed audit report"),
            ("sync",              "Process offline-queued actions"),
        ]),
        ("Skills", [
            ("skill",             "Skill catalog — all integrations"),
            ("skill add <name>",  "Install a skill"),
            ("skill info <name>", "Details & status of a skill"),
            ("skill health",      "Check all installed skill connections"),
        ]),
        ("System", [
            ("seed",              "Load demo data for testing"),
            ("webhook test",      "Test webhook connectivity"),
            ("completion <shell>","Generate shell autocompletion"),
        ]),
    ]

    for title, cmds in sections_data:
        print("  " + q(C.G2, title.upper()))
        print()
        for cmd, desc in cmds:
            print("    " + q(C.B7, cmd.ljust(22), bold=True) + q(C.G2, desc))
        print()

    print("  " + q(C.G3, "─" * 54))
    print()
    print("  " + q(C.G2, "Aliases") + "  " + q(C.G3, "s=status v=validate a=agent c=config l=ledger w=watch"))
    print()
    print("  " + q(C.G2, "Examples"))
    print()
    for ex in [
        'nova validate --action "Send email to john@x.com"',
        "nova ledger --limit 20 --verdict BLOCKED",
        "nova simulate --file actions.txt",
        "nova watch",
        "nova diff",
        "nova export --format csv",
    ]:
        print("    " + q(C.G3, "$ ") + q(C.W, ex))
    print()
    print("  " + q(C.G2, "Debug mode") + "  " + q(C.G3, "NOVA_DEBUG=1 nova status"))
    print("  " + q(C.G3, "Docs: ") + q(C.B7, "https://github.com/Santiagorubioads/nova-os"))
    print()


# ══════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(prog="nova", add_help=False)
    p.add_argument("command",     nargs="?", default="help")
    p.add_argument("subcommand",  nargs="?", default="")
    p.add_argument("third",       nargs="?", default="")
    p.add_argument("--token",  "-t", default="")
    p.add_argument("--action", "-a", default="")
    p.add_argument("--context","-c", default="")
    p.add_argument("--agent",        default="")
    p.add_argument("--key",          default="")
    p.add_argument("--value",        default="")
    p.add_argument("--importance",   default="5")
    p.add_argument("--limit",  type=int, default=10)
    p.add_argument("--verdict",      default="")
    p.add_argument("--format",       default="json")
    p.add_argument("--output", "-o", default="")
    p.add_argument("--file",  "-f",  default="")
    p.add_argument("--dry-run",      action="store_true")
    p.add_argument("--reconfigure",  action="store_true")
    p.add_argument("--interval",     type=int, default=3)
    p.add_argument("--help",   "-h", action="store_true")
    args = p.parse_args()

    # Resolve aliases
    if args.command in ALIASES:
        args.command = ALIASES[args.command]

    if args.help or args.command in ("help", "--help", "-h"):
        cmd_help(args)
        return

    # First-run detection
    if args.command not in ("init", "help", "--help", "-h", "completion") and not os.path.exists(CONFIG_FILE):
        print()
        print("  " + q(C.B6, "✦", bold=True) + "  " + q(C.W, "nova", bold=True))
        print()
        print("  " + q(C.G1, "nova isn't configured yet."))
        print()
        print("  " + q(C.B7, "nova init", bold=True) + "  " + q(C.G2, "— run setup to get started"))
        print()
        return

    if args.command == "help" or (not args.command):
        cmd_help(args)
        return

    routes = {
        # Core
        ("init",       ""):         cmd_init,
        ("status",     ""):         cmd_status,
        ("whoami",     ""):         cmd_whoami,
        # Agents
        ("agent",      "create"):   cmd_agent_create,
        ("agent",      "list"):     cmd_agent_list,
        ("agents",     ""):         cmd_agent_list,
        ("diff",       ""):         cmd_diff,
        # Validation
        ("validate",   ""):         cmd_validate,
        ("test",       ""):         cmd_test,
        ("simulate",   ""):         cmd_simulate,
        # Memory
        ("memory",     "save"):     cmd_memory_save,
        ("memory",     "list"):     cmd_memory_list,
        # Ledger
        ("ledger",     ""):         cmd_ledger,
        ("ledger",     "verify"):   cmd_verify,
        ("verify",     ""):         cmd_verify,
        ("watch",      ""):         cmd_watch,
        ("replay",     ""):         cmd_replay,
        ("alerts",     ""):         cmd_alerts,
        # Data
        ("export",     ""):         cmd_export,
        ("audit",      ""):         cmd_audit,
        ("sync",       ""):         cmd_sync,
        # Config
        ("config",     ""):         cmd_config,
        ("seed",       ""):         cmd_seed,
        # Skills
        ("skill",      ""):         cmd_skill_list,
        ("skill",      "list"):     cmd_skill_list,
        ("skills",     ""):         cmd_skill_list,
        ("skill",      "add"):      cmd_skill_add,
        ("skill",      "install"):  cmd_skill_add,
        ("skill",      "info"):     cmd_skill_info,
        ("skill",      "remove"):   cmd_skill_remove,
        ("skill",      "delete"):   cmd_skill_remove,
        ("skill",      "health"):   cmd_skill_health,
        ("skill",      "check"):    cmd_skill_health,
        # Webhook
        ("webhook",    ""):         cmd_webhook_test,
        ("webhook",    "test"):     cmd_webhook_test,
        # Completion
        ("completion", ""):         cmd_completion,
        ("completion", "bash"):     cmd_completion,
        ("completion", "zsh"):      cmd_completion,
        ("completion", "fish"):     cmd_completion,
    }

    fn = routes.get((args.command, args.subcommand)) or routes.get((args.command, ""))

    if not fn:
        fail("Unknown command: " + args.command +
             (" " + args.subcommand if args.subcommand else ""))
        print()
        info("Run  " + q(C.B7, "nova help") + "  to see all commands.")
        print()
        sys.exit(1)

    try:
        fn(args)
    except KeyboardInterrupt:
        print()
        warn("Cancelled.")
        print()


if __name__ == "__main__":
    main()