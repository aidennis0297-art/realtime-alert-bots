#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
디스코드 웹훅 알림 연동 테스트 스크립트
"""

import sys
import json
import urllib.request
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

def test_webhook():
    config_path = "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"[!] config.json 읽기 실패: {e}")
        return

    dc = cfg.get("discord", {})
    webhook_url = dc.get("webhook_url", "").strip()

    if not webhook_url or "여기에" in webhook_url:
        print("\n[!] config.json의 discord.webhook_url 에 디스코드 웹훅 주소를 먼저 입력해주세요!")
        return

    print(f"\n[+] 디스코드 웹훅으로 테스트 알림 전송 중...")

    embed = {
        "title": "✅ [테스트] KOBUS 고속버스 빈자리 알리미 연동 성공!",
        "description": "**서울경부 ➔ 부산** (2026-09-23 수요일 18시 이후)\n\n디스코드 모바일 푸시 알림이 정상적으로 연결되었습니다. 이제 빈자리가 나오면 폰으로 즉시 알림이 옵니다!",
        "url": "https://www.kobus.co.kr/mrs/rotinf.do",
        "color": 65280,  # Green
        "fields": [
            {
                "name": "모니터링 구간",
                "value": "서울경부 ➔ 부산",
                "inline": True
            },
            {
                "name": "희망 시간대",
                "value": "2026-09-23 18:00 ~ 22:05 (총 15편)",
                "inline": True
            }
        ],
        "footer": {
            "text": f"KOBUS 알리미 • 테스트 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
    }

    payload = json.dumps({
        "content": "@everyone 🔔 **KOBUS 빈자리 알리미 테스트 메시지입니다!** (스마트폰 알림 확인용)",
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

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                print("🎉 [성공] 디스코드로 테스트 알림이 발송되었습니다! 스마트폰 디스코드 앱을 확인해보세요.\n")
            else:
                print(f"[!] 응답 코드: {resp.status}")
    except Exception as e:
        print(f"❌ [실패] 전송 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    test_webhook()
