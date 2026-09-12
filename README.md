# 🚀 Realtime Alert Hub 2.0 (실시간 알리미 5대 올인원 포털 허브 & 양방향 디스코드 봇)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/Architecture-Zero--Dependency-success?style=for-the-badge" alt="Zero-Dependency" />
  <img src="https://img.shields.io/badge/Discord-2--Way_Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord Bot" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License" />
</p>

고속버스 취소표, KTX/SRT 열차, 메가박스 특별관 명당석, 대학교 수강신청 빈자리, 도서관 열람실 및 장학/해외파견 공지사항까지 **실시간 데이터 변동을 24시간 감시하고 디스코드 3연속 버스트 푸시 알림(@everyone) 및 스마트폰 양방향 원격 제어를 제공하는 올인원 관제 포털 허브**입니다.

---

## 🌟 올인원 통합 포털 허브 (Alert Hub 2.0)

개별 스크립트를 따로 띄울 필요 없이, **단 하나의 통합 웹 화면(`http://localhost:8000`)에서 5대 알리미를 한 번에 제어**할 수 있습니다.

```mermaid
graph TD
    User([사용자 브라우저 - http://localhost:8000]) <-->|통합 대시보드 SPA| HubServer[Alert Hub Server - hub_server.py]
    DiscordUser([스마트폰 디스코드 앱]) <-->|양방향 명령어 !버스| DiscordBot[Kobus Discord Bot - kobus_discord_bot.py]

    subgraph All-in-One Architecture
        HubServer --> KobusEngine[1. KOBUS 고속버스 엔진]
        HubServer --> TrainEngine[2. KTX / SRT 열차 엔진]
        HubServer --> CinemaEngine[3. 메가박스 특별관 엔진]
        HubServer --> SugangEngine[4. UOS 수강신청 엔진]
        HubServer --> CampusEngine[5. UOS 스마트캠퍼스 엔진]
        DiscordBot <--> KobusEngine
    end

    KobusEngine <-->|전국 224개 터미널 6대 권역| KobusNet[KOBUS 전산망]
    TrainEngine <-->|SRT NetFunnel 전산망 33개역| SrailNet[SRT / Korail 망]
    CinemaEngine <-->|전국 114개 극장 8대 권역| MegaboxNet[메가박스 전산망]
    SugangEngine <-->|3,026개 개설과목 실시간| SugangNet[대학 수강신청망]
    CampusEngine <-->|8개 열람실 + 4개 RSS| CampusNet[도서관 & 공지 포털]

    KobusEngine -->|빈자리 3연타 푸시| DiscordWebhook[Discord Webhook (@everyone)]
    TrainEngine -->|취소표 3연타 푸시| DiscordWebhook
    CinemaEngine -->|명당석 3연타 푸시| DiscordWebhook
    SugangEngine -->|결원 3연타 푸시| DiscordWebhook
    CampusEngine -->|키워드 공지 푸시| DiscordWebhook
```

---

## 🎯 5대 실시간 알리미 서비스 핵심 기능

### 1. 🚌 KOBUS 고속버스 취소표 알리미 & 📱 스마트폰 양방향 챗봇
- **전국 224개 터미널 6대 권역 분류**: 서울, 경기/인천, 강원, 대전/충청/세종, 광주/전라, 부산/대구/경상
- **다인승 연석 지원 (`min_seats`)**: 1석, 2석(연석), 3석, 4석 이상 필터
- **스마트폰 양방향 제어 디스코드 봇 (`kobus_discord_bot.py`)**:
  - 외출 중에도 스마트폰 디스코드 채팅창에 `!버스`만 치면 실시간 배차 즉시 조회
  - `!버스 시작 서울 대전` 입력 시 원격으로 백그라운드 24시간 감시 데몬 가동
  - `!버스 중지`, `!버스 상태`, `!터미널 서울`, `!도움말` 등 완벽 원격 제어 지원

### 2. 🚄 KTX / SRT 열차 취소표 알리미 (`train-seat-alert`)
- **전국 33개 주요 정차역 5대 권역 분류**: 서울/수도권(수서, 동탄, 평택지제), 대전/충청(천안아산, 오송, 대전, 공주), 대구/경북(동대구, 서대구, 포항), 부산/경남(부산, 울산, 창원, 마산, 진주), 광주/전라(광주송정, 전주, 여수EXPO, 목포 등)
- **SRT 모바일 NetFunnel 통신망 직통**: 초고속 배차 및 실시간 취소표 조회
- **일반실 & 특실/우등실 분리 감시**: 최소 잔여석 필터 지원 및 취소표 감지 시 디스코드 푸시 발송

### 3. 🎬 메가박스 영화관 특별관 & 명당 잔여석 알리미 (`cinema-seat-alert`)
- **전국 114개 극장 8개 광역시도 권역 분류**: 서울(18개), 경기(32개), 인천(7개), 대전/충청(16개), 부산/경상(25개), 광주/전라(9개), 강원(4개), 제주(3개)
- **특별관 전용 필터**: 돌비 시네마(Dolby Cinema), Dolby Atmos, Laser, Recliner, Comfort 등 프리미엄 상영관 집중 감시
- **인기 개봉작 명당 잔여석 감시**: 명당 취소표 및 최소 좌석수 기준 필터링 지원

### 4. 🎓 UOS 수강신청 빈자리 알리미 (`uos-sugang-alert`)
- **2026학년도 3,026개 개설과목 연동**: 년도/학기 선택, 단과대/학과/이수구분/학년 다차원 필터링
- **원클릭 별표(⭐) Watchlist**: 감시할 과목을 담아두면 24시간 실시간 결원 감지 및 3연타 디스코드 발송

### 5. 🏛️ UOS 스마트 캠퍼스 종합 관제
- **중앙/건축/경영도서관 8개 열람실 실시간 좌석**: 열람실별 총 좌석수, 사용 좌석, 잔여석, 실시간 점유율 프로그레스 바 제공
- **학사/장학/해외파견 공지사항 모아보기**:
  - 대학 RSS 4대 피드(학사, 장학, 일반, 뉴스) 로컬 캐시 및 실시간 동기화
  - 스마트 태그 자동 분류: `#장학금`, `#해외파견`, `#교환학생`, `#계절학기`, `#수강신청`, `#인턴십`, `#근로장학생`, `#휴복학`
  - 관심 키워드 백그라운드 실시간 감시 & 디스코드 알림 발송

---

## 🤖 KOBUS 스마트폰 디스코드 양방향 챗봇 사용법

외부에 있거나 컴퓨터를 켜지 않아도, **스마트폰 디스코드 앱에서 채팅으로 바로 실시간 조회 및 모니터링을 제어**할 수 있습니다.

### 1. 디스코드 봇 토큰 발급 (무료 1분)
1. [Discord Developer Portal](https://discord.com/developers/applications) 접속 후 **New Application** 생성
2. 좌측 메뉴 **Bot** 클릭 ➔ **Reset Token** 클릭하여 토큰 복사
3. **Privileged Gateway Intents** 섹션에서 **Message Content Intent** 체크 (ON)
4. 좌측 **OAuth2 ➔ URL Generator** ➔ Scopes: `bot`, Bot Permissions: `Send Messages`, `View Channels`, `Read Message History`, `Add Reactions` 선택 후 생성된 링크로 내 서버에 봇 초대

### 2. 설정 파일 (`config.json`) 입력
`kobus-seat-alert/config.json` (또는 `config.example.json` 복사):
```json
{
  "discord_bot": {
    "enabled": true,
    "bot_token": "여기에_발급받은_BOT_TOKEN_입력",
    "channel_id": "명령어를_입력할_채널_ID_입력",
    "prefix": "!"
  }
}
```

### 3. 챗봇 실행
- **Windows**: `kobus-seat-alert/run_discord_bot.bat` 더블 클릭!
- **Mac / Linux**:
  ```bash
  cd kobus-seat-alert
  python3 kobus_discord_bot.py
  ```

### 4. 사용 가능한 명령어
| 명령어 | 설명 | 예시 |
|---|---|---|
| `!버스` | 현재 설정된 노선의 실시간 잔여석 즉시 조회 | `!버스` |
| `!버스 [출발] [도착] [날짜]` | 특정 노선 및 날짜 배차 즉시 조회 | `!버스 서울 부산 20260925` |
| `!버스 시작` | 현재 설정된 노선으로 24시간 빈자리 감시 시작 | `!버스 시작` |
| `!버스 시작 [출발] [도착]` | 노선 변경 후 즉시 백그라운드 감시 시작 | `!버스 시작 서울 대전` |
| `!버스 중지` | 가동 중인 실시간 빈자리 감시 데몬 중지 | `!버스 중지` |
| `!버스 상태` | 현재 감시 상태 및 누적 점검 횟수 확인 | `!버스 상태` |
| `!터미널 [키워드]` | 전국 224개 터미널 이름 및 코드 검색 | `!터미널 광주`, `!터미널 센트럴` |
| `!도움말` | 전체 명령어 안내 임베드 출력 | `!help` |

---

## 💻 통합 허브 실행 방법

### Windows 원클릭 실행
- 최상위 폴더의 `run_hub.bat`을 더블 클릭하면 포트 `8000`에서 통합 허브가 실행되며 웹 브라우저(`http://localhost:8000`)가 자동으로 열립니다.

### Docker & Cloud 원클릭 24/7 배포
```bash
docker-compose up -d
```
> 브라우저에서 `http://서버IP:8000`에 접속하여 원격으로 5대 알리미를 모두 관리할 수 있습니다.
> `./data` 폴더가 볼륨으로 마운트되어 사용자 프로필/설정/관리자 키가 컨테이너 재시작 후에도 유지됩니다.

---

## 👥 멀티유저 & 호스트 관리 (Alert Hub 2.1)

Cloudflare 터널 등으로 허브를 외부에 공개하면 **여러 사람이 각자 다른 노선·학번·디스코드 웹훅**을 써야 합니다. 2.1부터는 프로필 단위로 설정과 감시 엔진이 완전히 분리됩니다.

```
data/
├── hub_settings.json         # 호스트 설정 (관리자 키, 등록 허용, 초대코드, 기본 웹훅, 자동 터널)
└── users/<uid>/
    ├── profile.json          # 프로필 (이름, PIN 해시)
    └── kobus.json, train.json, cinema.json, flight.json, uos.json, campus.json
```

| 역할 | 로그인 방법 | 할 수 있는 것 |
|---|---|---|
| **호스트** (서버 실행자) | 서버 콘솔에 출력되는 **관리자 키** (`data/hub_settings.json`) | 모든 기능 + 🛠️ 호스트 패널: 사용자 목록·가동 엔진 현황, 사용자 설정 열람/웹훅 일괄 지정/PIN 재설정/삭제, 신규 등록 허용·초대코드·최대 인원·기본 웹훅, **Cloudflare 터널 시작/중지 + 외부 URL·QR 코드** |
| **일반 사용자** | [새 프로필]에서 이름 + PIN 등록 → 이후 [로그인] | 본인 프로필의 6대 알리미 설정·감시 (다른 사용자와 완전 분리, 호스트 PC의 브라우저/사운드 알림은 사용하지 않음) |

- 기존 단일 사용자 시절의 `*/config.json`은 첫 실행 시 **호스트 프로필로 자동 마이그레이션**됩니다.
- 인증은 쿠키 + `X-Hub-Token` 헤더 둘 다 지원합니다. [내 프로필]에서 토큰을 복사해 iOS 단축어/스크립트에서 `curl -H "X-Hub-Token: ..." http://.../api/hub/status` 처럼 직접 API를 호출할 수 있습니다.
- 외부 공개는 호스트 패널 **[▶️ 터널 시작]** 한 번으로 끝납니다 (프로젝트 폴더의 `cloudflared.exe` 사용). 표시되는 `https://xxxx.trycloudflare.com` 주소나 QR을 공유하세요. 무료 Quick Tunnel은 재시작 시 URL이 바뀝니다.

### ☁️ GCP Compute Engine 24/7 배포 (권장: 서울 리전 e2-micro)
1. VM 만들기 — 리전 **asia-northeast3 (서울)**, 머신 **e2-micro** 또는 e2-small, OS Debian 12/13. 방화벽 포트는 열 필요 없음(Cloudflare 터널 사용).
2. VM의 **SSH(브라우저 창)** 에서 한 줄 실행:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/aidennis0297-art/realtime-alert-bots/main/deploy/gcp_setup.sh | sudo bash
   ```
   python3·cloudflared 설치 → `/opt/realtime-alert-bots` clone → `alert-hub` systemd 서비스 등록 → 터널 자동 가동 후 **관리자 키와 외부 접속 URL**을 출력합니다.
3. 출력된 `https://xxxx.trycloudflare.com` 으로 접속 → [호스트] 탭에 관리자 키 입력 → 각 알리미 ⚙️ 설정에서 웹훅/계정 입력.
- 코드 업데이트: `sudo bash /opt/realtime-alert-bots/deploy/update.sh` · 로그: `journalctl -u alert-hub -f`
- 서비스 재시작 시 Quick Tunnel URL이 바뀝니다. 고정 주소가 필요하면 Cloudflare 계정 + 도메인으로 Named Tunnel을 만들어 `cloudflared service install <token>` 하고 허브 설정의 자동 터널을 끄면 됩니다.

### 🔒 Cloudflare 없이 고정 HTTPS 주소로 쓰기 (권장)
터널 URL이 재시작마다 바뀌는 게 번거로우면, 도메인 없이 **`https://<IP>.sslip.io`** 고정 주소를 씁니다.
1. GCP 콘솔: VM 외부 IP를 **고정으로 예약**, VM 편집에서 **HTTP/HTTPS 트래픽 허용** 체크
2. VM: `sudo bash /opt/realtime-alert-bots/deploy/direct_https.sh` → Caddy 설치 + 인증서 자동 발급 + 허브의 자동 터널 OFF
3. 출력된 `https://34-x-x-x.sslip.io`가 고정 주소입니다 (디스코드에도 한 번 안내됨). 집 PC 열람실 푸시도 이 주소를 쓰면 됩니다.

### 🏛️ 열람실 좌석이 클라우드에서 안 보일 때 (집 PC 릴레이)
`library.uos.ac.kr`은 클라우드/해외 IP의 좌석 API 호출을 `/error/session`으로 차단합니다. VM 허브에서 열람실만 안 보이면 집 PC에서 좌석을 읽어 허브로 밀어 넣으세요.
1. 허브 관제 탭 → 호스트 패널 → 허브 설정의 **📚 열람실 푸시 키** 복사
2. 집 PC 프로젝트 폴더에 `tools/pusher_config.json` 생성: `{"hub": "http://VM외부IP:8000", "key": "lib_…"}`
   (VM 방화벽에서 tcp:8000 허용 + 고정 외부 IP 예약 권장. 터널 URL을 써도 되지만 재시작 시 바뀜)
3. `run_library_pusher.bat` 실행 → 20초마다 좌석을 허브로 전송, 열람실 탭에 "🏠 집 PC 릴레이" 표시로 나타남

### 📱 모바일 UI
같은 주소를 스마트폰으로 열면 하단 탭바 · 카드형 결과 목록 · 바텀시트 설정 화면으로 자동 전환됩니다. Safari/Chrome의 **"홈 화면에 추가"**로 앱처럼 설치할 수 있습니다 (PWA 매니페스트 포함).

---

## 📱 [디스코드 세팅 및 스마트폰 알림 100% 수신 가이드 (필독!)](./DISCORD_SETUP_GUIDE.md)
빈자리 발생 즉시 스마트폰 잠금화면으로 **1.5초 간격 3연타 진동 푸시(@everyone)**를 받으려면 디스코드 웹훅 연동이 필수입니다.
- **[👉 디스코드 웹훅 생성 & 스마트폰 진동/소리 알림 완벽 설정 가이드 바로가기](./DISCORD_SETUP_GUIDE.md)**

---

## 💡 Zero-Dependency 아키텍처 철학

| 항목 | 설계 내용 |
|---|---|
| **외부 패키지** | **0개** (`pip install` 불필요, Python 표준 라이브러리 `urllib`, `http.server`, `threading`, `json`만 사용) |
| **메모리 점유** | 전체 5대 서비스 통합 가동 시에도 약 **35MB** 내외의 초경량 리소스 점유 |
| **디스코드 봇** | 무거운 `discord.py`나 WebSocket 라이브러리 없이 순수 REST API 롱폴링으로 구현 |
| **한글 인코딩** | Windows 환경 한글 깨짐 방지를 위해 배치 파일 `CP949` 완벽 대응 |

---

## 📄 라이선스
MIT License
