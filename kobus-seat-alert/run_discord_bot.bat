@echo off
title KOBUS 고속버스 디스코드 양방향 챗봇
cd /d "%~dp0"

echo ========================================================
echo  KOBUS 고속버스 디스코드 양방향 제어 챗봇을 실행합니다...
echo ========================================================
echo  스마트폰 디스코드 앱에서 !버스, !버스 시작, !도움말 등의
echo  명령어로 원격 실시간 조회 및 모니터링이 가능합니다.
echo.

python kobus_discord_bot.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [오류] 봇 실행 중 오류가 발생했습니다.
    echo config.json의 discord_bot (bot_token, channel_id) 설정을 확인해주세요.
    pause
)
