#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
서울시립대학교(UOS) 수강신청 실시간 빈자리 감지 및 디스코드 3연타 알리미 코어 엔진
- sugang.uos.ac.kr 연동
- CLI 단독 실행 및 Web GUI 백엔드 연동 겸용 모듈
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
    except Exception:
        winsound = None
else:
    winsound = None

BASE_URL = "https://sugang.uos.ac.kr"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def get_current_academic_period():
    """
    현재 날짜 기준으로 서울시립대 수강신청 학년도 및 학기 코드를 자동 산출
    - 1월 ~ 4월: 1학기 (CCMN031.10)
    - 5월 ~ 6월: 여름계절학기 (CCMN031.11)
    - 7월 ~ 10월: 2학기 (CCMN031.20)
    - 11월 ~ 12월: 겨울계절학기 (CCMN031.21)
    """
    now = datetime.now()
    year = str(now.year)
    month = now.month

    if 1 <= month <= 4:
        sem_code = "CCMN031.10"
        sem_name = "1학기"
    elif 5 <= month <= 6:
        sem_code = "CCMN031.11"
        sem_name = "여름계절학기"
    elif 7 <= month <= 10:
        sem_code = "CCMN031.20"
        sem_name = "2학기"
    else:
        sem_code = "CCMN031.21"
        sem_name = "겨울계절학기"

    return {
        "year": year,
        "semester": sem_code,
        "semester_name": sem_name,
        "display": f"{year}학년도 {sem_name}"
    }


class UosSugangMonitor:
    def __init__(self, config_path="config.json", log_callback=None):
        self.config_path = config_path
        self.config = self.load_config()
        self.log_callback = log_callback
        self.recent_logs = deque(maxlen=200)
        self.jar = http.cookiejar.CookieJar()
        self.opener = self.create_opener()
        self.last_available_keys = set()
        self.check_count = 0
        self.last_heartbeat_time = time.time()
        self.heartbeat_interval = 10800  # 3시간

        self.running = False
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.targets_status = []
        self.course_cache = {}  # (year, sem) -> list of courses
        self.is_logged_in = False

    def get_academic_period(self):
        return get_current_academic_period()

    def load_config(self):
        period = get_current_academic_period()
        if not os.path.exists(self.config_path):
            default_config = {
                "student_id": "",
                "password": "",
                "device": "PC",
                "year": period["year"],
                "semester": period["semester"],
                "target_courses": [],
                "check_interval_seconds": 6,
                "discord": {
                    "enabled": True,
                    "webhook_url": ""
                }
            }
            return default_config
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not cfg.get("year"):
                cfg["year"] = period["year"]
            if not cfg.get("semester"):
                cfg["semester"] = period["semester"]
            return cfg

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

    def test_login_credentials(self, student_id, password):
        """특정 학번/비밀번호로 로그인 성공 여부 검증 (일회용)"""
        test_jar = http.cookiejar.CookieJar()
        test_ctx = ssl._create_unverified_context()
        try:
            test_ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except:
            pass
        test_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(test_jar),
            urllib.request.HTTPSHandler(context=test_ctx)
        )

        login_data = {
            "USER_ID": student_id,
            "PWD": password,
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

        try:
            with test_opener.open(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                res_json = json.loads(raw)
                err_info = res_json.get("ERRMSGINFO")
                if err_info and err_info.get("ERRMSG"):
                    return False, err_info.get("ERRMSG")
                return True, "로그인 성공"
        except Exception as e:
            return False, str(e)

    def login(self):
        """sugang.uos.ac.kr 로그인 수행 및 세션 쿠키 획득"""
        student_id = self.config.get("student_id", "").strip()
        password = self.config.get("password", "").strip()
        if not student_id or not password:
            raise Exception("학번 또는 비밀번호가 설정되지 않았습니다.")

        login_data = {
            "USER_ID": student_id,
            "PWD": password,
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
                self.is_logged_in = False
                raise Exception(f"로그인 실패: {err_info.get('ERRMSG')}")
            self.is_logged_in = True
            return True

    def fetch_courses(self, year="2026", semester="CCMN031.20", dept_cd="20016", force_refresh=False):
        """개설과목 및 실시간 수강인원 조회 (캐싱 지원)"""
        cache_key = f"{year}_{semester}"
        if not force_refresh and cache_key in self.course_cache:
            return self.course_cache[cache_key]

        if not self.is_logged_in:
            try:
                self.login()
            except Exception as e:
                self.log(f"과목 조회 전 자동 로그인 실패: {e}")
                return []

        query_data = {
            "strAcyr": str(year),
            "strSemstrCd": str(semester),
            "strDeptCd": str(dept_cd)
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

        try:
            with self.opener.open(req, timeout=12) as resp:
                res_json = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_list = res_json.get("dsMain", [])
                parsed = []
                def _clean_str(val):
                    return str(val).strip() if val is not None else ""

                for c in raw_list:
                    cur = int(c.get("TLSN_COUNT") or 0)
                    limit = int(c.get("TLSN_LIMIT_COUNT") or 0)
                    parsed.append({
                        "code": _clean_str(c.get("SBJC_NO")),
                        "div": _clean_str(c.get("DVCL_NO") or "01").zfill(2),
                        "name": _clean_str(c.get("SBJC_NM")),
                        "type": _clean_str(c.get("CMPN_DIVNM")),
                        "grade": _clean_str(c.get("CMPN_GRADE")),
                        "dept": _clean_str(c.get("OGDP_SCSBJT_NM")),
                        "prof": _clean_str(c.get("RPRS_PROFSR_NM")),
                        "point": _clean_str(c.get("CMPN_PNT")),
                        "time_room": _clean_str(c.get("LEC_NM")),
                        "cur": cur,
                        "limit": limit,
                        "rem": max(0, limit - cur)
                    })
                self.course_cache[cache_key] = parsed
                return parsed
        except Exception as e:
            self.log(f"과목 목록 로드 실패: {e}")
            return []

    def post_discord(self, payload_dict, webhook_url=None):
        if not webhook_url:
            webhook_url = self.config.get("discord", {}).get("webhook_url", "").strip()
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
                        self.log("디스코드 알림 발송 성공")
            except Exception as e:
                self.log(f"디스코드 전송 오류: {e}")

        threading.Thread(target=_send, daemon=True).start()
        return True, "전송 요청 완료"

    def send_startup(self, targets):
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        year = self.config.get("year", "2026")
        target_lines = [f"• **[{t.get('code')}-{t.get('div')}]** {t.get('name', '과목')}" for t in targets]
        if not target_lines:
            target_lines = ["• (등록된 감시 대상 과목 없음 - 별표를 눌러 추가하세요)"]

        payload = {
            "content": "🚀 **[가동 시작] 서울시립대학교 수강신청 빈자리 알리미 작동!**",
            "embeds": [{
                "title": "🏫 서울시립대 수강신청 24시간 실시간 감시",
                "description": (
                    f"**{year}학년도** 대상 과목을 실시간으로 감시합니다.\n\n"
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
        if not status_lines:
            status_lines = ["• 감시 중인 과목 없음"]

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

            # 폰 푸시 미리보기에는 content 만 보이므로 과목명·잔여석을 본문에도 넣는다
            brief = " / ".join(f"{c['name']}({c['prof']}) {c['rem']}석" for c in opened_courses[:4])
            if len(opened_courses) > 4:
                brief += f" 외 {len(opened_courses) - 4}과목"

            for idx in range(1, count + 1):
                now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                payload = {
                    "content": (
                        f"@everyone 🚨 [수강신청 빈자리 {idx}/{count}] **시립대 과목 잔여석 발생!**\n"
                        f"🎓 {brief}"
                    ),
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
                if winsound and self.config.get("sound_alert", True):
                    try:
                        winsound.Beep(1500, 200)
                    except Exception:
                        pass
                if idx < count:
                    time.sleep(delay)

        threading.Thread(target=_worker, daemon=True).start()

    def send_test_discord(self, custom_webhook=None):
        """디스코드 웹훅 연결 테스트"""
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        payload = {
            "content": "@everyone 🔔 **[테스트] 서울시립대 수강신청 알리미 연동 확인!**",
            "embeds": [{
                "title": "✅ 디스코드 모바일 푸시 알림 정상 작동",
                "description": "수강신청 빈자리 알리미와 디스코드 채널이 성공적으로 연결되었습니다!\n\n관심 과목에 빈자리가 생기면 스마트폰 잠금화면으로 1.5초 간격 3연타 진동 푸시가 전송됩니다.",
                "url": BASE_URL,
                "color": 65280,
                "footer": {"text": f"테스트 전송 시각 • {now_time}"}
            }]
        }
        return self.post_discord(payload, custom_webhook)

    def _monitor_loop(self):
        self.log("🚀 백그라운드 수강신청 모니터링 스레드 가동 시작")
        targets = self.config.get("target_courses", [])
        self.send_startup(targets)

        while not self.stop_event.is_set():
            self.check_count += 1
            now_str = datetime.now().strftime("%H:%M:%S")
            now_time = time.time()
            interval = self.config.get("check_interval_seconds", 6)
            year = self.config.get("year", "2026")
            semester = self.config.get("semester", "CCMN031.20")
            targets = self.config.get("target_courses", [])

            if not targets:
                self.targets_status = []
                self.log("• [대기] 현재 별표(⭐) 등록된 감시 대상 과목이 없습니다.", also_print=False)
                if self.stop_event.wait(interval):
                    break
                continue

            try:
                courses = self.fetch_courses(year, semester, force_refresh=True)
                if not courses:
                    self.log(f"[{now_str}] 세션 갱신 필요 -> 재로그인 시도...")
                    self.login()
                    courses = self.fetch_courses(year, semester, force_refresh=True)

                # 타겟 과목 매칭
                targets_status = []
                opened_courses = []

                for t in targets:
                    target_code = str(t.get("code", "")).strip()
                    target_div = str(t.get("div", "")).strip().zfill(2)

                    matched = None
                    for c in courses:
                        if c.get("code") == target_code and c.get("div") == target_div:
                            matched = c
                            break

                    if matched:
                        cur = matched["cur"]
                        limit = matched["limit"]
                        rem = matched["rem"]
                        info = {
                            "code": target_code,
                            "div": target_div,
                            "name": matched.get("name", t.get("name", "")),
                            "prof": matched.get("prof", ""),
                            "cur": cur,
                            "limit": limit,
                            "rem": rem,
                            "dept": matched.get("dept", ""),
                            "time_room": matched.get("time_room", "")
                        }
                        targets_status.append(info)
                        if rem > 0:
                            opened_courses.append(info)

                self.targets_status = targets_status
                current_keys = {f"{c['code']}_{c['div']}_{c['rem']}" for c in opened_courses}

                if opened_courses:
                    if current_keys != self.last_available_keys:
                        self.log(f"🚨 빈자리 감지!! 디스코드 3연타 알림 발송!")
                        for c in opened_courses:
                            self.log(f"   ★ [{c['code']}-{c['div']}] {c['name']} (잔여 {c['rem']}석!)")
                        self.send_burst_alert(opened_courses)
                        self.last_available_keys = current_keys
                    else:
                        summary = ", ".join(f"{c['name']}({c['rem']}석)" for c in opened_courses)
                        self.log(f"[#{self.check_count}] ★ 빈자리 유지 중: {summary}", also_print=False)
                else:
                    self.last_available_keys = set()
                    status_summary = ", ".join(f"{s['name']}({s['cur']}/{s['limit']})" for s in targets_status)
                    self.log(f"[#{self.check_count}] 전 과목 마감 대기 중 [{status_summary}]", also_print=False)

                # 3시간마다 하트비트
                if now_time - self.last_heartbeat_time >= self.heartbeat_interval:
                    self.send_heartbeat(targets_status)
                    self.last_heartbeat_time = now_time

            except Exception as e:
                self.log(f"점검 중 오류 발생: {e} (3초 후 재시도)")
                time.sleep(3)
                try:
                    self.login()
                except Exception:
                    pass

            jitter = random.uniform(-0.5, 0.5)
            wait_sec = max(2.0, interval + jitter)
            if self.stop_event.wait(wait_sec):
                break

        self.running = False
        self.log("🛑 모니터링 스레드가 안전하게 종료되었습니다.")

    def start_monitoring(self):
        if self.running:
            return False, "이미 모니터링이 실행 중입니다."
        self.stop_event.clear()
        self.running = True
        self.worker_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.worker_thread.start()
        return True, "모니터링 시작됨"

    def stop_monitoring(self):
        if not self.running:
            return False, "모니터링이 실행 중이 아닙니다."
        self.stop_event.set()
        self.running = False
        return True, "모니터링 중지 신호 전송됨"

    def get_status(self):
        return {
            "running": self.running,
            "check_count": self.check_count,
            "targets_status": self.targets_status,
            "is_logged_in": self.is_logged_in,
            "target_count": len(self.config.get("target_courses", [])),
            "recent_logs": list(self.recent_logs)
        }

    def run(self):
        """CLI 모드 실행"""
        self.start_monitoring()
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_monitoring()
            print("\n모니터링 종료")

if __name__ == "__main__":
    monitor = UosSugangMonitor("config.json")
    monitor.run()
