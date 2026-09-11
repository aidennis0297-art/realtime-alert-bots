#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KOBUS 고속버스 실시간 빈자리 알리미 로컬 웹 GUI 서버
- Zero-dependency: Python 표준 라이브러리(http.server, urllib, json, threading, webbrowser)만 사용
"""

import os
import sys
import json
import socket
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Windows 콘솔 한글 UTF-8 출력 보정
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from bus_alert import KobusMonitor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
INDEX_FILE = os.path.join(WEB_DIR, "index.html")

monitor = KobusMonitor(os.path.join(BASE_DIR, "config.json"))

class KobusWebHandler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            if os.path.exists(INDEX_FILE):
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    content = f.read().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "index.html not found")
            return

        if path == "/api/terminals":
            t_data = monitor.fetch_terminals()
            self.send_json(t_data)
            return

        if path == "/api/config":
            self.send_json(monitor.config)
            return

        if path == "/api/schedule":
            depr_cd = qs.get("deprCd", [monitor.config.get("departure_terminal", "010")])[0]
            arvl_cd = qs.get("arvlCd", [monitor.config.get("arrival_terminal", "700")])[0]
            date = qs.get("date", [monitor.config.get("date", "20260923")])[0]
            min_time = qs.get("minTime", [monitor.config.get("min_time", "00:00")])[0]
            max_time = qs.get("maxTime", [monitor.config.get("max_time", "23:59")])[0]

            buses = monitor.query_timetable(depr_cd, arvl_cd, date, min_time, max_time)
            self.send_json({"buses": buses})
            return

        if path == "/api/monitor/status":
            st = monitor.get_status()
            self.send_json(st)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            body = {}

        if path == "/api/config":
            curr = monitor.config
            for k, v in body.items():
                curr[k] = v
            monitor.save_config(curr)
            monitor.log("⚙️ 설정이 업데이트되었습니다.")
            self.send_json({"success": True, "message": "설정 저장 완료"})
            return

        if path == "/api/monitor/start":
            ok, msg = monitor.start_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/monitor/stop":
            ok, msg = monitor.stop_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/discord/test":
            hook_url = body.get("webhook_url") or None
            ok, msg = monitor.send_test_discord(hook_url)
            self.send_json({"success": ok, "message": msg})
            return

        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        return

def find_available_port(start_port=8081, max_attempts=10):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

def run_server(open_browser=True):
    port = find_available_port(8081)
    server = ThreadingHTTPServer(("127.0.0.1", port), KobusWebHandler)
    url = f"http://localhost:{port}"

    print("=" * 65)
    print("🚌 KOBUS 고속버스 빈자리 알리미 웹 GUI 대시보드")
    print("=" * 65)
    print(f"• 로컬 서버 주소: {url}")
    print("• 웹 브라우저가 자동으로 실행됩니다. (종료: Ctrl + C)")
    print("=" * 65)

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] 서버를 종료합니다...")
        monitor.stop_monitoring()
        server.server_close()
        print("서버가 종료되었습니다.")

if __name__ == "__main__":
    run_server(open_browser=True)
