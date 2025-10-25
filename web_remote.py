#!/usr/bin/env python3
"""
web_remote.py  –  unified web UI + diagnostics + remote control

Endpoints
---------
/               → HTML page with buttons, overlay text, diagnostics, and link to /log
/overlay        → JSON array of overlay text lines
/diag, /data    → JSON object of diagnostic metrics
/action?cmd=…   → inject control commands (next, prev, offset, toggle, quit)
/log            → contents of runtime.log (if present)
"""

from __future__ import annotations
import http.server
import socketserver
import threading
import urllib.parse
import html
import json
import time
import os
import traceback
import psutil
import platform
from typing import TYPE_CHECKING, Any

from events   import EventManager
from overlays import _fmt_hms, _next_real, PAUSE_SENTINEL
import config

if TYPE_CHECKING:                       # avoid circular import at runtime
    from app import TVEmulator

# ── diagnostics refresh cadence ───────────────────────────────────────────
_last_diag_time = 0.0
_diag_interval  = getattr(config, "DIAG_REFRESH_INTERVAL", 1.0)

# ── global diagnostic store ───────────────────────────────────────────────
monitor_data: dict[str, Any] = {
    "cpu_percent":       0.0,
    "cpu_per_core":      [],
    "mem_used":          "0 MB",
    "mem_total":         "0 MB",
    "disk_root":         "0%",
    "script_uptime":     "0d 00:00:00",
    "machine_uptime":    "0d 00:00:00",
    "load_avg":          "",
    "last_http_crash":   "",
    "python_version":    platform.python_version(),
}

_script_start = time.monotonic()
_boot_time    = psutil.boot_time()


# ── helpers ────────────────────────────────────────────────────────────────
def _fmt_duration(secs: float) -> str:
    d, rem = divmod(int(secs), 86400)
    h, rem = divmod(rem, 3600)
    m, s   = divmod(rem, 60)
    return f"{d}d {h:02}:{m:02}:{s:02}"


def _maybe_update_diagnostics() -> None:
    global _last_diag_time
    now = time.monotonic()
    if now - _last_diag_time >= _diag_interval:
        _last_diag_time = now
        _update_diagnostics()


def _update_diagnostics() -> None:
    """Refresh CPU, memory, disk, uptime, load, etc. in `monitor_data`."""
    # CPU
    per_core = psutil.cpu_percent(percpu=True)
    avg_cpu  = sum(per_core) / len(per_core) if per_core else 0.0
    monitor_data["cpu_percent"]  = round(avg_cpu, 1)
    monitor_data["cpu_per_core"] = [round(p, 1) for p in per_core]
    # Memory
    vm = psutil.virtual_memory()
    monitor_data["mem_used"]  = f"{vm.used // 1024**2} MB"
    monitor_data["mem_total"] = f"{vm.total // 1024**2} MB"
    # Disk
    du = psutil.disk_usage("/")
    monitor_data["disk_root"] = f"{du.percent}%"
    # Uptime
    now = time.monotonic()
    monitor_data["script_uptime"]  = _fmt_duration(now - _script_start)
    monitor_data["machine_uptime"] = _fmt_duration(time.time() - _boot_time)
    # Load average
    try:
        la = os.getloadavg()
        monitor_data["load_avg"] = ", ".join(f"{x:.2f}" for x in la)
    except Exception:
        monitor_data["load_avg"] = "N/A"


# ── reusable threaded HTTP server ──────────────────────────────────────────
class ReusableTCPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads      = True
    allow_reuse_address = True


# ── overlay text builder (for /overlay endpoint) ───────────────────────────
def _overlay_lines(tv: "TVEmulator") -> list[str]:
    ch_mgr, ch_num, ref = tv.ch_mgr, tv.curr_ch, tv.ref_time + tv.time_offset
    phase     = tv.phase
    elapsed   = time.time() - tv.static_start if phase == "static" else 0.0
    off_ms    = tv.time_offset * 1000.0

    lines: list[str] = [f"Channel {ch_num:02d}  Δ{off_ms:+.0f} ms"]  # ← NEW header
    chan = ch_mgr.channels.get(ch_num)

    if chan and chan.files:
        durs  = [d / 1_000_000 for d in chan.durations_us]
        total = chan.total_us / 1_000_000

        lines.append(f"Total len  {_fmt_hms(total)}")

        off = ch_mgr.offset(ch_num, time.time(), ref) % total
        lines.append(f"Position      {_fmt_hms(off)}")

        idx  = chan.files.index(chan.path)
        cur  = ("PAUSE" if chan.path == PAUSE_SENTINEL
                else html.escape(os.path.basename(chan.path)))
        rem  = max(0.0, durs[idx] - (off - chan.start_us[idx] / 1_000_000))
        nxt  = html.escape(os.path.basename(chan.files[_next_real(idx, chan.files)]))

        lines += [
            f"Current  {cur}",
            f"   rem   {_fmt_hms(rem)}",
            f"Next    {nxt}",
            "——  upcoming  ——",
        ]
        cum = 0.0
        for fp, dur in zip(chan.files, durs):
            if fp == PAUSE_SENTINEL:
                cum += dur
                continue
            until = (cum - off) if cum >= off else (total - off + cum)
            lines.append(f"{html.escape(os.path.basename(fp))}  in {_fmt_hms(until)}")
            cum += dur
    else:
        lines.append("No videos – static loop")

    if phase == "static":
        lines.append(
            f"Static burst {_fmt_hms(elapsed)} / {_fmt_hms(config.STATIC_BURST_SEC)}"
        )

    return lines


# ── request handler ────────────────────────────────────────────────────────
class RemoteHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        return  # silence default logging

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, qs = parsed.path, parsed.query

        if path == "/":
            return self._serve_html()
        if path == "/overlay":
            return self._serve_json(_overlay_lines(self.server.tv))   # type: ignore
        if path in ("/diag", "/data"):
            _maybe_update_diagnostics()
            return self._serve_json(monitor_data)
        if path == "/log":
            return self._serve_log()
        if path == "/action":
            return self._serve_action(qs)

        self.send_error(404, "Not found")

    # ── helpers for each route ───────────────────────────────────────────
    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))

    def _serve_json(self, obj: Any):
        b = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _serve_log(self):
        try:
            data = open("runtime.log", "rb").read()
        except Exception:
            return self.send_error(404, "Log file not found")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_action(self, query: str):
        qs = urllib.parse.parse_qs(query)
        cmd = qs.get("cmd", [""])[0]

        if cmd == "next":
            EventManager.post({"type": "switch_channel", "to": "next"})

        elif cmd == "prev":
            EventManager.post({"type": "switch_channel", "to": "prev"})

        elif cmd == "toggle":
            EventManager.post({"type": "toggle_overlay"})

        elif cmd == "quit":
            EventManager.post({"type": "quit"})

        elif cmd == "offset":
            # offset in *milliseconds* (can be ±)
            try:
                delta_ms = float(qs.get("ms", ["0"])[0])
            except ValueError:
                return self.send_error(400, "Invalid ms value")
            EventManager.post({"type": "adjust_offset",
                               "delta": delta_ms / 1000.0})

        else:
            return self.send_error(400, "Unknown cmd")

        self.send_response(204)
        self.end_headers()


# ── simple HTML UI ─────────────────────────────────────────────────────────
HTML_PAGE = """
<!doctype html><html><head><meta charset="utf-8">
<title>TV Remote & Diagnostics</title>
<style>
 body{background:#000;color:#0f0;font-family:monospace;padding:1em;}
 a.button{display:inline-block;margin:4px;padding:6px 12px;border:1px solid #0f0;
          text-decoration:none;color:#0f0;}
 pre{margin:0.5em 0;font-family:monospace;}
</style></head><body>
<h2>TV Emulator Remote</h2>
<!-- channel controls -->
<a class="button" href="/action?cmd=prev">◀ Channel −</a>
<a class="button" href="/action?cmd=next">Channel + ▶</a>

<!-- live offset nudge controls -->
<a class="button" href="/action?cmd=offset&ms=-3">−3 ms</a>
<a class="button" href="/action?cmd=offset&ms=3">+3 ms</a>
<a class="button" href="/action?cmd=offset&ms=-100">−100 ms</a>
<a class="button" href="/action?cmd=offset&ms=100">+100 ms</a>

<!-- misc -->
<a class="button" href="/action?cmd=toggle">Toggle overlay</a>
<a class="button" href="/action?cmd=quit">Quit</a>
<a class="button" href="/log">View log</a>

<div><h3>Overlay</h3><pre id="overlay"></pre></div>
<div><h3>Diagnostics</h3><pre id="diag"></pre></div>

<script>
 async function refreshUI(){
   try {
     let o  = await fetch('/overlay'); let ov = await o.json();
     document.getElementById('overlay').textContent = ov.join('\\n');
     let d  = await fetch('/diag');    let dg = await d.json();
     let txt = '';
     for (let [k,v] of Object.entries(dg)){
       txt += k.padEnd(20,' ') + v + '\\n';
     }
     document.getElementById('diag').textContent = txt;
   } catch(e){
     console.error(e);
   }
 }
 setInterval(refreshUI, 200);
 refreshUI();
</script>
</body></html>
"""


# ── server bootstrap with auto-restart ────────────────────────────────────
def start(tv: "TVEmulator", port: int = getattr(config, "WEB_PORT", 8080)):
    def _serve_loop():
        while True:
            try:
                with ReusableTCPServer(("", port), RemoteHandler) as httpd:
                    httpd.tv = tv
                    httpd.serve_forever()
            except Exception:
                tb = traceback.format_exc().replace("\n", "<br>")
                monitor_data["last_http_crash"] = tb
                time.sleep(1)

    threading.Thread(target=_serve_loop, daemon=True).start()
    print(f"🌐 Web UI & diagnostics listening on port {port}")
