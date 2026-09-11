@echo off
title Realtime Alert Hub 2.0 (통합 관제 포털)
cd /d "%~dp0"

echo ========================================================
echo  Realtime Alert Hub 2.0 (통합 관제 포털) 가동 중...
echo ========================================================
echo  포트 8000에서 5대 실시간 알리미 통합 관제가 시작됩니다.
echo  - 고속버스 (KOBUS) 빈자리 알리미
echo  - KTX / SRT 열차 취소표 알리미
echo  - 메가박스 영화관 특별관 & 명당 잔여석 알리미
echo  - 시립대 수강신청 빈자리 알리미
echo  - 시립대 중앙도서관 열람실 및 공지사항 알리미
echo ========================================================
echo.

python hub_server.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [오류] 허브 서버 실행 중 문제가 발생했습니다. Python 설치 상태를 확인해주세요.
    pause
)
