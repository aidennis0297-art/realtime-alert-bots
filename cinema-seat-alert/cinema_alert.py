import os
import sys
import time
import json
import urllib.request
import urllib.parse
import ssl
import threading
import webbrowser
from datetime import datetime

# Windows 콘솔 한글 인코딩
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
THEATERS_FILE = os.path.join(CURRENT_DIR, "cinema_theaters.json")


def load_theaters_data():
    if os.path.exists(THEATERS_FILE):
        try:
            with open(THEATERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback 기본 데이터
    return {
        "서울": [
            {"code": "1372", "name": "강남"},
            {"code": "1351", "name": "코엑스"},
            {"code": "1212", "name": "홍대"},
            {"code": "1371", "name": "센트럴"}
        ],
        "경기/인천": [
            {"code": "0029", "name": "광명AK플라자"},
            {"code": "4121", "name": "고양스타필드"},
            {"code": "4062", "name": "송도"}
        ]
    }


class CinemaMonitor:
    """영화관(메가박스) 특별관 명당 및 잔여석 실시간 감시 엔진"""
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(CURRENT_DIR, "config.json")
        self.config = self.load_config()
        self.theaters_map = load_theaters_data()
        self.is_running = False
        self.monitor_thread = None
        self.check_count = 0
        self.vacant_shows = []
        self.recent_logs = []
        self.lock = threading.Lock()

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

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
            "theater_code": "1351",         # 코엑스
            "theater_name": "코엑스",
            "date": datetime.now().strftime("%Y%m%d"),
            "target_movie": "",              # 빈 문자열이면 전체 영화
            "special_hall_only": False,      # 돌비, 레이저, 리클라이너 등 특별관만 감시
            "min_seats": 1,                  # 알림 기준 잔여석 (1석, 2석 이상 등)
            "check_interval_seconds": 10,
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
                print(f"[!] Cinema 설정 로드 실패: {e}")
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

    def fetch_theaters(self):
        return self.theaters_map

    def query_showtimes(self, theater_code=None, date=None, movie_filter=None, special_only=None, min_seats=None):
        brch = theater_code or self.config.get("theater_code", "1351")
        target_date = (date or self.config.get("date", datetime.now().strftime("%Y%m%d"))).replace("-", "")
        mv_query = (movie_filter if movie_filter is not None else self.config.get("target_movie", "")).strip().lower()
        is_spc_only = special_only if special_only is not None else self.config.get("special_hall_only", False)
        threshold = int(min_seats if min_seats is not None else self.config.get("min_seats", 1))

        url = "https://m.megabox.co.kr/on/oh/ohb/SimpleBooking/selectBokdList.do"
        post_data = urllib.parse.urlencode({
            "menuId": "M-RE-TH-02",
            "sortMthd": "3",
            "brchNo1": brch,
            "playDe": target_date,
            "flag": "BRANCH",
            "sellChnlCd": "MOBILEWEB"
        }).encode("utf-8")

        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://m.megabox.co.kr/booking"
        }

        try:
            req = urllib.request.Request(url, data=post_data, headers=headers)
            with urllib.request.urlopen(req, context=self.ctx, timeout=8) as res:
                raw = res.read().decode("utf-8")
                d = json.loads(raw)

                sched_list = d.get("scheduleList", [])
                parsed_shows = []

                for s in sched_list:
                    mv_name = s.get("movieNm", "")
                    if mv_query and mv_query not in mv_name.lower():
                        continue

                    hall_name = s.get("theabExpoNm", "")
                    hall_lower = hall_name.lower()
                    is_special = any(k in hall_lower for k in ["돌비", "dolby", "laser", "레이저", "리클라이너", "recliner", "mx", "comfort", "부티크"])

                    if is_spc_only and not is_special:
                        continue

                    rest_seats = int(s.get("restSeatCnt", 0))
                    tot_seats = int(s.get("totSeatCnt", 0))
                    start_tm = s.get("playStartTime", "")
                    end_tm = s.get("playEndTime", "")
                    sch_no = s.get("playSchdlNo", "")

                    has_seats = rest_seats >= threshold

                    parsed_shows.append({
                        "schedule_no": sch_no,
                        "movie_name": mv_name,
                        "hall_name": hall_name,
                        "is_special": is_special,
                        "start_time": start_tm,
                        "end_time": end_tm,
                        "rest_seats": rest_seats,
                        "total_seats": tot_seats,
                        "has_seats": has_seats,
                        "booking_url": f"https://m.megabox.co.kr/booking"
                    })

                return parsed_shows
        except Exception as e:
            self.log(f"영화 상영시간표 조회 중 오류: {e}")
            return []

    def send_discord_burst(self, vacant_shows):
        webhook_url = self.config.get("discord", {}).get("webhook_url", "").strip()
        if not webhook_url or not webhook_url.startswith("http"):
            return

        mention = self.config.get("discord", {}).get("mention", "@everyone")
        th_name = self.config.get("theater_name", "영화관")
        date_str = self.config.get("date", "")

        show_lines = []
        for s in vacant_shows[:5]:
            show_lines.append(f"• **[{s['movie_name']}]** {s['start_time']} ({s['hall_name']}) ➔ **잔여 {s['rest_seats']}/{s['total_seats']}석**")

        content_text = (
            f"🎬🎬🎬 **[취소표/예매 오픈!] 영화관 잔여석 감지!** {mention}\n\n"
            f"📍 **극장**: 메가박스 {th_name}\n"
            f"📅 **일정**: {date_str}\n"
            f"🎟️ **예매 가능 상영 회차**:\n" + "\n".join(show_lines) + "\n\n"
            f"🔗 **즉시 예매**: https://m.megabox.co.kr/booking\n"
            f"⚡ 매진되기 전에 서둘러 좌석을 선점하세요!"
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
                self.log(f"디스코드 발송 오류 ({burst_idx}/3): {e}")

    def send_test_discord(self, custom_webhook=None):
        url = custom_webhook or self.config.get("discord", {}).get("webhook_url", "").strip()
        if not url or not url.startswith("http"):
            return False, "웹훅 URL이 올바르지 않습니다."

        payload = {
            "content": f"🔔 **[영화관 알리미] 디스코드 테스트 알림** @everyone\n"
                       f"• 영화관 알리미 시스템이 정상 연결되었습니다.\n"
                       f"• 특별관/명당 취소표 및 티켓 오픈 시 1.5초 간격 3회 연속 진동 푸시가 전송됩니다."
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
        th_name = self.config.get("theater_name", "영화관")
        self.log(f"🎬 영화관 모니터링 시작: 메가박스 {th_name} ({self.config.get('date')})")

        while self.is_running:
            self.check_count += 1
            shows = self.query_showtimes()
            vacant = [s for s in shows if s["has_seats"]]
            self.vacant_shows = vacant

            if vacant:
                self.log(f"🎉🎉🎉 잔여석 감지! ({len(vacant)}개 회차 예매 가능)")
                for v in vacant[:3]:
                    self.log(f"  ▶ [{v['movie_name']}] {v['start_time']} ({v['hall_name']}): 잔여 {v['rest_seats']}석")

                sys.stdout.write("\a")
                sys.stdout.flush()
                try:
                    webbrowser.open("https://m.megabox.co.kr/booking")
                except Exception:
                    pass

                self.send_discord_burst(vacant)
                time.sleep(20)
            else:
                if self.check_count % 10 == 1:
                    self.log(f"점검 {self.check_count}회차: 매진 상태 유지 중... (감시 계속)")

            interval = int(self.config.get("check_interval_seconds", 10))
            time.sleep(max(5, interval))

    def start_monitoring(self):
        if self.is_running:
            return False, "이미 모니터링이 실행 중입니다."
        self.is_running = True
        self.check_count = 0
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        return True, "영화관 잔여석 감시가 시작되었습니다."

    def stop_monitoring(self):
        if not self.is_running:
            return False, "모니터링이 실행 중이지 않습니다."
        self.is_running = False
        self.log("🛑 영화관 모니터링을 중지했습니다.")
        return True, "영화관 잔여석 감시가 중지되었습니다."

    def get_status(self):
        return {
            "running": self.is_running,
            "check_count": self.check_count,
            "theater_code": self.config.get("theater_code"),
            "theater_name": self.config.get("theater_name"),
            "date": self.config.get("date"),
            "target_movie": self.config.get("target_movie"),
            "special_hall_only": self.config.get("special_hall_only"),
            "min_seats": self.config.get("min_seats", 1),
            "vacant_shows": self.vacant_shows,
            "recent_logs": list(self.recent_logs)
        }
