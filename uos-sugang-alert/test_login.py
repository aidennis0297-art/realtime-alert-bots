#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
서울시립대학교 수강신청 시스템 (sugang.uos.ac.kr) 로그인 테스트 스크립트
"""

import sys
import json
import ssl
import http.cookiejar
import urllib.request
import urllib.parse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_URL = "https://sugang.uos.ac.kr"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

def test_login(config_path="config.json"):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"[!] config.json 읽기 오류: {e}")
        return

    student_id = cfg.get("student_id", "").strip()
    password = cfg.get("password", "").strip()

    if not student_id or "학번" in student_id:
        print("\n[!] config.json 파일에 본인의 서울시립대 학번과 비밀번호를 입력해주세요!")
        return

    print(f"\n[+] 서울시립대 수강신청 시스템 접속 시도: 학번({student_id})")

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

    # 1. 메인 페이지 방문 (쿠키 초기화)
    try:
        req_main = urllib.request.Request(BASE_URL, headers={"User-Agent": USER_AGENT})
        opener.open(req_main, timeout=10)
    except Exception as e:
        print(f"[!] 메인 접속 오류: {e}")

    # 2. 로그인 요청
    login_data = {
        "USER_ID": student_id,
        "PWD": password,
        "DEVICE": cfg.get("device", "PC"),
        "LANG": "KOR",
        "UNIV": "UNIV",
        "GDHL": ""
    }

    req_login = urllib.request.Request(
        f"{BASE_URL}/Login/login.do",
        data=urllib.parse.urlencode(login_data).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "req-protocol": "urlencoded",
            "res-protocol": "json",
            "User-Agent": USER_AGENT,
            "Referer": BASE_URL
        }
    )

    try:
        with opener.open(req_login, timeout=10) as resp:
            raw_res = resp.read().decode("utf-8", errors="replace")
            res_json = json.loads(raw_res)

            err_info = res_json.get("ERRMSGINFO")
            if err_info and err_info.get("ERRMSG"):
                print(f"\n❌ [로그인 실패] {err_info.get('ERRMSG')}")
            else:
                print("\n🎉 [로그인 성공!] 세션 쿠키가 정상 발급되었습니다.")
                cookies = [c.name for c in jar]
                print(f"• 세션 쿠키: {cookies}")
    except Exception as e:
        print(f"\n[!] 요청 중 예외 발생: {e}")

if __name__ == "__main__":
    test_login()
