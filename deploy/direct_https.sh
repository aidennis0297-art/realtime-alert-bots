#!/usr/bin/env bash
# =============================================================================
# Cloudflare 터널 없이 고정 HTTPS 주소로 공개 — Caddy + sslip.io (도메인 불필요)
#
#   사전 준비 (GCP 콘솔):
#     1) VM 외부 IP를 "고정(static)"으로 예약   (VM 켜져 있는 동안 무료)
#     2) 방화벽: VM 편집 → "HTTP 트래픽 허용" + "HTTPS 트래픽 허용" 체크 (tcp 80/443)
#
#   VM 에서:
#     sudo bash /opt/realtime-alert-bots/deploy/direct_https.sh                     # → https://34-x-x-x.sslip.io
#     sudo DOMAIN=uoshub.kro.kr bash /opt/realtime-alert-bots/deploy/direct_https.sh # → 내 도메인 (A 레코드 필요)
#
#   결과: https://<외부IP를 -로 연결>.sslip.io  (예: 34.64.1.2 → https://34-64-1-2.sslip.io)
#         허브 설정의 자동 터널은 꺼지고, 이 고정 주소가 호스트 패널과 디스코드에 안내됩니다.
# =============================================================================
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/realtime-alert-bots}"
APP_USER="${APP_USER:-hub}"
PORT="${PORT:-8000}"

if [[ $EUID -ne 0 ]]; then echo "[!] sudo 로 실행하세요" >&2; exit 1; fi

echo "==> [1/4] 외부 IP 확인"
EXT_IP="${EXT_IP:-$(curl -fsS -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip 2>/dev/null || true)}"
if [[ -z "$EXT_IP" ]]; then EXT_IP=$(curl -fsS https://api.ipify.org || true); fi
if [[ -z "$EXT_IP" ]]; then echo "[!] 외부 IP를 알 수 없습니다. EXT_IP=1.2.3.4 로 지정해 다시 실행하세요." >&2; exit 1; fi
# DOMAIN=내도메인 으로 지정하면 그 도메인을 사용 (예: uoshub.kro.kr, uoshub.duckdns.org — A 레코드를 이 VM IP로 미리 등록)
if [[ -n "${DOMAIN:-}" ]]; then
  HOST_NAME="$DOMAIN"
  RESOLVED=$(getent hosts "$HOST_NAME" | awk '{print $1}' | head -1 || true)
  if [[ "$RESOLVED" != "$EXT_IP" ]]; then
    echo "[!] 경고: ${HOST_NAME} 이(가) ${RESOLVED:-'(미해석)'} 로 풀립니다. 이 VM IP(${EXT_IP})를 A 레코드로 등록했는지 확인하세요. (DNS 전파에 몇 분 걸릴 수 있음)"
  fi
else
  HOST_NAME="$(echo "$EXT_IP" | tr . -).sslip.io"
fi
PUBLIC_URL="https://${HOST_NAME}"
echo "    외부 IP: ${EXT_IP} → 주소: ${PUBLIC_URL}"

echo "==> [2/4] Caddy 설치"
if ! command -v caddy >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl gnupg >/dev/null
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy >/dev/null
fi
caddy version

echo "==> [3/4] 리버스 프록시 설정 (${HOST_NAME} → localhost:${PORT})"
cat > /etc/caddy/Caddyfile <<CADDY
${HOST_NAME} {
    encode gzip
    reverse_proxy localhost:${PORT}
}
CADDY
systemctl enable caddy >/dev/null 2>&1 || true
systemctl restart caddy

echo "==> [4/4] 허브 설정: 자동 터널 OFF, 고정 주소 등록"
python3 - "$APP_DIR/data/hub_settings.json" "$PUBLIC_URL" <<'PY'
import json, sys, os
p, url = sys.argv[1], sys.argv[2]
d = json.load(open(p)) if os.path.exists(p) else {}
d["auto_tunnel"] = False
d["public_url"] = url
json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
PY
chown "$APP_USER":"$APP_USER" "$APP_DIR/data/hub_settings.json" 2>/dev/null || true
systemctl restart alert-hub

echo "    인증서 발급 대기 (최대 60초)..."
OK=""
for i in $(seq 1 20); do
  sleep 3
  if curl -fsS -o /dev/null -m 8 "${PUBLIC_URL}/api/auth/me"; then OK=1; break; fi
done

echo
echo "=============================================================="
if [[ -n "$OK" ]]; then
  echo " ✅ 고정 HTTPS 주소 준비 완료: ${PUBLIC_URL}"
else
  echo " ⚠️  아직 응답이 없습니다. 아래를 확인하세요:"
  echo "    - GCP 방화벽에서 tcp 80/443 허용 (VM 편집 → HTTP/HTTPS 트래픽 허용)"
  echo "    - journalctl -u caddy -n 30 --no-pager   (인증서 발급 로그)"
  echo "    준비되면 주소는 ${PUBLIC_URL} 입니다."
fi
echo " 열람실 푸시용 주소(집 PC pusher_config.json): ${PUBLIC_URL}"
echo " 재부팅해도 주소가 유지됩니다 (고정 IP 예약 필수)."
echo "=============================================================="
