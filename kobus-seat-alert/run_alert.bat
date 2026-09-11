@echo off
chcp 65001 > nul
title KOBUS 고속버스 빈자리 알리미 (서울경부 -> 부산)

echo ========================================================
echo KOBUS 고속버스 빈자리 모니터링 알리미를 시작합니다...
echo ========================================================
echo.

python bus_alert.py

if errorlevel 1 (
    echo.
    echo [오류] 파이썬 실행 중 오류가 발생했습니다. Python이 정상적으로 설치되어 있는지 확인해주세요.
    pause
)
