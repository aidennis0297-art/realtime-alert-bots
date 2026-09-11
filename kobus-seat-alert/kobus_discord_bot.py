import os
import sys
import time
import json
import re
import urllib.request
import urllib.parse
import ssl
import threading
from datetime import datetime

# Windows 콘솔 한글 인코딩
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from bus_alert import KobusMonitor

TERMINAL_ALIASES = {
    "서울": ("010", "서울경부"),
    "강남": ("021", "센트럴시티(서울)"),
    "센트럴": ("021", "센트럴시티(서울)"),
    "센트럴시티": ("021", "센트럴시티(서울)"),
    "동서울": ("032", "동서울"),
    "부산": ("700", "부산"),
    "사상": ("703", "부산사상"),
    "대전": ("300", "대전복합"),
    "유성": ("305", "대전유성"),
    "광주": ("500", "광주(유·스퀘어)"),
    "대구": ("801", "동대구"),
    "동대구": ("801", "동대구"),
    "서대구": ("805", "서대구"),
    "전주": ("602", "전주고속터미널"),
    "강릉": ("200", "강릉"),
    "울산": ("715", "울산"),
    "청주": ("310", "청주고속터미널"),
    "천안": ("320", "천안고속터미널"),
    "포항": ("830", "포항"),
    "창원": ("730", "창원"),
    "마산": ("735", "마산"),
    "진주": ("740", "진주고속터미널"),
    "목포": ("520", "목포"),
    "순천": ("515", "순천"),
    "여수": ("510", "여수"),
    "서산": ("393", "서산")
}


class KobusDiscordBot:
    """Zero-dependency 디스코드 양방향 챗봇 엔진"""
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(CURRENT_DIR, "config.json")
        if not os.path.exists(self.config_path):
            self.config_path = os.path.join(CURRENT_DIR, "config.example.json")
        self.config = self.load_config()
        self.kobus = KobusMonitor(self.config_path)
        self.is_running = False
        self.last_message_id = None
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def load_config(self):
        default_cfg = {
            "discord_bot": {
                "enabled": True,
                "bot_token": "",
                "channel_id": "",
                "prefix": "!"
            }
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "discord_bot" in data:
                        default_cfg["discord_bot"].update(data["discord_bot"])
                    default_cfg.update(data)
            except Exception:
                pass
        return default_cfg

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def get_token(self):
        return self.config.get("discord_bot", {}).get("bot_token", "").strip()

    def get_channel_id(self):
        return self.config.get("discord_bot", {}).get("channel_id", "").strip()

    def resolve_terminal(self, name):
        name_clean = name.strip()
        if name_clean in TERMINAL_ALIASES:
            return TERMINAL_ALIASES[name_clean]

        deps = self.kobus.fetch_terminals().get("departures", [])
        # 1. Exact match
        for t in deps:
            if t["name"] == name_clean:
                return t["code"], t["name"]
        # 2. Starts with
        for t in deps:
            if t["name"].startswith(name_clean):
                return t["code"], t["name"]
        # 3. Contains
        for t in deps:
            if name_clean in t["name"]:
                return t["code"], t["name"]
        return None, None

    def api_request(self, method, endpoint, data=None):
        token = self.get_token()
        if not token:
            return None

        url = f"https://discord.com/api/v10{endpoint}"
        headers = {
            "Authorization": f"Bot {token}",
            "User-Agent": "DiscordBot (https://github.com/aidennis0297-art/realtime-alert-bots, v2.0)",
            "Content-Type": "application/json"
        }

        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=8) as res:
                raw = res.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except Exception as e:
            # Silently log errors
            return None

    def send_message(self, channel_id, content=None, embeds=None):
        payload = {}
        if content:
            payload["content"] = content
        if embeds:
            payload["embeds"] = embeds
        return self.api_request("POST", f"/channels/{channel_id}/messages", payload)

    def add_reaction(self, channel_id, message_id, emoji_encoded):
        return self.api_request("PUT", f"/channels/{channel_id}/messages/{message_id}/reactions/{emoji_encoded}/@me")

    def get_new_messages(self, channel_id):
        endpoint = f"/channels/{channel_id}/messages?limit=5"
        if self.last_message_id:
            endpoint += f"&after={self.last_message_id}"

        res = self.api_request("GET", endpoint)
        if isinstance(res, list):
            # Sort chronologically
            res.sort(key=lambda m: int(m.get("id", 0)))
            return res
        return []

    def handle_command(self, msg):
        content = msg.get("content", "").strip()
        channel_id = msg.get("channel_id")
        msg_id = msg.get("id")
        author = msg.get("author", {})

        # Ignore messages from bots (including self)
        if author.get("bot"):
            return

        prefix = self.config.get("discord_bot", {}).get("prefix", "!")
        if not content.startswith(prefix):
            return

        cmd_line = content[len(prefix):].strip()
        parts = cmd_line.split()
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        # Acknowledge with reaction
        self.add_reaction(channel_id, msg_id, "%F0%9F%9A%8C")  # 🚌

        # Command Dispatch
        if cmd in ["도움말", "help", "명령어"]:
            self.cmd_help(channel_id)
        elif cmd in ["버스", "bus"]:
            if not args or args[0] in ["조회", "search"]:
                self.cmd_bus_search(channel_id, args[1:] if args else [])
            elif args[0] in ["시작", "start", "감시"]:
                self.cmd_bus_start(channel_id, args[1:])
            elif args[0] in ["중지", "stop", "종료"]:
                self.cmd_bus_stop(channel_id)
            elif args[0] in ["상태", "status"]:
                self.cmd_bus_status(channel_id)
            else:
                # Direct route query: e.g. !버스 서울 부산 20260925
                self.cmd_bus_search(channel_id, args)
        elif cmd in ["시작", "start"]:
            self.cmd_bus_start(channel_id, args)
        elif cmd in ["중지", "stop"]:
            self.cmd_bus_stop(channel_id)
        elif cmd in ["상태", "status"]:
            self.cmd_bus_status(channel_id)
        elif cmd in ["터미널", "terminal"]:
            self.cmd_terminal_search(channel_id, args)

    def cmd_help(self, channel_id):
        embed = {
            "title": "🚌 KOBUS 고속버스 양방향 챗봇 명령어",
            "description": "스마트폰 디스코드 앱에서 명령어를 입력하여 실시간 조회 및 모니터링을 제어하세요.",
            "color": 3901686,
            "fields": [
                {
                    "name": "🔍 실시간 배차 조회",
                    "value": "• `!버스`: 현재 설정된 노선 잔여석 조회\n• `!버스 [출발지] [도착지] [날짜]`: 특정 노선 즉시 조회\n  *(예: `!버스 서울 부산 20260925`)*",
                    "inline": False
                },
                {
                    "name": "▶️ 빈자리 24시간 감시 시작",
                    "value": "• `!버스 시작`: 현재 노선 감시 시작\n• `!버스 시작 [출발지] [도착지]`: 노선 변경 후 감시 시작\n  *(예: `!버스 시작 서울 대전`)*",
                    "inline": False
                },
                {
                    "name": "🛑 감시 중지 및 상태 확인",
                    "value": "• `!버스 중지`: 실시간 감시 데몬 중지\n• `!버스 상태`: 현재 가동 현황 및 누적 점검 횟수 확인",
                    "inline": False
                },
                {
                    "name": "📍 터미널 검색",
                    "value": "• `!터미널 [키워드]`: 전국 224개 터미널 이름 검색\n  *(예: `!터미널 서울`, `!터미널 광주`)*",
                    "inline": False
                }
            ],
            "footer": {"text": "Realtime Alert Hub • 2-Way Interactive Bot"}
        }
        self.send_message(channel_id, embeds=[embed])

    def cmd_bus_search(self, channel_id, args):
        dep_code = self.kobus.config.get("departure_terminal", "010")
        arr_code = self.kobus.config.get("arrival_terminal", "700")
        dep_name = self.kobus.config.get("departure_name", "서울경부")
        arr_name = self.kobus.config.get("arrival_name", "부산")
        date_str = self.kobus.config.get("date", datetime.now().strftime("%Y%m%d"))

        if len(args) >= 2:
            d_cd, d_nm = self.resolve_terminal(args[0])
            a_cd, a_nm = self.resolve_terminal(args[1])
            if not d_cd:
                self.send_message(channel_id, content=f"⚠️ 출발지 터미널 `{args[0]}`을(를) 찾을 수 없습니다. `!터미널` 명령어로 이름을 확인하세요.")
                return
            if not a_cd:
                self.send_message(channel_id, content=f"⚠️ 도착지 터미널 `{args[1]}`을(를) 찾을 수 없습니다. `!터미널` 명령어로 이름을 확인하세요.")
                return
            dep_code, dep_name = d_cd, d_nm
            arr_code, arr_name = a_cd, a_nm

        if len(args) >= 3:
            date_str = args[2].replace("-", "").replace(".", "")

        self.send_message(channel_id, content=f"🔄 **[{dep_name} ➔ {arr_name}]** ({date_str}) 배차 및 잔여석을 조회 중입니다...")

        buses = self.kobus.query_timetable(dep_code, arr_code, date_str)
        if not buses:
            self.send_message(channel_id, content=f"❌ 해당 날짜/구간에 운행하는 고속버스 배차가 없습니다.")
            return

        vacant_buses = [b for b in buses if b["is_vacant"]]
        lines = []
        for b in buses[:12]:
            badge = "✅ 예약가능" if b["is_vacant"] else "❌ 매진"
            lines.append(f"• **[{b['depr_time']}]** {b['company']} ({b['bus_grade']}) | 잔여: `{b['rem_seats']}/{b['tot_seats']}석` | {badge}")

        embed = {
            "title": f"🚌 KOBUS 실시간 배차: {dep_name} ➔ {arr_name}",
            "description": f"📅 **일정:** {date_str} (전체 {len(buses)}개 배차 중 {len(vacant_buses)}개 잔여석 있음)\n\n" + "\n".join(lines),
            "color": 65280 if vacant_buses else 16724530,
            "fields": [
                {
                    "name": "🔗 예매 바로가기",
                    "value": "[👉 KOBUS 공식 예매 페이지 열기](https://www.kobus.co.kr/mrs/rotinf.do)",
                    "inline": False
                }
            ],
            "footer": {"text": f"조회 시각: {datetime.now().strftime('%H:%M:%S')} • Alert Bot"}
        }
        self.send_message(channel_id, embeds=[embed])

    def cmd_bus_start(self, channel_id, args):
        if len(args) >= 2:
            d_cd, d_nm = self.resolve_terminal(args[0])
            a_cd, a_nm = self.resolve_terminal(args[1])
            if d_cd and a_cd:
                self.kobus.config["departure_terminal"] = d_cd
                self.kobus.config["departure_name"] = d_nm
                self.kobus.config["arrival_terminal"] = a_cd
                self.kobus.config["arrival_name"] = a_nm
                if len(args) >= 3:
                    self.kobus.config["date"] = args[2].replace("-", "")
                self.kobus.save_config()

        ok, msg = self.kobus.start_monitoring()
        dep = self.kobus.config.get("departure_name", "출발지")
        arr = self.kobus.config.get("arrival_name", "도착지")
        dt = self.kobus.config.get("date", "")

        if ok:
            embed = {
                "title": "▶️ KOBUS 실시간 취소표 감시 시작",
                "description": f"**구간:** {dep} ➔ {arr}\n**날짜:** {dt}\n**주기:** 6초마다 실시간 점검\n\n취소표가 발생하는 즉시 이곳으로 3연속 진동 알림(@everyone)을 발송합니다!",
                "color": 65280
            }
            self.send_message(channel_id, embeds=[embed])
        else:
            self.send_message(channel_id, content=f"⚠️ {msg}")

    def cmd_bus_stop(self, channel_id):
        ok, msg = self.kobus.stop_monitoring()
        embed = {
            "title": "🛑 KOBUS 감시 중지 완료",
            "description": "실시간 백그라운드 모니터링 데몬이 안전하게 종료되었습니다.",
            "color": 16724530
        }
        self.send_message(channel_id, embeds=[embed])

    def cmd_bus_status(self, channel_id):
        st = self.kobus.get_status()
        embed = {
            "title": "📊 KOBUS 실시간 감시 상태",
            "color": 3901686,
            "fields": [
                {"name": "가동 여부", "value": "🟢 가동 중" if st["running"] else "🔴 중지됨", "inline": True},
                {"name": "점검 횟수", "value": f"{st['check_count']}회", "inline": True},
                {"name": "감시 구간", "value": f"{st['departure_name']} ➔ {st['arrival_name']}", "inline": True},
                {"name": "감시 날짜", "value": st["date"], "inline": True},
                {"name": "시간 범위", "value": f"{st['min_time']} ~ {st['max_time']}", "inline": True},
                {"name": "최소 잔여석", "value": f"{st.get('min_seats', 1)}석 이상", "inline": True}
            ],
            "footer": {"text": f"상태 확인 시각: {datetime.now().strftime('%H:%M:%S')}"}
        }
        self.send_message(channel_id, embeds=[embed])

    def cmd_terminal_search(self, channel_id, args):
        if not args:
            self.send_message(channel_id, content="검색할 지역이나 터미널 이름을 입력해주세요. (예: `!터미널 서울`)")
            return

        kw = args[0].strip()
        deps = self.kobus.fetch_terminals().get("departures", [])
        matched = [t for t in deps if kw.lower() in t["name"].lower()]

        if not matched:
            self.send_message(channel_id, content=f"❌ `{kw}` 관련 터미널을 찾을 수 없습니다.")
            return

        items = [f"• **{t['name']}** (코드: `{t['code']}`)" for t in matched[:15]]
        embed = {
            "title": f"📍 '{kw}' 관련 터미널 검색 결과 (총 {len(matched)}개)",
            "description": "\n".join(items),
            "color": 3901686
        }
        self.send_message(channel_id, embeds=[embed])

    def run_polling(self):
        token = self.get_token()
        channel_id = self.get_channel_id()

        if not token or not channel_id:
            print("=" * 68)
            print("🤖 [안내] 디스코드 양방향 챗봇 구동에 필요한 설정이 필요합니다.")
            print("=" * 68)
            print("1. Discord Developer Portal(https://discord.com/developers) 접속")
            print("2. New Application 생성 ➔ Bot ➔ Token 복사")
            print("3. Privileged Gateway Intents에서 'MESSAGE CONTENT INTENT' 활성화")
            print("4. Bot을 개인 서버에 초대")
            print("5. 챗봇과 대화할 채널 ID 복사")
            print("=" * 68)
            print("설정 파일 위치: kobus-seat-alert/config.json 내 'discord_bot' 섹션")
            print("=" * 68)
            return

        print(f"🤖 KOBUS 양방향 디스코드 챗봇이 시작되었습니다! (채널 ID: {channel_id})")
        print("디스코드 채팅창에서 '!도움말' 또는 '!버스'를 입력해보세요. (종료: Ctrl + C)")
        self.is_running = True

        # Initial fetch to get latest message ID so we don't process old history
        init_msgs = self.get_new_messages(channel_id)
        if init_msgs:
            self.last_message_id = init_msgs[-1].get("id")

        while self.is_running:
            try:
                new_msgs = self.get_new_messages(channel_id)
                for m in new_msgs:
                    self.last_message_id = m.get("id")
                    self.handle_command(m)
            except Exception as e:
                pass
            time.sleep(2.0)


if __name__ == "__main__":
    bot = KobusDiscordBot()
    bot.run_polling()
