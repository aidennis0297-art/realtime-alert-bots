@echo off
title 영화관 명당/취소표 알리미
cd /d "%~dp0"
echo ========================================================
echo  영화관(메가박스) 특별관/명당 실시간 알리미를 시작합니다...
echo ========================================================
echo  잠시 후 Alert Hub 통합 포털(http://localhost:8000)이 열립니다.
echo.
cd ..
python hub_server.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [오류] 실행 중 문제가 발생했습니다. Python 설치 상태를 확인해주세요.
    pause
)
