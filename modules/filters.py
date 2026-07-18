# -*- coding: utf-8 -*-
"""
modules/filters.py
--------------------
مدیریت فیلترهای سفارشی (کلیدواژه -> پاسخ) توسط ادمین‌ها.
اجرای واقعی پاسخ‌گویی در modules/auto_reply.py انجام می‌شود.

دستورات:
    فیلتر [کلیدواژه] [پاسخ]
    لیست فیلترها
    حذف فیلتر [کلیدواژه]
"""

from core.logger import get_logger
from core import permissions
from database import database as db
from utils import helpers

log = get_logger("filters")


def handle_filter_command(client, message, group_guid, user_guid) -> bool:
    text = helpers.get_message_text(message)
    normalized = helpers.normalize_text(text)

    arg = helpers.command_starts_with(normalized, "فیلتر ")
    if arg is not None:
        return _cmd_add_filter(client, message, group_guid, user_guid, arg)

    if helpers.command_matches(normalized, "لیست فیلترها", "لیست فیلتر ها"):
        return _cmd_list_filters(client, message, group_guid)

    arg = helpers.command_starts_with(normalized, "حذف فیلتر ")
    if arg is not None:
        return _cmd_remove_filter(client, message, group_guid, user_guid, arg)

    return False


@permissions.require_level(permissions.Level.ADMIN)
def _cmd_add_filter(client, message, group_guid, user_guid, arg):
    parts = arg.split(" ", 1)
    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
        client.send_text(
            group_guid,
            "فرمت درست: فیلتر [کلیدواژه] [متن پاسخ]\nمثال: فیلتر قوانین لطفا قوانین گروه را رعایت کنید.",
            helpers.get_message_id(message),
        )
        return True
    keyword, response = parts[0].strip(), parts[1].strip()
    db.add_filter(group_guid, keyword, response)
    client.send_text(
        group_guid, f"✅ فیلتر «{keyword}» ذخیره شد.", helpers.get_message_id(message)
    )
    log.info(f"فیلتر '{keyword}' در گروه {group_guid} توسط {user_guid} اضافه شد.")
    return True


def _cmd_list_filters(client, message, group_guid):
    rows = db.list_filters(group_guid)
    if not rows:
        client.send_text(group_guid, "هیچ فیلتری ثبت نشده است.", helpers.get_message_id(message))
        return True
    lines = ["📋 لیست فیلترها:\n"]
    for row in rows:
        lines.append(f"• {row['keyword']}")
    client.send_text(group_guid, "\n".join(lines), helpers.get_message_id(message))
    return True


@permissions.require_level(permissions.Level.ADMIN)
def _cmd_remove_filter(client, message, group_guid, user_guid, keyword):
    keyword = keyword.strip()
    db.remove_filter(group_guid, keyword)
    client.send_text(group_guid, f"✅ فیلتر «{keyword}» حذف شد.", helpers.get_message_id(message))
    log.info(f"فیلتر '{keyword}' در گروه {group_guid} توسط {user_guid} حذف شد.")
    return True
