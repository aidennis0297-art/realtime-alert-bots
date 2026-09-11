#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Realtime Alert Hub (실시간 알리미 통합 포털 허브)
- 포트: 8000 (기본값)
- 고속버스(KOBUS) 및 서울시립대학교(UOS) 수강신청 통합 서빙
- Zero-dependency: Python 표준 내장 라이브러리만 사용
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_HUB_DIR = os.path.join(BASE_DIR, "web_hub")
INDEX_FILE = os.path.join(WEB_HUB_DIR, "index.html")

# 서브모듈 sys.path 등록
kobus_path = os.path.join(BASE_DIR, "kobus-seat-alert")
uos_path = os.path.join(BASE_DIR, "uos-sugang-alert")
if kobus_path not in sys.path:
    sys.path.insert(0, kobus_path)
if uos_path not in sys.path:
    sys.path.insert(0, uos_path)

# 모니터 엔진 로드
from bus_alert import KobusMonitor
from uos_sugang_alert import UosSugangMonitor

# 설정 파일 경로
kobus_cfg_path = os.path.join(kobus_path, "config.json")
if not os.path.exists(kobus_cfg_path):
    kobus_cfg_path = os.path.join(kobus_path, "config.example.json")

uos_cfg_path = os.path.join(uos_path, "config.json")
if not os.path.exists(uos_cfg_path):
    uos_cfg_path = os.path.join(uos_path, "config.example.json")

kobus_monitor = KobusMonitor(kobus_cfg_path)
uos_monitor = UosSugangMonitor(uos_cfg_path)

class AlertHubHandler(BaseHTTPRequestHandler):
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

        # 1. 정적 SPA 서빙
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
                self.send_error(404, "web_hub/index.html not found")
            return

        # 2. Hub 통합 상태 API
        if path == "/api/hub/status":
            self.send_json({
                "kobus": kobus_monitor.get_status(),
                "uos": uos_monitor.get_status()
            })
            return

        # 3. KOBUS APIs
        if path == "/api/kobus/terminals":
            self.send_json(kobus_monitor.fetch_terminals())
            return

        if path == "/api/kobus/config":
            self.send_json(kobus_monitor.config)
            return

        if path == "/api/kobus/schedule":
            depr_cd = qs.get("deprCd", [kobus_monitor.config.get("departure_terminal", "010")])[0]
            arvl_cd = qs.get("arvlCd", [kobus_monitor.config.get("arrival_terminal", "700")])[0]
            date = qs.get("date", [kobus_monitor.config.get("date", "20260923")])[0]
            min_time = qs.get("minTime", [kobus_monitor.config.get("min_time", "00:00")])[0]
            max_time = qs.get("maxTime", [kobus_monitor.config.get("max_time", "23:59")])[0]
            buses = kobus_monitor.query_timetable(depr_cd, arvl_cd, date, min_time, max_time)
            self.send_json({"buses": buses})
            return

        if path == "/api/kobus/monitor/status":
            self.send_json(kobus_monitor.get_status())
            return

        # 4. UOS APIs
        if path == "/api/uos/config":
            cfg = uos_monitor.config
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

        if path == "/api/uos/courses":
            year = qs.get("year", ["2026"])[0]
            sem = qs.get("sem", ["CCMN031.20"])[0]
            refresh = qs.get("refresh", ["0"])[0] == "1"
            courses = uos_monitor.fetch_courses(year=year, semester=sem, force_refresh=refresh)
            self.send_json({"courses": courses})
            return

        if path == "/api/uos/monitor/status":
            self.send_json(uos_monitor.get_status())
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

        # KOBUS POSTs
        if path == "/api/kobus/config":
            curr = kobus_monitor.config
            for k, v in body.items():
                curr[k] = v
            kobus_monitor.save_config(curr)
            kobus_monitor.log("⚙️ KOBUS 설정이 업데이트되었습니다.")
            self.send_json({"success": True, "message": "설정 저장 완료"})
            return

        if path == "/api/kobus/monitor/start":
            ok, msg = kobus_monitor.start_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/kobus/monitor/stop":
            ok, msg = kobus_monitor.stop_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/kobus/discord/test":
            hook = body.get("webhook_url") or None
            ok, msg = kobus_monitor.send_test_discord(hook)
            self.send_json({"success": ok, "message": msg})
            return

        # UOS POSTs
        if path == "/api/uos/config":
            curr = uos_monitor.config
            if "student_id" in body: curr["student_id"] = body["student_id"]
            if "password" in body: curr["password"] = body["password"]
            if "year" in body: curr["year"] = body["year"]
            if "semester" in body: curr["semester"] = body["semester"]
            if "check_interval_seconds" in body: curr["check_interval_seconds"] = body["check_interval_seconds"]
            if "discord" in body: curr["discord"] = body["discord"]
            uos_monitor.save_config(curr)
            uos_monitor.log("⚙️ UOS 설정이 업데이트되었습니다.")
            self.send_json({"success": True, "message": "설정 저장 완료"})
            return

        if path == "/api/uos/login_test":
            sid = body.get("student_id", "").strip() or uos_monitor.config.get("student_id", "").strip()
            pwd = body.get("password", "").strip() or uos_monitor.config.get("password", "").strip()
            if not sid or not pwd:
                self.send_json({"success": False, "message": "학번과 비밀번호를 입력해주세요."})
                return
            ok, msg = uos_monitor.test_login_credentials(sid, pwd)
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/uos/targets/toggle":
            code = str(body.get("code", "")).strip()
            div = str(body.get("div", "01")).strip().zfill(2)
            name = body.get("name", "")
            prof = body.get("prof", "")
            dept = body.get("dept", "")
            course_type = body.get("type", "")

            targets = uos_monitor.config.get("target_courses", [])
            existing_idx = -1
            for idx, t in enumerate(targets):
                if str(t.get("code", "")).strip() == code and str(t.get("div", "")).strip().zfill(2) == div:
                    existing_idx = idx
                    break

            if existing_idx >= 0:
                removed = targets.pop(existing_idx)
                uos_monitor.log(f"⭐ 감시 해제: [{removed.get('code')}-{removed.get('div')}] {removed.get('name')}")
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
                uos_monitor.log(f"⭐ 감시 등록: [{code}-{div}] {name} ({prof} 교수)")

            uos_monitor.config["target_courses"] = targets
            uos_monitor.save_config()
            self.send_json({"success": True, "target_courses": targets})
            return

        if path == "/api/uos/monitor/start":
            ok, msg = uos_monitor.start_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/uos/monitor/stop":
            ok, msg = uos_monitor.stop_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/uos/discord/test":
            custom_hook = body.get("webhook_url", "").strip() or None
            ok, msg = uos_monitor.send_test_discord(custom_hook)
            self.send_json({"success": ok, "message": msg})
            return

        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        return

def find_available_port(start_port=8000, max_attempts=10):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return start_port

def run_server(open_browser=True, port=None):
    if port is None:
        port = find_available_port(8000)
    server = ThreadingHTTPServer(("0.0.0.0", port), AlertHubHandler)
    url = f"http://localhost:{port}"

    print("=" * 68)
    print("🚀 Realtime Alert Hub (실시간 알리미 통합 포털 허브)")
    print("=" * 68)
    print(f"• 통합 대시보드 주소: {url}")
    print("• KOBUS 고속버스 + 서울시립대 수강신청 올인원 가동 중")
    print("• 웹 브라우저가 자동으로 실행됩니다. (종료: Ctrl + C)")
    print("=" * 68)

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] 통합 허브를 종료합니다...")
        kobus_monitor.stop_monitoring()
        uos_monitor.stop_monitoring()
        server.server_close()
        print("서버가 안전하게 종료되었습니다.")

if __name__ == "__main__":
    is_docker = os.environ.get("DOCKER_CONTAINER") == "1"
    run_server(open_browser=not is_docker, port=8000 if is_docker else None)
