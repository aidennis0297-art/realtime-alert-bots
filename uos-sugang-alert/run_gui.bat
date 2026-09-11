@echo off
chcp 65001 > nul
title 서울시립대학교 수강신청 실시간 알리미 대시보드 (Web GUI)

echo ========================================================
echo 서울시립대학교 수강신청 알리미 웹 GUI를 시작합니다...
echo ========================================================
echo 잠시 후 웹 브라우저가 자동으로 실행됩니다.
echo.

python uos_web_server.py

if errorlevel 1 (
    echo.
    echo [오류] 실행 중 문제가 발생했습니다. Python 설치 상태를 확인해주세요.
    pause
)
