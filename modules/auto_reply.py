# -*- coding: utf-8 -*-
"""
modules/auto_reply.py
------------------------
اجرای پاسخ خودکار بر اساس فیلترهای ثبت‌شده (modules/filters.py) و همچنین
دستور روشن/خاموش کردن کلی پاسخ خودکار برای هر گروه.
"""

from core.logger import get_logger
from core import permissions
from database import database as db
from utils import helpers

log = get_logger("auto_reply")


def handle_toggle_command(client, message, group_guid, user_guid) -> bool:
    text = helpers.normalize_text(helpers.get_message_text(message))

    if helpers.command_matches(text, "پاسخ خودکار فعال"):
        return _toggle(client, message, group_guid, user_guid, True)

    if helpers.command_matches(text, "پاسخ خودکار غیرفعال"):
        return _toggle(client, message, group_guid, user_guid, False)

    return False


@permissions.require_level(permissions.Level.ADMIN)
def _toggle(client, message, group_guid, user_guid, enable):
    db.update_setting(group_guid, "auto_reply_enabled", 1 if enable else 0)
    state = "فعال" if enable else "غیرفعال"
    client.send_text(group_guid, f"✅ پاسخ خودکار {state} شد.", helpers.get_message_id(message))
    return True


def try_auto_reply(client, message, group_guid) -> bool:
    """
    اگر متن پیام با یکی از کلیدواژه‌های فیلترشده مطابقت داشت، پاسخ خودکار
    ارسال می‌شود. True یعنی پیام پاسخ داده شد.
    """
    settings = db.get_settings(group_guid)
    if not settings["auto_reply_enabled"]:
        return False

    text = helpers.get_message_text(message)
    if not text:
        return False

    filters_rows = db.list_filters(group_guid)
    if not filters_rows:
        return False

    lowered = text.lower()
    for row in filters_rows:
        if row["keyword"].lower() in lowered:
            client.send_text(group_guid, row["response"], helpers.get_message_id(message))
            return True

    return False
