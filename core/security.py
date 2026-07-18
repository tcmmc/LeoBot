# -*- coding: utf-8 -*-
"""
core/security.py
-------------------
توابع امنیتی مشترک:
    - بررسی رمز پنل مالک (بدون نگه‌داری رمز خام)
    - محدودیت تلاش ورود (Brute-force protection)
    - تشخیص فلود و پیام تکراری (Anti Spam / Anti Flood)
"""

import hashlib
import time

import config
from database import database as db
from core.logger import get_logger

log = get_logger("security")


# ---------------------------------------------------------------------------
# پنل Owner
# ---------------------------------------------------------------------------
def hash_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


def verify_panel_password(user_guid: str, raw_password: str) -> bool:
    locked_until = db.is_panel_locked(user_guid)
    if locked_until:
        log.warning(f"تلاش ورود به پنل توسط {user_guid} در حالی که قفل است.")
        return False

    is_correct = hash_password(raw_password) == config.PANEL_PASSWORD_HASH
    if is_correct:
        db.set_panel_authenticated(user_guid, True)
        log.info(f"ورود موفق به پنل مالک توسط {user_guid}.")
    else:
        db.register_failed_panel_login(
            user_guid,
            config.PANEL_MAX_LOGIN_ATTEMPTS,
            config.PANEL_LOCKOUT_SECONDS,
        )
        log.warning(f"تلاش ناموفق ورود به پنل مالک توسط {user_guid}.")
    return is_correct


def is_panel_authenticated(user_guid: str) -> bool:
    session = db.get_panel_session(user_guid)
    return bool(session["authenticated"])


def logout_panel(user_guid: str):
    db.set_panel_authenticated(user_guid, False)


def panel_lock_remaining_seconds(user_guid: str) -> int:
    locked_until = db.is_panel_locked(user_guid)
    if not locked_until:
        return 0
    return max(0, locked_until - int(time.time()))


# ---------------------------------------------------------------------------
# Anti-Flood / Anti-Duplicate
# ---------------------------------------------------------------------------
def text_hash(text: str) -> str:
    normalized = (text or "").strip().lower()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def check_flood(group_guid: str, user_guid: str) -> bool:
    """
    True برمی‌گرداند اگر کاربر در حال فلود کردن باشد.
    """
    history = db.recent_message_history(
        group_guid, user_guid, config.DEFAULT_FLOOD_WINDOW
    )
    return len(history) >= config.DEFAULT_FLOOD_LIMIT


def check_duplicate(group_guid: str, user_guid: str, text: str) -> bool:
    """
    True برمی‌گرداند اگر همین پیام به‌صورت متوالی چندین بار تکرار شده باشد.
    """
    h = text_hash(text)
    history = db.recent_message_history(
        group_guid, user_guid, config.DEFAULT_FLOOD_WINDOW * 3
    )
    duplicate_count = sum(1 for row in history if row["text_hash"] == h)
    return duplicate_count >= config.DEFAULT_DUPLICATE_LIMIT


def record_message(group_guid: str, user_guid: str, text: str):
    db.add_message_history(group_guid, user_guid, text_hash(text))
