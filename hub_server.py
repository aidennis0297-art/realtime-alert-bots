#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Realtime Alert Hub 2.0 (실시간 알리미 통합 포털 허브)
- 포트: 8000 (기본값)
- 5대 통합 모니터링 서비스:
  1. 고속버스(KOBUS) 취소표 알리미 (광역시도별 권역 필터 + 잔여석 기준)
  2. KTX/SRT 열차 취소표 알리미 (광역시도별 역 선택 + 잔여석 기준)
  3. 영화관(메가박스) 특별관/명당 잔여석 알리미 (114개 극장 + 돌비시네마 등 특별관)
  4. 시립대(UOS) 수강신청 빈자리 알리미 (3,026개 과목 + 별표 Watchlist)
  5. 시립대(UOS) 스마트 캠퍼스 (중앙도서관 열람실 실시간 좌석 + 학사/장학/해외파견 공지 모아보기 & 추천 검색어)
- Zero-dependency: Python 3 표준 내장 라이브러리만 사용
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
sub_paths = [
    os.path.join(BASE_DIR, "kobus-seat-alert"),
    os.path.join(BASE_DIR, "train-seat-alert"),
    os.path.join(BASE_DIR, "cinema-seat-alert"),
    os.path.join(BASE_DIR, "uos-sugang-alert"),
    os.path.join(BASE_DIR, "flight-seat-alert")
]
for p in sub_paths:
    if p not in sys.path:
        sys.path.insert(0, p)

# 1. KOBUS 엔진 로드
from bus_alert import KobusMonitor
kobus_cfg = os.path.join(BASE_DIR, "kobus-seat-alert", "config.json")
if not os.path.exists(kobus_cfg):
    kobus_cfg = os.path.join(BASE_DIR, "kobus-seat-alert", "config.example.json")
kobus_monitor = KobusMonitor(kobus_cfg)

# 2. Train (KTX/SRT) 엔진 로드
from train_alert import TrainMonitor, STATION_REGIONS
train_cfg = os.path.join(BASE_DIR, "train-seat-alert", "config.json")
if not os.path.exists(train_cfg):
    train_cfg = os.path.join(BASE_DIR, "train-seat-alert", "config.example.json")
train_monitor = TrainMonitor(train_cfg)

# 3. Cinema (Megabox & CGV) 엔진 로드
from cinema_alert import CinemaMonitor
cinema_cfg = os.path.join(BASE_DIR, "cinema-seat-alert", "config.json")
if not os.path.exists(cinema_cfg):
    cinema_cfg = os.path.join(BASE_DIR, "cinema-seat-alert", "config.example.json")
cinema_monitor = CinemaMonitor(cinema_cfg)

# 4. UOS 수강신청 엔진 로드
from uos_sugang_alert import UosSugangMonitor
uos_cfg = os.path.join(BASE_DIR, "uos-sugang-alert", "config.json")
if not os.path.exists(uos_cfg):
    uos_cfg = os.path.join(BASE_DIR, "uos-sugang-alert", "config.example.json")
uos_monitor = UosSugangMonitor(uos_cfg)

# 5. UOS 스마트 캠퍼스 (도서관 & 공지) 엔진 로드
from uos_campus_alert import UosCampusMonitor, RECOMMENDED_TAGS
campus_cfg = os.path.join(BASE_DIR, "uos-sugang-alert", "campus_config.json")
campus_monitor = UosCampusMonitor(campus_cfg)

# 6. Flight (제주 & 일본 특가) 엔진 로드
from flight_alert import FlightMonitor, POPULAR_ROUTES, AIRPORTS
flight_cfg = os.path.join(BASE_DIR, "flight-seat-alert", "config.json")
if not os.path.exists(flight_cfg):
    flight_cfg = os.path.join(BASE_DIR, "flight-seat-alert", "config.example.json")
flight_monitor = FlightMonitor(flight_cfg)


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
                "train": train_monitor.get_status(),
                "cinema": cinema_monitor.get_status(),
                "uos_sugang": uos_monitor.get_status(),
                "uos_campus": campus_monitor.get_status(),
                "flight": flight_monitor.get_status()
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

        # 4. Train (KTX/SRT) APIs
        if path == "/api/train/stations":
            self.send_json({"regions": STATION_REGIONS})
            return

        if path == "/api/train/config":
            self.send_json(train_monitor.config)
            return

        if path == "/api/train/schedule":
            dep = qs.get("depCode", [train_monitor.config.get("departure_station", "0551")])[0]
            arr = qs.get("arrCode", [train_monitor.config.get("arrival_station", "0020")])[0]
            date = qs.get("date", [train_monitor.config.get("date", "")])[0]
            min_time = qs.get("minTime", [train_monitor.config.get("min_time", "00:00")])[0]
            max_time = qs.get("maxTime", [train_monitor.config.get("max_time", "23:59")])[0]
            trains = train_monitor.query_trains(dep, arr, date, min_time, max_time)
            self.send_json({"trains": trains})
            return

        if path == "/api/train/monitor/status":
            self.send_json(train_monitor.get_status())
            return

        # 5. Cinema (CGV IMAX & Megabox) APIs
        if path == "/api/cinema/theaters":
            brand = qs.get("brand", [cinema_monitor.config.get("brand", "CGV")])[0].upper()
            self.send_json({
                "brand": brand,
                "brands": ["CGV", "MEGABOX"],
                "regions": cinema_monitor.fetch_theaters(brand)
            })
            return

        if path == "/api/cinema/config":
            self.send_json(cinema_monitor.config)
            return

        if path == "/api/cinema/schedule":
            brand = qs.get("brand", [cinema_monitor.config.get("brand", "CGV")])[0].upper()
            default_th = "0013" if brand == "CGV" else "1351"
            th = qs.get("theaterCode", [cinema_monitor.config.get("theater_code", default_th)])[0]
            date = qs.get("date", [cinema_monitor.config.get("date", "")])[0]
            mv = qs.get("movieFilter", [cinema_monitor.config.get("target_movie", "")])[0]
            spc = qs.get("specialOnly", ["0"])[0] == "1"
            min_seats = int(qs.get("minSeats", [cinema_monitor.config.get("min_seats", 1)])[0])
            shows = cinema_monitor.query_showtimes(brand=brand, theater_code=th, date=date, movie_filter=mv, special_only=spc, min_seats=min_seats)
            self.send_json({"brand": brand, "showtimes": shows})
            return

        if path == "/api/cinema/monitor/status":
            self.send_json(cinema_monitor.get_status())
            return

        # 6. UOS Sugang APIs
        if path == "/api/uos/config":
            cfg = uos_monitor.config
            period = uos_monitor.get_academic_period()
            safe_cfg = {
                "student_id": cfg.get("student_id", ""),
                "password": cfg.get("password", ""),
                "device": cfg.get("device", "PC"),
                "year": cfg.get("year", period["year"]),
                "semester": cfg.get("semester", period["semester"]),
                "academic_period": period,
                "target_courses": cfg.get("target_courses", []),
                "check_interval_seconds": cfg.get("check_interval_seconds", 6),
                "discord": cfg.get("discord", {})
            }
            self.send_json(safe_cfg)
            return

        if path == "/api/uos/courses":
            period = uos_monitor.get_academic_period()
            year = qs.get("year", [period["year"]])[0]
            sem = qs.get("sem", [period["semester"]])[0]
            refresh = qs.get("refresh", ["0"])[0] == "1"
            courses = uos_monitor.fetch_courses(year=year, semester=sem, force_refresh=refresh)
            self.send_json({"courses": courses, "academic_period": period})
            return

        if path == "/api/uos/monitor/status":
            self.send_json(uos_monitor.get_status())
            return

        # 7. UOS Smart Campus APIs (Library & Notices)
        if path == "/api/campus/library":
            rooms = campus_monitor.fetch_library_seats()
            self.send_json({"rooms": rooms})
            return

        if path == "/api/campus/notices":
            refresh = qs.get("refresh", ["0"])[0] == "1"
            notices, _ = campus_monitor.fetch_notices(force_refresh=refresh)
            self.send_json({
                "notices": notices,
                "recommended_tags": RECOMMENDED_TAGS
            })
            return

        if path == "/api/campus/config":
            self.send_json(campus_monitor.config)
            return

        if path == "/api/campus/monitor/status":
            self.send_json(campus_monitor.get_status())
            return

        # 8. Flight (제주 & 일본 특가) APIs
        if path == "/api/flight/routes":
            self.send_json({
                "routes": POPULAR_ROUTES,
                "airports": AIRPORTS
            })
            return

        if path == "/api/flight/config":
            self.send_json(flight_monitor.config)
            return

        if path == "/api/flight/schedule":
            dep = qs.get("dep", [flight_monitor.config.get("dep_code", "GMP")])[0]
            arr = qs.get("arr", [flight_monitor.config.get("arr_code", "CJU")])[0]
            date = qs.get("date", [flight_monitor.config.get("date", "")])[0]
            max_price = int(qs.get("maxPrice", [flight_monitor.config.get("max_price", 999999)])[0])
            golden_only = qs.get("goldenOnly", ["0"])[0] == "1"
            promo_only = qs.get("promoOnly", ["0"])[0] == "1"
            flights = flight_monitor.query_flights(dep_code=dep, arr_code=arr, date_str=date, max_price=max_price, golden_only=golden_only, promo_only=promo_only)
            self.send_json({"dep": dep, "arr": arr, "flights": flights})
            return

        if path == "/api/flight/monitor/status":
            self.send_json(flight_monitor.get_status())
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

        # 1. Master Start / Stop
        if path == "/api/hub/start_all":
            k_ok, _ = kobus_monitor.start_monitoring()
            t_ok, _ = train_monitor.start_monitoring()
            c_ok, _ = cinema_monitor.start_monitoring()
            u_ok, _ = uos_monitor.start_monitoring()
            cp_ok, _ = campus_monitor.start_monitoring()
            fl_ok, _ = flight_monitor.start_monitoring()
            self.send_json({"success": True, "message": "전체 감시 엔진(고속버스/열차/영화관/수강/캠퍼스/항공권)이 가동되었습니다."})
            return

        if path == "/api/hub/stop_all":
            kobus_monitor.stop_monitoring()
            train_monitor.stop_monitoring()
            cinema_monitor.stop_monitoring()
            uos_monitor.stop_monitoring()
            campus_monitor.stop_monitoring()
            flight_monitor.stop_monitoring()
            self.send_json({"success": True, "message": "전체 감시 엔진이 중지되었습니다."})
            return

        # 2. KOBUS POSTs
        if path == "/api/kobus/config":
            curr = kobus_monitor.config
            for k, v in body.items():
                curr[k] = v
            kobus_monitor.save_config(curr)
            self.send_json({"success": True, "message": "KOBUS 설정 저장 완료"})
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

        # 3. Train POSTs
        if path == "/api/train/config":
            curr = train_monitor.config
            for k, v in body.items():
                curr[k] = v
            train_monitor.save_config(curr)
            self.send_json({"success": True, "message": "KTX/SRT 설정 저장 완료"})
            return

        if path == "/api/train/monitor/start":
            ok, msg = train_monitor.start_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/train/monitor/stop":
            ok, msg = train_monitor.stop_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/train/discord/test":
            hook = body.get("webhook_url") or None
            ok, msg = train_monitor.send_test_discord(hook)
            self.send_json({"success": ok, "message": msg})
            return

        # 4. Cinema POSTs
        if path == "/api/cinema/config":
            curr = cinema_monitor.config
            for k, v in body.items():
                curr[k] = v
            cinema_monitor.save_config(curr)
            self.send_json({"success": True, "message": "영화관 설정 저장 완료"})
            return

        if path == "/api/cinema/monitor/start":
            ok, msg = cinema_monitor.start_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/cinema/monitor/stop":
            ok, msg = cinema_monitor.stop_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/cinema/discord/test":
            hook = body.get("webhook_url") or None
            ok, msg = cinema_monitor.send_test_discord(hook)
            self.send_json({"success": ok, "message": msg})
            return

        # 5. UOS Sugang POSTs
        if path == "/api/uos/config":
            curr = uos_monitor.config
            for k in ["student_id", "password", "year", "semester", "check_interval_seconds", "discord"]:
                if k in body:
                    curr[k] = body[k]
            uos_monitor.save_config(curr)
            self.send_json({"success": True, "message": "수강신청 설정 저장 완료"})
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

        # 6. UOS Campus POSTs
        if path == "/api/campus/config":
            curr = campus_monitor.config
            if "watch_keywords" in body:
                curr["watch_keywords"] = body["watch_keywords"]
            if "check_interval_seconds" in body:
                curr["check_interval_seconds"] = body["check_interval_seconds"]
            if "discord" in body:
                curr["discord"] = body["discord"]
            campus_monitor.save_config(curr)
            self.send_json({"success": True, "message": "스마트 캠퍼스 설정 저장 완료"})
            return

        if path == "/api/campus/monitor/start":
            ok, msg = campus_monitor.start_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/campus/monitor/stop":
            ok, msg = campus_monitor.stop_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/campus/discord/test":
            custom_hook = body.get("webhook_url", "").strip() or None
            test_obj = {
                "category": "테스트공지",
                "title": "[테스트] 시립대 스마트 캠퍼스 알리미 연동 확인",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "link": "https://www.uos.ac.kr",
                "tags": ["#장학금", "#해외파견", "#계절학기"]
            }
            campus_monitor.send_discord_notice_burst(test_obj)
            self.send_json({"success": True, "message": "테스트 알림 발송 완료!"})
            return

        # 7. Flight POSTs
        if path == "/api/flight/config":
            curr = flight_monitor.config
            for k in ["route_id", "dep_code", "arr_code", "date", "max_price", "golden_time_only", "promo_only", "check_interval_seconds", "discord"]:
                if k in body:
                    curr[k] = body[k]
            flight_monitor.save_config(curr)
            self.send_json({"success": True, "message": "항공권 설정 저장 완료"})
            return

        if path == "/api/flight/monitor/start":
            ok, msg = flight_monitor.start_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/flight/monitor/stop":
            ok, msg = flight_monitor.stop_monitoring()
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/flight/discord/test":
            custom_hook = body.get("webhook_url", "").strip() or None
            ok, msg = flight_monitor.send_test_discord(custom_hook)
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

    print("=" * 72)
    print("🚀 Realtime Alert Hub 2.0 (실시간 알리미 6대 올인원 포털 허브)")
    print("=" * 72)
    print(f"• 통합 대시보드 주소: {url}")
    print("• 가동 서비스: 고속버스 + KTX/SRT + 특가 항공권 + 영화관 명당 + 수강신청 + 캠퍼스")
    print("• 웹 브라우저가 자동으로 실행됩니다. (종료: Ctrl + C)")
    print("=" * 72)

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] 통합 허브를 종료합니다...")
        kobus_monitor.stop_monitoring()
        train_monitor.stop_monitoring()
        cinema_monitor.stop_monitoring()
        uos_monitor.stop_monitoring()
        campus_monitor.stop_monitoring()
        flight_monitor.stop_monitoring()
        server.server_close()
        print("서버가 안전하게 종료되었습니다.")


if __name__ == "__main__":
    is_docker = os.environ.get("DOCKER_CONTAINER") == "1"
    run_server(open_browser=not is_docker, port=8000 if is_docker else None)
