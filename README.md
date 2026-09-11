# 🚀 Real-time Alert Bots (실시간 알리미 봇 모음)

고속버스 취소표, 대학 수강신청 빈자리 등 **실시간 데이터 변동을 24시간 감시하고 디스코드 3연속 버스트 푸시 알림을 발송하는 경량 모니터링 자동화 봇 모음**입니다.

---

## 📦 포함된 프로젝트

### 1. 🚌 [kobus-seat-alert](./kobus-seat-alert)
- **KOBUS 고속버스 실시간 잔여 좌석 감지 및 3연타 알리미**
- 서울경부 ➔ 부산 등 원하는 일자 및 시간대의 매진된 노선을 24시간 감시
- 취소표 발생 즉시 **1.5초 간격 3회 연속 디스코드 푸시(@everyone) + PC 경보음 + 브라우저 자동 오픈**
- 로컬 PC 단독 실행 및 GCP 클라우드 24/7 백그라운드 서버 모드 지원

### 2. 🎓 [uos-sugang-alert](./uos-sugang-alert)
- **서울시립대학교(UOS) 수강신청 빈자리 실시간 감지 알리미**
- `sugang.uos.ac.kr` 대상 개설 과목의 정원 대비 신청인원을 실시간 조회
- 잔여석 발생 즉시 디스코드 3연타 모바일 푸시 발송
- 세션 만료 시 자동 재로그인 및 자가 복구 기능 탑재
- *※ 대학 학칙 및 운영 지침 준수를 위해 순수 "알림" 전용으로 제작 (자동 신청 매크로 미포함)*

### 3. 🛠️ [AUTOMATION_BLUEPRINT.md](./AUTOMATION_BLUEPRINT.md)
- **클라우드 24/7 자동 모니터링 시스템 아키텍처 청사진 & AI 프롬프트 명세서**
- GCP 한국 리전(`asia-northeast3`) + Python 표준 라이브러리 + systemd 데몬 + 디스코드 푸시 파이프라인
- 다른 티켓팅/예매 사이트로 시스템을 확장할 때 ChatGPT, Claude 등에 바로 복사해서 사용할 수 있는 표준 프롬프트 제공

---

## 💡 공통 아키텍처 핵심 요약

| 구성 요소 | 적용 기술 / 전략 | 장점 |
|---|---|---|
| **의존성 (Dependency)** | Python 3 내장 라이브러리만 사용 (`urllib`, `http.cookiejar`, `ssl`, `json`, `re`) | `pip install` 불필요, 25MB 이하 극경량 메모리 점유 |
| **보안 통신 (SSL)** | `DEFAULT@SECLEVEL=1` | 구형 레거시 전산망 및 관공서 시스템 SSL 핸드셰이크 호환 |
| **알림 (Notification)** | 디스코드 웹훅 3연타 버스트 전송 | 화면 꺼짐/잠금 상태에서도 모바일 진동/소리로 확실한 인지 |
| **안정성 (Reliability)** | 직전 상태 메모리 캐싱 & 3시간 주기 하트비트 | 중복 알림 방지 및 장기 구동 안정성 확보 |
| **자가 복구 (Self-healing)** | Linux systemd 데몬 등록 (`Restart=always`) | 예기치 않은 세션 끊김이나 서버 재부팅 시 5초 내 자동 부활 |

---

## 🚀 설치 및 사용법

각 프로젝트 디렉터리의 상세 `README.md`를 참고하세요:
- [KOBUS 알리미 사용법](./kobus-seat-alert/README.md)
- [서울시립대 수강신청 알리미 사용법](./uos-sugang-alert/README.md)

---

## 📄 라이선스
MIT License
