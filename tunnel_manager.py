"""
OmniTrade Cloudflare Tunnel Daemon & Self-Healing Watchdog
Spawns cloudflared tunnel for port 8899, captures trycloudflare.com URL,
verifies reachability, and auto-restarts on drops or zombie hangs.
"""
import subprocess
import sys
import re
import time
import os
import json
import threading
import requests
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
URL_FILE_1 = BASE_DIR / "cloudflare_url.txt"
URL_FILE_2 = Path("E:/omnitrade_live_url.txt")
STATUS_FILE = BASE_DIR / "tunnel_status.json"

CLOUDFLARED_PATH = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
if not os.path.exists(CLOUDFLARED_PATH):
    CLOUDFLARED_PATH = "cloudflared"

active_url = None
is_running = True
current_process = None
consecutive_failures = 0

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [TunnelManager] {msg}", flush=True)

def update_status(status_dict):
    try:
        STATUS_FILE.write_text(json.dumps(status_dict, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"Error saving status: {e}")

def keepalive_pinger():
    global active_url, is_running, consecutive_failures, current_process
    log("Keepalive watchdog pinger thread started.")
    while is_running:
        time.sleep(15)
        if not active_url:
            continue
        try:
            t0 = time.time()
            # Test local port 8899 first
            r_local = requests.get("http://127.0.0.1:8899/health", timeout=3)
            local_ok = (r_local.status_code == 200)
            
            # Test public edge URL
            r_edge = requests.get(f"{active_url}/health", timeout=8)
            lat = round((time.time() - t0) * 1000, 1)
            
            if r_edge.status_code == 200:
                consecutive_failures = 0
                update_status({
                    "url": active_url,
                    "alive": True,
                    "http_status": 200,
                    "latency_ms": lat,
                    "local_port_8899": local_ok,
                    "last_ping": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "service": "OmniTrade Institutional Pro Matrix"
                })
            else:
                consecutive_failures += 1
                log(f"Warning: Public health check returned HTTP {r_edge.status_code} (failures: {consecutive_failures})")
        except Exception as e:
            consecutive_failures += 1
            log(f"Keepalive ping failure #{consecutive_failures}: {e}")
            update_status({
                "url": active_url,
                "alive": False,
                "error": str(e),
                "consecutive_failures": consecutive_failures,
                "last_ping": time.strftime("%Y-%m-%d %H:%M:%S")
            })

        # Auto-heal: If 3 consecutive failures occur, kill the current cloudflared process to force respawn
        if consecutive_failures >= 3 and current_process:
            log(f"🚨 3 consecutive tunnel failures detected. Force-restarting cloudflared...")
            try:
                current_process.terminate()
                time.sleep(1)
                current_process.kill()
            except Exception:
                pass
            consecutive_failures = 0

def run_tunnel():
    global active_url, current_process
    cmd = [CLOUDFLARED_PATH, "tunnel", "--url", "http://127.0.0.1:8899", "--no-autoupdate"]
    log(f"Starting cloudflared tunnel: {' '.join(cmd)}")
    
    current_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace"
    )
    
    url_found = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    
    for line in current_process.stdout:
        line_clean = line.strip()
        if not line_clean:
            continue
        print(f"[cloudflared] {line_clean}", flush=True)
        
        match = url_pattern.search(line_clean)
        if match and "api.trycloudflare.com" not in match.group(0) and not url_found:
            url_found = match.group(0)
            active_url = url_found
            log("=" * 60)
            log(f">>> LIVE CLOUDFLARE URL ACQUIRED: {url_found}")
            log("=" * 60)
            
            # Save URL
            try:
                URL_FILE_1.write_text(url_found, encoding="utf-8")
                URL_FILE_2.write_text(url_found, encoding="utf-8")
            except Exception as e:
                log(f"Error saving URL: {e}")
            
            update_status({
                "url": active_url,
                "alive": True,
                "status": "INITIALIZED",
                "last_ping": time.strftime("%Y-%m-%d %H:%M:%S")
            })

    rc = current_process.wait()
    log(f"Cloudflared process exited with returncode {rc}. Re-spawning in 2 seconds...")
    active_url = None
    current_process = None
    time.sleep(2)

def main():
    log("OmniTrade Cloudflare Tunnel Watchdog Started.")
    pinger_thread = threading.Thread(target=keepalive_pinger, daemon=True)
    pinger_thread.start()
    
    while True:
        try:
            run_tunnel()
        except KeyboardInterrupt:
            log("Shutting down tunnel manager.")
            break
        except Exception as e:
            log(f"Exception in tunnel loop: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
