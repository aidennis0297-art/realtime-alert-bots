#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KOBUS 고속버스 실시간 잔여 좌석 감지 및 알림 프로그램
- 출발지: 서울경부(010)
- 도착지: 부산(700)
- 일  시: 2026년 9월 23일(수) 18:00 이후 배차
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

# Windows 콘솔 한글 UTF-8 출력 보정
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    import winsound
    import ctypes

BASE_URL = "https://www.kobus.co.kr"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

class KobusMonitor:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.opener = self.create_session()
        self.last_available_keys = set()
        self.check_count = 0
        self.session_created_time = time.time()

    def load_config(self, path):
        default_config = {
            "departure_terminal": "010",
            "arrival_terminal": "700",
            "departure_name": "서울경부",
            "arrival_name": "부산",
            "date": "20260923",
            "min_time": "18:00",
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
                "enabled": False,
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
            print(f"[!] 초기 세션 접속 주의: {e}")
        self.session_created_time = time.time()
        return opener

    def query_timetable(self):
        # 30분마다 세션 재설정
        if time.time() - self.session_created_time > 1800:
            self.opener = self.create_session()

        data = {
            "deprCd": self.config["departure_terminal"],
            "arvlCd": self.config["arrival_terminal"],
            "pathDvs": "sngl",
            "pathStep": "1",
            "deprDtm": self.config["date"],
            "busClsCd": "0",
            "rtrpChc": "1",
            "timeLinkMin": self.config["min_time"].split(":")[0],
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

        with self.opener.open(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        rows = re.findall(r'<p\b[^>]*role=[\x22\x27]row[\x22\x27][^>]*>(.*?)</p>', html, re.DOTALL)
        buses = []

        for r in rows:
            time_m = re.search(r'class=[\x22\x27]start_time[\x22\x27][^>]*>(.*?)</span>', r)
            if not time_m:
                continue
            dep_time = re.sub(r'<[^>]+>', '', time_m.group(1)).strip().replace(" ", "")

            if dep_time < self.config["min_time"] or dep_time > self.config["max_time"]:
                continue

            com_m = re.search(r'class=[\x22\x27]bus_com[\x22\x27][^>]*>(.*?)</span>', r)
            if not com_m:
                com_m = re.search(r'class=[\x22\x27]bus_info[\x22\x27][^>]*>.*?<span[^>]*>(.*?)</span>', r, re.DOTALL)
            company = re.sub(r'<[^>]+>', '', com_m.group(1)).strip() if com_m else ""

            grade_m = re.search(r'class=[\x22\x27]grade_mo[\x22\x27][^>]*>(.*?)</span>', r)
            if not grade_m:
                grade_m = re.search(r'class=[\x22\x27]grade[\x22\x27][^>]*>(.*?)</span>', r)
            grade = re.sub(r'<[^>]+>', '', grade_m.group(1)).strip() if grade_m else ""
            grade = re.sub(r'\s+', ' ', grade).strip()

            if "임시" in r and "(임시)" not in grade:
                grade += "(임시)"

            rem_m = re.search(r'class=[\x22\x27]remain[\x22\x27][^>]*>(.*?)</span>', r)
            rem_text = re.sub(r'<[^>]+>', '', rem_m.group(1)).strip() if rem_m else ""

            status_m = re.search(r'class=[\x22\x27]status[\x22\x27][^>]*>(.*?)</span>', r)
            status_text = re.sub(r'<[^>]+>', '', status_m.group(1)).strip() if status_m else ""

            cnt_m = re.search(r'(\d+)', rem_text)
            seats = int(cnt_m.group(1)) if cnt_m else 0

            has_action = "fnSatsChc" in r
            bookable = (seats > 0 and has_action) or ("선택" in status_text and "매진" not in status_text)

            buses.append({
                "time": dep_time,
                "company": company,
                "grade": grade,
                "seats": seats,
                "seats_text": rem_text,
                "status": status_text,
                "bookable": bookable
            })

        return buses

    def play_sound(self):
        if sys.platform == "win32" and self.config.get("sound_alert", True):
            def _beep():
                for _ in range(3):
                    winsound.Beep(1200, 200)
                    winsound.Beep(1800, 300)
                    time.sleep(0.1)
            threading.Thread(target=_beep, daemon=True).start()

    def show_popup(self, message):
        if sys.platform == "win32" and self.config.get("popup_alert", True):
            def _popup():
                ctypes.windll.user32.MessageBoxW(
                    0,
                    message,
                    "★ KOBUS 고속버스 빈자리 알림 ★",
                    0x40 | 0x1000  # MB_ICONINFORMATION | MB_SETFOREGROUND
                )
            threading.Thread(target=_popup, daemon=True).start()

    def open_browser(self):
        if self.config.get("auto_open_browser", True):
            try:
                webbrowser.open(f"{BASE_URL}/mrs/rotinf.do")
            except Exception as e:
                print(f"[!] 브라우저 열기 실패: {e}")

    def send_telegram(self, message):
        tg = self.config.get("telegram", {})
        if not tg.get("enabled"):
            return
        token = tg.get("bot_token", "").strip()
        chat_id = tg.get("chat_id", "").strip()
        if not token or not chat_id or "여기에" in token:
            return

        def _send():
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5):
                    pass
            except Exception as e:
                print(f"[!] 텔레그램 전송 실패: {e}")

        threading.Thread(target=_send, daemon=True).start()

    def send_discord(self, message, available_buses=None):
        dc = self.config.get("discord", {})
        if not dc.get("enabled"):
            return
        webhook_url = dc.get("webhook_url", "").strip()
        if not webhook_url or "여기에" in webhook_url:
            return

        def _send():
            try:
                dep_name = self.config.get("departure_name", "서울경부")
                arr_name = self.config.get("arrival_name", "부산")
                date_str = self.config.get("date", "20260923")
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

                fields = []
                if available_buses:
                    bus_lines = []
                    for b in available_buses:
                        bus_lines.append(f"⏰ **{b['time']}** | {b['company']} ({b['grade']}) ➔ **{b['seats']}석**")
                    fields.append({
                        "name": "💺 예약 가능 배차 목록",
                        "value": "\n".join(bus_lines),
                        "inline": False
                    })

                embed = {
                    "title": f"🚨 [빈자리 발생!] {dep_name} ➔ {arr_name}",
                    "description": f"**일시:** {formatted_date}(수) 18시 이후\n\n지금 바로 아래 링크를 눌러 예매를 진행하세요!",
                    "url": f"{BASE_URL}/mrs/rotinf.do",
                    "color": 3447003,  # Blue/Cyan
                    "fields": fields,
                    "footer": {
                        "text": f"KOBUS 알리미 • 감지 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }

                payload = json.dumps({
                    "content": "@everyone 🚨 **서울경부 ➔ 부산 고속버스 빈자리가 나왔습니다!**",
                    "embeds": [embed]
                }).encode("utf-8")

                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": USER_AGENT
                    }
                )
                with urllib.request.urlopen(req, timeout=5):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📱 디스코드 모바일 푸시 알림 전송 완료!")
            except Exception as e:
                print(f"[!] 디스코드 전송 실패: {e}")

        threading.Thread(target=_send, daemon=True).start()

    def trigger_alert(self, available_buses):
        lines = []
        dep_name = self.config.get("departure_name", "서울경부")
        arr_name = self.config.get("arrival_name", "부산")
        date_str = self.config.get("date", "20260923")

        lines.append(f"🚨 [빈자리 발견!] {dep_name} ➔ {arr_name}")
        lines.append(f"📅 날짜: {date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}")
        lines.append("───────────────────────────────")
        for b in available_buses:
            lines.append(f"⏰ {b['time']} | {b['company']} | {b['grade']} | 잔여 {b['seats']}석")
        lines.append("───────────────────────────────")
        lines.append("👉 지금 바로 KOBUS에서 예매하세요! (브라우저가 열렸습니다)")

        alert_text = "\n".join(lines)
        print("\n" + "=" * 50)
        print(alert_text)
        print("=" * 50 + "\n")

        self.play_sound()
        self.show_popup(alert_text)
        self.open_browser()
        self.send_telegram(alert_text)
        self.send_discord(alert_text, available_buses)

    def run(self):
        date_str = self.config.get("date", "20260923")
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        dep_name = self.config.get("departure_name", "서울경부")
        arr_name = self.config.get("arrival_name", "부산")
        min_time = self.config.get("min_time", "18:00")
        interval = self.config.get("check_interval_seconds", 6)

        print("=" * 60)
        print("🚌 KOBUS 고속버스 빈자리 모니터링 알리미")
        print("=" * 60)
        print(f"• 구간: {dep_name} ➔ {arr_name}")
        print(f"• 날짜: {formatted_date} (수요일)")
        print(f"• 시간: {min_time} 이후 모든 배차")
        print(f"• 주기: 약 {interval}초 간격")
        print(f"• 사운드 알림: {'켜짐' if self.config.get('sound_alert') else '꺼짐'}")
        print(f"• 팝업 알림: {'켜짐' if self.config.get('popup_alert') else '꺼짐'}")
        print(f"• 브라우저 자동 오픈: {'켜짐' if self.config.get('auto_open_browser') else '꺼짐'}")
        print(f"• 텔레그램: {'켜짐' if self.config.get('telegram', {}).get('enabled') else '꺼짐'}")
        print(f"• 디스코드: {'켜짐' if self.config.get('discord', {}).get('enabled') else '꺼짐'}")
        print("=" * 60)
        print("※ 프로그램을 종료하려면 Ctrl + C 를 누르세요.\n")

        while True:
            self.check_count += 1
            now_str = datetime.now().strftime("%H:%M:%S")

            try:
                buses = self.query_timetable()
                available = [b for b in buses if b["bookable"]]

                current_available_keys = {f"{b['time']}_{b['seats']}" for b in available}

                if available:
                    # 새로운 좌석 변동이 있거나 처음 발견된 경우 알림
                    if current_available_keys != self.last_available_keys:
                        self.trigger_alert(available)
                        self.last_available_keys = current_available_keys
                    else:
                        print(f"[{now_str} | #{self.check_count}] ★ 빈자리 계속 유지 중: {', '.join(b['time'] + '(' + str(b['seats']) + '석)' for b in available)}")
                else:
                    self.last_available_keys = set()
                    print(f"[{now_str} | #{self.check_count}] 총 {len(buses)}개 배차 조회 완료 ➔ 전편 매진 (대기 중...)", end="\r", flush=True)

            except KeyboardInterrupt:
                print("\n\n사용자에 의해 모니터링이 중단되었습니다.")
                break
            except Exception as e:
                print(f"\n[{now_str} | #{self.check_count}] 일시적 조회 오류 발생: {e} (재시도 대기)")
                # 오류 발생 시 세션 재수립 시도
                time.sleep(3)
                try:
                    self.opener = self.create_session()
                except Exception:
                    pass

            # 랜덤 지연을 약간 주어 트래픽 패턴 분산
            jitter = random.uniform(-0.5, 1.0)
            sleep_time = max(3.0, interval + jitter)
            time.sleep(sleep_time)

if __name__ == "__main__":
    monitor = KobusMonitor("config.json")
    monitor.run()
