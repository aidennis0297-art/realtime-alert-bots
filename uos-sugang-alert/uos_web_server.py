#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
서울시립대학교 수강신청 실시간 알리미 로컬 웹 GUI 서버
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

# 코어 모듈 임포트
from uos_sugang_alert import UosSugangMonitor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
INDEX_FILE = os.path.join(WEB_DIR, "index.html")

monitor = UosSugangMonitor(os.path.join(BASE_DIR, "config.json"))

class UosWebHandler(BaseHTTPRequestHandler):
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

        # API: Config 조회
        if path == "/api/config":
            cfg = monitor.config
            safe_cfg = {
                "student_id": cfg.get("student_id", ""),
                "password": cfg.get("password", ""),
                "device": cfg.get("device", "PC"),
                "year": cfg.get("year", "2026"),
                "semester": cfg.get("semester", "CCMN031.20"),
                "target_courses": cfg.get("target_courses", []),
                "check_interval_seconds": cfg.get("check_interval_seconds", 6),
                "discord": cfg.get("discord", {})
            }
            self.send_json(safe_cfg)
            return

        # API: 개설과목 조회
        if path == "/api/courses":
            year = qs.get("year", ["2026"])[0]
            sem = qs.get("sem", ["CCMN031.20"])[0]
            refresh = qs.get("refresh", ["0"])[0] == "1"
            courses = monitor.fetch_courses(year=year, semester=sem, force_refresh=refresh)
            self.send_json({"courses": courses})
            return

        # API: 모니터링 상태 조회
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

        # API: 설정 저장
        if path == "/api/config":
            curr = monitor.config
            if "student_id" in body: curr["student_id"] = body["student_id"]
            if "password" in body: curr["password"] = body["password"]
            if "year" in body: curr["year"] = body["year"]
            if "semester" in body: curr["semester"] = body["semester"]
            if "check_interval_seconds" in body: curr["check_interval_seconds"] = body["check_interval_seconds"]
            if "discord" in body: curr["discord"] = body["discord"]

            monitor.save_config(curr)
            monitor.log("⚙️ 웹 화면에서 설정이 변경 및 저장되었습니다.")
            self.send_json({"success": True, "message": "설정이 저장되었습니다."})
            return

        # API: 로그인 검증
        if path == "/api/login_test":
            sid = body.get("student_id", "").strip() or monitor.config.get("student_id", "").strip()
            pwd = body.get("password", "").strip() or monitor.config.get("password", "").strip()
            if not sid or not pwd:
                self.send_json({"success": False, "message": "학번과 비밀번호를 입력해주세요."})
                return
            ok, msg = monitor.test_login_credentials(sid, pwd)
            self.send_json({"success": ok, "message": msg})
            return

        # API: 감시 대상 별표 토글 (Watchlist 추가/삭제)
        if path == "/api/targets/toggle":
            code = str(body.get("code", "")).strip()
            div = str(body.get("div", "01")).strip().zfill(2)
            name = body.get("name", "")
            prof = body.get("prof", "")
            dept = body.get("dept", "")
            course_type = body.get("type", "")

            targets = monitor.config.get("target_courses", [])
            existing_idx = -1
            for idx, t in enumerate(targets):
                if str(t.get("code", "")).strip() == code and str(t.get("div", "")).strip().zfill(2) == div:
                    existing_idx = idx
                    break

            if existing_idx >= 0:
                removed = targets.pop(existing_idx)
                monitor.log(f"⭐ 감시 해제: [{removed.get('code')}-{removed.get('div')}] {removed.get('name')}")
            else:
                new_target = {
                    "code": code,
                    "div": div,
                    "name": name,
                    "prof": prof,
                    "dept": dept,
                    "type": course_type
                }
                targets.append(new_target)
                monitor.log(f"⭐ 감시 등록: [{code}-{div}] {name} ({prof} 교수)")

            monitor.config["target_courses"] = targets
            monitor.save_config()
            self.send_json({"success": True, "target_courses": targets})
            return

        # API: 모니터링 시작
        if path == "/api/monitor/start":
            ok, msg = monitor.start_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        # API: 모니터링 중지
        if path == "/api/monitor/stop":
            ok, msg = monitor.stop_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        # API: 디스코드 테스트 알림
        if path == "/api/discord/test":
            custom_hook = body.get("webhook_url", "").strip() or None
            ok, msg = monitor.send_test_discord(custom_hook)
            self.send_json({"success": ok, "message": msg})
            return

        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # 웹 요청 콘솔 노이즈 최소화
        return

def find_available_port(start_port=8080, max_attempts=10):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

def run_server(open_browser=True):
    port = find_available_port(8080)
    server = ThreadingHTTPServer(("127.0.0.1", port), UosWebHandler)
    url = f"http://localhost:{port}"

    print("=" * 65)
    print("🎓 서울시립대학교 수강신청 실시간 알리미 웹 GUI 대시보드")
    print("=" * 65)
    print(f"• 로컬 서버 주소: {url}")
    print("• 웹 브라우저가 자동으로 실행됩니다. (종료: Ctrl + C)")
    print("=" * 65)

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] 웹 서버를 종료합니다...")
        monitor.stop_monitoring()
        server.server_close()
        print("서버가 안전하게 종료되었습니다.")

if __name__ == "__main__":
    run_server(open_browser=True)
