import base64
import hmac
import json
import os
import secrets

from paths import DATA_DIR

AUTH_FILE = DATA_DIR / "auth.json"

DEFAULT_USERNAME = "admin"


def _load_credentials():
    env_user = os.environ.get("AUTH_USERNAME")
    env_pass = os.environ.get("AUTH_PASSWORD")
    if env_user and env_pass:
        return env_user, env_pass

    if AUTH_FILE.is_file():
        data = json.loads(AUTH_FILE.read_text())
        return data["username"], data["password"]

    # First run with no env vars and no saved file: generate a random password,
    # save it locally (data/ is git-ignored) and print it once.
    password = secrets.token_urlsafe(12)
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps({"username": DEFAULT_USERNAME, "password": password}))
    print(f"[auth] 首次运行，已生成登录账号: {DEFAULT_USERNAME} / 密码: {password}（保存在 {AUTH_FILE}）")
    return DEFAULT_USERNAME, password


USERNAME, PASSWORD = _load_credentials()


def check_auth(header_value):
    if not header_value or not header_value.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header_value[6:]).decode("utf-8")
        user, _, pwd = decoded.partition(":")
    except Exception:
        return False
    return hmac.compare_digest(user, USERNAME) and hmac.compare_digest(pwd, PASSWORD)
