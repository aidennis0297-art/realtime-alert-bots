@echo off
chcp 949 >nul
title UOS 열람실 -> Alert Hub 푸시 (집 PC 릴레이)
cd /d "%~dp0"

if not exist "tools\pusher_config.json" (
    echo [!] tools\pusher_config.json 이 없습니다. 아래 형식으로 만들어 주세요:
    echo     {"hub": "http://VM주소:8000", "key": "lib_xxxxxxxx"}
    echo     ^(키는 허브 관제 탭 - 호스트 패널 - 허브 설정에서 확인^)
    pause
    exit /b
)

for /f "usebackq delims=" %%A in (`python -c "import json;d=json.load(open('tools/pusher_config.json'));print(d['hub'])"`) do set HUB_URL=%%A
for /f "usebackq delims=" %%A in (`python -c "import json;d=json.load(open('tools/pusher_config.json'));print(d['key'])"`) do set LIBRARY_PUSH_KEY=%%A

python tools\library_pusher.py
pause
