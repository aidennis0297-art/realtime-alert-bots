import os
import sys
import time
import json
import urllib.request
import urllib.parse
import ssl
import threading
import xml.etree.ElementTree as ET
from datetime import datetime

# Windows 콘솔 한글 인코딩
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(CURRENT_DIR, "uos_notices_cache.json")


RECOMMENDED_TAGS = [
    "#장학금",
    "#해외파견",
    "#교환학생",
    "#계절학기",
    "#수강신청",
    "#등록금",
    "#인턴십",
    "#근로장학생",
    "#성적",
    "#졸업",
    "#휴복학",
    "#마이크로디그리"
]


class UosCampusMonitor:
    """시립대 도서관 열람실 잔여석 및 공지사항(학사/장학/해외파견) 실시간 모니터링 엔진"""
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(CURRENT_DIR, "uos_campus_config.json")
        self.config = self.load_config()
        self.notices_cache = self.load_cached_notices()
        self.is_running = False
        self.monitor_thread = None
        self.check_count = 0
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
        default_cfg = {
            "watch_keywords": ["장학금", "해외파견", "계절학기"],
            "target_library_rooms": [],     # 감시할 열람실 목록 (빈 리스트면 알림 비활성화)
            "check_interval_seconds": 30,
            "discord": {
                "webhook_url": "",
                "mention": "@everyone"
            }
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_cfg.update(data)
            except Exception:
                pass
        return default_cfg

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

    def load_cached_notices(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save_cached_notices(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.notices_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def fetch_library_seats(self):
        """중앙도서관, 건축도서관, 경영도서관 등 전체 열람실 실시간 잔여석 조회"""
        lib_map = {
            "C": "중앙도서관",
            "A": "건축도서관",
            "M": "경영도서관"
        }
        rooms = []
        for lib, lib_name in lib_map.items():
            url = "https://library.uos.ac.kr/seatStatus"
            data = f"lib={lib}&time={int(time.time() * 1000)}".encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://library.uos.ac.kr/",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest"
                }
            )
            try:
                with urllib.request.urlopen(req, context=self.ctx, timeout=6) as res:
                    raw = res.read().decode("utf-8")
                    d = json.loads(raw)
                    items = d.get("seatStatus", {}).get("root", {}).get("item", [])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        r_name = item.get("room_name", "")
                        tot = int(item.get("total_seat", 0))
                        use = int(item.get("use_seat", 0))
                        rem = int(item.get("remain_seat", 0))
                        rate = round((use / tot * 100), 1) if tot > 0 else 0
                        rooms.append({
                            "lib_code": lib,
                            "lib_name": lib_name,
                            "room_name": r_name,
                            "total_seat": tot,
                            "use_seat": use,
                            "remain_seat": rem,
                            "occupancy_rate": rate
                        })
            except Exception as e:
                self.log(f"[{lib_name}] 좌석 조회 오류: {e}")
        return rooms

    def fetch_notices(self, force_refresh=False):
        """학사/장학/일반/뉴스 RSS 피드 파싱 및 태깅"""
        feeds = [
            ("학사공지", "https://www.uos.ac.kr/rss/hBoard.do"),
            ("장학공지", "https://www.uos.ac.kr/rss/jBoard.do"),
            ("일반공지", "https://www.uos.ac.kr/rss/gBoard.do"),
            ("뉴스속UOS", "https://www.uos.ac.kr/rss/nBoard.do")
        ]

        seen_links = {n.get("link") for n in self.notices_cache if n.get("link")}
        new_items = []

        for category, feed_url in feeds:
            req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, context=self.ctx, timeout=8) as res:
                    raw = res.read().decode("utf-8", errors="ignore")
                    root = ET.fromstring(raw)
                    items = root.findall(".//item")
                    for it in items:
                        title_el = it.find("title")
                        link_el = it.find("link")
                        date_el = it.find("pubDate")

                        title = title_el.text.strip() if title_el is not None and title_el.text else ""
                        link = link_el.text.strip() if link_el is not None and link_el.text else ""
                        pub_date = date_el.text.strip() if date_el is not None and date_el.text else ""

                        if not title:
                            continue

                        # 자동 태깅 부여
                        matched_tags = []
                        for tag in RECOMMENDED_TAGS:
                            tag_word = tag[1:]  # '#' 제거
                            if tag_word in title or (category == "장학공지" and tag_word == "장학금"):
                                matched_tags.append(tag)

                        notice_obj = {
                            "category": category,
                            "title": title,
                            "link": link,
                            "date": pub_date,
                            "tags": matched_tags
                        }

                        if link not in seen_links:
                            seen_links.add(link)
                            new_items.append(notice_obj)
                            self.notices_cache.insert(0, notice_obj)
            except Exception as e:
                self.log(f"[{category}] 공지 피드 파싱 실패: {e}")

        # 최신 300개까지만 유지
        self.notices_cache = self.notices_cache[:300]
        self.save_cached_notices()
        return self.notices_cache, new_items

    def send_discord_notice_burst(self, notice):
        webhook_url = self.config.get("discord", {}).get("webhook_url", "").strip()
        if not webhook_url or not webhook_url.startswith("http"):
            return

        mention = self.config.get("discord", {}).get("mention", "@everyone")
        tags_str = " ".join([f"`{t}`" for t in notice.get("tags", [])])

        content_text = (
            f"📢📢📢 **[신규 대학 공지 감지!] {notice.get('category')}** {mention}\n\n"
            f"📌 **제목**: {notice.get('title')}\n"
            f"🏷️ **관련 태그**: {tags_str or '일반'}\n"
            f"📅 **게시일**: {notice.get('date')}\n\n"
            f"🔗 **상세 내용 바로가기**: {notice.get('link')}"
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
                self.log(f"공지 디스코드 발송 오류 ({burst_idx}/3): {e}")

    def _monitor_loop(self):
        self.log("🎓 시립대 스마트 캠퍼스(도서관 잔여석 + 공지 키워드) 감시 시작")
        keywords = [k.strip().lower() for k in self.config.get("watch_keywords", []) if k.strip()]
        self.log(f"• 등록된 알림 키워드: {', '.join(keywords) if keywords else '없음'}")

        # 최초 실행 시 현재 피드 동기화
        self.fetch_notices()

        while self.is_running:
            self.check_count += 1
            _, new_notices = self.fetch_notices()

            for n in new_notices:
                t_lower = n.get("title", "").lower()
                matched = any(kw in t_lower for kw in keywords)
                if matched:
                    self.log(f"🔔 키워드 일치 신규 공지 발견!: {n.get('title')}")
                    self.send_discord_notice_burst(n)

            interval = int(self.config.get("check_interval_seconds", 30))
            time.sleep(max(10, interval))

    def start_monitoring(self):
        if self.is_running:
            return False, "이미 모니터링이 실행 중입니다."
        self.is_running = True
        self.check_count = 0
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        return True, "스마트 캠퍼스 모니터링이 시작되었습니다."

    def stop_monitoring(self):
        if not self.is_running:
            return False, "모니터링이 실행 중이지 않습니다."
        self.is_running = False
        self.log("🛑 스마트 캠퍼스 모니터링을 중지했습니다.")
        return True, "스마트 캠퍼스 모니터링이 중지되었습니다."

    def get_status(self):
        return {
            "running": self.is_running,
            "check_count": self.check_count,
            "watch_keywords": self.config.get("watch_keywords", []),
            "recommended_tags": RECOMMENDED_TAGS,
            "cached_notices_count": len(self.notices_cache),
            "recent_logs": list(self.recent_logs)
        }
