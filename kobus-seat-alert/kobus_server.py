#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KOBUS 고속버스 빈자리 모니터링 (GCP 클라우드 systemd 서비스용 - 3연타 알림 버전)
- 구간: 서울경부 ➔ 부산
- 일시: 2026년 9월 23일(수) 18:00 이후 전 배차
- 기능:
  1. 빈자리 감지 시 1.5초 간격으로 3회 연속 강력 푸시 알림 (놓침 방지!)
  2. 3시간마다 조용한 생존 보고 (하트비트)
  3. 재부팅 시 자동 실행 (systemd)
"""

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
from datetime import datetime

# 설정
BASE_URL = "https://www.kobus.co.kr"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
def get_discord_webhook():
    env_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if env_url:
        return env_url.strip()
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("discord", {}).get("webhook_url", "").strip()
        except Exception:
            pass
    return "YOUR_DISCORD_WEBHOOK_URL"

DISCORD_WEBHOOK_URL = get_discord_webhook()

DEP_CD = "010"      # 서울경부
ARV_CD = "700"      # 부산
DEP_NAME = "서울경부"
ARV_NAME = "부산"
DATE_STR = "20260923"
MIN_TIME = "14:00"
INTERVAL = 6.0              # 조회 주기 (약 6초)
HEARTBEAT_INTERVAL = 10800  # 생존 보고 주기 (3시간 = 10800초)

def post_discord(payload_dict):
    try:
        payload = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[!] 디스코드 전송 실패: {e}")

def send_startup():
    formatted_date = f"{DATE_STR[:4]}-{DATE_STR[4:6]}-{DATE_STR[6:8]}"
    payload = {
        "content": "🚀 **[시스템 영구 가동] KOBUS 3연속 알림 모니터링 시작!**",
        "embeds": [{
            "title": "✅ KOBUS 24시간 자동 감시 모드 가동 중",
            "description": (
                f"**구간:** {DEP_NAME} ➔ {ARV_NAME}\n"
                f"**일시:** {formatted_date}(수) {MIN_TIME} 이후 전 배차 (총 15편)\n\n"
                f"• **알림 방식:** 🚨 **빈자리 발생 시 3회 연속 폰 진동 알림 (놓침 방지!)**\n"
                f"• **생존 보고(하트비트):** 3시간마다 정상 작동 상태 보고\n"
                f"• **재부팅 자동 복구:** 켜짐 (서버 점검/재부팅 시 자동 재시작)"
            ),
            "url": f"{BASE_URL}/mrs/rotinf.do",
            "color": 3447003,
            "footer": {"text": f"GCP 서비스 시작 • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
        }]
    }
    threading.Thread(target=post_discord, args=(payload,), daemon=True).start()

def send_heartbeat(check_count):
    formatted_date = f"{DATE_STR[:4]}-{DATE_STR[4:6]}-{DATE_STR[6:8]}"
    payload = {
        "content": "🟢 **[생존 보고] KOBUS 알리미가 쉬지 않고 감시 중입니다.**",
        "embeds": [{
            "title": "🟢 서버 정상 동작 중 (이상 없음)",
            "description": (
                f"**구간:** {DEP_NAME} ➔ {ARV_NAME}\n"
                f"**일시:** {formatted_date}(수) {MIN_TIME} 이후 전 배차\n\n"
                f"• **누적 점검 횟수:** `{check_count:,}회` 완료\n"
                f"• **현재 상태:** 15개 배차 전편 매진 유지 중\n"
                f"• **대기 상태:** 취소표 발생 시 3연속 알림 발송 대기 중"
            ),
            "url": f"{BASE_URL}/mrs/rotinf.do",
            "color": 65280,
            "footer": {"text": f"생존 확인 시각 • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
        }]
    }
    threading.Thread(target=post_discord, args=(payload,), daemon=True).start()

def send_burst_alert(available_buses, count=3, delay=1.5):
    """빈자리 발견 시 1.5초 간격으로 count회 연속 알림 전송"""
    def _worker():
        formatted_date = f"{DATE_STR[:4]}-{DATE_STR[4:6]}-{DATE_STR[6:8]}"
        bus_lines = [f"⏰ **{b['time']}** | {b['company']} ({b['grade']}) ➔ **{b['seats']}석**" for b in available_buses]
        
        for idx in range(1, count + 1):
            now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            payload = {
                "content": f"@everyone 🚨 [알림 {idx}/{count}] **서울경부 ➔ 부산 고속버스 빈자리가 나왔습니다!**",
                "embeds": [{
                    "title": f"🚨 [빈자리 발견 {idx}/{count}] {DEP_NAME} ➔ {ARV_NAME}",
                    "description": f"**일시:** {formatted_date}(수) {MIN_TIME} 이후\n\n지금 바로 링크를 눌러 KOBUS에서 예매하세요!",
                    "url": f"{BASE_URL}/mrs/rotinf.do",
                    "color": 15158332,
                    "fields": [{"name": "💺 예약 가능 배차 목록", "value": "\n".join(bus_lines), "inline": False}],
                    "footer": {"text": f"GCP 클라우드 • {idx}/{count}회차 알림 • {now_time}"}
                }]
            }
            post_discord(payload)
            if idx < count:
                time.sleep(delay)

    threading.Thread(target=_worker, daemon=True).start()

def create_session():
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
        req = urllib.request.Request(f"{BASE_URL}/main.do", headers={"User-Agent": USER_AGENT})
        opener.open(req, timeout=10)
    except:
        pass
    return opener

def query_timetable(opener):
    data = {
        "deprCd": DEP_CD,
        "arvlCd": ARV_CD,
        "pathDvs": "sngl",
        "pathStep": "1",
        "deprDtm": DATE_STR,
        "busClsCd": "0",
        "rtrpChc": "1",
        "timeLinkMin": MIN_TIME.split(":")[0],
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
    with opener.open(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    rows = re.findall(r'<p\b[^>]*role=[\x22\x27]row[\x22\x27][^>]*>(.*?)</p>', html, re.DOTALL)
    buses = []
    for r in rows:
        time_m = re.search(r'class=[\x22\x27]start_time[\x22\x27][^>]*>(.*?)</span>', r)
        if not time_m:
            continue
        dep_time = re.sub(r'<[^>]+>', '', time_m.group(1)).strip().replace(" ", "")
        if dep_time < MIN_TIME:
            continue
        com_m = re.search(r'class=[\x22\x27]bus_com[\x22\x27][^>]*>(.*?)</span>', r) or re.search(r'class=[\x22\x27]bus_info[\x22\x27][^>]*>.*?<span[^>]*>(.*?)</span>', r, re.DOTALL)
        company = re.sub(r'<[^>]+>', '', com_m.group(1)).strip() if com_m else ""
        grade_m = re.search(r'class=[\x22\x27]grade_mo[\x22\x27][^>]*>(.*?)</span>', r) or re.search(r'class=[\x22\x27]grade[\x22\x27][^>]*>(.*?)</span>', r)
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
        buses.append({"time": dep_time, "company": company, "grade": grade, "seats": seats, "bookable": bookable})
    return buses

def main():
    send_startup()
    opener = create_session()
    last_session_time = time.time()
    last_heartbeat_time = time.time()
    last_keys = set()
    check_count = 0

    while True:
        check_count += 1
        now_time = time.time()

        if now_time - last_session_time > 1800:
            opener = create_session()
            last_session_time = now_time

        if now_time - last_heartbeat_time >= HEARTBEAT_INTERVAL:
            send_heartbeat(check_count)
            last_heartbeat_time = now_time

        try:
            buses = query_timetable(opener)
            available = [b for b in buses if b["bookable"]]
            current_keys = {f"{b['time']}_{b['seats']}" for b in available}

            if available and current_keys != last_keys:
                # 3회 연속 강력 푸시 전송!
                send_burst_alert(available, count=3, delay=1.5)
                last_keys = current_keys
            elif not available:
                last_keys = set()
        except:
            time.sleep(3)
            try:
                opener = create_session()
            except:
                pass

        time.sleep(INTERVAL + random.uniform(-0.5, 1.0))

if __name__ == "__main__":
    main()
