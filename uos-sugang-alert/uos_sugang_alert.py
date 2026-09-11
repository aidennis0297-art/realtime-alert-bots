#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
서울시립대학교(UOS) 수강신청 실시간 빈자리 감지 및 디스코드 3연타 알리미
- 대상: sugang.uos.ac.kr 2026학년도 2학기 개설 과목
- 기능:
  1. 지정한 과목의 잔여석(정원 - 신청인원) 실시간 감지
  2. 빈자리 발생 시 1.5초 간격 3회 연속 디스코드 푸시 (@everyone)
  3. 세션 만료 시 자동 재로그인 및 자가 복구
  4. 3시간마다 조용한 생존 보고(하트비트)
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
from datetime import datetime

# Windows 콘솔 한글 UTF-8 출력 보정
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    import winsound

BASE_URL = "https://sugang.uos.ac.kr"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

class UosSugangMonitor:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.jar = http.cookiejar.CookieJar()
        self.opener = self.create_opener()
        self.last_available_keys = set()
        self.check_count = 0
        self.last_heartbeat_time = time.time()
        self.heartbeat_interval = 10800  # 3시간

    def load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def create_opener(self):
        ctx = ssl._create_unverified_context()
        try:
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            pass
        return urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.HTTPSHandler(context=ctx)
        )

    def login(self):
        """sugang.uos.ac.kr 로그인 수행 및 세션 쿠키 획득"""
        login_data = {
            "USER_ID": self.config["student_id"],
            "PWD": self.config["password"],
            "DEVICE": self.config.get("device", "PC"),
            "LANG": "KOR",
            "UNIV": "UNIV",
            "GDHL": ""
        }

        req = urllib.request.Request(
            f"{BASE_URL}/Login/login.do",
            data=urllib.parse.urlencode(login_data).encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "req-protocol": "urlencoded",
                "res-protocol": "json",
                "User-Agent": USER_AGENT,
                "Referer": f"{BASE_URL}/"
            }
        )

        with self.opener.open(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            res_json = json.loads(raw)
            err_info = res_json.get("ERRMSGINFO")
            if err_info and err_info.get("ERRMSG"):
                raise Exception(f"로그인 실패: {err_info.get('ERRMSG')}")
        return True

    def fetch_all_courses(self):
        """2026-2학기 전체 개설과목 및 실시간 수강인원 조회"""
        query_data = {
            "strAcyr": "2026",
            "strSemstrCd": "CCMN031.20",
            "strDeptCd": "20016"
        }

        req = urllib.request.Request(
            f"{BASE_URL}/SucrMjTimeInq/list.do",
            data=urllib.parse.urlencode(query_data).encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "req-protocol": "urlencoded",
                "res-protocol": "json",
                "User-Agent": USER_AGENT,
                "Referer": f"{BASE_URL}/"
            }
        )

        with self.opener.open(req, timeout=10) as resp:
            res_json = json.loads(resp.read().decode("utf-8", errors="replace"))
            return res_json.get("dsMain", [])

    def post_discord(self, payload_dict):
        webhook_url = self.config.get("discord", {}).get("webhook_url", "").strip()
        if not webhook_url or not self.config.get("discord", {}).get("enabled"):
            return

        def _send():
            try:
                payload = json.dumps(payload_dict).encode("utf-8")
                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}
                )
                with urllib.request.urlopen(req, timeout=10):
                    pass
            except Exception as e:
                print(f"[!] 디스코드 전송 실패: {e}")

        threading.Thread(target=_send, daemon=True).start()

    def send_startup(self, targets):
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        target_lines = [f"• **[{t.get('code')}-{t.get('div')}]** {t.get('name', '과목')}" for t in targets]
        payload = {
            "content": "🚀 **[가동 시작] 서울시립대학교 수강신청 빈자리 알리미 작동!**",
            "embeds": [{
                "title": "🏫 서울시립대 수강신청 24시간 실시간 감시",
                "description": (
                    "**2026학년도 2학기** 대상 과목을 실시간으로 감시합니다.\n\n"
                    "🎯 **모니터링 대상 과목:**\n" + "\n".join(target_lines) + "\n\n"
                    "• **알림 조건:** 누군가 수강 취소하여 잔여석 ≥ 1석 발생 시\n"
                    "• **알림 방식:** 🚨 1.5초 간격 3회 연속 폰 진동 푸시 (@everyone)\n"
                    "• **생존 보고:** 3시간마다 정상 작동 보고"
                ),
                "url": BASE_URL,
                "color": 3447003,
                "footer": {"text": f"시립대 수강알리미 시작 • {now_time}"}
            }]
        }
        self.post_discord(payload)

    def send_heartbeat(self, targets_status):
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status_lines = []
        for s in targets_status:
            status_lines.append(f"• **[{s['code']}-{s['div']}] {s['name']}**: {s['cur']}/{s['limit']}명 ({s['rem']}석 남음)")

        payload = {
            "content": "🟢 **[생존 보고] 서울시립대 수강신청 알리미 정상 감시 중**",
            "embeds": [{
                "title": "🟢 서버 정상 동작 중 (이상 없음)",
                "description": (
                    f"• **누적 점검 횟수:** `{self.check_count:,}회` 완료\n\n"
                    "📊 **현재 대상 과목 정원 상태:**\n" + "\n".join(status_lines) + "\n\n"
                    "취소표 발생 시 즉시 3연타 진동 푸시가 발송됩니다."
                ),
                "url": BASE_URL,
                "color": 65280,
                "footer": {"text": f"생존 확인 시각 • {now_time}"}
            }]
        }
        self.post_discord(payload)

    def send_burst_alert(self, opened_courses, count=3, delay=1.5):
        """빈자리 감지 시 1.5초 간격 3회 연속 전송"""
        def _worker():
            lines = []
            for c in opened_courses:
                lines.append(f"⏰ **[{c['code']}-{c['div']}] {c['name']}** ({c['prof']} 교수)\n➔ 신청/정원: **{c['cur']}/{c['limit']}명** (🎉 **{c['rem']}석 발생!**)")

            for idx in range(1, count + 1):
                now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                payload = {
                    "content": f"@everyone 🚨 [수강신청 빈자리 {idx}/{count}] **시립대 과목 잔여석이 나왔습니다! 지금 접속하세요!**",
                    "embeds": [{
                        "title": f"🚨 [빈자리 발생 {idx}/{count}] 서울시립대학교 수강신청",
                        "description": (
                            "누군가 수강을 취소하여 빈자리가 생겼습니다!\n\n"
                            + "\n\n".join(lines)
                            + f"\n\n👉 **[수강신청 바로가기 (클릭)]({BASE_URL})**"
                        ),
                        "url": BASE_URL,
                        "color": 15158332,
                        "footer": {"text": f"시립대 수강알리미 • {idx}/{count}회차 알림 • {now_time}"}
                    }]
                }
                self.post_discord(payload)
                if sys.platform == "win32":
                    try:
                        winsound.Beep(1500, 200)
                    except:
                        pass
                if idx < count:
                    time.sleep(delay)

        threading.Thread(target=_worker, daemon=True).start()

    def run(self):
        targets = self.config.get("target_courses", [])
        interval = self.config.get("check_interval_seconds", 6)

        print("=" * 65)
        print("🏫 서울시립대학교 수강신청 빈자리 3연타 알리미")
        print("=" * 65)
        print(f"• 학번: {self.config['student_id']}")
        print(f"• 모니터링 대상 과목 ({len(targets)}개):")
        for t in targets:
            print(f"   - [{t.get('code')}-{t.get('div')}] {t.get('name', '')}")
        print(f"• 점검 주기: 약 {interval}초")
        print("=" * 65)

        print("\n[+] 수강신청 시스템 로그인 중...")
        self.login()
        print("🎉 로그인 성공! 세션 활성화 완료.")

        self.send_startup(targets)
        print("\n[+] 실시간 빈자리 모니터링을 시작합니다. (종료: Ctrl + C)\n")

        while True:
            self.check_count += 1
            now_str = datetime.now().strftime("%H:%M:%S")
            now_time = time.time()

            try:
                courses = self.fetch_all_courses()
                if not courses:
                    # 세션 만료 가능성 -> 재로그인
                    print(f"\n[{now_str}] 세션 만료 감지 -> 자동 재로그인 시도...")
                    self.login()
                    courses = self.fetch_all_courses()

                # 타겟 과목 매칭
                targets_status = []
                opened_courses = []

                for t in targets:
                    target_code = str(t.get("code", "")).strip()
                    target_div = str(t.get("div", "")).strip().zfill(2)

                    matched = None
                    for c in courses:
                        if c.get("SBJC_NO") == target_code and str(c.get("DVCL_NO", "")).zfill(2) == target_div:
                            matched = c
                            break

                    if matched:
                        cur = int(matched.get("TLSN_COUNT", 0))
                        limit = int(matched.get("TLSN_LIMIT_COUNT", 0))
                        rem = limit - cur
                        info = {
                            "code": target_code,
                            "div": target_div,
                            "name": matched.get("SBJC_NM", t.get("name", "")),
                            "prof": matched.get("RPRS_PROFSR_NM", ""),
                            "cur": cur,
                            "limit": limit,
                            "rem": rem
                        }
                        targets_status.append(info)
                        if rem > 0:
                            opened_courses.append(info)

                current_keys = {f"{c['code']}_{c['div']}_{c['rem']}" for c in opened_courses}

                if opened_courses:
                    if current_keys != self.last_available_keys:
                        print(f"\n🚨 [{now_str}] 빈자리 감지!! 디스코드 3연타 알림 전송!")
                        for c in opened_courses:
                            print(f"   ★ [{c['code']}-{c['div']}] {c['name']} (잔여 {c['rem']}석!)")
                        self.send_burst_alert(opened_courses)
                        self.last_available_keys = current_keys
                    else:
                        print(f"[{now_str} | #{self.check_count}] ★ 빈자리 계속 유지 중: {', '.join(c['name'] + '(' + str(c['rem']) + '석)' for c in opened_courses)}")
                else:
                    self.last_available_keys = set()
                    status_summary = ", ".join(f"{s['name']}({s['cur']}/{s['limit']})" for s in targets_status)
                    print(f"[{now_str} | #{self.check_count}] 전 과목 마감 대기 중... [{status_summary}]", end="\r", flush=True)

                # 3시간마다 하트비트
                if now_time - self.last_heartbeat_time >= self.heartbeat_interval:
                    self.send_heartbeat(targets_status)
                    self.last_heartbeat_time = now_time

            except KeyboardInterrupt:
                print("\n\n사용자에 의해 모니터링이 중단되었습니다.")
                break
            except Exception as e:
                print(f"\n[{now_str} | #{self.check_count}] 오류 발생: {e} (3초 후 재로그인 및 재시도)")
                time.sleep(3)
                try:
                    self.login()
                except Exception:
                    pass

            time.sleep(interval + random.uniform(-0.5, 1.0))

if __name__ == "__main__":
    monitor = UosSugangMonitor("config.json")
    monitor.run()
