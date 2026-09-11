@echo off
title Realtime Alert Hub (통합 알리미 포털)
cd /d "%~dp0"
echo ========================================================
echo  Realtime Alert Hub (통합 알리미 포털)을 시작합니다...
echo ========================================================
echo  잠시 후 웹 브라우저(http://localhost:8000)가 열립니다.
echo.
python hub_server.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [오류] 실행 중 문제가 발생했습니다. Python 설치 상태를 확인해주세요.
    pause
)
