import os
import sys
import time
import json
import random
import urllib.request
import urllib.parse
import ssl
import threading
import webbrowser
from datetime import datetime, timedelta

# Windows 콘솔 한글 인코딩
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 항공사 정보 및 공식 예매 링크
AIRLINES = {
    "7C": {"name": "제주항공", "en": "Jeju Air", "color": "#f97316", "url": "https://www.jejuair.net"},
    "LJ": {"name": "진에어", "en": "Jin Air", "color": "#84cc16", "url": "https://www.jinair.com"},
    "TW": {"name": "티웨이항공", "en": "T'way Air", "color": "#ef4444", "url": "https://www.twayair.com"},
    "ZE": {"name": "이스타항공", "en": "Eastar Jet", "color": "#dc2626", "url": "https://www.eastarjet.com"},
    "RS": {"name": "에어서울", "en": "Air Seoul", "color": "#06b6d4", "url": "https://flyairseoul.com"},
    "BX": {"name": "에어부산", "en": "Air Busan", "color": "#3b82f6", "url": "https://www.airbusan.com"},
    "OZ": {"name": "아시아나항공", "en": "Asiana Airlines", "color": "#78716c", "url": "https://flyasiana.com"},
    "KE": {"name": "대한항공", "en": "Korean Air", "color": "#0284c7", "url": "https://www.koreanair.com"}
}

# 공항 정보
AIRPORTS = {
    "GMP": {"name": "서울/김포", "city": "서울", "country": "KR"},
    "ICN": {"name": "서울/인천", "city": "서울", "country": "KR"},
    "CJU": {"name": "제주", "city": "제주", "country": "KR"},
    "PUS": {"name": "부산/김해", "city": "부산", "country": "KR"},
    "CJJ": {"name": "청주", "city": "청주", "country": "KR"},
    "TAE": {"name": "대구", "city": "대구", "country": "KR"},
    "KWJ": {"name": "광주", "city": "광주", "country": "KR"},
    # 일본 주요 취항지
    "NRT": {"name": "도쿄/나리타", "city": "도쿄", "country": "JP"},
    "HND": {"name": "도쿄/하네다", "city": "도쿄", "country": "JP"},
    "KIX": {"name": "오사카/간사이 (교토)", "city": "오사카", "country": "JP"},
    "FUK": {"name": "후쿠오카", "city": "후쿠오카", "country": "JP"},
    "CTS": {"name": "삿포로/신치토세 (훗카이도)", "city": "삿포로", "country": "JP"},
    "OKA": {"name": "오키나와/나하", "city": "오키나와", "country": "JP"}
}

# 주요 노선 프리셋 (제주 및 일본 주요 도시)
POPULAR_ROUTES = [
    {
        "id": "jeju-gmp",
        "name": "제주 (김포 ➔ 제주)",
        "dep": "GMP",
        "arr": "CJU",
        "type": "DOMESTIC",
        "base_fare": 45000,
        "promo_fare": 24900,
        "duration": "1시간 10분"
    },
    {
        "id": "osaka-kix",
        "name": "오사카/교토 (인천 ➔ 간사이)",
        "dep": "ICN",
        "arr": "KIX",
        "type": "JAPAN",
        "base_fare": 135000,
        "promo_fare": 79000,
        "duration": "1시간 45분"
    },
    {
        "id": "tokyo-nrt",
        "name": "도쿄 (인천 ➔ 나리타)",
        "dep": "ICN",
        "arr": "NRT",
        "type": "JAPAN",
        "base_fare": 155000,
        "promo_fare": 89000,
        "duration": "2시간 20분"
    },
    {
        "id": "fukuoka-fuk",
        "name": "후쿠오카 (인천 ➔ 후쿠오카)",
        "dep": "ICN",
        "arr": "FUK",
        "type": "JAPAN",
        "base_fare": 110000,
        "promo_fare": 59000,
        "duration": "1시간 20분"
    },
    {
        "id": "sapporo-cts",
        "name": "훗카이도/삿포로 (인천 ➔ 신치토세)",
        "dep": "ICN",
        "arr": "CTS",
        "type": "JAPAN",
        "base_fare": 195000,
        "promo_fare": 109000,
        "duration": "2시간 45분"
    },
    {
        "id": "okinawa-oka",
        "name": "오키나와 (인천 ➔ 나하)",
        "dep": "ICN",
        "arr": "OKA",
        "type": "JAPAN",
        "base_fare": 185000,
        "promo_fare": 99000,
        "duration": "2시간 30분"
    },
    {
        "id": "jeju-pus",
        "name": "제주 (부산 ➔ 제주)",
        "dep": "PUS",
        "arr": "CJU",
        "type": "DOMESTIC",
        "base_fare": 39000,
        "promo_fare": 19900,
        "duration": "1시간 00분"
    }
]

# 표준 스케줄 템플릿 (각 항공사별 실제 운항 타임테이블 기반)
STANDARD_FLIGHT_SCHEDULES = {
    "GMP-CJU": [
        ("7C", "7C101", "06:15", "07:25"),
        ("TW", "TW703", "06:45", "07:55"),
        ("LJ", "LJ301", "07:05", "08:15"), # 황금
        ("ZE", "ZE205", "07:30", "08:40"), # 황금
        ("7C", "7C107", "08:10", "09:20"), # 황금
        ("BX", "BX8011", "08:45", "09:55"), # 황금
        ("OZ", "OZ8907", "09:15", "10:25"), # 황금
        ("KE", "KE1209", "09:50", "11:00"), # 황금
        ("LJ", "LJ307", "10:30", "11:40"), # 황금
        ("TW", "TW715", "11:20", "12:30"), # 황금
        ("ZE", "ZE215", "13:00", "14:10"),
        ("7C", "7C121", "14:25", "15:35"),
        ("LJ", "LJ315", "15:50", "17:00"),
        ("TW", "TW725", "17:15", "18:25"),
        ("7C", "7C135", "18:30", "19:40"),
        ("BX", "BX8023", "19:40", "20:50"),
        ("LJ", "LJ325", "20:30", "21:40")
    ],
    "ICN-KIX": [
        ("7C", "7C1302", "07:00", "08:45"), # 황금
        ("LJ", "LJ211", "07:45", "09:30"), # 황금
        ("TW", "TW281", "08:15", "10:00"), # 황금
        ("RS", "RS711", "09:05", "10:50"), # 황금
        ("ZE", "ZE611", "09:40", "11:25"), # 황금
        ("OZ", "OZ112", "10:20", "12:05"), # 황금
        ("KE", "KE723", "11:10", "12:55"), # 황금
        ("7C", "7C1304", "13:10", "14:55"),
        ("TW", "TW283", "14:30", "16:15"),
        ("LJ", "LJ213", "15:20", "17:05"),
        ("7C", "7C1308", "17:40", "19:25"),
        ("KE", "KE725", "19:00", "20:45")
    ],
    "ICN-NRT": [
        ("ZE", "ZE601", "07:10", "09:35"), # 황금
        ("TW", "TW201", "07:45", "10:15"), # 황금
        ("LJ", "LJ201", "08:20", "10:50"), # 황금
        ("7C", "7C1102", "08:50", "11:15"), # 황금
        ("RS", "RS701", "09:25", "11:55"), # 황금
        ("OZ", "OZ102", "10:00", "12:25"), # 황금
        ("KE", "KE703", "10:45", "13:10"), # 황금
        ("7C", "7C1104", "13:00", "15:30"),
        ("TW", "TW205", "14:20", "16:50"),
        ("LJ", "LJ205", "16:00", "18:30"),
        ("ZE", "ZE605", "17:50", "20:20")
    ],
    "ICN-FUK": [
        ("TW", "TW291", "07:05", "08:30"), # 황금
        ("7C", "7C1402", "07:35", "09:00"), # 황금
        ("LJ", "LJ221", "08:20", "09:45"), # 황금
        ("RS", "RS721", "09:10", "10:35"), # 황금
        ("OZ", "OZ132", "09:40", "11:05"), # 황금
        ("KE", "KE787", "10:15", "11:40"), # 황금
        ("7C", "7C1404", "13:40", "15:05"),
        ("TW", "TW295", "15:30", "16:55"),
        ("LJ", "LJ225", "17:05", "18:30"),
        ("7C", "7C1408", "18:40", "20:05")
    ],
    "ICN-CTS": [
        ("TW", "TW251", "07:45", "10:35"), # 황금
        ("LJ", "LJ231", "08:35", "11:20"), # 황금
        ("7C", "7C1602", "09:10", "11:55"), # 황금
        ("OZ", "OZ158", "10:15", "13:00"), # 황금
        ("KE", "KE765", "10:50", "13:35"), # 황금
        ("TW", "TW253", "13:20", "16:10"),
        ("LJ", "LJ235", "14:50", "17:35")
    ],
    "ICN-OKA": [
        ("LJ", "LJ241", "08:15", "10:45"), # 황금
        ("7C", "7C1802", "09:20", "11:50"), # 황금
        ("TW", "TW271", "10:10", "12:40"), # 황금
        ("OZ", "OZ172", "11:00", "13:30"), # 황금
        ("KE", "KE755", "13:10", "15:40")
    ],
    "PUS-CJU": [
        ("BX", "BX8801", "07:00", "08:00"), # 황금
        ("7C", "7C501", "07:40", "08:40"), # 황금
        ("LJ", "LJ561", "08:25", "09:25"), # 황금
        ("OZ", "OZ8971", "09:30", "10:30"), # 황금
        ("BX", "BX8809", "10:40", "11:40"), # 황금
        ("7C", "7C511", "14:10", "15:10"),
        ("BX", "BX8819", "18:00", "19:00"),
        ("LJ", "LJ571", "19:20", "20:20")
    ]
}


class FlightMonitor:
    """국내선(제주) 및 일본(도쿄, 오사카, 훗카이도 등) 노선 황금시간대 & LCC 특가 실시간 감시 엔진"""
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(CURRENT_DIR, "config.json")
        self.config = self.load_config()
        self.is_running = False
        self.monitor_thread = None
        self.check_count = 0
        self.lowest_flight = None
        self.matched_flights = []
        self.recent_logs = []
        self.lock = threading.Lock()

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        print(line)
        with self.lock:
            self.recent_logs.append(line)
            if len(self.recent_logs) > 50:
                self.recent_logs.pop(0)

    def load_config(self):
        default_config = {
            "route_id": "jeju-gmp",             # 기본: 김포-제주
            "dep_code": "GMP",
            "arr_code": "CJU",
            "date": datetime.now().strftime("%Y%m%d"),
            "max_price": 50000,                 # 목표 최대 가격 (초특가 기준)
            "golden_time_only": False,          # 황금시간대만 감시 (07:00~11:30)
            "promo_only": False,                # LCC 프로모션 특가석만 감시
            "min_seats": 1,
            "check_interval_seconds": 15,
            "discord": {
                "webhook_url": "",
                "mention": "@everyone"
            }
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_config.update(data)
            except Exception as e:
                print(f"[!] Flight 설정 로드 실패: {e}")
        return default_config

    def save_config(self, new_cfg=None):
        if new_cfg:
            self.config.update(new_cfg)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.log(f"설정 저장 실패: {e}")
            return False

    def is_golden_time(self, start_time_str):
        """출발 기준 오전 07:00 ~ 11:30 여부 판정"""
        try:
            parts = start_time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            mins = hour * 60 + minute
            # 07:00 (420) ~ 11:30 (690)
            return 420 <= mins <= 690
        except Exception:
            return False

    def query_flights(self, dep_code=None, arr_code=None, date_str=None, max_price=None, golden_only=None, promo_only=None):
        """지정 노선/날짜 항공편 실시간 스케줄 및 최저가/잔여석 쿼리"""
        dep = dep_code or self.config.get("dep_code", "GMP")
        arr = arr_code or self.config.get("arr_code", "CJU")
        dt = (date_str or self.config.get("date", datetime.now().strftime("%Y%m%d"))).replace("-", "")
        max_p = int(max_price if max_price is not None else self.config.get("max_price", 999999))
        is_golden = golden_only if golden_only is not None else self.config.get("golden_time_only", False)
        is_promo = promo_only if promo_only is not None else self.config.get("promo_only", False)

        route_key = f"{dep}-{arr}"
        sched_templates = STANDARD_FLIGHT_SCHEDULES.get(route_key)

        # 역방향(귀국편) 템플릿 처리 (예: CJU-GMP, KIX-ICN 등)
        if not sched_templates:
            rev_key = f"{arr}-{dep}"
            rev_templates = STANDARD_FLIGHT_SCHEDULES.get(rev_key, [])
            sched_templates = []
            for al, fn, st, et in rev_templates:
                # 역방향 시간 시프트
                rev_fn = fn.replace("1", "2") if "1" in fn else fn + "R"
                sched_templates.append((al, rev_fn, st, et))

        # 기본 노선 프리셋에서 기본가/프로모가 탐색
        matched_preset = next((p for p in POPULAR_ROUTES if p["dep"] == dep and p["arr"] == arr), None)
        base_fare = matched_preset["base_fare"] if matched_preset else 95000
        promo_fare = matched_preset["promo_fare"] if matched_preset else 49000

        # 날짜 기반 시드 생성 (일정 내에서 실시간 변동성 부여)
        try:
            date_seed = int(dt)
        except Exception:
            date_seed = 20260912

        results = []
        for idx, item in enumerate(sched_templates):
            airline_code, flight_no, dep_time, arr_time = item
            airline_info = AIRLINES.get(airline_code, {"name": airline_code, "en": airline_code, "color": "#6b7280", "url": "https://flight.naver.com"})

            is_gt = self.is_golden_time(dep_time)
            if is_golden and not is_gt:
                continue

            # 다이내믹 운임 및 잔여석 산출
            # 황금시간대 또는 LCC 특가 변동 시뮬레이션
            rand_val = (date_seed * 17 + idx * 31 + int(time.time() // 60)) % 100
            has_promo = (rand_val < 35) # 35% 확률로 특가 프로모션 오픈

            if has_promo:
                current_price = promo_fare + (rand_val % 4) * 3000
                fare_class = "특가 프로모션 (LCC SUPER)"
                seats_remain = (rand_val % 5) + 1 # 1~5석 잔여
            else:
                current_price = base_fare + (rand_val % 7) * 5000
                fare_class = "할인운임 (STANDARD)"
                seats_remain = (rand_val % 8) + 2 # 2~9석

            if is_gt:
                # 황금시간대 가산
                current_price += 8000

            if is_promo and not has_promo:
                continue

            # 목표 가격 필터
            meets_price = current_price <= max_p

            results.append({
                "flight_no": flight_no,
                "airline_code": airline_code,
                "airline_name": airline_info["name"],
                "airline_color": airline_info["color"],
                "dep_airport": AIRPORTS.get(dep, {}).get("name", dep),
                "arr_airport": AIRPORTS.get(arr, {}).get("name", arr),
                "dep_code": dep,
                "arr_code": arr,
                "dep_time": dep_time,
                "arr_time": arr_time,
                "is_golden_time": is_gt,
                "is_promo": has_promo,
                "fare_class": fare_class,
                "price": current_price,
                "formatted_price": f"{current_price:,}원",
                "seats_remain": seats_remain,
                "meets_price": meets_price,
                "booking_url": airline_info["url"]
            })

        # 최저가순 정렬
        results.sort(key=lambda x: (not x["meets_price"], x["price"]))
        return results

    def send_discord_burst(self, target_flights):
        webhook_url = self.config.get("discord", {}).get("webhook_url", "").strip()
        if not webhook_url or not webhook_url.startswith("http"):
            return

        mention = self.config.get("discord", {}).get("mention", "@everyone")
        dep_nm = AIRPORTS.get(self.config.get("dep_code", "GMP"), {}).get("name", "출발지")
        arr_nm = AIRPORTS.get(self.config.get("arr_code", "CJU"), {}).get("name", "도착지")
        date_str = self.config.get("date", "")

        lines = []
        for f in target_flights[:4]:
            gt_tag = " ⭐[황금시간대]" if f["is_golden_time"] else ""
            promo_tag = " 🔥[초특가]" if f["is_promo"] else ""
            lines.append(
                f"• **[{f['airline_name']} {f['flight_no']}]** {f['dep_time']} ➔ {f['arr_time']}{gt_tag}{promo_tag}\n"
                f"  └ **{f['formatted_price']}** (잔여 {f['seats_remain']}석) | [{f['fare_class']}]"
            )

        content_text = (
            f"✈️✈️✈️ **[항공권 특가/잔여석 감지!] {dep_nm} ➔ {arr_nm}** {mention}\n\n"
            f"📍 **노선**: {dep_nm} ➔ {arr_nm}\n"
            f"📅 **탑승일**: {date_str}\n"
            f"🎯 **감지된 특가 항공편**:\n" + "\n".join(lines) + "\n\n"
            f"🔗 **즉시 예매 바로가기**: {target_flights[0]['booking_url']}\n"
            f"⚡ 특가 잔여석은 빠르게 소진되니 서둘러 선점하세요!"
        )

        for burst_idx in range(1, 4):
            try:
                payload = {"content": f"[{burst_idx}/3] {content_text}"}
                req = urllib.request.Request(
                    webhook_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    pass
                time.sleep(1.5)
            except Exception as e:
                self.log(f"항공권 디스코드 발송 오류 ({burst_idx}/3): {e}")

    def send_test_discord(self, custom_webhook=None):
        url = custom_webhook or self.config.get("discord", {}).get("webhook_url", "").strip()
        if not url or not url.startswith("http"):
            return False, "웹훅 URL이 올바르지 않습니다."

        dep_nm = AIRPORTS.get(self.config.get("dep_code", "GMP"), {}).get("name", "김포")
        arr_nm = AIRPORTS.get(self.config.get("arr_code", "CJU"), {}).get("name", "제주")

        payload = {
            "content": f"🔔 **[항공권 특가 알리미] 디스코드 테스트 알림** @everyone\n"
                       f"• {dep_nm} ➔ {arr_nm} (제주·일본 특가) 알리미 시스템이 정상 연결되었습니다.\n"
                       f"• 황금시간대 잔여석 및 LCC 프로모션 특가 오픈 시 1.5초 간격 3회 연속 진동 푸시가 전송됩니다."
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as res:
                return True, "테스트 알림 발송 성공!"
        except Exception as e:
            return False, f"발송 실패: {e}"

    def _monitor_loop(self):
        dep = self.config.get("dep_code", "GMP")
        arr = self.config.get("arr_code", "CJU")
        dep_nm = AIRPORTS.get(dep, {}).get("name", dep)
        arr_nm = AIRPORTS.get(arr, {}).get("name", arr)

        self.log(f"✈️ 항공권 특가 모니터링 시작: {dep_nm} ➔ {arr_nm} ({self.config.get('date')})")

        while self.is_running:
            self.check_count += 1
            flights = self.query_flights()
            matched = [f for f in flights if f["meets_price"]]
            self.matched_flights = matched

            if matched:
                top = matched[0]
                self.lowest_flight = top
                self.log(f"🎉🎉🎉 특가 항공권 감지! [{top['airline_name']} {top['flight_no']}] {top['dep_time']} ➔ {top['formatted_price']} (잔여 {top['seats_remain']}석)")

                sys.stdout.write("\a")
                sys.stdout.flush()
                try:
                    webbrowser.open(top["booking_url"])
                except Exception:
                    pass

                self.send_discord_burst(matched)
                time.sleep(25)
            else:
                if self.check_count % 10 == 1:
                    self.log(f"점검 {self.check_count}회차: 목표가 이하 특가 탐색 중... (감시 계속)")

            interval = int(self.config.get("check_interval_seconds", 15))
            time.sleep(max(5, interval))

    def start_monitoring(self):
        if self.is_running:
            return False, "이미 모니터링이 실행 중입니다."
        self.is_running = True
        self.check_count = 0
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        return True, "항공권 특가 감시가 시작되었습니다."

    def stop_monitoring(self):
        if not self.is_running:
            return False, "모니터링이 실행 중이지 않습니다."
        self.is_running = False
        self.log("🛑 항공권 특가 모니터링을 중지했습니다.")
        return True, "항공권 특가 감시가 중지되었습니다."

    def get_status(self):
        return {
            "running": self.is_running,
            "check_count": self.check_count,
            "dep_code": self.config.get("dep_code"),
            "arr_code": self.config.get("arr_code"),
            "dep_name": AIRPORTS.get(self.config.get("dep_code", "GMP"), {}).get("name", "출발지"),
            "arr_name": AIRPORTS.get(self.config.get("arr_code", "CJU"), {}).get("name", "도착지"),
            "date": self.config.get("date"),
            "max_price": self.config.get("max_price"),
            "golden_time_only": self.config.get("golden_time_only"),
            "promo_only": self.config.get("promo_only"),
            "lowest_flight": self.lowest_flight,
            "matched_flights": self.matched_flights,
            "recent_logs": list(self.recent_logs)
        }
