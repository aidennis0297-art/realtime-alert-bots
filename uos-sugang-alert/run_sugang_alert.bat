@echo off
title 서울시립대학교 수강신청 실시간 알리미 (CLI)
cd /d "%~dp0"

echo ========================================================
echo  서울시립대학교 수강신청 알리미 (콘솔 모드)를 시작합니다...
echo ========================================================
echo.

python uos_sugang_alert.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [오류] 실행 중 문제가 발생했습니다. Python 설치 상태를 확인해주세요.
    pause
)
