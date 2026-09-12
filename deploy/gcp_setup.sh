#!/usr/bin/env bash
# =============================================================================
# Realtime Alert Hub 2.1 — GCP Compute Engine (Debian/Ubuntu) 원클릭 설치 스크립트
#
#   VM 브라우저 SSH 창에서:
#     curl -fsSL https://raw.githubusercontent.com/aidennis0297-art/realtime-alert-bots/main/deploy/gcp_setup.sh | sudo bash
#
#   하는 일:
#     1. python3 / git / cloudflared 설치, 타임존 Asia/Seoul
#     2. /opt/realtime-alert-bots 에 저장소 clone (이미 있으면 git pull)
#     3. systemd 서비스(alert-hub) 등록 — 재부팅/크래시 시 자동 재시작
#     4. 서버 시작 시 Cloudflare 터널 자동 가동(auto_tunnel) → 외부 HTTPS 주소 발급
#     5. 관리자 키와 외부 접속 URL 출력
# =============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/aidennis0297-art/realtime-alert-bots.git}"
APP_DIR="${APP_DIR:-/opt/realtime-alert-bots}"
APP_USER="${APP_USER:-hub}"
PORT="${PORT:-8000}"
SERVICE="alert-hub"

if [[ $EUID -ne 0 ]]; then
  echo "[!] root 권한이 필요합니다: sudo bash $0" >&2
  exit 1
fi

echo "==> [1/5] 패키지 설치 (python3, git, curl) + 타임존 Asia/Seoul"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 git curl ca-certificates >/dev/null
timedatectl set-timezone Asia/Seoul || true

echo "==> [2/5] cloudflared 설치"
if ! command -v cloudflared >/dev/null 2>&1; then
  ARCH=$(dpkg --print-architecture)   # amd64 / arm64
  curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}" -o /usr/local/bin/cloudflared
  chmod +x /usr/local/bin/cloudflared
fi
cloudflared --version

echo "==> [3/5] 앱 배치: ${APP_DIR}"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi
mkdir -p "$APP_DIR/data"
# 서버 첫 기동 시 터널 자동 가동 (secret/admin_key 는 hub_server.py 가 채워 넣음)
if [[ ! -f "$APP_DIR/data/hub_settings.json" ]]; then
  echo '{"auto_tunnel": true}' > "$APP_DIR/data/hub_settings.json"
fi
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

# (선택) NOTIFY_WEBHOOK=https://discord.com/api/webhooks/... 환경변수가 있으면 터널 주소 알림 웹훅으로 저장
if [[ -n "${NOTIFY_WEBHOOK:-}" ]]; then
  python3 - "$APP_DIR/data/hub_settings.json" "$NOTIFY_WEBHOOK" <<'PY'
import json, sys, os
p, hook = sys.argv[1], sys.argv[2]
d = json.load(open(p)) if os.path.exists(p) else {}
d["notify_webhook"] = hook; d["notify_on_tunnel_url"] = True
json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
print("notify_webhook 저장됨")
PY
fi

echo "==> [4/5] systemd 서비스 등록: ${SERVICE}"
cat > /etc/systemd/system/${SERVICE}.service <<EOF
[Unit]
Description=Realtime Alert Hub 2.1 (multi-user alert portal)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=HUB_NO_BROWSER=1
Environment=HUB_HEADLESS=1
Environment=HUB_PORT=${PORT}
Environment=TZ=Asia/Seoul
ExecStart=/usr/bin/python3 ${APP_DIR}/hub_server.py --no-browser
Restart=always
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null
systemctl restart "$SERVICE"

echo "==> [5/5] 기동 대기 (터널 URL 발급까지 최대 40초)"
URL=""
for i in $(seq 1 20); do
  sleep 2
  URL=$(journalctl -u "$SERVICE" --since "-2 min" --no-pager -o cat 2>/dev/null | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true)
  [[ -n "$URL" ]] && break
done
ADMIN_KEY=$(python3 -c "import json;print(json.load(open('${APP_DIR}/data/hub_settings.json'))['admin_key'])" 2>/dev/null || echo "(data/hub_settings.json 확인)")

echo
echo "=============================================================="
echo " ✅ Realtime Alert Hub 설치 완료"
echo "=============================================================="
echo " 로컬 주소        : http://localhost:${PORT}  (VM 내부)"
echo " 외부 접속 URL    : ${URL:-'(아직 발급 전) → journalctl -u alert-hub -f 로 확인'}"
echo " 🔑 호스트 관리자 키: ${ADMIN_KEY}"
echo
echo " 상태 확인  : systemctl status ${SERVICE}"
echo " 실시간 로그: journalctl -u ${SERVICE} -f"
echo " 코드 업데이트: sudo bash ${APP_DIR}/deploy/update.sh"
echo
echo " ※ 무료 Quick Tunnel 은 서비스가 재시작될 때마다 URL 이 바뀝니다."
echo "    (재부팅/업데이트 후 새 URL 은 호스트 패널 또는 journalctl 에서 확인)"
echo "=============================================================="
