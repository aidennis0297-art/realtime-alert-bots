@echo off
title KOBUS 고속버스 빈자리 알리미
cd /d "%~dp0"

echo ========================================================
echo  KOBUS 고속버스 빈자리 알리미를 시작합니다...
echo ========================================================
echo.

python bus_alert.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [오류] 실행 중 문제가 발생했습니다. Python 설치 상태를 확인해주세요.
    pause
)
