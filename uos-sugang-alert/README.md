# 🎓 서울시립대학교(UOS) 수강신청 빈자리 실시간 알리미

서울시립대학교 수강신청 시스템(`sugang.uos.ac.kr`)의 정원 변동 및 잔여 좌석을 실시간으로 감지하여, 수강 취소 등으로 빈자리가 발생하는 즉시 **디스코드 3연타 모바일 푸시 알림 및 사운드 경보**를 전송하는 프로그램입니다.

---

## 📌 주요 특징

1. **실시간 정원 감지 (Real-time Polling)**:
   - 과목코드 및 분반별 `정원`과 `신청인원`을 실시간 대조하여 잔여석(`정원 - 신청`) 감지
   - 여러 과목 동시 감시 지원
2. **디스코드 3연속 버스트 푸시 (@everyone)**:
   - 빈자리 발생 순간 놓치지 않도록 **1.5초 간격으로 3회 연속 알림** 발송
   - 스마트폰 잠금화면 알림 진동/소리로 신속한 수강신청 대응 가능
3. **세션 지속 및 자동 복구 (Auto-recovery)**:
   - 학교 포털 세션 만료 시 백그라운드에서 자동 재로그인하여 중단 없이 감시 유지
   - SSL 레거시 환경 호환(`SECLEVEL=1`) 적용
4. **외부 라이브러리 의존성 0개 (Zero-dependency)**:
   - Python 3 내장 라이브러리(`urllib`, `http.cookiejar`, `ssl`, `json` 등)만 사용
   - `pip install` 없이 즉시 실행 가능
5. **학칙 및 윤리 준수**:
   - 본 프로그램은 **'빈자리 감지 및 알림'** 기능만을 수행합니다.
   - 대학 학칙 및 수강신청 윤리 규정을 준수하기 위해 **자동 수강신청(매크로 수강신청) 기능은 포함하지 않습니다.**

---

## 🚀 빠른 시작 가이드

### 1. 설정 파일 생성
`config.example.json` 파일을 복사하여 `config.json`을 만듭니다:
```bash
# Windows cmd
copy config.example.json config.json

# Linux / Mac
cp config.example.json config.json
```

### 2. `config.json` 설정
에디터(메모장, VS Code 등)로 `config.json`을 열어 정보를 입력합니다:
```json
{
  "student_id": "본인_포털_학번",
  "password": "본인_포털_비밀번호",
  "device": "PC",
  "target_courses": [
    {
      "code": "30034",
      "div": "01",
      "name": "알고리듬"
    },
    {
      "code": "30033",
      "div": "01",
      "name": "컴퓨터네트워크"
    }
  ],
  "check_interval_seconds": 6,
  "discord": {
    "enabled": true,
    "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
  }
}
```

### 3. 로그인 테스트 실행
계정 정보가 올바르게 입력되었는지 확인합니다:
```bash
python test_login.py
```
성공 시 `🎉 [로그인 성공!] 세션 쿠키가 정상 발급되었습니다.` 메시지가 출력됩니다.

### 4. 알리미 가동
- **더블 클릭 실행**: `run_sugang_alert.bat` 실행
- **콘솔 실행**:
  ```bash
  python uos_sugang_alert.py
  ```

---

## 🎮 디스코드 웹훅 연동 방법
1. 디스코드에서 알림을 받을 본인 개인 서버(채널) 접속
2. 채널 우클릭 ➔ **채널 편집** ➔ **연동** ➔ **웹훅** ➔ **새 웹훅 만들기**
3. **웹훅 URL 복사** 클릭 후 `config.json`의 `discord.webhook_url`에 붙여넣기
4. 모바일 디스코드 앱에서 알림을 켜두면 화면 잠금 상태에서도 즉시 알림 수신 가능

---

## ⚙️ 설정 항목 상세 설명
| 항목 | 타입 | 설명 |
|---|---|---|
| `student_id` | 문자열 | 서울시립대 포털 로그인 아이디 (학번) |
| `password` | 문자열 | 포털 로그인 비밀번호 |
| `device` | 문자열 | 접속 디바이스 (기본값: `"PC"`) |
| `target_courses` | 배열 | 감시할 과목 목록 (과목코드 `code`, 분반 `div`, 과목명 `name`) |
| `check_interval_seconds` | 숫자 | 조회 간격 (초 단위, 권장: 5~7초) |
| `discord.enabled` | 부울 | 디스코드 알림 활성화 여부 (`true` / `false`) |
| `discord.webhook_url` | 문자열 | 디스코드 채널 웹훅 URL |

---

## ⚠️ 유의사항
- 학교 서버에 과도한 부하를 주지 않도록 기본 조회 간격(5초 이상)을 유지하십시오.
- 실제 수강신청 페이지 접속 및 신청은 알림 수신 후 본인이 브라우저를 통해 직접 진행해야 합니다.
