#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KOBUS 고속버스 실시간 잔여 좌석 감지 및 3연타 알리미 코어 엔진
- CLI 및 로컬 Web GUI 백엔드 겸용 모듈
"""

import os
import sys
import time
import json
import random
import threading
import ssl
import http.cookiejar
import urllib.request
import urllib.parse
import re
import webbrowser
from datetime import datetime
from collections import deque

# Windows 콘솔 한글 UTF-8 출력 보정
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        import winsound
        import ctypes
    except Exception:
        winsound = None
        ctypes = None
else:
    winsound = None
    ctypes = None

BASE_URL = "https://www.kobus.co.kr"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

class KobusMonitor:
    def __init__(self, config_path="config.json", log_callback=None):
        self.config_path = config_path
        self.config = self.load_config(config_path)
        self.log_callback = log_callback
        self.recent_logs = deque(maxlen=200)
        self.opener = self.create_session()
        self.last_available_keys = set()
        self.check_count = 0
        self.session_created_time = time.time()
        self.last_heartbeat_time = time.time()
        self.heartbeat_interval = 10800  # 3시간

        self.running = False
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.last_buses = []
        self.vacant_buses = []
        self.terminals_cache = None

    def load_config(self, path):
        default_config = {
            "departure_terminal": "010",
            "arrival_terminal": "700",
            "departure_name": "서울경부",
            "arrival_name": "부산",
            "date": "20260923",
            "min_time": "14:00",
            "max_time": "23:59",
            "check_interval_seconds": 6,
            "sound_alert": True,
            "popup_alert": True,
            "auto_open_browser": True,
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": ""
            },
            "discord": {
                "enabled": True,
                "webhook_url": ""
            }
        }
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                    default_config.update(user_cfg)
            except Exception as e:
                print(f"[!] 설정 파일 읽기 오류: {e}, 기본 설정을 사용합니다.")
        return default_config

    def save_config(self, new_config=None):
        if new_config:
            self.config = new_config
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def log(self, msg, also_print=True):
        now_str = datetime.now().strftime("%H:%M:%S")
        entry = f"[{now_str}] {msg}"
        self.recent_logs.append(entry)
        if also_print:
            try:
                print(entry)
            except Exception:
                pass
        if self.log_callback:
            try:
                self.log_callback(entry)
            except Exception:
                pass

    def create_session(self):
        jar = http.cookiejar.CookieJar()
        ctx = ssl._create_unverified_context()
        try:
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            pass
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar),
            urllib.request.HTTPSHandler(context=ctx)
        )
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/main.do",
                headers={"User-Agent": USER_AGENT}
            )
            opener.open(req, timeout=10)
        except Exception as e:
            pass
        self.session_created_time = time.time()
        return opener

    def fetch_terminals(self):
        """KOBUS 1,240개 노선 연동하여 출발/도착 터미널 매핑 데이터 반환"""
        if self.terminals_cache:
            return self.terminals_cache

        try:
            req = urllib.request.Request(
                f"{BASE_URL}/mrs/readRotLinInf.ajax",
                data=b"",
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": f"{BASE_URL}/mrs/rotinf.do",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            with self.opener.open(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                rot_list = data.get("rotInfList", [])

                dep_map = {}
                routes_map = {}

                for r in rot_list:
                    d_cd = r.get("deprCd")
                    d_nm = r.get("deprNm")
                    a_cd = r.get("arvlCd")
                    a_nm = r.get("arvlNm")
                    if d_cd and d_nm and a_cd and a_nm:
                        dep_map[d_cd] = d_nm
                        if d_cd not in routes_map:
                            routes_map[d_cd] = []
                        routes_map[d_cd].append({"arvlCd": a_cd, "arvlNm": a_nm})

                # 정렬
                dep_list = [{"code": k, "name": v} for k, v in dep_map.items()]
                dep_list.sort(key=lambda x: x["name"])

                for k in routes_map:
                    routes_map[k].sort(key=lambda x: x["arvlNm"])

                self.terminals_cache = {
                    "departures": dep_list,
                    "routes": routes_map
                }
                return self.terminals_cache
        except Exception as e:
            self.log(f"터미널 목록 로드 실패: {e}")
            return {"departures": [], "routes": {}}

    def query_timetable(self, depr_cd=None, arvl_cd=None, date=None, min_time=None, max_time=None):
        """KOBUS 실시간 배차 및 좌석 조회"""
        if time.time() - self.session_created_time > 1800:
            self.opener = self.create_session()

        depr_cd = depr_cd or self.config.get("departure_terminal", "021")
        arvl_cd = arvl_cd or self.config.get("arrival_terminal", "393")
        date = (date or self.config.get("date", "20260923")).replace("-", "")
        min_time = min_time or self.config.get("min_time", "00:00")
        max_time = max_time or self.config.get("max_time", "23:59")

        min_hour = min_time.split(":")[0] if ":" in min_time else "00"

        data = {
            "deprCd": depr_cd,
            "arvlCd": arvl_cd,
            "pathDvs": "sngl",
            "pathStep": "1",
            "deprDtm": date,
            "busClsCd": "0",
            "rtrpChc": "1",
            "timeLinkMin": min_hour,
            "timeLinkMax": "23"
        }

        req = urllib.request.Request(
            f"{BASE_URL}/mrs/alcnSrch.do",
            data=urllib.parse.urlencode(data).encode("utf-8"),
            headers={
                "User-Agent": USER_AGENT,
                "Referer": f"{BASE_URL}/mrs/rotinf.do",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )

        try:
            with self.opener.open(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.log(f"KOBUS 배차 조회 네트워크 오류: {e}")
            return []

        rows = re.findall(r'<p\b[^>]*role=[\x22\x27]row[\x22\x27][^>]*>(.*?)</p>', html, re.DOTALL)
        results = []

        for r in rows:
            time_m = re.search(r'class=[\x22\x27]start_time[\x22\x27][^>]*>(.*?)</span>', r)
            if not time_m:
                continue
            dep_time = re.sub(r'<[^>]+>', '', time_m.group(1)).strip().replace(" ", "")

            if dep_time < min_time or dep_time > max_time:
                continue

            com_m = re.search(r'class=[\x22\x27]bus_com[\x22\x27][^>]*>(.*?)</span>', r)
            if not com_m:
                com_m = re.search(r'class=[\x22\x27]bus_info[\x22\x27][^>]*>.*?<span[^>]*>(.*?)</span>', r, re.DOTALL)
            company = re.sub(r'<[^>]+>', '', com_m.group(1)).strip() if com_m else ""

            grd_m = re.search(r'class=[\x22\x27]grade[\x22\x27][^>]*>(.*?)</span>', r)
            bus_grade = re.sub(r'<[^>]+>', '', grd_m.group(1)).strip() if grd_m else "일반"

            rem_m = re.search(r'class=[\x22\x27]rem_seat[\x22\x27][^>]*>(.*?)</span>', r)
            tot_m = re.search(r'class=[\x22\x27]tot_seat[\x22\x27][^>]*>(.*?)</span>', r)

            rem_seats = 0
            if rem_m:
                rem_text = re.sub(r'<[^>]+>', '', rem_m.group(1)).strip()
                digits = re.findall(r'\d+', rem_text)
                if digits:
                    rem_seats = int(digits[0])

            tot_seats = 0
            if tot_m:
                tot_text = re.sub(r'<[^>]+>', '', tot_m.group(1)).strip()
                digits = re.findall(r'\d+', tot_text)
                if digits:
                    tot_seats = int(digits[0])

            key = f"{dep_time}_{company}_{bus_grade}"
            results.append({
                "depr_time": dep_time,
                "company": company,
                "bus_grade": bus_grade,
                "tot_seats": tot_seats,
                "rem_seats": rem_seats,
                "is_vacant": rem_seats > 0,
                "key": key
            })

        return results

    def post_discord(self, payload_dict, webhook_url=None):
        if not webhook_url:
            dc = self.config.get("discord", {})
            if not dc.get("enabled", True):
                return False, "디스코드 알림이 비활성화되어 있습니다."
            webhook_url = dc.get("webhook_url", "").strip()

        if not webhook_url:
            return False, "웹훅 URL이 설정되지 않았습니다."

        def _send():
            try:
                payload = json.dumps(payload_dict).encode("utf-8")
                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status in (200, 204):
                        self.log("디스코드 알림 발송 완료")
            except Exception as e:
                self.log(f"디스코드 전송 실패: {e}")

        threading.Thread(target=_send, daemon=True).start()
        return True, "전송 요청 완료"

    def send_startup_discord(self):
        dep_name = self.config.get("departure_name", "출발지")
        arr_name = self.config.get("arrival_name", "도착지")
        date_str = self.config.get("date", "")
        min_time = self.config.get("min_time", "")

        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else date_str

        payload = {
            "content": "🚀 **[모니터링 시작] KOBUS 고속버스 빈자리 알리미 가동!**",
            "embeds": [{
                "title": f"🚌 {dep_name} ➔ {arr_name}",
                "description": (
                    f"**일시:** {formatted_date} {min_time} 이후 배차\n\n"
                    "• **알림 조건:** 취소표/빈자리 ≥ 1석 발생 시 즉시 감지\n"
                    "• **알림 방식:** 🚨 1.5초 간격 3회 연속 폰 진동 푸시 (@everyone)\n"
                    "• **예매 바로가기:** 아래 링크를 누르면 KOBUS로 즉시 이동합니다."
                ),
                "url": "https://www.kobus.co.kr/mrs/rotinf.do",
                "color": 3447003,
                "footer": {"text": f"KOBUS 알리미 • 시작 시각: {now_time}"}
            }]
        }
        self.post_discord(payload)

    def trigger_alerts(self, available_buses, count=3, delay=1.5):
        dep_name = self.config.get("departure_name", "출발지")
        arr_name = self.config.get("arrival_name", "도착지")
        date_str = self.config.get("date", "")
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else date_str

        # 1. PC 사운드
        if self.config.get("sound_alert", True) and winsound:
            def _sound():
                for _ in range(3):
                    try:
                        winsound.Beep(2000, 250)
                        time.sleep(0.1)
                        winsound.Beep(2500, 300)
                    except Exception:
                        pass
                    time.sleep(0.2)
            threading.Thread(target=_sound, daemon=True).start()

        # 2. 브라우저 오픈
        if self.config.get("auto_open_browser", True):
            try:
                webbrowser.open("https://www.kobus.co.kr/mrs/rotinf.do")
            except Exception:
                pass

        # 3. 화면 팝업
        if self.config.get("popup_alert", True) and ctypes:
            def _popup():
                lines = [f"{b['depr_time']} ({b['bus_grade']}) - 잔여 {b['rem_seats']}석" for b in available_buses]
                msg = f"[{dep_name} ➔ {arr_name}]\n{formatted_date}\n\n" + "\n".join(lines) + "\n\n지금 바로 예매하세요!"
                try:
                    ctypes.windll.user32.MessageBoxW(0, msg, "🚨 [KOBUS] 빈자리 발생 알림!", 0x40 | 0x1000)
                except Exception:
                    pass
            threading.Thread(target=_popup, daemon=True).start()

        # 4. 디스코드 3연타 버스트
        def _discord():
            bus_lines = []
            for b in available_buses:
                bus_lines.append(f"⏰ **{b['depr_time']}** | {b['company']} ({b['bus_grade']}) ➔ 🎉 **{b['rem_seats']}석 잔여!**")

            for idx in range(1, count + 1):
                now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                payload = {
                    "content": f"@everyone 🚨 [취소표 발생 {idx}/{count}] **{dep_name} ➔ {arr_name} 고속버스 빈자리가 나왔습니다!**",
                    "embeds": [{
                        "title": f"🎉 [{dep_name} ➔ {arr_name}] 빈자리 즉시 예매 가능!",
                        "description": (
                            f"**출발일시:** {formatted_date}\n\n"
                            + "\n".join(bus_lines)
                            + "\n\n👉 **[KOBUS 예매 바로가기 (클릭)](https://www.kobus.co.kr/mrs/rotinf.do)**"
                        ),
                        "url": "https://www.kobus.co.kr/mrs/rotinf.do",
                        "color": 15158332,
                        "footer": {"text": f"KOBUS 알리미 • {idx}/{count}회차 알림 • {now_time}"}
                    }]
                }
                self.post_discord(payload)
                if idx < count:
                    time.sleep(delay)

        threading.Thread(target=_discord, daemon=True).start()

    def send_test_discord(self, custom_webhook=None):
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dep_name = self.config.get("departure_name", "출발지")
        arr_name = self.config.get("arrival_name", "도착지")
        payload = {
            "content": "@everyone 🔔 **[테스트] KOBUS 고속버스 빈자리 알리미 연동 확인!**",
            "embeds": [{
                "title": "✅ 디스코드 모바일 푸시 알림 정상 작동",
                "description": f"**{dep_name} ➔ {arr_name}** 모니터링 알림이 정상 연결되었습니다.\n\n취소표가 발생하면 스마트폰 잠금화면으로 1.5초 간격 3연타 진동 푸시가 발송됩니다.",
                "url": "https://www.kobus.co.kr/mrs/rotinf.do",
                "color": 65280,
                "footer": {"text": f"KOBUS 알리미 • 테스트 시각: {now_time}"}
            }]
        }
        return self.post_discord(payload, custom_webhook)

    def _monitor_loop(self):
        dep_name = self.config.get("departure_name", "출발지")
        arr_name = self.config.get("arrival_name", "도착지")
        self.log(f"🚀 KOBUS 실시간 모니터링 시작: {dep_name} ➔ {arr_name}")
        self.send_startup_discord()

        while not self.stop_event.is_set():
            self.check_count += 1
            now_str = datetime.now().strftime("%H:%M:%S")
            interval = self.config.get("check_interval_seconds", 6)

            try:
                buses = self.query_timetable()
                self.last_buses = buses
                vacant = [b for b in buses if b["is_vacant"]]
                self.vacant_buses = vacant

                current_keys = {b["key"] for b in vacant}

                if vacant:
                    if current_keys != self.last_available_keys:
                        self.log(f"🚨 취소표/빈자리 감지!! ({len(vacant)}개 배차)")
                        for b in vacant:
                            self.log(f"   ★ [{b['depr_time']}] {b['company']} ({b['bus_grade']}): {b['rem_seats']}석 잔여!")
                        self.trigger_alerts(vacant)
                        self.last_available_keys = current_keys
                    else:
                        summary = ", ".join(f"{b['depr_time']}({b['rem_seats']}석)" for b in vacant)
                        self.log(f"[#{self.check_count}] ★ 빈자리 유지 중: {summary}", also_print=False)
                else:
                    self.last_available_keys = set()
                    self.log(f"[#{self.check_count}] 전 배차 매진 대기 중 (총 {len(buses)}개 배차)", also_print=False)

            except Exception as e:
                self.log(f"점검 중 오류 발생: {e}")

            jitter = random.uniform(-0.5, 0.5)
            wait_sec = max(3.0, interval + jitter)
            if self.stop_event.wait(wait_sec):
                break

        self.running = False
        self.log("🛑 KOBUS 모니터링 스레드가 안전하게 종료되었습니다.")

    def start_monitoring(self):
        if self.running:
            return False, "이미 모니터링이 가동 중입니다."
        self.stop_event.clear()
        self.running = True
        self.worker_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.worker_thread.start()
        return True, "모니터링이 시작되었습니다."

    def stop_monitoring(self):
        if not self.running:
            return False, "모니터링이 실행 중이 아닙니다."
        self.stop_event.set()
        self.running = False
        return True, "모니터링 중지 신호가 전송되었습니다."

    def get_status(self):
        return {
            "running": self.running,
            "check_count": self.check_count,
            "departure_name": self.config.get("departure_name", ""),
            "arrival_name": self.config.get("arrival_name", ""),
            "date": self.config.get("date", ""),
            "min_time": self.config.get("min_time", ""),
            "max_time": self.config.get("max_time", ""),
            "last_buses_count": len(self.last_buses),
            "vacant_buses": self.vacant_buses,
            "recent_logs": list(self.recent_logs)
        }

    def run(self):
        """CLI 단독 실행"""
        self.start_monitoring()
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_monitoring()
            print("\n모니터링 종료")

if __name__ == "__main__":
    monitor = KobusMonitor("config.json")
    monitor.run()
