#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UOS 도서관 열람실 → Alert Hub 푸시 스크립트 (집 PC용, 표준 라이브러리만 사용)

도서관 서버(library.uos.ac.kr)가 클라우드 VM IP를 차단하므로, 국내 PC에서 좌석을 읽어
VM 허브에 밀어 넣는다. 허브는 직접 조회가 막히면 이 스냅샷을 열람실 탭에 표시한다.

사용법:
  python tools/library_pusher.py --hub http://VM주소:8000 --key lib_xxxxxxxx [--interval 20]
  (환경변수 HUB_URL / LIBRARY_PUSH_KEY 로도 지정 가능. 키는 호스트 패널 > 허브 설정에서 확인)
"""
import os
import sys
import ssl
import json
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

LIB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://library.uos.ac.kr/",
    "Origin": "https://library.uos.ac.kr",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}
LIBS = {"C": "중앙도서관", "A": "건축도서관", "M": "경영도서관"}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch_rooms():
    rooms = []
    for code, name in LIBS.items():
        req = urllib.request.Request(
            "https://library.uos.ac.kr/seatStatus",
            data=f"lib={code}&time={int(time.time() * 1000)}".encode("utf-8"),
            headers=LIB_HEADERS,
        )
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=10) as res:
                d = json.loads(res.read().decode("utf-8", "replace"))
            items = d.get("seatStatus", {}).get("root", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            for it in items:
                if not isinstance(it, dict):
                    continue
                tot = int(it.get("total_seat", 0) or 0)
                use = int(it.get("use_seat", 0) or 0)
                rem = int(it.get("remain_seat", 0) or 0)
                rooms.append({
                    "lib_code": code, "lib_name": name,
                    "room_name": str(it.get("room_name", "")).strip(),
                    "total_seat": tot, "use_seat": use, "remain_seat": rem,
                    "occupancy_rate": round(use / tot * 100, 1) if tot > 0 else 0,
                })
        except Exception as e:
            log(f"[{name}] 조회 실패: {e}")
    return rooms


def push(hub, key, rooms):
    body = json.dumps({"rooms": rooms, "source": os.environ.get("COMPUTERNAME") or "home-pc"}).encode("utf-8")
    req = urllib.request.Request(
        hub.rstrip("/") + "/api/campus/library/push", data=body,
        headers={"Content-Type": "application/json", "X-Push-Key": key, "User-Agent": "AlertHub-LibraryPusher/1.0"},
    )
    with urllib.request.urlopen(req, context=CTX, timeout=15) as res:
        return json.loads(res.read().decode("utf-8", "replace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", default=os.environ.get("HUB_URL", ""), help="허브 주소 (예: http://34.1.2.3:8000 또는 https://xxx.trycloudflare.com)")
    ap.add_argument("--key", default=os.environ.get("LIBRARY_PUSH_KEY", ""), help="호스트 패널 > 허브 설정의 열람실 푸시 키")
    ap.add_argument("--interval", type=int, default=int(os.environ.get("PUSH_INTERVAL", "20")))
    ap.add_argument("--once", action="store_true", help="한 번만 푸시하고 종료")
    a = ap.parse_args()
    if not a.hub or not a.key:
        ap.error("--hub 와 --key 가 필요합니다. (또는 HUB_URL / LIBRARY_PUSH_KEY 환경변수)")

    print("=" * 64)
    print("📚 UOS 열람실 → Alert Hub 푸시 (집 PC 릴레이)")
    print(f"   허브: {a.hub}   주기: {a.interval}초   종료: Ctrl + C")
    print("=" * 64)
    fails = 0
    while True:
        rooms = fetch_rooms()
        if rooms:
            try:
                r = push(a.hub, a.key, rooms)
                fails = 0
                log(f"푸시 OK — {r.get('message', '')} (잔여 합계 {sum(x['remain_seat'] for x in rooms)}석)")
            except urllib.error.HTTPError as e:
                fails += 1
                log(f"푸시 실패 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:120]}")
            except Exception as e:
                fails += 1
                log(f"푸시 실패: {e}")
        else:
            log("열람실 데이터 없음 (도서관 서버 응답 없음) — 재시도")
        if a.once:
            break
        time.sleep(a.interval if fails < 5 else min(300, a.interval * fails))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n종료")
