@echo off
chcp 949 >nul
title Cloudflare External Tunnel (Alert Hub 2.0)
echo ====================================================================
echo  [Alert Hub 2.0] 외부 접속용 Cloudflare 터널을 시작합니다...
echo  잠시 후 화면에 출력되는 https://xxxx.trycloudflare.com 링크를
echo  스마트폰 브라우저나 외부 PC에서 열어보세요!
echo  (종료하려면 창을 닫거나 Ctrl + C를 누르세요)
echo ====================================================================
echo.

if not exist "%~dp0cloudflared.exe" (
    echo [!] cloudflared.exe 파일이 없습니다.
    pause
    exit /b
)

"%~dp0cloudflared.exe" tunnel --url http://localhost:8000
pause
