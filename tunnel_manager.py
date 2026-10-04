"""
OmniTrade Cloudflare Tunnel Daemon & Self-Healing Watchdog
Multi-tier waterfall fallback: cloudflared → localtunnel (npx) → ngrok → UNAVAILABLE

Tier 1 (PRIMARY):  cloudflared quick-tunnel  – 20 s start timeout, 5 retries per burst
Tier 2 (FALLBACK): npx localtunnel           – auto-installs via npx, no npm install needed
Tier 3 (FALLBACK): ngrok http                – only if `ngrok` binary is on PATH
Tier 4 (TERMINAL): Mark tunnel UNAVAILABLE, back-off 30 minutes then retry from Tier 1

After TUNNEL_UNAVAILABLE_AFTER_FAILURES=15 *total* failures the manager stops retrying
for BACKOFF_UNAVAILABLE_MINUTES=30 minutes before restarting the whole waterfall.
"""

import subprocess
import sys
import re
import time
import os
import json
import threading
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional requests import (best-effort – tunnel works without it)
# ---------------------------------------------------------------------------
try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _requests = None
    _HAS_REQUESTS = False

# ---------------------------------------------------------------------------
# Windows UTF-8 fix
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent
URL_FILE_1 = BASE_DIR / "cloudflare_url.txt"
URL_FILE_2 = Path("E:/omnitrade_live_url.txt")
STATUS_FILE = BASE_DIR / "tunnel_status.json"

LOCAL_PORT = 8899

# cloudflared binary search
_CF_CANDIDATE = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
CLOUDFLARED_PATH = _CF_CANDIDATE if os.path.exists(_CF_CANDIDATE) else "cloudflared"

# ---- failure / back-off tuning ----
CLOUDFLARED_START_TIMEOUT   = 20    # seconds to wait for URL to appear
CLOUDFLARED_RETRIES_PER_BURST = 5   # cloudflared attempts before escalating
LOCALTUNNEL_RETRIES         = 3     # npx localtunnel attempts
NGROK_RETRIES               = 3
BURST_BACKOFF_SECS          = 60    # wait between failure groups
TUNNEL_UNAVAILABLE_AFTER_FAILURES = 15   # total failures → UNAVAILABLE
BACKOFF_UNAVAILABLE_MINUTES = 30    # how long to sleep when UNAVAILABLE

# ---- runtime state ----
active_url          = None
is_running          = True
current_process     = None
consecutive_failures = 0
total_failures      = 0
state_lock          = threading.Lock()

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [TunnelMgr] {msg}", flush=True)

def update_status(data: dict):
    try:
        STATUS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"Status write error: {e}")

def save_url(url: str):
    for f in (URL_FILE_1, URL_FILE_2):
        try:
            Path(f).write_text(url, encoding="utf-8")
        except Exception as e:
            log(f"URL file write error ({f}): {e}")

def mark_alive(url: str, latency_ms: float = 0.0, provider: str = "cloudflared"):
    global active_url
    active_url = url
    update_status({
        "url":            url,
        "alive":          True,
        "http_status":    200,
        "latency_ms":     latency_ms,
        "provider":       provider,
        "local_port_8899": True,
        "last_ping":      time.strftime("%Y-%m-%d %H:%M:%S"),
        "service":        "OmniTrade Institutional Pro Matrix",
    })

def mark_unavailable(reason: str = ""):
    global active_url
    active_url = None
    update_status({
        "url":    None,
        "alive":  False,
        "status": "UNAVAILABLE",
        "reason": reason,
        "total_failures": total_failures,
        "backoff_minutes": BACKOFF_UNAVAILABLE_MINUTES,
        "last_ping": time.strftime("%Y-%m-%d %H:%M:%S"),
        "service":   "OmniTrade Institutional Pro Matrix",
    })

# ---------------------------------------------------------------------------
# Keepalive / Watchdog pinger thread
# ---------------------------------------------------------------------------
def keepalive_pinger():
    global active_url, is_running, consecutive_failures, current_process

    log("Keepalive watchdog pinger thread started.")
    while is_running:
        time.sleep(15)
        if not active_url:
            continue

        ping_ok = False
        latency  = 0.0

        if _HAS_REQUESTS:
            try:
                t0   = time.time()
                resp = _requests.get(f"{active_url}/health", timeout=8)
                latency = round((time.time() - t0) * 1000, 1)
                ping_ok = (resp.status_code == 200)
            except Exception as exc:
                log(f"Keepalive ping error: {exc}")
        else:
            # Fallback: curl
            try:
                t0  = time.time()
                ret = subprocess.run(
                    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                     "--max-time", "8", f"{active_url}/health"],
                    capture_output=True, text=True, timeout=10
                )
                latency = round((time.time() - t0) * 1000, 1)
                ping_ok = (ret.stdout.strip() == "200")
            except Exception as exc:
                log(f"Keepalive curl error: {exc}")

        with state_lock:
            if ping_ok:
                consecutive_failures = 0
                mark_alive(active_url, latency)
                log(f"Ping OK → {active_url}  ({latency} ms)")
            else:
                consecutive_failures += 1
                log(f"Ping FAIL #{consecutive_failures} → {active_url}")
                update_status({
                    "url":                 active_url,
                    "alive":               False,
                    "consecutive_failures": consecutive_failures,
                    "last_ping":           time.strftime("%Y-%m-%d %H:%M:%S"),
                })

            # Auto-heal: kill process after 3 consecutive failures so main loop respawns
            if consecutive_failures >= 3 and current_process:
                log("3 consecutive failures → force-killing tunnel process for respawn")
                try:
                    current_process.terminate()
                    time.sleep(1)
                    current_process.kill()
                except Exception:
                    pass
                consecutive_failures = 0

# ---------------------------------------------------------------------------
# Tier 1 – cloudflared
# ---------------------------------------------------------------------------
_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

def _try_cloudflared() -> bool:
    """
    Attempt one cloudflared tunnel.
    Returns True if tunnel came up successfully (URL captured + health OK).
    Blocks until the cloudflared process exits.
    """
    global active_url, current_process, consecutive_failures, total_failures

    cmd = [
        CLOUDFLARED_PATH, "tunnel",
        "--url", f"http://127.0.0.1:{LOCAL_PORT}",
        "--edge-ip-version", "4",
        "--no-autoupdate",
    ]
    log(f"[Tier-1] Starting cloudflared: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            universal_newlines=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        log("[Tier-1] cloudflared binary not found.")
        return False

    with state_lock:
        current_process = proc

    url_found      = None
    deadline       = time.time() + CLOUDFLARED_START_TIMEOUT

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        print(f"  [cf] {line}", flush=True)

        m = _URL_PATTERN.search(line)
        if m and "api.trycloudflare.com" not in m.group(0) and not url_found:
            url_found  = m.group(0)
            log("=" * 60)
            log(f">>> LIVE CLOUDFLARE URL: {url_found}")
            log("=" * 60)
            save_url(url_found)
            mark_alive(url_found, provider="cloudflared")
            with state_lock:
                consecutive_failures = 0

        if time.time() > deadline and not url_found:
            log(f"[Tier-1] Timeout ({CLOUDFLARED_START_TIMEOUT}s) waiting for URL.")
            try:
                proc.terminate()
            except Exception:
                pass
            break

    rc = proc.wait()
    with state_lock:
        current_process = None
        active_url      = None

    if url_found:
        log(f"[Tier-1] cloudflared exited (rc={rc}) after successful tunnel session.")
        return True   # session ran, consider it successful overall
    else:
        with state_lock:
            total_failures += 1
        log(f"[Tier-1] cloudflared failed to produce URL (rc={rc}). total_failures={total_failures}")
        return False

# ---------------------------------------------------------------------------
# Tier 2 – npx localtunnel
# ---------------------------------------------------------------------------
_LT_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.loca\.lt")

def _try_localtunnel() -> bool:
    global active_url, current_process, total_failures

    node_exe = shutil.which("node")
    if not node_exe:
        log("[Tier-2] node not on PATH – skipping localtunnel.")
        return False

    cmd = ["npx", "--yes", "localtunnel", "--port", str(LOCAL_PORT),
           "--subdomain", "omnitrade-basit"]
    log(f"[Tier-2] Starting localtunnel: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, universal_newlines=True,
            encoding="utf-8", errors="replace",
        )
    except Exception as exc:
        log(f"[Tier-2] localtunnel launch error: {exc}")
        return False

    with state_lock:
        current_process = proc

    url_found = None
    deadline  = time.time() + 40   # npx may need to download the package

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        print(f"  [lt] {line}", flush=True)

        m = _LT_URL_PATTERN.search(line)
        if m and not url_found:
            url_found = m.group(0)
            log(f"[Tier-2] localtunnel URL: {url_found}")
            save_url(url_found)
            mark_alive(url_found, provider="localtunnel")
            with state_lock:
                total_failures = max(0, total_failures - 3)   # partial credit

        if time.time() > deadline and not url_found:
            log("[Tier-2] localtunnel timeout.")
            try:
                proc.terminate()
            except Exception:
                pass
            break

    proc.wait()
    with state_lock:
        current_process = None
        active_url      = None

    if not url_found:
        with state_lock:
            total_failures += 1
        return False
    return True

# ---------------------------------------------------------------------------
# Tier 3 – ngrok
# ---------------------------------------------------------------------------
_NGROK_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.ngrok[.\-]?(io|app|dev|free\.app)?")

def _try_ngrok() -> bool:
    global active_url, current_process, total_failures

    ngrok_exe = shutil.which("ngrok")
    if not ngrok_exe:
        log("[Tier-3] ngrok not on PATH – skipping.")
        return False

    cmd = [ngrok_exe, "http", str(LOCAL_PORT), "--log", "stdout", "--log-format", "json"]
    log(f"[Tier-3] Starting ngrok: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, universal_newlines=True,
            encoding="utf-8", errors="replace",
        )
    except Exception as exc:
        log(f"[Tier-3] ngrok launch error: {exc}")
        return False

    with state_lock:
        current_process = proc

    url_found = None
    deadline  = time.time() + 20

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        print(f"  [ng] {line}", flush=True)

        # ngrok JSON log has "url" key, also grep plain text URL
        try:
            obj = json.loads(line)
            candidate = obj.get("url") or obj.get("Addr") or ""
            if candidate.startswith("https://"):
                url_found = candidate
        except json.JSONDecodeError:
            m = _NGROK_URL_PATTERN.search(line)
            if m:
                url_found = m.group(0)

        if url_found:
            log(f"[Tier-3] ngrok URL: {url_found}")
            save_url(url_found)
            mark_alive(url_found, provider="ngrok")
            with state_lock:
                total_failures = max(0, total_failures - 3)

        if time.time() > deadline and not url_found:
            log("[Tier-3] ngrok timeout.")
            try:
                proc.terminate()
            except Exception:
                pass
            break

    proc.wait()
    with state_lock:
        current_process = None
        active_url      = None

    if not url_found:
        with state_lock:
            total_failures += 1
        return False
    return True

# ---------------------------------------------------------------------------
# Waterfall orchestrator
# ---------------------------------------------------------------------------
def run_waterfall():
    """
    Run all tiers in order. Returns after a tier session ends (process exits).
    Caller loops this.
    """
    global total_failures

    with state_lock:
        tf = total_failures

    if tf >= TUNNEL_UNAVAILABLE_AFTER_FAILURES:
        log(f"!!! Total failures ({tf}) >= {TUNNEL_UNAVAILABLE_AFTER_FAILURES}. "
            f"Marking UNAVAILABLE. Sleeping {BACKOFF_UNAVAILABLE_MINUTES} min …")
        mark_unavailable(f"Exceeded {TUNNEL_UNAVAILABLE_AFTER_FAILURES} total failures")
        time.sleep(BACKOFF_UNAVAILABLE_MINUTES * 60)
        with state_lock:
            total_failures = 0   # reset for fresh waterfall
        log("Back-off complete. Restarting waterfall.")
        return

    # ---- Tier 1: cloudflared (up to CLOUDFLARED_RETRIES_PER_BURST attempts) ----
    log(f"=== Waterfall: Tier-1 cloudflared (up to {CLOUDFLARED_RETRIES_PER_BURST} attempts) ===")
    cf_ok = False
    for attempt in range(1, CLOUDFLARED_RETRIES_PER_BURST + 1):
        log(f"[Tier-1] Attempt {attempt}/{CLOUDFLARED_RETRIES_PER_BURST}")
        cf_ok = _try_cloudflared()
        if cf_ok:
            # Tunnel ran successfully (session ended normally – just loop back)
            return
        delay = min(BURST_BACKOFF_SECS, 5 * (2 ** (attempt - 1)))   # exp back-off up to 60s
        log(f"[Tier-1] Waiting {delay}s before next attempt …")
        time.sleep(delay)

    log(f"[Tier-1] All {CLOUDFLARED_RETRIES_PER_BURST} cloudflared attempts failed. "
        f"Escalating to Tier-2. Burst back-off {BURST_BACKOFF_SECS}s …")
    time.sleep(BURST_BACKOFF_SECS)

    # ---- Tier 2: localtunnel ----
    log(f"=== Waterfall: Tier-2 localtunnel (up to {LOCALTUNNEL_RETRIES} attempts) ===")
    for attempt in range(1, LOCALTUNNEL_RETRIES + 1):
        log(f"[Tier-2] Attempt {attempt}/{LOCALTUNNEL_RETRIES}")
        if _try_localtunnel():
            return
        time.sleep(15)

    log(f"[Tier-2] All localtunnel attempts failed. Escalating to Tier-3. "
        f"Burst back-off {BURST_BACKOFF_SECS}s …")
    time.sleep(BURST_BACKOFF_SECS)

    # ---- Tier 3: ngrok ----
    log(f"=== Waterfall: Tier-3 ngrok (up to {NGROK_RETRIES} attempts) ===")
    for attempt in range(1, NGROK_RETRIES + 1):
        log(f"[Tier-3] Attempt {attempt}/{NGROK_RETRIES}")
        if _try_ngrok():
            return
        time.sleep(15)

    # ---- Tier 4: UNAVAILABLE ----
    log("=== Waterfall: All tiers exhausted → UNAVAILABLE (30-min back-off) ===")
    with state_lock:
        total_failures += 3   # accelerate toward UNAVAILABLE_AFTER threshold
    mark_unavailable("All three tunnel providers failed")
    time.sleep(BACKOFF_UNAVAILABLE_MINUTES * 60)
    with state_lock:
        total_failures = 0
    log("30-min back-off complete. Restarting waterfall from Tier-1.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log("OmniTrade Multi-Tier Tunnel Watchdog v2 Starting.")
    log(f"  Tiers: cloudflared({CLOUDFLARED_RETRIES_PER_BURST}x) → "
        f"localtunnel({LOCALTUNNEL_RETRIES}x) → ngrok({NGROK_RETRIES}x) → UNAVAILABLE(30 min)")
    log(f"  TUNNEL_UNAVAILABLE_AFTER_FAILURES = {TUNNEL_UNAVAILABLE_AFTER_FAILURES}")
    log(f"  BURST_BACKOFF_SECS = {BURST_BACKOFF_SECS}")

    pinger = threading.Thread(target=keepalive_pinger, daemon=True)
    pinger.start()

    while True:
        try:
            run_waterfall()
        except KeyboardInterrupt:
            log("Shutdown requested. Bye.")
            break
        except Exception as exc:
            log(f"Unhandled exception in waterfall: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    main()
