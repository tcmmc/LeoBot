# -*- coding: utf-8 -*-
"""
config.py
---------
تمام تنظیمات LeoBot از اینجا خوانده می‌شود.
مقادیر حساس (رمز پنل، شناسه مالک و ...) از فایل .env خوانده می‌شوند
و هرگز به‌صورت مستقیم داخل کد نوشته نمی‌شوند.
"""

import os
import sys
import hashlib
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("[CONFIG] پکیج python-dotenv نصب نیست. با دستور زیر نصب کنید:")
    print("         pip install python-dotenv")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if not ENV_PATH.exists():
    print(f"[CONFIG] فایل .env پیدا نشد. فایل .env.example را کپی و مقداردهی کنید.")
    print(f"         مسیر مورد انتظار: {ENV_PATH}")

load_dotenv(dotenv_path=ENV_PATH)


def _get_env(key: str, default=None, required: bool = False, cast=str):
    value = os.getenv(key, default)
    if required and (value is None or str(value).strip() == ""):
        raise RuntimeError(
            f"[CONFIG] مقدار الزامی '{key}' در فایل .env تنظیم نشده است."
        )
    if value is None:
        return None
    try:
        if cast is bool:
            return str(value).strip().lower() in ("1", "true", "yes", "on")
        return cast(value)
    except (TypeError, ValueError):
        raise RuntimeError(f"[CONFIG] مقدار '{key}' نامعتبر است.")


# ---------------------------------------------------------------------------
# هویت ربات (اتصال با Bot Token رسمی روبیکا)
# ---------------------------------------------------------------------------
# LeoBot از توکن رسمی بات (که از @BotFather روبیکا دریافت می‌شود) استفاده می‌کند.
# هیچ لاگین با شماره تلفن یا Session شخصی انجام نمی‌شود.
BOT_TOKEN = _get_env("BOT_TOKEN", required=True, cast=str)

# ---------------------------------------------------------------------------
# دسترسی‌ها
# ---------------------------------------------------------------------------
OWNER_ID = _get_env("OWNER_ID", required=True, cast=str)
CREATOR_IDS = [
    x.strip() for x in _get_env("CREATOR_IDS", default="").split(",") if x.strip()
]

# شناسه‌ی سایر مدیرانی که اجازه‌ی باز کردن «پنل ادمین» در PV را دارند
# (مالک همیشه و به‌صورت خودکار جزو این لیست است).
PANEL_ADMIN_IDS = [
    x.strip() for x in _get_env("PANEL_ADMIN_IDS", default="").split(",") if x.strip()
]
if OWNER_ID not in PANEL_ADMIN_IDS:
    PANEL_ADMIN_IDS.append(OWNER_ID)

# رمز پنل به صورت هش شده (SHA-256) نگه‌داری می‌شود، نه متن ساده.
# طبق نیاز پروژه مقدار پیش‌فرض رمز «GG777mahi» است؛ همیشه از env خوانده می‌شود
# و هرگز به‌صورت متن ساده داخل کد نوشته نشده است.
_RAW_ADMIN_PASSWORD = _get_env("ADMIN_PASSWORD", default=None)
PANEL_PASSWORD_HASH = _get_env("ADMIN_PASSWORD_HASH", default=None)

if PANEL_PASSWORD_HASH is None and _RAW_ADMIN_PASSWORD:
    PANEL_PASSWORD_HASH = hashlib.sha256(
        _RAW_ADMIN_PASSWORD.encode("utf-8")
    ).hexdigest()

if not PANEL_PASSWORD_HASH:
    raise RuntimeError(
        "[CONFIG] هیچ رمزی برای پنل ادمین تنظیم نشده است. "
        "ADMIN_PASSWORD یا ADMIN_PASSWORD_HASH را در .env تنظیم کنید."
    )

# ---------------------------------------------------------------------------
# دیتابیس / لاگ / بکاپ
# ---------------------------------------------------------------------------
# روی Railway، فایل‌سیستم پیش‌فرض کانتینر Ephemeral است (با هر Deploy/Restart
# پاک می‌شود). اگر یک Railway Volume وصل کرده‌اید، مسیر Mount آن را در
# DATA_DIR_PATH بگذارید (مثلاً /data) تا دیتابیس و لاگ‌ها ماندگار بمانند.
_data_dir_override = _get_env("DATA_DIR_PATH", default=None)
DATA_DIR = Path(_data_dir_override) if _data_dir_override else (BASE_DIR / "data")

try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception as _exc:
    print(f"[CONFIG] ساخت پوشه‌ی داده در {DATA_DIR} ناموفق بود ({_exc})؛ از /tmp استفاده می‌شود.")
    DATA_DIR = Path("/tmp/leobot-data")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

try:
    LOG_DIR = BASE_DIR / "logs"
    LOG_DIR.mkdir(exist_ok=True)
except Exception:
    LOG_DIR = Path("/tmp/leobot-logs")
    LOG_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = str(DATA_DIR / _get_env("DATABASE_FILE", default="leobot.db"))
LOG_FILE_PATH = str(LOG_DIR / _get_env("LOG_FILE", default="leobot.log"))
LOG_LEVEL = _get_env("LOG_LEVEL", default="INFO")

# اطلاعات محیط اجرا (برای عیب‌یابی در لاگ‌های Railway)
RAILWAY_ENVIRONMENT = _get_env("RAILWAY_ENVIRONMENT", default=None)
RAILWAY_SERVICE_NAME = _get_env("RAILWAY_SERVICE_NAME", default=None)

# ---------------------------------------------------------------------------
# رفتار امنیتی پیش‌فرض
# ---------------------------------------------------------------------------
DEFAULT_WARN_LIMIT = _get_env("DEFAULT_WARN_LIMIT", default=3, cast=int)
DEFAULT_FLOOD_LIMIT = _get_env("DEFAULT_FLOOD_LIMIT", default=6, cast=int)   # پیام در بازه
DEFAULT_FLOOD_WINDOW = _get_env("DEFAULT_FLOOD_WINDOW", default=8, cast=int)  # ثانیه
DEFAULT_DUPLICATE_LIMIT = _get_env("DEFAULT_DUPLICATE_LIMIT", default=3, cast=int)

PANEL_MAX_LOGIN_ATTEMPTS = _get_env("PANEL_MAX_LOGIN_ATTEMPTS", default=3, cast=int)
PANEL_LOCKOUT_SECONDS = _get_env("PANEL_LOCKOUT_SECONDS", default=300, cast=int)

# ---------------------------------------------------------------------------
# اتصال / اتصال مجدد
# ---------------------------------------------------------------------------
RECONNECT_DELAY_SECONDS = _get_env("RECONNECT_DELAY_SECONDS", default=5, cast=int)
RECONNECT_MAX_DELAY_SECONDS = _get_env("RECONNECT_MAX_DELAY_SECONDS", default=60, cast=int)

BOT_NAME = "LeoBot"
BOT_VERSION = "2.0.0"
