# 🛠️ 클라우드 기반 24시간 자동 모니터링 & 디스코드 알리미 청사진 (Blueprint)

> 본 문서는 **GCP 한국 서버 + Python 표준 라이브러리 + systemd 데몬 + 디스코드 푸시 알림** 파이프라인의 전체 설계 내역과, 다른 프로젝트를 만들 때 AI에게 바로 전달할 수 있는 표준 프롬프트 명세서입니다.

---

## 📌 1. 시스템 아키텍처 및 사용 기술 명세

### 1) 클라우드 인프라 (Infrastructure)
* **제공사**: Google Cloud Platform (GCP)
* **서비스**: Compute Engine (가상 서버 VM)
* **머신 스펙**: `e2-micro` (2 vCPU, 1GB RAM)
* **리전**: `asia-northeast3` (한국 서울)
  * *국내 타겟 서비스 접속 시 레이턴시 1~3ms 초저지연 + 해외 IP 차단 필터 완벽 우회*
* **운영체제**: Debian GNU/Linux

### 2) 소프트웨어 스택 (Software Stack)
* **언어**: Python 3
* **외부 패키지 의존성**: **0개 (`pip install` 불필요)**
  * Python 내장 라이브러리(`urllib.request`, `http.cookiejar`, `ssl`, `json`, `re`, `threading`)만 사용하여 프로세스 메모리 사용량 25MB 이하 극경량화
* **보안 통신 (SSL)**: `DEFAULT@SECLEVEL=1` 적용으로 국내 구형 레거시 전산망 SSL 핸드셰이크 호환
* **세션 관리**: `CookieJar` 객체로 실제 브라우저와 동일한 쿠키 지속성 및 `User-Agent` 유지
* **탐색 간격**: 기본 6.0초 + 무작위 지연(-0.5초 ~ +1.0초) 적용으로 기계적 탐색 차단 우회

### 3) 영구 구동 및 안정성 (Systemd Daemon)
* **서비스 데몬**: 리눅스 표준 시스템 서비스 `/etc/systemd/system/*.service` 등록
* **자가 복구(Self-Healing)**: `Restart=always`, `RestartSec=5`로 예기치 않은 오류나 서버 재부팅 시 5초 내 자동 부활

### 4) 알림 파이프라인 (Notification Pipeline)
* **플랫폼**: 디스코드 웹훅 (Discord Webhook)
* **3연타 알림 (Burst Alert)**: 목표 조건 달성 시 놓치지 않도록 **1.5초 간격 3회 연속 `@everyone` 푸시 전송**
* **스마트 링크**: 알림 카드의 제목/링크 클릭 시 스마트폰에서 타겟 예약/조회 페이지로 즉시 이동
* **생존 보고(Heartbeat)**: 3시간마다 조용한 초록색 메시지로 누적 탐색 횟수 및 정상 동작 상태 보고

---

## 📋 2. 다른 AI에게 전달하는 표준 개발 요청 프롬프트

> 새로운 모니터링/알리미가 필요할 때, 아래 프롬프트의 **`[ ]`** 부분만 채워서 ChatGPT, Claude 등에 그대로 붙여넣으시면 동일한 아키텍처로 코드를 생성해 줍니다.

```markdown
[시스템 아키텍처 개발 요청서]

목표: 특정 웹사이트의 데이터 변동을 24시간 실시간으로 감지하여 디스코드로 푸시 알림을 전송하는 경량 백그라운드 프로그램을 작성해줘.

1. 타겟 정보 및 조건
- 대상 사이트/기능: [모니터링할 웹사이트 또는 기능 입력]
- 감지 조건: [알림을 울릴 조건 입력 (예: 잔여 좌석 > 0, 특정 공지 등록 등)]
- 모니터링 주기: 약 5~7초 (랜덤 지연 필수)

2. 기술 요구사항
- 언어: Python 3
- 라이브러리: pip 설치 없이 Python 표준 내장 라이브러리(urllib, http.cookiejar, ssl, json, re, threading)만 사용
- 세션/보안: 실제 브라우저 User-Agent 탑재, CookieJar 세션 유지, SSL SECLEVEL=1 호환성 처리
- 데이터 비교: 직전 상태(state)를 메모리에 캐싱하여 중복 알림 방지

3. 디스코드 알림 요구사항
- 알림 전송: 디스코드 웹훅(Webhook)
- 긴급 알림: 조건 달성 시 놓치지 않도록 1.5초 간격으로 3회 연속 푸시 전송 (@everyone 멘션 포함)
- 임베드 카드: 상세 정보 표시 및 클릭 시 타겟 페이지로 바로 이동하는 원클릭 링크 포함
- 생존 보고(하트비트): 3시간마다 누적 점검 횟수와 함께 조용한 상태 메시지 전송

4. Linux / GCP 배포 파일
- systemd 서비스 파일(.service)과 백그라운드 등록 명령어를 포함하여 재부팅 시에도 영구 자동 복구되도록 작성
```

---

## 🛠️ 3. 리눅스 서버 필수 명령어 요약

* **서비스 상태 확인**: `sudo systemctl status kobus.service`
* **서비스 중지 (예매 성공 후)**: `sudo systemctl stop kobus.service`
* **서비스 재시작**: `sudo systemctl restart kobus.service`
* **실시간 로그 확인**: `journalctl -u kobus.service -f`
* **서버 시간대 한국(KST) 설정**: `sudo timedatectl set-timezone Asia/Seoul`
