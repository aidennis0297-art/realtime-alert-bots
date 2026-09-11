# 🚌 KOBUS 고속버스 빈자리 모니터링 알리미

서울경부(서울고속버스터미널)에서 부산으로 가는 고속버스 배차를 실시간으로 모니터링하여, **취소표/빈자리**가 발생하면 즉시 사용자에게 소리, 팝업, 모바일 푸시 등으로 알려주는 프로그램입니다.

---

## 📌 주요 기능

1. **실시간 배차 모니터링**: 
   - 센트럴시티 ➔ 부산 (18:00 ~ 22:05 총 15개 배차)
   - 일반/우등/임시/심야우등 전 노선 실시간 감지
2. **다채로운 알림 수단**:
   - 🔊 **PC 스피커 경보음**: 비프음 연속 발생 (`winsound`)
   - 🖥️ **Windows 화면 팝업**: 최상단 팝업 알림창 띄우기
   - 🌐 **브라우저 자동 열기**: 빈자리 감지 즉시 KOBUS 예매 페이지 자동 오픈
   - 📱 **스마트폰 푸시 알림 (선택)**: 텔레그램 봇 또는 디스코드 웹훅 연동 지원
3. **추가 라이브러리 설치 불필요**:
   - Python 기본 표준 라이브러리만으로 제작되어 `pip install` 없이 즉시 실행 가능합니다.

---

## 🚀 실행 방법

### 방법 1. 간편 실행 (더블 클릭)
- `run_alert.bat` 파일을 더블 클릭하여 실행합니다.

### 방법 2. 콘솔 실행
```bash
python bus_alert.py
```

---

## ⚙️ 설정 파일 안내 (`config.json`)

`config.json` 파일을 메모장이나 에디터로 열어 원하는 대로 수정할 수 있습니다:

```json
{
  "departure_terminal": "010",
  "arrival_terminal": "700",
  "departure_name": "서울경부",
  "arrival_name": "부산",
  "date": "20260923",
  "min_time": "18:00",
  "max_time": "23:59",
  "check_interval_seconds": 6,
  "sound_alert": true,
  "popup_alert": true,
  "auto_open_browser": true,
  "telegram": {
    "enabled": false,
    "bot_token": "봇토큰",
    "chat_id": "채팅아이디"
  },
  "discord": {
    "enabled": false,
    "webhook_url": "웹훅URL"
  }
}
```

### 📱 텔레그램 스마트폰 알림 설정 방법 (선택)
1. 텔레그램에서 `@BotFather` 검색 후 `/newbot` 입력하여 봇 생성 ➔ **API Token** 복사
2. 텔레그램에서 `@userinfobot` 검색 후 대화 시작 ➔ 내 **Id**(숫자) 확인
3. 생성한 봇에게 아무 메시지나 1회 전송 (대화방 활성화)
4. `config.json`에서 `"enabled": true`로 바꾸고 `bot_token`, `chat_id` 입력

### 🎮 디스코드 웹훅 알림 설정 방법 (선택)
1. 디스코드 서버 채널 설정 ➔ 연동 ➔ 웹훅 만들기 ➔ 웹훅 URL 복사
2. `config.json`의 `discord`에서 `"enabled": true`로 바꾸고 `webhook_url` 입력

---

## 💡 주의 사항
- KOBUS 서버 정책에 따라 너무 빠른 요청은 차단될 수 있으므로, 기본 주기인 5~7초를 유지하는 것을 권장합니다.
