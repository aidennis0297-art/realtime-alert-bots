#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Realtime Alert Hub 2.1 (실시간 알리미 멀티유저 통합 포털 허브)
- 포트: 8000 (기본값)
- 6대 통합 모니터링 서비스 (고속버스 / KTX·SRT / 영화관 / 항공권 / UOS 수강신청 / UOS 스마트캠퍼스)
- 멀티유저: 사용자(프로필)마다 독립된 설정 파일 + 독립된 감시 엔진 인스턴스
    data/
      hub_settings.json          # 호스트 설정 (관리자 키, 등록 허용 여부, 초대코드 ...)
      users/<uid>/profile.json   # 프로필 (이름, PIN 해시)
      users/<uid>/<engine>.json  # 엔진별 설정 (kobus / train / cinema / flight / uos / campus)
- 호스트(관리자): 관리자 키로 로그인 → 사용자 데이터 열람/정리, Cloudflare 터널 제어
- Zero-dependency: Python 3 표준 내장 라이브러리만 사용
"""

import os
import re
import sys
import json
import time
import hmac
import shutil
import socket
import secrets
import hashlib
import threading
import subprocess
import webbrowser
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Windows 콘솔 한글 UTF-8 출력 보정
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_HUB_DIR = os.path.join(BASE_DIR, "web_hub")
INDEX_FILE = os.path.join(WEB_HUB_DIR, "index.html")
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_DIR = os.path.join(DATA_DIR, "users")
SETTINGS_FILE = os.path.join(DATA_DIR, "hub_settings.json")
HOST_UID = "host"
SERVER_STARTED_AT = time.time()
# 헤드리스(리눅스 서버·Docker·클라우드 VM): 어떤 사용자도 서버 PC의 브라우저/사운드/팝업 알림을 쓰지 않는다
HEADLESS = (sys.platform != "win32") or os.environ.get("HUB_HEADLESS") == "1" or os.environ.get("DOCKER_CONTAINER") == "1"

# 서브모듈 sys.path 등록
sub_paths = [
    os.path.join(BASE_DIR, "kobus-seat-alert"),
    os.path.join(BASE_DIR, "train-seat-alert"),
    os.path.join(BASE_DIR, "cinema-seat-alert"),
    os.path.join(BASE_DIR, "uos-sugang-alert"),
    os.path.join(BASE_DIR, "flight-seat-alert")
]
for p in sub_paths:
    if p not in sys.path:
        sys.path.insert(0, p)

from bus_alert import KobusMonitor
from train_alert import TrainMonitor, STATION_REGIONS
from cinema_alert import CinemaMonitor
from uos_sugang_alert import UosSugangMonitor
from uos_campus_alert import UosCampusMonitor, RECOMMENDED_TAGS
from flight_alert import FlightMonitor, POPULAR_ROUTES, AIRPORTS

ENGINE_KEYS = ["kobus", "train", "cinema", "flight", "uos", "campus"]
ENGINE_LABELS = {
    "kobus": "🚌 고속버스", "train": "🚄 KTX/SRT", "cinema": "🎬 영화관",
    "flight": "✈️ 항공권", "uos": "🎓 수강신청", "campus": "🏛️ 캠퍼스"
}
# 기존 단일 사용자 시절의 설정 파일 → 호스트 계정으로 마이그레이션
LEGACY_CONFIGS = {
    "kobus": os.path.join(BASE_DIR, "kobus-seat-alert", "config.json"),
    "train": os.path.join(BASE_DIR, "train-seat-alert", "config.json"),
    "cinema": os.path.join(BASE_DIR, "cinema-seat-alert", "config.json"),
    "flight": os.path.join(BASE_DIR, "flight-seat-alert", "config.json"),
    "uos": os.path.join(BASE_DIR, "uos-sugang-alert", "config.json"),
    "campus": os.path.join(BASE_DIR, "uos-sugang-alert", "campus_config.json"),
}
EXAMPLE_CONFIGS = {
    "kobus": os.path.join(BASE_DIR, "kobus-seat-alert", "config.example.json"),
    "train": os.path.join(BASE_DIR, "train-seat-alert", "config.example.json"),
    "cinema": os.path.join(BASE_DIR, "cinema-seat-alert", "config.example.json"),
    "flight": os.path.join(BASE_DIR, "flight-seat-alert", "config.example.json"),
    "uos": os.path.join(BASE_DIR, "uos-sugang-alert", "config.example.json"),
}


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# =====================================================================
# 1. 허브(호스트) 설정
# =====================================================================
class HubSettings:
    DEFAULTS = {
        "registration_open": True,     # 신규 프로필 등록 허용
        "invite_code": "",             # 비어 있으면 초대코드 불필요
        "max_users": 20,
        "default_webhook": "",         # 신규 사용자 엔진 설정에 기본 주입할 디스코드 웹훅
        "auto_tunnel": False,          # 서버 시작 시 Cloudflare 터널 자동 가동
        "notify_webhook": "",          # 터널 URL 변경 알림용 디스코드 웹훅 (비우면 호스트 프로필 엔진 웹훅 사용)
        "notify_on_tunnel_url": True,  # 터널 URL 발급/변경 시 디스코드로 새 주소 전송
        "last_tunnel_url": "",         # 마지막으로 알린 터널 URL (변경 감지용)
    }

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        data = read_json(path, {}) or {}
        changed = False
        if not data.get("secret"):
            data["secret"] = secrets.token_hex(32)
            changed = True
        if not data.get("admin_key"):
            data["admin_key"] = "-".join(secrets.token_hex(2).upper() for _ in range(3))
            changed = True
        if not data.get("created_at"):
            data["created_at"] = now_iso()
            changed = True
        for k, v in self.DEFAULTS.items():
            if k not in data:
                data[k] = v
                changed = True
        self.data = data
        if changed:
            write_json(path, data)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, patch):
        with self.lock:
            for k in self.DEFAULTS:
                if k in patch:
                    self.data[k] = patch[k]
            write_json(self.path, self.data)

    def public(self):
        return {k: self.data.get(k) for k in self.DEFAULTS}

    def regenerate_admin_key(self):
        with self.lock:
            self.data["admin_key"] = "-".join(secrets.token_hex(2).upper() for _ in range(3))
            write_json(self.path, self.data)
            return self.data["admin_key"]


SETTINGS = HubSettings(SETTINGS_FILE)


# =====================================================================
# 2. 사용자 저장소 (프로필 + PIN)
# =====================================================================
def hash_pin(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt), 120_000).hex()


class UserStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.users = {}          # uid -> profile dict
        self._last_touch_saved = {}
        os.makedirs(USERS_DIR, exist_ok=True)
        self.load_all()
        self.ensure_host()

    def user_dir(self, uid):
        return os.path.join(USERS_DIR, uid)

    def profile_path(self, uid):
        return os.path.join(self.user_dir(uid), "profile.json")

    def load_all(self):
        with self.lock:
            self.users = {}
            for uid in os.listdir(USERS_DIR):
                p = read_json(self.profile_path(uid))
                if p and p.get("uid") == uid:
                    self.users[uid] = p

    def save(self, profile):
        write_json(self.profile_path(profile["uid"]), profile)

    def ensure_host(self):
        if HOST_UID not in self.users:
            self.create("호스트", None, uid=HOST_UID, is_host=True)

    def find_by_name(self, name):
        key = (name or "").strip().lower()
        with self.lock:
            for p in self.users.values():
                if p.get("name", "").strip().lower() == key:
                    return p
        return None

    def create(self, name, pin, uid=None, is_host=False):
        with self.lock:
            uid = uid or secrets.token_hex(4)
            while uid in self.users:
                uid = secrets.token_hex(4)
            salt = secrets.token_hex(16)
            profile = {
                "uid": uid,
                "name": name.strip(),
                "is_host": is_host,
                "salt": salt,
                "pin_hash": hash_pin(pin, salt) if pin else "",
                "created_at": now_iso(),
                "last_seen": now_iso(),
            }
            os.makedirs(self.user_dir(uid), exist_ok=True)
            self.save(profile)
            self.users[uid] = profile
            return profile

    def verify_pin(self, profile, pin):
        if not profile.get("pin_hash"):
            return False
        return hmac.compare_digest(profile["pin_hash"], hash_pin(pin or "", profile["salt"]))

    def set_pin(self, uid, pin):
        with self.lock:
            p = self.users.get(uid)
            if not p:
                return False
            p["salt"] = secrets.token_hex(16)
            p["pin_hash"] = hash_pin(pin, p["salt"])
            self.save(p)
            return True

    def rename(self, uid, name):
        with self.lock:
            p = self.users.get(uid)
            if not p:
                return False
            p["name"] = name.strip()
            self.save(p)
            return True

    def touch(self, uid):
        with self.lock:
            p = self.users.get(uid)
            if not p:
                return
            p["last_seen"] = now_iso()
            last = self._last_touch_saved.get(uid, 0)
            if time.time() - last > 60:
                self._last_touch_saved[uid] = time.time()
                try:
                    self.save(p)
                except Exception:
                    pass

    def delete(self, uid):
        with self.lock:
            if uid == HOST_UID or uid not in self.users:
                return False
            self.users.pop(uid, None)
            shutil.rmtree(self.user_dir(uid), ignore_errors=True)
            return True

    def public_profile(self, p):
        return {
            "uid": p["uid"], "name": p["name"], "is_host": bool(p.get("is_host")),
            "created_at": p.get("created_at"), "last_seen": p.get("last_seen"),
            "has_pin": bool(p.get("pin_hash")),
        }


USERS = UserStore()


# =====================================================================
# 3. 사용자별 감시 엔진 묶음
# =====================================================================
WEBHOOK_RE = re.compile(r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")


def is_valid_webhook(url):
    return bool(url) and bool(WEBHOOK_RE.match(url.strip()))


def sanitize_placeholders(key, cfg):
    """config.example.json 에서 유래한 플레이스홀더 값을 비운다 (잘못된 웹훅으로 400 나는 것 방지)"""
    disc = cfg.get("discord")
    if isinstance(disc, dict):
        hook = (disc.get("webhook_url") or "").strip()
        if hook and not is_valid_webhook(hook):
            disc["webhook_url"] = ""
    if key == "uos":
        if str(cfg.get("password", "")).strip().upper() in ("YOUR_PASSWORD", "PASSWORD"):
            cfg["password"] = ""
        if str(cfg.get("student_id", "")).strip() == "2024000000":
            cfg["student_id"] = ""


class UserEngines:
    """한 사용자에게 귀속된 6개의 독립 감시 엔진"""

    def __init__(self, uid):
        self.uid = uid
        self.is_host = (uid == HOST_UID)
        self.user_dir = USERS.user_dir(uid)
        os.makedirs(self.user_dir, exist_ok=True)
        self.created_at = time.time()

        paths = {k: os.path.join(self.user_dir, f"{k}.json") for k in ENGINE_KEYS}
        fresh = {k: not os.path.exists(paths[k]) for k in ENGINE_KEYS}
        for k in ENGINE_KEYS:
            if fresh[k]:
                self._seed_config(k, paths[k])

        self.kobus = KobusMonitor(paths["kobus"])
        self.train = TrainMonitor(paths["train"])
        self.cinema = CinemaMonitor(paths["cinema"])
        self.flight = FlightMonitor(paths["flight"])
        self.uos = UosSugangMonitor(paths["uos"])
        self.campus = UosCampusMonitor(paths["campus"])

        # 원격(비호스트) 사용자는 호스트 PC의 브라우저/사운드/팝업 알림을 쓰지 않는다
        for k in ENGINE_KEYS:
            eng = getattr(self, k)
            sanitize_placeholders(k, eng.config)
            if HEADLESS:
                # 서버에 화면/스피커가 없으므로 (메모리상에서만) 로컬 알림을 끈다 — 디스코드 알림만 사용
                eng.config["auto_open_browser"] = False
                eng.config["sound_alert"] = False
                eng.config["popup_alert"] = False
            if fresh[k]:
                if not self.is_host:
                    eng.config["auto_open_browser"] = False
                    eng.config["sound_alert"] = False
                    eng.config["popup_alert"] = False
                default_hook = SETTINGS.get("default_webhook") or ""
                disc = eng.config.get("discord") or {}
                if default_hook and not disc.get("webhook_url"):
                    disc["webhook_url"] = default_hook
                    disc.setdefault("mention", "@everyone")
                    eng.config["discord"] = disc
                try:
                    eng.save_config()
                except Exception:
                    pass

    def _seed_config(self, key, dest):
        """신규 설정 파일 시드
        - 호스트: 기존 단일 사용자 시절 config.json → (없으면) 엔진 기본값
        - 일반 사용자: 엔진 기본값 (예시 학번/플레이스홀더 웹훅이 섞이지 않도록 example은 쓰지 않음)
        """
        if not self.is_host:
            return
        src = LEGACY_CONFIGS.get(key, "")
        if src and os.path.exists(src):
            try:
                shutil.copyfile(src, dest)
            except Exception:
                pass

    def all(self):
        return [(k, getattr(self, k)) for k in ENGINE_KEYS]

    @staticmethod
    def _running(eng):
        return bool(getattr(eng, "is_running", getattr(eng, "running", False)))

    def running_map(self):
        return {k: self._running(e) for k, e in self.all()}

    def running_count(self):
        return sum(1 for v in self.running_map().values() if v)

    def status(self):
        return {
            "kobus": self.kobus.get_status(),
            "train": self.train.get_status(),
            "cinema": self.cinema.get_status(),
            "uos_sugang": self.uos.get_status(),
            "uos_campus": self.campus.get_status(),
            "flight": self.flight.get_status(),
        }

    def start_all(self):
        for _, e in self.all():
            try:
                e.start_monitoring()
            except Exception:
                pass

    def stop_all(self):
        for _, e in self.all():
            try:
                e.stop_monitoring()
            except Exception:
                pass

    def summary(self):
        """호스트 관리 화면용 축약 상태"""
        out = {}
        for k, e in self.all():
            cfg = e.config or {}
            if k in ("kobus", "train"):
                desc = f"{cfg.get('departure_name', '')} ➔ {cfg.get('arrival_name', '')} · {cfg.get('date', '')}"
            elif k == "cinema":
                desc = f"{cfg.get('brand', '')} {cfg.get('theater_name', '')} · {cfg.get('date', '')}"
            elif k == "flight":
                desc = f"{cfg.get('dep_code', '')} ➔ {cfg.get('arr_code', '')} · {cfg.get('date', '')} · ≤{cfg.get('max_price', '')}원"
            elif k == "uos":
                desc = f"감시 {len(cfg.get('target_courses', []))}과목 · ID {'설정됨' if cfg.get('student_id') else '없음'}"
            else:
                desc = "키워드: " + ", ".join((cfg.get("watch_keywords") or [])[:3])
            hook = (cfg.get("discord") or {}).get("webhook_url") or ""
            out[k] = {
                "label": ENGINE_LABELS[k],
                "running": self._running(e),
                "check_count": getattr(e, "check_count", 0),
                "desc": desc,
                "webhook_set": hook.startswith("http"),
                "last_log": (list(e.recent_logs)[-1] if getattr(e, "recent_logs", None) else ""),
            }
        return out


ENGINES = {}
ENGINES_LOCK = threading.Lock()


def get_engines(uid):
    with ENGINES_LOCK:
        eng = ENGINES.get(uid)
        if eng is None:
            eng = UserEngines(uid)
            ENGINES[uid] = eng
        return eng


def drop_engines(uid):
    with ENGINES_LOCK:
        eng = ENGINES.pop(uid, None)
    if eng:
        eng.stop_all()


def stop_everything():
    with ENGINES_LOCK:
        items = list(ENGINES.values())
    for e in items:
        e.stop_all()


# =====================================================================
# 3-1. 즐겨찾기 (노선/극장/항공편 프리셋) — 사용자별 data/users/<uid>/favorites.json
# =====================================================================
FAV_SERVICES = {"kobus", "train", "cinema", "flight"}
FAV_LOCK = threading.Lock()
FAV_MAX = 40


def fav_path(uid):
    return os.path.join(USERS.user_dir(uid), "favorites.json")


def load_favorites(uid):
    data = read_json(fav_path(uid), []) or []
    return [f for f in data if isinstance(f, dict) and f.get("service") in FAV_SERVICES]


def save_favorites(uid, favs):
    write_json(fav_path(uid), favs)


# =====================================================================
# 4. Cloudflare 터널 관리자
# =====================================================================
class TunnelManager:
    URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

    def __init__(self, base_dir):
        self.lock = threading.Lock()
        self.proc = None
        self.url = ""
        self.started_at = None
        self.log_tail = []
        self.port = None
        self.on_url = None          # URL 발급 시 호출되는 콜백 (디스코드 알림 등)
        self.exe = self._find_exe(base_dir)

    @staticmethod
    def _find_exe(base_dir):
        local = os.path.join(base_dir, "cloudflared.exe" if sys.platform == "win32" else "cloudflared")
        if os.path.exists(local):
            return local
        return shutil.which("cloudflared")

    def _log(self, line):
        self.log_tail.append(line.rstrip()[:300])
        if len(self.log_tail) > 60:
            self.log_tail.pop(0)

    def is_running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, port):
        with self.lock:
            if self.is_running():
                return True, "터널이 이미 가동 중입니다."
            if not self.exe:
                return False, "cloudflared 실행 파일을 찾을 수 없습니다. (프로젝트 폴더에 cloudflared.exe 배치)"
            self.url = ""
            self.log_tail = []
            self.port = port
            cmd = [self.exe, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"]
            kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True,
                      "encoding": "utf-8", "errors": "replace", "bufsize": 1}
            if sys.platform == "win32":
                kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
            try:
                self.proc = subprocess.Popen(cmd, **kwargs)
            except Exception as e:
                return False, f"터널 실행 실패: {e}"
            self.started_at = time.time()
            threading.Thread(target=self._reader, daemon=True).start()
            return True, "Cloudflare 터널을 시작했습니다. 잠시 후 외부 접속 URL이 표시됩니다."

    def _reader(self):
        proc = self.proc
        try:
            for line in proc.stdout:
                self._log(line)
                if not self.url:
                    m = self.URL_RE.search(line)
                    if m:
                        self.url = m.group(0)
                        print(f"🌐 [Tunnel] 외부 접속 URL: {self.url}")
                        if self.on_url:
                            threading.Thread(target=self.on_url, args=(self.url,), daemon=True).start()
        except Exception:
            pass

    def stop(self):
        with self.lock:
            if not self.is_running():
                self.proc = None
                self.url = ""
                return True, "터널이 가동 중이 아닙니다."
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=4)
                except Exception:
                    self.proc.kill()
            except Exception:
                pass
            self.proc = None
            self.url = ""
            self.started_at = None
            return True, "터널을 중지했습니다."

    def status(self):
        running = self.is_running()
        return {
            "available": bool(self.exe),
            "exe": self.exe or "",
            "running": running,
            "url": self.url if running else "",
            "port": self.port,
            "uptime_sec": int(time.time() - self.started_at) if (running and self.started_at) else 0,
            "log_tail": self.log_tail[-12:],
        }


TUNNEL = TunnelManager(BASE_DIR)


# =====================================================================
# 4-1. 터널 URL 디스코드 알림
# =====================================================================
def resolve_notify_webhook():
    """알림 웹훅: 허브 설정 → (없으면) 호스트 프로필의 6개 엔진 설정 중 첫 번째 웹훅"""
    hook = (SETTINGS.get("notify_webhook") or "").strip()
    if is_valid_webhook(hook):
        return hook
    host_dir = USERS.user_dir(HOST_UID)
    for k in ENGINE_KEYS:
        cfg = read_json(os.path.join(host_dir, f"{k}.json"), {}) or {}
        h = ((cfg.get("discord") or {}).get("webhook_url") or "").strip()
        if is_valid_webhook(h):
            return h
    return ""


def post_discord(webhook, payload):
    import urllib.request
    import urllib.error
    req = urllib.request.Request(
        webhook, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "AlertHub/2.1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} {body}".strip())


def notify_tunnel_url(url, force=False):
    """터널 URL이 새로 발급/변경되면 디스코드로 주소와 QR을 보낸다. force=True면 같은 주소여도 재전송."""
    if not url:
        return False, "가동 중인 터널 URL이 없습니다."
    if not force and not SETTINGS.get("notify_on_tunnel_url"):
        return False, "터널 URL 알림이 꺼져 있습니다."
    prev = SETTINGS.get("last_tunnel_url") or ""
    if not force and prev == url:
        return False, "이미 알린 주소입니다."
    hook = resolve_notify_webhook()
    if not hook:
        return False, "알림에 사용할 유효한 디스코드 웹훅이 없습니다. (호스트 패널 > 허브 설정 > 터널 주소 알림 웹훅 입력)"
    qr = "https://api.qrserver.com/v1/create-qr-code/?size=220x220&margin=8&data=" + url
    invite = (SETTINGS.get("invite_code") or "").strip()
    desc = "👉 **[여기를 눌러 접속]({0})**".format(url)
    if invite:
        desc += "\n초대코드: `{0}`".format(invite)
    desc += "\n\n📱 QR을 폰 카메라로 스캔해도 됩니다. 홈 화면에 추가하면 앱처럼 쓸 수 있어요."
    head = "🌐 Alert Hub 외부 접속 주소가 " + ("갱신되었습니다" if prev else "발급되었습니다") + "!"
    payload = {
        # 본문에 원문 URL을 <...> 로 넣으면 클릭 가능한 링크가 되고, 디스코드 자동 미리보기(중복 임베드)는 억제된다
        "content": "@everyone " + head + "\n<" + url + ">",
        "embeds": [{
            "title": "⚡ Realtime Alert Hub 접속하기",
            "url": url,
            "description": desc,
            "color": 0x3B82F6,
            "image": {"url": qr},
            "footer": {"text": f"서버 기동 {datetime.fromtimestamp(SERVER_STARTED_AT).strftime('%m/%d %H:%M')} · 주소는 서버 재시작 시 바뀌며 그때마다 다시 알려드립니다"}
        }]
    }
    try:
        post_discord(hook, payload)
        SETTINGS.update({"last_tunnel_url": url})
        print(f"📣 [Tunnel] 새 접속 주소를 디스코드로 알렸습니다: {url}")
        return True, "디스코드로 접속 주소를 전송했습니다."
    except Exception as e:
        print(f"[!] [Tunnel] 디스코드 알림 실패: {e}")
        return False, f"디스코드 전송 실패: {e}"


TUNNEL.on_url = notify_tunnel_url


# =====================================================================
# 5. 인증 토큰
# =====================================================================
def make_token(uid):
    sig = hmac.new(SETTINGS.get("secret").encode("utf-8"), uid.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{uid}.{sig}"


def verify_token(token):
    if not token or "." not in token:
        return None
    uid, sig = token.split(".", 1)
    if uid not in USERS.users:
        return None
    if hmac.compare_digest(make_token(uid), f"{uid}.{sig}"):
        return uid
    return None


def masked_uos_config(cfg, period):
    return {
        "student_id": cfg.get("student_id", ""),
        "password": "",
        "has_password": bool(cfg.get("password")),
        "device": cfg.get("device", "PC"),
        "year": cfg.get("year", period["year"]),
        "semester": cfg.get("semester", period["semester"]),
        "academic_period": period,
        "target_courses": cfg.get("target_courses", []),
        "check_interval_seconds": cfg.get("check_interval_seconds", 6),
        "discord": cfg.get("discord", {})
    }


# =====================================================================
# 6. HTTP 핸들러
# =====================================================================
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


class AlertHubHandler(BaseHTTPRequestHandler):
    server_version = "AlertHub/2.1"

    # ---------- 응답 헬퍼 ----------
    def send_json(self, data, status=200, extra_headers=None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, rel_path):
        safe = os.path.normpath(rel_path).lstrip(os.sep).lstrip("/")
        full = os.path.join(WEB_HUB_DIR, safe)
        if not os.path.abspath(full).startswith(os.path.abspath(WEB_HUB_DIR)) or not os.path.isfile(full):
            self.send_error(404, "Not Found")
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = STATIC_TYPES.get(ext)
        if not ctype:
            self.send_error(404, "Not Found")
            return
        with open(full, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Hub-Token")
        self.end_headers()

    def log_message(self, format, *args):
        return

    # ---------- 인증 ----------
    def current_uid(self):
        token = self.headers.get("X-Hub-Token", "")
        if not token:
            raw = self.headers.get("Cookie", "")
            if raw:
                try:
                    c = SimpleCookie()
                    c.load(raw)
                    if "hub_token" in c:
                        token = c["hub_token"].value
                except Exception:
                    token = ""
        uid = verify_token(token)
        if uid:
            USERS.touch(uid)
        return uid

    def auth_cookie_header(self, token):
        return ("Set-Cookie", f"hub_token={token}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax")

    def require_login(self):
        uid = self.current_uid()
        if not uid:
            self.send_json({"success": False, "error": "auth_required", "message": "로그인이 필요합니다."}, status=401)
        return uid

    def require_host(self):
        uid = self.current_uid()
        if not uid:
            self.send_json({"success": False, "error": "auth_required", "message": "로그인이 필요합니다."}, status=401)
            return None
        if not USERS.users.get(uid, {}).get("is_host"):
            self.send_json({"success": False, "error": "forbidden", "message": "호스트(관리자) 권한이 필요합니다."}, status=403)
            return None
        return uid

    def read_body(self):
        content_len = int(self.headers.get("Content-Length", 0) or 0)
        post_data = self.rfile.read(content_len).decode("utf-8", errors="replace") if content_len > 0 else "{}"
        try:
            return json.loads(post_data) if post_data else {}
        except Exception:
            return {}

    # =====================================================================
    # GET
    # =====================================================================
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # 0. 정적 파일
        if path in ("/", "/index.html"):
            if os.path.exists(INDEX_FILE):
                self.send_static("index.html")
            else:
                self.send_error(404, "web_hub/index.html not found")
            return
        if not path.startswith("/api/"):
            self.send_static(path)
            return

        # 1. 인증 상태
        if path == "/api/auth/me":
            uid = self.current_uid()
            if not uid:
                self.send_json({
                    "logged_in": False,
                    "registration_open": bool(SETTINGS.get("registration_open")),
                    "invite_required": bool(SETTINGS.get("invite_code")),
                })
                return
            p = USERS.users[uid]
            self.send_json({
                "logged_in": True,
                "user": USERS.public_profile(p),
                "token": make_token(uid),
                "registration_open": bool(SETTINGS.get("registration_open")),
                "invite_required": bool(SETTINGS.get("invite_code")),
            })
            return

        # 2. 호스트 관리 API
        if path.startswith("/api/admin/"):
            self.handle_admin_get(path, qs)
            return

        # 3. 사용자 엔진 API (로그인 필수)
        uid = self.require_login()
        if not uid:
            return
        eng = get_engines(uid)

        if path == "/api/favorites":
            self.send_json({"favorites": load_favorites(uid)})
            return

        if path == "/api/hub/status":
            st = eng.status()
            st["_user"] = {"uid": uid, "name": USERS.users[uid]["name"], "is_host": bool(USERS.users[uid].get("is_host"))}
            self.send_json(st)
            return

        # ---- KOBUS ----
        if path == "/api/kobus/terminals":
            self.send_json(eng.kobus.fetch_terminals())
            return
        if path == "/api/kobus/config":
            self.send_json(eng.kobus.config)
            return
        if path == "/api/kobus/schedule":
            cfg = eng.kobus.config
            depr_cd = qs.get("deprCd", [cfg.get("departure_terminal", "010")])[0]
            arvl_cd = qs.get("arvlCd", [cfg.get("arrival_terminal", "700")])[0]
            date = qs.get("date", [cfg.get("date", "")])[0]
            min_time = qs.get("minTime", [cfg.get("min_time", "00:00")])[0]
            max_time = qs.get("maxTime", [cfg.get("max_time", "23:59")])[0]
            buses = eng.kobus.query_timetable(depr_cd, arvl_cd, date, min_time, max_time)
            self.send_json({"buses": buses})
            return
        if path == "/api/kobus/monitor/status":
            self.send_json(eng.kobus.get_status())
            return

        # ---- Train ----
        if path == "/api/train/stations":
            self.send_json({"regions": STATION_REGIONS})
            return
        if path == "/api/train/config":
            self.send_json(eng.train.config)
            return
        if path == "/api/train/schedule":
            cfg = eng.train.config
            dep = qs.get("depCode", [cfg.get("departure_station", "0551")])[0]
            arr = qs.get("arrCode", [cfg.get("arrival_station", "0020")])[0]
            date = qs.get("date", [cfg.get("date", "")])[0]
            min_time = qs.get("minTime", [cfg.get("min_time", "00:00")])[0]
            max_time = qs.get("maxTime", [cfg.get("max_time", "23:59")])[0]
            trains = eng.train.query_trains(dep, arr, date, min_time, max_time)
            self.send_json({"trains": trains})
            return
        if path == "/api/train/monitor/status":
            self.send_json(eng.train.get_status())
            return

        # ---- Cinema ----
        if path == "/api/cinema/theaters":
            brand = qs.get("brand", [eng.cinema.config.get("brand", "CGV")])[0].upper()
            self.send_json({"brand": brand, "brands": ["CGV", "MEGABOX"], "regions": eng.cinema.fetch_theaters(brand)})
            return
        if path == "/api/cinema/config":
            self.send_json(eng.cinema.config)
            return
        if path == "/api/cinema/schedule":
            cfg = eng.cinema.config
            brand = qs.get("brand", [cfg.get("brand", "CGV")])[0].upper()
            default_th = "0013" if brand == "CGV" else "1351"
            th = qs.get("theaterCode", [cfg.get("theater_code", default_th)])[0]
            date = qs.get("date", [cfg.get("date", "")])[0]
            mv = qs.get("movieFilter", [cfg.get("target_movie", "")])[0]
            spc = qs.get("specialOnly", ["0"])[0] == "1"
            min_seats = int(qs.get("minSeats", [cfg.get("min_seats", 1)])[0])
            shows = eng.cinema.query_showtimes(brand=brand, theater_code=th, date=date, movie_filter=mv, special_only=spc, min_seats=min_seats)
            self.send_json({"brand": brand, "showtimes": shows})
            return
        if path == "/api/cinema/monitor/status":
            self.send_json(eng.cinema.get_status())
            return

        # ---- UOS Sugang ----
        if path == "/api/uos/config":
            self.send_json(masked_uos_config(eng.uos.config, eng.uos.get_academic_period()))
            return
        if path == "/api/uos/courses":
            period = eng.uos.get_academic_period()
            year = qs.get("year", [period["year"]])[0]
            sem = qs.get("sem", [period["semester"]])[0]
            refresh = qs.get("refresh", ["0"])[0] == "1"
            courses = eng.uos.fetch_courses(year=year, semester=sem, force_refresh=refresh)
            self.send_json({"courses": courses, "academic_period": period})
            return
        if path == "/api/uos/monitor/status":
            self.send_json(eng.uos.get_status())
            return

        # ---- UOS Campus ----
        if path == "/api/campus/library":
            rooms = eng.campus.fetch_library_seats()
            self.send_json({"rooms": rooms, "errors": getattr(eng.campus, "last_library_errors", []), "fetched_at": now_iso()})
            return
        if path == "/api/campus/notices":
            refresh = qs.get("refresh", ["0"])[0] == "1"
            notices, _ = eng.campus.fetch_notices(force_refresh=refresh)
            self.send_json({"notices": notices, "recommended_tags": RECOMMENDED_TAGS})
            return
        if path == "/api/campus/config":
            self.send_json(eng.campus.config)
            return
        if path == "/api/campus/monitor/status":
            self.send_json(eng.campus.get_status())
            return

        # ---- Flight ----
        if path == "/api/flight/routes":
            self.send_json({"routes": POPULAR_ROUTES, "airports": AIRPORTS})
            return
        if path == "/api/flight/config":
            self.send_json(eng.flight.config)
            return
        if path == "/api/flight/schedule":
            cfg = eng.flight.config
            dep = qs.get("dep", [cfg.get("dep_code", "GMP")])[0]
            arr = qs.get("arr", [cfg.get("arr_code", "CJU")])[0]
            date = qs.get("date", [cfg.get("date", "")])[0]
            max_price = int(qs.get("maxPrice", [cfg.get("max_price", 999999)])[0])
            golden_only = qs.get("goldenOnly", ["0"])[0] == "1"
            promo_only = qs.get("promoOnly", ["0"])[0] == "1"
            flights = eng.flight.query_flights(dep_code=dep, arr_code=arr, date_str=date, max_price=max_price, golden_only=golden_only, promo_only=promo_only)
            self.send_json({"dep": dep, "arr": arr, "flights": flights})
            return
        if path == "/api/flight/monitor/status":
            self.send_json(eng.flight.get_status())
            return

        self.send_error(404, "Not Found")

    # =====================================================================
    # POST
    # =====================================================================
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self.read_body()

        # 1. 인증
        if path.startswith("/api/auth/"):
            self.handle_auth_post(path, body)
            return

        # 2. 호스트 관리
        if path.startswith("/api/admin/"):
            self.handle_admin_post(path, body)
            return

        # 3. 사용자 엔진 (로그인 필수)
        uid = self.require_login()
        if not uid:
            return
        eng = get_engines(uid)

        # ---- 즐겨찾기 ----
        if path == "/api/favorites/save":
            svc = str(body.get("service", "")).strip()
            name = str(body.get("name", "")).strip()[:40]
            params = body.get("params") or {}
            if svc not in FAV_SERVICES or not name or not isinstance(params, dict):
                self.send_json({"success": False, "message": "저장할 서비스/이름/조건이 올바르지 않습니다."})
                return
            with FAV_LOCK:
                favs = load_favorites(uid)
                if len(favs) >= FAV_MAX:
                    self.send_json({"success": False, "message": f"즐겨찾기는 최대 {FAV_MAX}개까지 저장할 수 있습니다."})
                    return
                fav = {"id": secrets.token_hex(4), "service": svc, "name": name, "params": params, "created_at": now_iso()}
                favs.append(fav)
                save_favorites(uid, favs)
            self.send_json({"success": True, "message": f"⭐ '{name}' 즐겨찾기 저장", "favorite": fav, "favorites": favs})
            return

        if path == "/api/favorites/delete":
            fid = str(body.get("id", "")).strip()
            with FAV_LOCK:
                favs = load_favorites(uid)
                remain = [f for f in favs if f.get("id") != fid]
                save_favorites(uid, remain)
            self.send_json({"success": True, "message": "즐겨찾기를 삭제했습니다.", "favorites": remain})
            return

        if path == "/api/favorites/rename":
            fid = str(body.get("id", "")).strip()
            name = str(body.get("name", "")).strip()[:40]
            with FAV_LOCK:
                favs = load_favorites(uid)
                for f in favs:
                    if f.get("id") == fid and name:
                        f["name"] = name
                save_favorites(uid, favs)
            self.send_json({"success": True, "message": "이름을 변경했습니다.", "favorites": favs})
            return

        # ---- Master ----
        if path == "/api/hub/start_all":
            eng.start_all()
            self.send_json({"success": True, "message": "전체 감시 엔진(고속버스/열차/영화관/수강/캠퍼스/항공권)이 가동되었습니다."})
            return
        if path == "/api/hub/stop_all":
            eng.stop_all()
            self.send_json({"success": True, "message": "전체 감시 엔진이 중지되었습니다."})
            return

        # ---- 공통 패턴: /api/<svc>/monitor/start|stop, /api/<svc>/discord/test, /api/<svc>/config ----
        m = re.match(r"^/api/(kobus|train|cinema|flight|uos|campus)/(monitor/start|monitor/stop|discord/test|config)$", path)
        if m:
            svc, action = m.group(1), m.group(2)
            e = getattr(eng, svc)

            if action == "monitor/start":
                if svc == "uos":
                    cfg = e.config
                    if not cfg.get("student_id") or not cfg.get("password"):
                        self.send_json({"success": False, "message": "학번/비밀번호가 설정되지 않았습니다. [계정 및 알림 설정]에서 먼저 등록하세요."})
                        return
                    if not cfg.get("target_courses"):
                        self.send_json({"success": False, "message": "감시 대상 과목이 0개입니다. 과목 목록에서 ⭐를 눌러 등록하세요."})
                        return
                ok, msg = e.start_monitoring()
                self.send_json({"success": ok, "message": msg})
                return

            if action == "monitor/stop":
                ok, msg = e.stop_monitoring()
                self.send_json({"success": ok, "message": msg})
                return

            if action == "discord/test":
                hook = (body.get("webhook_url") or "").strip() or None
                if svc == "campus":
                    test_obj = {
                        "category": "테스트공지",
                        "title": "[테스트] 시립대 스마트 캠퍼스 알리미 연동 확인",
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "link": "https://www.uos.ac.kr",
                        "tags": ["#장학금", "#해외파견", "#계절학기"]
                    }
                    prev = None
                    if hook:
                        prev = dict(e.config.get("discord") or {})
                        e.config["discord"] = {**prev, "webhook_url": hook}
                    try:
                        e.send_discord_notice_burst(test_obj)
                    finally:
                        if prev is not None:
                            e.config["discord"] = prev
                    self.send_json({"success": True, "message": "테스트 알림 발송 완료!"})
                    return
                ok, msg = e.send_test_discord(hook)
                self.send_json({"success": ok, "message": msg})
                return

            if action == "config":
                curr = e.config
                if svc == "uos":
                    for k in ["student_id", "year", "semester", "check_interval_seconds", "discord", "device"]:
                        if k in body:
                            curr[k] = body[k]
                    if body.get("password"):
                        curr["password"] = body["password"]
                    e.save_config(curr)
                    self.send_json({"success": True, "message": "수강신청 설정 저장 완료"})
                    return
                if svc == "campus":
                    for k in ["watch_keywords", "check_interval_seconds", "discord", "target_library_rooms"]:
                        if k in body:
                            curr[k] = body[k]
                    e.save_config(curr)
                    self.send_json({"success": True, "message": "스마트 캠퍼스 설정 저장 완료"})
                    return
                if svc == "flight":
                    for k in ["route_id", "dep_code", "arr_code", "date", "max_price", "golden_time_only", "promo_only", "min_seats", "check_interval_seconds", "discord"]:
                        if k in body:
                            curr[k] = body[k]
                    e.save_config(curr)
                    self.send_json({"success": True, "message": "항공권 설정 저장 완료"})
                    return
                # kobus / train / cinema: 자유 병합
                for k, v in body.items():
                    curr[k] = v
                e.save_config(curr)
                label = {"kobus": "KOBUS", "train": "KTX/SRT", "cinema": "영화관"}[svc]
                self.send_json({"success": True, "message": f"{label} 설정 저장 완료"})
                return

        # ---- UOS 전용 ----
        if path == "/api/uos/login_test":
            sid = (body.get("student_id") or "").strip() or (eng.uos.config.get("student_id") or "").strip()
            pwd = (body.get("password") or "").strip() or (eng.uos.config.get("password") or "").strip()
            if not sid or not pwd:
                self.send_json({"success": False, "message": "학번과 비밀번호를 입력해주세요."})
                return
            ok, msg = eng.uos.test_login_credentials(sid, pwd)
            self.send_json({"success": ok, "message": msg})
            return

        if path == "/api/uos/targets/toggle":
            code = str(body.get("code", "")).strip()
            div = str(body.get("div", "01")).strip().zfill(2)
            targets = eng.uos.config.get("target_courses", [])
            existing_idx = -1
            for idx, t in enumerate(targets):
                if str(t.get("code", "")).strip() == code and str(t.get("div", "")).strip().zfill(2) == div:
                    existing_idx = idx
                    break
            if existing_idx >= 0:
                removed = targets.pop(existing_idx)
                eng.uos.log(f"⭐ 감시 해제: [{removed.get('code')}-{removed.get('div')}] {removed.get('name')}")
            else:
                targets.append({
                    "code": code, "div": div,
                    "name": body.get("name", ""), "prof": body.get("prof", ""),
                    "dept": body.get("dept", ""), "type": body.get("type", "")
                })
                eng.uos.log(f"⭐ 감시 등록: [{code}-{div}] {body.get('name', '')} ({body.get('prof', '')} 교수)")
            eng.uos.config["target_courses"] = targets
            eng.uos.save_config()
            self.send_json({"success": True, "target_courses": targets})
            return

        self.send_error(404, "Not Found")

    # =====================================================================
    # 인증 라우트
    # =====================================================================
    def handle_auth_post(self, path, body):
        if path == "/api/auth/login":
            name = (body.get("name") or "").strip()
            pin = (body.get("pin") or "").strip()
            p = USERS.find_by_name(name)
            if not p or p.get("is_host") and not p.get("pin_hash"):
                self.send_json({"success": False, "message": "존재하지 않는 프로필이거나 PIN이 올바르지 않습니다."}, status=401)
                return
            if not USERS.verify_pin(p, pin):
                self.send_json({"success": False, "message": "존재하지 않는 프로필이거나 PIN이 올바르지 않습니다."}, status=401)
                return
            token = make_token(p["uid"])
            self.send_json({"success": True, "token": token, "user": USERS.public_profile(p)},
                           extra_headers=[self.auth_cookie_header(token)])
            return

        if path == "/api/auth/register":
            name = (body.get("name") or "").strip()
            pin = (body.get("pin") or "").strip()
            invite = (body.get("invite_code") or "").strip()
            if not SETTINGS.get("registration_open"):
                self.send_json({"success": False, "message": "현재 신규 프로필 등록이 닫혀 있습니다. 호스트에게 문의하세요."}, status=403)
                return
            if SETTINGS.get("invite_code") and invite != SETTINGS.get("invite_code"):
                self.send_json({"success": False, "message": "초대코드가 올바르지 않습니다."}, status=403)
                return
            if len(name) < 2 or len(name) > 20:
                self.send_json({"success": False, "message": "이름은 2~20자로 입력하세요."})
                return
            if len(pin) < 4 or len(pin) > 32:
                self.send_json({"success": False, "message": "PIN은 4자 이상 입력하세요."})
                return
            if USERS.find_by_name(name):
                self.send_json({"success": False, "message": "이미 사용 중인 이름입니다. 다른 이름을 입력하세요."})
                return
            non_host = [u for u in USERS.users.values() if not u.get("is_host")]
            if len(non_host) >= int(SETTINGS.get("max_users") or 20):
                self.send_json({"success": False, "message": "등록 가능한 최대 사용자 수에 도달했습니다."}, status=403)
                return
            p = USERS.create(name, pin)
            token = make_token(p["uid"])
            print(f"👤 [User] 신규 프로필 등록: {p['name']} ({p['uid']})")
            self.send_json({"success": True, "token": token, "user": USERS.public_profile(p), "message": f"'{name}' 프로필이 생성되었습니다."},
                           extra_headers=[self.auth_cookie_header(token)])
            return

        if path == "/api/auth/host":
            key = (body.get("admin_key") or "").strip().upper()
            if not key or not hmac.compare_digest(key, SETTINGS.get("admin_key")):
                time.sleep(0.8)  # 무차별 대입 완화
                self.send_json({"success": False, "message": "관리자 키가 올바르지 않습니다. (서버 콘솔 또는 data/hub_settings.json 확인)"}, status=401)
                return
            p = USERS.users[HOST_UID]
            token = make_token(HOST_UID)
            self.send_json({"success": True, "token": token, "user": USERS.public_profile(p)},
                           extra_headers=[self.auth_cookie_header(token)])
            return

        if path == "/api/auth/logout":
            self.send_json({"success": True}, extra_headers=[("Set-Cookie", "hub_token=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")])
            return

        if path == "/api/auth/change_pin":
            uid = self.require_login()
            if not uid:
                return
            pin = (body.get("pin") or "").strip()
            if len(pin) < 4:
                self.send_json({"success": False, "message": "PIN은 4자 이상 입력하세요."})
                return
            USERS.set_pin(uid, pin)
            self.send_json({"success": True, "message": "PIN이 변경되었습니다."})
            return

        self.send_error(404, "Not Found")

    # =====================================================================
    # 호스트 관리 라우트
    # =====================================================================
    def handle_admin_get(self, path, qs):
        uid = self.require_host()
        if not uid:
            return

        if path == "/api/admin/overview":
            with ENGINES_LOCK:
                loaded = dict(ENGINES)
            users_out = []
            total_running = 0
            for p in sorted(USERS.users.values(), key=lambda x: (not x.get("is_host"), x.get("created_at", ""))):
                item = USERS.public_profile(p)
                eng = loaded.get(p["uid"])
                if eng:
                    item["loaded"] = True
                    item["engines"] = eng.summary()
                    item["running_count"] = eng.running_count()
                    total_running += item["running_count"]
                else:
                    item["loaded"] = False
                    item["engines"] = {}
                    item["running_count"] = 0
                users_out.append(item)
            self.send_json({
                "server": {
                    "port": self.server.server_address[1],
                    "started_at": datetime.fromtimestamp(SERVER_STARTED_AT).strftime("%Y-%m-%d %H:%M:%S"),
                    "uptime_sec": int(time.time() - SERVER_STARTED_AT),
                    "python": sys.version.split()[0],
                    "threads": threading.active_count(),
                    "users_count": len(USERS.users),
                    "loaded_users": len(loaded),
                    "engines_running_total": total_running,
                    "data_dir": DATA_DIR,
                },
                "settings": SETTINGS.public(),
                "admin_key": SETTINGS.get("admin_key"),
                "tunnel": TUNNEL.status(),
                "users": users_out,
            })
            return

        if path == "/api/admin/user/config":
            target = qs.get("uid", [""])[0]
            if target not in USERS.users:
                self.send_json({"success": False, "message": "사용자를 찾을 수 없습니다."}, status=404)
                return
            out = {}
            for k in ENGINE_KEYS:
                cfg = read_json(os.path.join(USERS.user_dir(target), f"{k}.json"), None)
                if isinstance(cfg, dict) and "password" in cfg:
                    cfg = dict(cfg)
                    cfg["password"] = "••••••" if cfg.get("password") else ""
                out[k] = cfg
            self.send_json({"success": True, "uid": target, "user": USERS.public_profile(USERS.users[target]), "configs": out})
            return

        if path == "/api/admin/tunnel/status":
            self.send_json(TUNNEL.status())
            return

        self.send_error(404, "Not Found")

    def handle_admin_post(self, path, body):
        uid = self.require_host()
        if not uid:
            return

        if path == "/api/admin/settings":
            patch = {}
            if "registration_open" in body:
                patch["registration_open"] = bool(body["registration_open"])
            if "invite_code" in body:
                patch["invite_code"] = str(body["invite_code"]).strip()
            if "max_users" in body:
                try:
                    patch["max_users"] = max(1, int(body["max_users"]))
                except Exception:
                    pass
            if "default_webhook" in body:
                patch["default_webhook"] = str(body["default_webhook"]).strip()
            if "auto_tunnel" in body:
                patch["auto_tunnel"] = bool(body["auto_tunnel"])
            if "notify_webhook" in body:
                patch["notify_webhook"] = str(body["notify_webhook"]).strip()
            if "notify_on_tunnel_url" in body:
                patch["notify_on_tunnel_url"] = bool(body["notify_on_tunnel_url"])
            SETTINGS.update(patch)
            self.send_json({"success": True, "message": "호스트 설정이 저장되었습니다.", "settings": SETTINGS.public()})
            return

        if path == "/api/admin/regenerate_key":
            new_key = SETTINGS.regenerate_admin_key()
            print(f"🔑 [Host] 관리자 키가 재발급되었습니다: {new_key}")
            self.send_json({"success": True, "admin_key": new_key, "message": "관리자 키가 재발급되었습니다."})
            return

        target = (body.get("uid") or "").strip()

        if path == "/api/admin/user/stop_all":
            if target in ENGINES:
                ENGINES[target].stop_all()
            self.send_json({"success": True, "message": "해당 사용자의 감시 엔진을 모두 중지했습니다."})
            return

        if path == "/api/admin/user/unload":
            drop_engines(target)
            self.send_json({"success": True, "message": "해당 사용자의 엔진을 메모리에서 내렸습니다. (설정은 보존)"})
            return

        if path == "/api/admin/user/delete":
            if target == HOST_UID:
                self.send_json({"success": False, "message": "호스트 계정은 삭제할 수 없습니다."})
                return
            drop_engines(target)
            ok = USERS.delete(target)
            self.send_json({"success": ok, "message": "사용자와 모든 설정 데이터를 삭제했습니다." if ok else "사용자를 찾을 수 없습니다."})
            return

        if path == "/api/admin/user/reset_pin":
            pin = (body.get("pin") or "").strip()
            if target not in USERS.users or len(pin) < 4:
                self.send_json({"success": False, "message": "대상 사용자 또는 PIN(4자 이상)을 확인하세요."})
                return
            USERS.set_pin(target, pin)
            self.send_json({"success": True, "message": "PIN을 재설정했습니다."})
            return

        if path == "/api/admin/user/rename":
            name = (body.get("name") or "").strip()
            if target not in USERS.users or len(name) < 2:
                self.send_json({"success": False, "message": "대상 사용자 또는 이름(2자 이상)을 확인하세요."})
                return
            dup = USERS.find_by_name(name)
            if dup and dup["uid"] != target:
                self.send_json({"success": False, "message": "이미 사용 중인 이름입니다."})
                return
            USERS.rename(target, name)
            self.send_json({"success": True, "message": "이름을 변경했습니다."})
            return

        if path == "/api/admin/user/webhook":
            # 특정 사용자의 6개 엔진 웹훅을 일괄 지정 (호스트 데이터 관리)
            hook = (body.get("webhook_url") or "").strip()
            if target not in USERS.users:
                self.send_json({"success": False, "message": "사용자를 찾을 수 없습니다."})
                return
            eng = get_engines(target)
            for _, e in eng.all():
                disc = dict(e.config.get("discord") or {})
                disc["webhook_url"] = hook
                disc.setdefault("mention", "@everyone")
                e.config["discord"] = disc
                e.save_config()
            self.send_json({"success": True, "message": "해당 사용자의 모든 엔진 웹훅을 갱신했습니다."})
            return

        if path == "/api/admin/stop_everything":
            stop_everything()
            self.send_json({"success": True, "message": "모든 사용자의 감시 엔진을 중지했습니다."})
            return

        if path == "/api/admin/tunnel/start":
            ok, msg = TUNNEL.start(self.server.server_address[1])
            self.send_json({"success": ok, "message": msg, "tunnel": TUNNEL.status()})
            return

        if path == "/api/admin/tunnel/stop":
            ok, msg = TUNNEL.stop()
            self.send_json({"success": ok, "message": msg, "tunnel": TUNNEL.status()})
            return

        if path == "/api/admin/tunnel/notify":
            ok, msg = notify_tunnel_url(TUNNEL.url if TUNNEL.is_running() else "", force=True)
            self.send_json({"success": ok, "message": msg})
            return

        self.send_error(404, "Not Found")


# =====================================================================
# 7. 서버 실행
# =====================================================================
def find_available_port(start_port=8000, max_attempts=10):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return start_port


def run_server(open_browser=True, port=None):
    if port is None:
        port = find_available_port(8000)
    server = ThreadingHTTPServer(("0.0.0.0", port), AlertHubHandler)
    server.daemon_threads = True
    url = f"http://localhost:{port}"

    print("=" * 72)
    print("🚀 Realtime Alert Hub 2.1 (멀티유저 실시간 알리미 통합 포털 허브)")
    print("=" * 72)
    print(f"• 통합 대시보드 주소 : {url}")
    print(f"• 데이터 폴더        : {DATA_DIR}")
    print(f"• 등록된 프로필      : {len(USERS.users)}명 (등록 허용: {'예' if SETTINGS.get('registration_open') else '아니오'})")
    print(f"🔑 호스트 관리자 키   : {SETTINGS.get('admin_key')}   ← 대시보드 [호스트 로그인]에 입력")
    print(f"• Cloudflare 터널    : {'사용 가능 (호스트 패널에서 시작)' if TUNNEL.exe else 'cloudflared 없음'}")
    print("• 종료: Ctrl + C")
    print("=" * 72)

    # 호스트 엔진은 미리 로드 (기존 config.json 마이그레이션 포함)
    try:
        get_engines(HOST_UID)
    except Exception as e:
        print(f"[!] 호스트 엔진 로드 중 경고: {e}")

    if SETTINGS.get("auto_tunnel"):
        ok, msg = TUNNEL.start(port)
        print(f"🌐 [Tunnel] {msg}")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] 통합 허브를 종료합니다...")
    finally:
        stop_everything()
        TUNNEL.stop()
        server.server_close()
        print("서버가 안전하게 종료되었습니다.")


if __name__ == "__main__":
    is_docker = os.environ.get("DOCKER_CONTAINER") == "1"
    no_browser = is_docker or os.environ.get("HUB_NO_BROWSER") == "1" or "--no-browser" in sys.argv
    env_port = os.environ.get("HUB_PORT")
    port = 8000 if is_docker else (int(env_port) if env_port else None)
    run_server(open_browser=not no_browser, port=port)
