# -*- coding: utf-8 -*-
"""
core/permissions.py
---------------------
سیستم سطح دسترسی LeoBot.

سطح‌ها (از بالا به پایین):
    owner       -> مالک اصلی ربات (در .env تنظیم می‌شود)
    creator     -> سازنده‌ی گروه
    full_admin  -> ادمین کامل (تنظیم شده توسط اونر/سازنده)
    admin       -> ادمین معمولی (دسترسی محدودتر)
    user        -> کاربر عادی
"""

from enum import IntEnum

import config
from database import database as db

LEVEL_ORDER_NAMES = ["user", "admin", "full_admin", "creator", "owner"]


class Level(IntEnum):
    USER = 0
    ADMIN = 1
    FULL_ADMIN = 2
    CREATOR = 3
    OWNER = 4


_NAME_TO_LEVEL = {
    "user": Level.USER,
    "admin": Level.ADMIN,
    "full_admin": Level.FULL_ADMIN,
    "creator": Level.CREATOR,
    "owner": Level.OWNER,
}


def get_user_level(group_guid: str, user_guid: str) -> Level:
    if user_guid == config.OWNER_ID:
        return Level.OWNER
    if user_guid in config.CREATOR_IDS:
        return Level.CREATOR

    group = db.get_group(group_guid) if group_guid else None
    if group and group["owner_guid"] and group["owner_guid"] == user_guid:
        return Level.CREATOR

    level_name = db.get_admin_level(group_guid, user_guid) if group_guid else None
    if level_name and level_name in _NAME_TO_LEVEL:
        return _NAME_TO_LEVEL[level_name]

    return Level.USER


def has_level(group_guid: str, user_guid: str, required: Level) -> bool:
    return get_user_level(group_guid, user_guid) >= required


def require_level(required: Level):
    """
    دکوراتور برای دستورات ماژول‌ها.
    تابع تزئین‌شده باید امضای (client, message, group_guid, user_guid, *args) داشته باشد
    و مقدار بازگشتی آن به کاربر ارسال می‌شود اگر دسترسی کافی نبود.
    """

    def decorator(func):
        def wrapper(client, message, group_guid, user_guid, *args, **kwargs):
            if not has_level(group_guid, user_guid, required):
                client.send_text(
                    group_guid,
                    "⛔️ شما اجازه استفاده از این دستور را ندارید.",
                    message.message_id if hasattr(message, "message_id") else None,
                )
                return None
            return func(client, message, group_guid, user_guid, *args, **kwargs)

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator


def level_display_name(level: Level) -> str:
    mapping = {
        Level.OWNER: "مالک ربات",
        Level.CREATOR: "سازنده گروه",
        Level.FULL_ADMIN: "ادمین کامل",
        Level.ADMIN: "ادمین",
        Level.USER: "کاربر عادی",
    }
    return mapping.get(level, "نامشخص")
