import os
import sys
import time
import json
import re
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

STATION_REGIONS = {
    "서울/수도권": [
        {
            "name": "수서",
            "code": "0551"
        },
        {
            "name": "서울",
            "code": "0001"
        },
        {
            "name": "용산",
            "code": "0002"
        },
        {
            "name": "영등포",
            "code": "0004"
        },
        {
            "name": "광명",
            "code": "0501"
        },
        {
            "name": "행신",
            "code": "0008"
        },
        {
            "name": "수원",
            "code": "0011"
        },
        {
            "name": "청량리",
            "code": "0003"
        },
        {
            "name": "동탄",
            "code": "0552"
        },
        {
            "name": "평택지제",
            "code": "0553"
        }
    ],
    "강원권": [
        {
            "name": "강릉",
            "code": "0274"
        },
        {
            "name": "만종",
            "code": "0268"
        },
        {
            "name": "횡성",
            "code": "0269"
        },
        {
            "name": "둔내",
            "code": "0270"
        },
        {
            "name": "평창",
            "code": "0271"
        },
        {
            "name": "진부",
            "code": "0272"
        },
        {
            "name": "동해",
            "code": "0280"
        }
    ],
    "대전/충청권": [
        {
            "name": "천안아산",
            "code": "0502"
        },
        {
            "name": "오송",
            "code": "0297"
        },
        {
            "name": "대전",
            "code": "0010"
        },
        {
            "name": "서대전",
            "code": "0013"
        },
        {
            "name": "공주",
            "code": "0514"
        },
        {
            "name": "조치원",
            "code": "0009"
        }
    ],
    "대구/경북권": [
        {
            "name": "동대구",
            "code": "0015"
        },
        {
            "name": "서대구",
            "code": "0506"
        },
        {
            "name": "김천(구미)",
            "code": "0507"
        },
        {
            "name": "경주",
            "code": "0508"
        },
        {
            "name": "포항",
            "code": "0515"
        },
        {
            "name": "안동",
            "code": "0130"
        }
    ],
    "부산/경남권": [
        {
            "name": "부산",
            "code": "0020"
        },
        {
            "name": "구포",
            "code": "0018"
        },
        {
            "name": "울산(통도사)",
            "code": "0509"
        },
        {
            "name": "밀양",
            "code": "0017"
        },
        {
            "name": "진영",
            "code": "0056"
        },
        {
            "name": "창원중앙",
            "code": "0512"
        },
        {
            "name": "창원",
            "code": "0057"
        },
        {
            "name": "마산",
            "code": "0059"
        },
        {
            "name": "진주",
            "code": "0063"
        }
    ],
    "광주/전라권": [
        {
            "name": "광주송정",
            "code": "0036"
        },
        {
            "name": "익산",
            "code": "0030"
        },
        {
            "name": "전주",
            "code": "0045"
        },
        {
            "name": "정읍",
            "code": "0033"
        },
        {
            "name": "남원",
            "code": "0048"
        },
        {
            "name": "곡성",
            "code": "0049"
        },
        {
            "name": "구례구",
            "code": "0050"
        },
        {
            "name": "순천",
            "code": "0051"
        },
        {
            "name": "여천",
            "code": "0139"
        },
        {
            "name": "여수EXPO",
            "code": "0053"
        },
        {
            "name": "나주",
            "code": "0037"
        },
        {
            "name": "목포",
            "code": "0041"
        }
    ]
}

STATION_MAP = {}
for region, stns in STATION_REGIONS.items():
    for stn in stns:
        STATION_MAP[stn["code"]] = stn["name"]


class NetFunnelHelper:
    """SRT NetFunnel 대기열 우회 키 발급 헬퍼"""
    def __init__(self):
        self.cached_key = None
        self.last_key_time = 0

    def get_key(self, force_refresh=False):
        now = time.time()
        if not force_refresh and self.cached_key and (now - self.last_key_time < 120):
            return self.cached_key

        ts = int(now * 1000)
        nf_url = f"http://nf.letskorail.com/ts.wseq?opcode=5101&nfid=0&prefix=NetFunnel.gRtype%3D5101%3B&sid=service_1&aid=act_10&js=true&{ts}="
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 SRT-APP-iOS V.2.0.18",
            "Referer": "https://app.srail.or.kr:443"
        }

        try:
            req = urllib.request.Request(nf_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as res:
                raw = res.read().decode("utf-8")
                m = re.search(r"key=([^&]+)", raw)
                if not m:
                    return "NET000001"
                key = m.group(1)

            # setComplete 호출
            ts2 = int(time.time() * 1000)
            sc_url = f"http://nf.letskorail.com/ts.wseq?opcode=5004&key={key}&nfid=0&prefix=NetFunnel.gRtype%3D5004%3B&js=true&{ts2}="
            req_sc = urllib.request.Request(sc_url, headers=headers)
            with urllib.request.urlopen(req_sc, timeout=5) as res_sc:
                _ = res_sc.read()

            self.cached_key = key
            self.last_key_time = now
            return key
        except Exception:
            return "NET000001"


class TrainMonitor:
    """KTX/SRT 열차 취소표 실시간 감시 엔진"""
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "config.json")
        self.config = self.load_config()
        self.netfunnel = NetFunnelHelper()
        self.is_running = False
        self.monitor_thread = None
        self.check_count = 0
        self.vacant_trains = []
        self.recent_logs = []
        self.lock = threading.Lock()

        # SSL 컨텍스트
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
            "departure_station": "0551",  # 수서
            "departure_name": "수서",
            "arrival_station": "0020",    # 부산
            "arrival_name": "부산",
            "date": datetime.now().strftime("%Y%m%d"),
            "min_time": "06:00",
            "max_time": "23:59",
            "train_type": "ALL",          # ALL, SRT, KTX
            "seat_type": "ALL",           # ALL, GENERAL, SPECIAL
            "min_seats": 1,               # 알림 기준 최소 잔여석 (1석 이상, 2석 이상 등)
            "check_interval_seconds": 6,
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
                print(f"[!] KTX/SRT 설정 로드 실패: {e}")
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

    def query_trains(self, dep_code=None, arr_code=None, date=None, min_time=None, max_time=None):
        dep = dep_code or self.config.get("departure_station", "0551")
        arr = arr_code or self.config.get("arrival_station", "0020")
        target_date = (date or self.config.get("date", datetime.now().strftime("%Y%m%d"))).replace("-", "")
        min_tm_str = (min_time or self.config.get("min_time", "00:00")).replace(":", "") + "00"
        max_tm_str = (max_time or self.config.get("max_time", "23:59")).replace(":", "") + "59"
        min_tm_int = int(min_tm_str[:4])
        max_tm_int = int(max_tm_str[:4])

        key = self.netfunnel.get_key()
        url = "https://app.srail.or.kr:443/ara/selectListAra10007_n.do"

        post_data = urllib.parse.urlencode({
            "chtnDvCd": "1",
            "arriveTime": "N",
            "seatAttCd": "015",
            "psgNum": 1,
            "trnGpCd": 109,
            "stlbTrnClsfCd": "05",
            "dptDt": target_date,
            "dptTm": min_tm_str,
            "arvRsStnCd": arr,
            "dptRsStnCd": dep,
            "netfunnelKey": key
        }).encode("utf-8")

        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 SRT-APP-iOS V.2.0.18",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        try:
            req = urllib.request.Request(url, data=post_data, headers=headers)
            with urllib.request.urlopen(req, context=self.ctx, timeout=8) as res:
                raw = res.read().decode("utf-8")
                d = json.loads(raw)

                # NetFunnel 키 만료 시 1회 재발급 시도
                if d.get("resultMap", [{}])[0].get("msgCd") == "NET000001":
                    key = self.netfunnel.get_key(force_refresh=True)
                    post_data = urllib.parse.urlencode({
                        "chtnDvCd": "1",
                        "arriveTime": "N",
                        "seatAttCd": "015",
                        "psgNum": 1,
                        "trnGpCd": 109,
                        "stlbTrnClsfCd": "05",
                        "dptDt": target_date,
                        "dptTm": min_tm_str,
                        "arvRsStnCd": arr,
                        "dptRsStnCd": dep,
                        "netfunnelKey": key
                    }).encode("utf-8")
                    req = urllib.request.Request(url, data=post_data, headers=headers)
                    with urllib.request.urlopen(req, context=self.ctx, timeout=8) as res2:
                        d = json.loads(res2.read().decode("utf-8"))

                train_items = d.get("outDataSets", {}).get("dsOutput1", [])
                parsed_trains = []

                for t in train_items:
                    raw_dpt = str(t.get("dptTm", ""))
                    raw_arv = str(t.get("arvTm", ""))
                    if not raw_dpt or len(raw_dpt) < 4:
                        continue

                    dpt_hhmm = f"{raw_dpt[:2]}:{raw_dpt[2:4]}"
                    arv_hhmm = f"{raw_arv[:2]}:{raw_arv[2:4]}"
                    dpt_int = int(raw_dpt[:4])

                    if not (min_tm_int <= dpt_int <= max_tm_int):
                        continue

                    gen_str = t.get("gnrmRsvPsbStr", "매진")
                    spc_str = t.get("sprmRsvPsbStr", "매진")
                    has_gen = "예약가능" in gen_str
                    has_spc = "예약가능" in spc_str
                    has_vacant = has_gen or has_spc

                    trn_clsf = t.get("stlbTrnClsfNm") or "SRT"
                    trn_no = t.get("trnNo", "")

                    parsed_trains.append({
                        "trn_no": trn_no,
                        "trn_name": f"{trn_clsf} {trn_no}",
                        "dpt_time": dpt_hhmm,
                        "arv_time": arv_hhmm,
                        "general_seat": gen_str,
                        "special_seat": spc_str,
                        "has_seat": has_vacant,
                        "reserve_url": "https://etk.srail.kr"
                    })

                return parsed_trains
        except Exception as e:
            self.log(f"열차 배차 조회 중 오류: {e}")
            return []

    def send_discord_burst(self, vacant_trains):
        webhook_url = self.config.get("discord", {}).get("webhook_url", "").strip()
        if not webhook_url or not webhook_url.startswith("http"):
            return

        mention = self.config.get("discord", {}).get("mention", "@everyone")
        dep_name = STATION_MAP.get(self.config.get("departure_station"), "출발역")
        arr_name = STATION_MAP.get(self.config.get("arrival_station"), "도착역")
        date_str = self.config.get("date", "")

        train_lines = []
        for t in vacant_trains:
            train_lines.append(f"• **[{t['trn_name']}]** {t['dpt_time']} ➔ {t['arv_time']} (일반실: `{t['general_seat']}`, 특실: `{t['special_seat']}`)")

        content_text = (
            f"🚨🚨🚨 **[취소표 발생!] KTX/SRT 열차 잔여석 감지!** {mention}\n\n"
            f"📍 **구간**: {dep_name} ➔ {arr_name}\n"
            f"📅 **일정**: {date_str}\n"
            f"🚄 **예약 가능 열차**:\n" + "\n".join(train_lines) + "\n\n"
            f"🔗 **즉시 예매**: https://etk.srail.kr\n"
            f"⚡ 지금 즉시 링크를 클릭하여 예매를 완료하세요!"
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
            "content": f"🔔 **[KTX/SRT 알리미] 디스코드 테스트 알림** @everyone\n"
                       f"• 시스템이 정상적으로 연결되었습니다.\n"
                       f"• 열차 취소표 발생 시 1.5초 간격 3회 연속 진동 푸시가 전송됩니다."
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
        dep_name = STATION_MAP.get(self.config.get("departure_station"), "출발역")
        arr_name = STATION_MAP.get(self.config.get("arrival_station"), "도착역")
        self.log(f"🚄 KTX/SRT 취소표 모니터링 시작: {dep_name} ➔ {arr_name} ({self.config.get('date')})")

        while self.is_running:
            self.check_count += 1
            trains = self.query_trains()
            vacant = [t for t in trains if t["has_seat"]]
            self.vacant_trains = vacant

            if vacant:
                self.log(f"🎉🎉🎉 취소표 발견! ({len(vacant)}개 열차 예약 가능)")
                for v in vacant:
                    self.log(f"  ▶ [{v['trn_name']}] {v['dpt_time']} (일반: {v['general_seat']}, 특실: {v['special_seat']})")

                # 사운드 및 브라우저
                sys.stdout.write("\a")
                sys.stdout.flush()
                try:
                    webbrowser.open("https://etk.srail.kr")
                except Exception:
                    pass

                # 디스코드 3연타
                self.send_discord_burst(vacant)
                # 발견 후 15초 대기
                time.sleep(15)
            else:
                if self.check_count % 10 == 1:
                    self.log(f"점검 {self.check_count}회차: 전체 매진 상태 유지 중... (감시 계속)")

            interval = int(self.config.get("check_interval_seconds", 6))
            time.sleep(max(3, interval))

    def start_monitoring(self):
        if self.is_running:
            return False, "이미 모니터링이 실행 중입니다."
        self.is_running = True
        self.check_count = 0
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        return True, "KTX/SRT 취소표 감시가 시작되었습니다."

    def stop_monitoring(self):
        if not self.is_running:
            return False, "모니터링이 실행 중이지 않습니다."
        self.is_running = False
        self.log("🛑 KTX/SRT 모니터링을 중지했습니다.")
        return True, "KTX/SRT 취소표 감시가 중지되었습니다."

    def get_status(self):
        dep_name = STATION_MAP.get(self.config.get("departure_station"), "출발역")
        arr_name = STATION_MAP.get(self.config.get("arrival_station"), "도착역")
        return {
            "running": self.is_running,
            "check_count": self.check_count,
            "departure_name": dep_name,
            "arrival_name": arr_name,
            "date": self.config.get("date"),
            "min_time": self.config.get("min_time"),
            "max_time": self.config.get("max_time"),
            "min_seats": self.config.get("min_seats", 1),
            "vacant_trains": self.vacant_trains,
            "recent_logs": list(self.recent_logs)
        }
