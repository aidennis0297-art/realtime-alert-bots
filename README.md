# 🚀 Real-time Alert Bots (실시간 알리미 봇 모음 & 통합 허브)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/Architecture-Zero--Dependency-success?style=for-the-badge" alt="Zero-Dependency" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License" />
</p>

고속버스 취소표, 대학교 수강신청 빈자리 등 **실시간 데이터 변동을 24시간 감시하고 디스코드 3연속 버스트 푸시 알림(@everyone)을 발송하는 경량 모니터링 자동화 봇 & 올인원 통합 포털**입니다.

---

## 🌟 올인원 통합 포털 허브 (Alert Hub)

이제 고속버스와 수강신청 알리미를 각각 실행할 필요 없이, **단 하나의 웹 화면(`http://localhost:8000`)에서 탭으로 전환하며 전체를 한 번에 관리**할 수 있습니다.

```mermaid
graph TD
    User([사용자 브라우저 - http://localhost:8000]) <-->|통합 대시보드| HubServer[Alert Hub Server - hub_server.py]

    subgraph Docker Container or Local Server
        HubServer --> HubUI[Alert Hub Web UI - SPA Tabs]
        HubServer --> KobusController[KOBUS 고속버스 엔진]
        HubServer --> UosController[UOS 수강신청 엔진]
    end

    KobusController <-->|HTTPS 배차 조회| KobusNet[KOBUS 전산망]
    UosController <-->|HTTPS 잔여석 조회| UosNet[대학 수강신청 서버]

    KobusController -->|빈자리 3연타 푸시| DiscordWebhook[Discord Webhook (@everyone)]
    UosController -->|잔여석 3연타 푸시| DiscordWebhook
```

### 🎯 Alert Hub 주요 기능
- **단일 포트 통합 (`8000`)**: `http://localhost:8000` 접속만으로 모든 알리미 제어
- **모던 SPA 탭 네비게이션**:
  - 🚌 **KOBUS 고속버스 탭**: 전국 224개 터미널 연동, 출발/도착지 및 날짜/시간대 선택, 실시간 배차표 조회, 빈자리 감시 On/Off
  - 🎓 **UOS 수강신청 탭**: 개설년도/학기 선택, 단과대/학과/이수구분/학년 다차원 필터, 실시간 검색, 관심 과목 별표(⭐) Watchlist 등록/해제, 잔여석 감시 On/Off
  - 📊 **통합 현황 & 콘솔 탭**: 전체 서비스 가동 현황, 누적 점검 횟수, 실시간 통합 로그 스트림 한눈에 모니터링
- **Zero-Dependency**: `pip install` 불필요! Python 표준 라이브러리(`http.server`, `urllib`, `threading`, `json`)만으로 구동

---

## 🐳 Docker & Cloud 원클릭 24/7 배포

AWS EC2, GCP Compute Engine, Oracle Cloud, 홈서버 등 도커 환경이 갖춰진 곳이라면 **단 한 줄의 명령어로 24시간 무중단 가동**할 수 있습니다.

```bash
# 1. 저장소 클론 및 이동
git clone https://github.com/aidennis0297-art/realtime-alert-bots.git
cd realtime-alert-bots

# 2. Docker Compose 원클릭 실행 (백그라운드 가동)
docker-compose up -d

# 3. 가동 상태 및 로그 확인
docker-compose ps
docker-compose logs -f

# 4. 종료 시
docker-compose down
```
> 가동 후 웹 브라우저에서 `http://서버IP:8000`에 접속하면 즉시 통합 대시보드를 사용할 수 있습니다. (한국 시간 `Asia/Seoul` 자동 동기화)

---

## 💻 로컬 PC 원클릭 실행 (Windows / Mac / Linux)

### Windows
- 폴더 내 `run_hub.bat`을 더블 클릭하면 검은 콘솔창과 함께 웹 브라우저(`http://localhost:8000`)가 자동으로 열립니다.

### Mac / Linux
```bash
python3 hub_server.py
```

---

## 📱 [디스코드 세팅 및 스마트폰 알림 100% 수신 가이드 (필독!)](./DISCORD_SETUP_GUIDE.md)

빈자리 발생 즉시 스마트폰 잠금화면으로 **1.5초 간격 3연타 진동 푸시(@everyone)**를 받으려면 디스코드 웹훅 연동이 필수입니다.
- **[👉 디스코드 웹훅 생성 & 스마트폰 진동/소리 알림 완벽 설정 가이드 바로가기](./DISCORD_SETUP_GUIDE.md)**
  1. 디스코드 무료 개인 서버 및 `#알림` 채널 생성
  2. 웹훅(Webhook) URL 발급 및 복사
  3. 스마트폰(아이폰/갤럭시) `@everyone` 진동 및 잠금화면 알림 허용 설정
  4. 웹 GUI `[⚙️ 알림 설정]`에서 원클릭 테스트 발송

---

## 📦 포함된 개별 프로젝트 (독립 실행 지원)

통합 허브뿐만 아니라 필요에 따라 각 프로젝트 폴더에서 **독립된 웹 GUI 대시보드**로도 각각 실행할 수 있습니다.

### 1. 🚌 [kobus-seat-alert](./kobus-seat-alert) (포트 8081)
- **KOBUS 고속버스 실시간 잔여 좌석 감지 및 3연타 알리미**
- **독립 웹 GUI**: `run_gui.bat` 실행 시 `http://localhost:8081` 오픈
- **전국 노선 연동**: 224개 터미널 및 1,240개 노선 자동 연동, 실시간 배차 시간표 조회
- **4중 입체 알림**: 🔊 PC 사운드 비프음 + 🖥️ 화면 팝업 + 🌐 KOBUS 예매창 자동 오픈 + 📱 디스코드 3연타 모바일 푸시(@everyone)

### 2. 🎓 [uos-sugang-alert](./uos-sugang-alert) (포트 8080)
- **서울시립대학교(UOS) 수강신청 실시간 빈자리 알리미 & 웹 GUI 대시보드**
- **독립 웹 GUI**: `run_gui.bat` 실행 시 `http://localhost:8080` 오픈
- **동적 과목 탐색**: 년도/학기 선택 조회, 120+개 학과/학부 필터, 이수구분(전필/전선/교필/교선 등), 학년(1~4), 실시간 통합 검색
- **관심 과목 별표(⭐) Watchlist**: 테이블에서 ⭐ 클릭 시 실시간 감시 대상으로 등록/해제
- **3연속 모바일 푸시 알림**: 빈자리 발생 즉시 1.5초 간격 3회 연속 디스코드 푸시(@everyone)
- *※ 대학 학칙 준수를 위해 순수 "알림" 전용으로 제작 (자동 신청 매크로 미포함)*

### 3. 🛠️ [AUTOMATION_BLUEPRINT.md](./AUTOMATION_BLUEPRINT.md)
- **클라우드 24/7 자동 모니터링 시스템 아키텍처 청사진 & AI 프롬프트 명세서**
- GCP 한국 리전(`asia-northeast3`) + Python 표준 라이브러리 + systemd 데몬 + 디스코드 푸시 파이프라인
- 다른 티켓팅/예매 사이트로 시스템을 확장할 때 ChatGPT, Claude 등에 바로 복사해서 사용할 수 있는 표준 프롬프트 제공

---

## 💡 공통 아키텍처 핵심 요약

| 구성 요소 | 적용 기술 / 전략 | 장점 |
|---|---|---|
| **의존성 (Dependency)** | Python 3 내장 라이브러리만 사용 (`urllib`, `http.server`, `ssl`, `json`, `threading`) | `pip install` 불필요, 25MB 이하 극경량 메모리 점유 |
| **인터페이스 (UI)** | 모던 다크 테마 SPA 웹 대시보드 | 무거운 GUI 패키지 없이 브라우저에서 직관적인 제어 (포트 8000 통합 & 8080, 8081 독립 지원) |
| **컨테이너 (Docker)** | Python 3.11-slim 베이스 + docker-compose | `docker-compose up -d` 한 줄로 어디서나 24시간 무중단 가동 |
| **보안 통신 (SSL)** | `DEFAULT@SECLEVEL=1` | 구형 레거시 전산망 및 관공서 시스템 SSL 핸드셰이크 호환 |
| **알림 (Notification)** | 디스코드 웹훅 3연타 버스트 전송 | 화면 꺼짐/잠금 상태에서도 모바일 진동/소리로 확실한 인지 |
| **자가 복구 (Self-healing)** | 세션 자동 갱신 & 재시작 보장 (`restart: always`) | 예기치 않은 세션 만료나 서버 재부팅 시 자동 부활 |

---

## 📄 라이선스
MIT License
