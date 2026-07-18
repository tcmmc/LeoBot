# -*- coding: utf-8 -*-
"""
modules/statistics.py
------------------------
دستور «آمار» برای نمایش آمار کلی گروه.
"""

from core.logger import get_logger
from database import database as db
from utils import helpers

log = get_logger("statistics")


def handle_command(client, message, group_guid, user_guid) -> bool:
    text = helpers.normalize_text(helpers.get_message_text(message))
    if not helpers.command_matches(text, "آمار"):
        return False

    member_count = db.count_members(group_guid)
    admins = db.list_admins(group_guid)
    top_members = db.top_active_members(group_guid, limit=5)

    lines = [
        "📊 آمار گروه:\n",
        f"• تعداد اعضای ثبت‌شده: {member_count}",
        f"• تعداد ادمین‌ها: {len(admins)}",
        "",
        "🏆 فعال‌ترین اعضا:",
    ]
    if top_members:
        for i, row in enumerate(top_members, start=1):
            name = row["first_name"] or row["user_guid"]
            lines.append(f"{i}. {name} — {row['message_count']} پیام")
    else:
        lines.append("داده‌ای موجود نیست.")

    client.send_text(group_guid, "\n".join(lines), helpers.get_message_id(message))
    return True
