import sys
import time
import json
import re
import ssl
import http.cookiejar
import urllib.request
import urllib.parse
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_URL = "https://www.kobus.co.kr"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_session():
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
    req = urllib.request.Request(f"{BASE_URL}/main.do", headers={"User-Agent": USER_AGENT})
    try:
        opener.open(req, timeout=10)
    except Exception as e:
        print(f"[!] 초기 세션 생성 주의: {e}")
    return opener

def check_seats(opener, depr_cd="010", arvl_cd="700", date="20260923", min_time="18:00"):
    data = {
        "deprCd": depr_cd,
        "arvlCd": arvl_cd,
        "pathDvs": "sngl",
        "pathStep": "1",
        "deprDtm": date,
        "busClsCd": "0",
        "rtrpChc": "1",
        "timeLinkMin": min_time.split(":")[0],
        "timeLinkMax": "23"
    }
    
    req = urllib.request.Request(
        f"{BASE_URL}/mrs/alcnSrch.do",
        data=urllib.parse.urlencode(data).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Referer": f"{BASE_URL}/mrs/rotinf.do",
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    
    with opener.open(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    
    rows = re.findall(r'<p\b[^>]*role=[\x22\x27]row[\x22\x27][^>]*>(.*?)</p>', html, re.DOTALL)
    
    results = []
    for r in rows:
        time_m = re.search(r'class=[\x22\x27]start_time[\x22\x27][^>]*>(.*?)</span>', r)
        if not time_m:
            continue
        dep_time = re.sub(r'<[^>]+>', '', time_m.group(1)).strip().replace(" ", "")
        
        if dep_time < min_time:
            continue
            
        # Company
        com_m = re.search(r'class=[\x22\x27]bus_com[\x22\x27][^>]*>(.*?)</span>', r)
        if not com_m:
            com_m = re.search(r'class=[\x22\x27]bus_info[\x22\x27][^>]*>.*?<span[^>]*>(.*?)</span>', r, re.DOTALL)
        company = re.sub(r'<[^>]+>', '', com_m.group(1)).strip() if com_m else ""
        
        # Grade
        grade_m = re.search(r'class=[\x22\x27]grade_mo[\x22\x27][^>]*>(.*?)</span>', r)
        if not grade_m:
            grade_m = re.search(r'class=[\x22\x27]grade[\x22\x27][^>]*>(.*?)</span>', r)
        grade = re.sub(r'<[^>]+>', '', grade_m.group(1)).strip() if grade_m else ""
        grade = re.sub(r'\s+', ' ', grade).strip()
        
        # Is Temporary
        is_temporary = "임시" in r
        if is_temporary and "(임시)" not in grade:
            grade += "(임시)"
        
        # Remaining seats
        rem_m = re.search(r'class=[\x22\x27]remain[\x22\x27][^>]*>(.*?)</span>', r)
        rem_text = re.sub(r'<[^>]+>', '', rem_m.group(1)).strip() if rem_m else ""
        
        # Status
        status_m = re.search(r'class=[\x22\x27]status[\x22\x27][^>]*>(.*?)</span>', r)
        status_text = re.sub(r'<[^>]+>', '', status_m.group(1)).strip() if status_m else ""
        
        cnt_m = re.search(r'(\d+)', rem_text)
        seats = int(cnt_m.group(1)) if cnt_m else 0
        
        has_action = "fnSatsChc" in r
        bookable = (seats > 0 and has_action) or ("선택" in status_text and "매진" not in status_text)
        
        results.append({
            "time": dep_time,
            "company": company,
            "grade": grade,
            "seats": seats,
            "seats_text": rem_text,
            "status": status_text,
            "bookable": bookable
        })
        
    return results

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KOBUS 서울경부 -> 부산 배차 조회 중...")
    session = get_session()
    buses = check_seats(session, "010", "700", "20260923", "18:00")
    print(f"조회 완료: 18:00 이후 총 {len(buses)}개 배차 확인")
    print("-" * 55)
    print(f"{'출발시간':<8} | {'운행회사':<12} | {'등급':<10} | {'잔여석':<6} | {'상태'}")
    print("-" * 55)
    for b in buses:
        status_display = f"★ {b['seats']}석 빈자리 발생! ★" if b['bookable'] else "매진"
        print(f"{b['time']:<8} | {b['company']:<12} | {b['grade']:<10} | {b['seats_text']:<6} | {status_display}")
    print("-" * 55)
