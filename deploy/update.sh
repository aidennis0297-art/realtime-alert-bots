#!/usr/bin/env bash
# 코드 업데이트: git pull 후 서비스 재시작 (data/ 는 그대로 유지)
#   sudo bash /opt/realtime-alert-bots/deploy/update.sh
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/realtime-alert-bots}"
APP_USER="${APP_USER:-hub}"
git -C "$APP_DIR" pull --ff-only

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
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
systemctl restart alert-hub
sleep 8
echo "외부 접속 URL: $(journalctl -u alert-hub --since '-1 min' --no-pager -o cat | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || echo '(발급 대기 중 — journalctl -u alert-hub -f)')"
systemctl --no-pager --lines=5 status alert-hub || true
