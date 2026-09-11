@echo off
chcp 949 >nul
echo [INFO] 항공권(제주·일본 노선) 특가 및 잔여석 알리미를 시작합니다...
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python 3가 설치되어 있지 않거나 PATH에 등록되지 않았습니다.
    pause
    exit /b 1
)

python flight_alert.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] 실행 중 오류가 발생했습니다.
    pause
)
