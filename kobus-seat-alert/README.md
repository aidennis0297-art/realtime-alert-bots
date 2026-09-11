# 🚌 KOBUS 고속버스 실시간 빈자리 알리미 & Web GUI 대시보드

전국 고속버스 터미널(서울경부, 센트럴시티, 동서울, 부산 등)의 배차 및 잔여 좌석을 **브라우저 GUI 화면에서 출발지/도착지/날짜/시간대를 자유롭게 지정**하여 실시간으로 조회하고, 취소표(빈자리)가 발생하는 즉시 **디스코드 3연타 모바일 진동 알림 + PC 사운드 경보 + KOBUS 예매창 자동 팝업**을 전송하는 프로그램입니다.

---

## 📌 주요 기능

1. **Zero-dependency 로컬 웹 GUI 대시보드 (`kobus_web_server.py`)**:
   - 외부 라이브러리(`pip install`) 설치가 일체 필요 없는 Python 표준 라이브러리(`http.server`, `urllib`, `threading`, `json`, `webbrowser`) 기반
   - `run_gui.bat` 더블 클릭 한 번으로 로컬 서버 실행 및 기본 웹 브라우저(`http://localhost:8081`) 자동 오픈
2. **출발지 및 도착지 터미널 동적 연동**:
   - KOBUS 공식 1,240개 노선 연동으로 출발지 선택 시 운행 가능한 도착지 목록 자동 필터링
3. **달력(Calendar) 및 시간대 지정**:
   - 원하는 예매 날짜(`YYYY-MM-DD`) 및 시간대(예: 14:00 ~ 23:59) 자유 선택
4. **실시간 배차 현황 조회 (Timetable Explorer)**:
   - [🔄 실시간 배차 조회] 클릭 시 출발시각, 운행회사, 버스등급(우등/프리미엄/일반), 잔여석/총좌석 실시간 표시
5. **다채로운 4중 알림 수단**:
   - 🔊 **PC 스피커 경보음**: 비프음 연속 발생 (`winsound`)
   - 🖥️ **Windows 화면 팝업**: 최상단 팝업 알림창 띄우기
   - 🌐 **브라우저 자동 열기**: 빈자리 감지 즉시 KOBUS 예매 페이지 자동 오픈
   - 📱 **스마트폰 디스코드 3연타 푸시**: 1.5초 간격 3회 연속 `@everyone` 모바일 진동 알림
6. **장치별 알림 On/Off 토글**:
   - 웹 화면에서 사운드, 팝업, 브라우저 오픈, 디스코드 알림을 각각 켜고 끌 수 있음

---

## 🚀 실행 방법

### 방법 1. 웹 GUI 대시보드 실행 (강력 추천 ⭐)
- `run_gui.bat` 파일을 더블 클릭합니다.
- 또는 콘솔에서:
  ```bash
  python kobus_web_server.py
  ```
- 기본 브라우저에서 `http://localhost:8081` 대시보드가 자동으로 열립니다.

### 방법 2. 콘솔 CLI 단독 실행
- `run_alert.bat` 파일을 더블 클릭하거나 콘솔에서 실행:
  ```bash
  python bus_alert.py
  ```

---

## ⚙️ 설정 파일 안내 (`config.json`)

대시보드 우측 상단 [⚙️ 설정] 메뉴에서 입력하거나 직접 수정할 수 있습니다:

```json
{
  "departure_terminal": "010",
  "arrival_terminal": "700",
  "departure_name": "서울경부",
  "arrival_name": "부산",
  "date": "20260923",
  "min_time": "14:00",
  "max_time": "23:59",
  "check_interval_seconds": 6,
  "sound_alert": true,
  "popup_alert": true,
  "auto_open_browser": true,
  "discord": {
    "enabled": true,
    "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
  }
}
```
