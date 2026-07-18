# -*- coding: utf-8 -*-
"""
modules/anti_spam.py
----------------------
- حذف پیام کاربران سکوت‌شده (چون rubpy همیشه امکان محدودسازی per-member ندارد،
  این حذف نرم‌افزاری جایگزین سکوت واقعی می‌شود).
- تشخیص فلود (تعداد پیام در بازه زمانی کوتاه) و پیام تکراری.
- در صورت فلود: سکوت موقت خودکار کاربر.
"""

import time

import config
from core.logger import get_logger
from core import security, permissions
from database import database as db
from utils import helpers

log = get_logger("anti_spam")

AUTO_MUTE_SECONDS = 300  # سکوت موقت خودکار بعد از فلود


def enforce(client, message, group_guid, user_guid) -> bool:
    """
    اگر پیام باید مسدود/حذف شود True برمی‌گرداند تا پردازش بیشتر متوقف شود.
    """
    settings = db.get_settings(group_guid)

    # ادمین‌ها و بالاتر از محدودیت‌های آنتی‌اسپم مستثنی هستند
    is_privileged = permissions.has_level(group_guid, user_guid, permissions.Level.ADMIN)

    # ۰) کاربر بن‌شده (نرم) -> چون Bot API رسمی متد حذف عضو ندارد، هر پیام
    #    بعدی این کاربر با متد رسمی deleteMessage حذف می‌شود.
    if db.is_banned(group_guid, user_guid) and not is_privileged:
        message_id = helpers.get_message_id(message)
        if message_id:
            client.delete_message(group_guid, message_id)
        log.info(f"پیام کاربر بن‌شده {user_guid} در گروه {group_guid} حذف شد.")
        return True

    # ۱) کاربر سکوت‌شده -> حذف فوری پیام
    if db.is_muted(group_guid, user_guid) and not is_privileged:
        message_id = helpers.get_message_id(message)
        if message_id:
            client.delete_message(group_guid, message_id)
        log.info(f"پیام کاربر سکوت‌شده {user_guid} در گروه {group_guid} حذف شد.")
        return True

    if is_privileged:
        return False

    text = helpers.get_message_text(message)

    # ۲) ثبت تاریخچه برای بررسی فلود/تکرار
    security.record_message(group_guid, user_guid, text)

    if not settings["anti_flood"] and not settings["anti_spam"]:
        return False

    flooding = settings["anti_flood"] and security.check_flood(group_guid, user_guid)
    duplicate = settings["anti_spam"] and security.check_duplicate(group_guid, user_guid, text)

    if flooding or duplicate:
        message_id = helpers.get_message_id(message)
        if message_id:
            client.delete_message(group_guid, message_id)
        until = int(time.time()) + AUTO_MUTE_SECONDS
        db.mute_user(group_guid, user_guid, muted_by="anti_spam", until=until)
        client.send_text(
            group_guid,
            "🚫 به‌دلیل ارسال پیام بیش‌ازحد (اسپم/فلود)، به‌مدت ۵ دقیقه سکوت شدید.",
        )
        log.info(f"کاربر {user_guid} در گروه {group_guid} به‌دلیل فلود/اسپم سکوت شد.")
        return True

    return False
