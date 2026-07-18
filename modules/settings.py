# -*- coding: utf-8 -*-
"""
modules/settings.py
----------------------
نمایش خلاصه تنظیمات گروه و دستور تغییر سقف اخطار.

دستورات:
    تنظیمات
    تنظیم سقف اخطار [عدد]
"""

from core.logger import get_logger
from core import permissions
from database import database as db
from utils import helpers

log = get_logger("settings")


def handle_command(client, message, group_guid, user_guid) -> bool:
    text = helpers.normalize_text(helpers.get_message_text(message))

    if helpers.command_matches(text, "تنظیمات"):
        return _show_settings(client, message, group_guid)

    arg = helpers.command_starts_with(text, "تنظیم سقف اخطار ")
    if arg is not None:
        return _set_warn_limit(client, message, group_guid, user_guid, arg)

    return False


def _show_settings(client, message, group_guid):
    s = db.get_settings(group_guid)
    lines = [
        "⚙️ تنظیمات گروه:\n",
        f"• آنتی‌اسپم: {'فعال' if s['anti_spam'] else 'غیرفعال'}",
        f"• آنتی‌فلود: {'فعال' if s['anti_flood'] else 'غیرفعال'}",
        f"• خوشامدگویی: {'فعال' if s['welcome_enabled'] else 'غیرفعال'}",
        f"• خداحافظی: {'فعال' if s['goodbye_enabled'] else 'غیرفعال'}",
        f"• پاسخ خودکار: {'فعال' if s['auto_reply_enabled'] else 'غیرفعال'}",
        f"• سقف اخطار: {s['warn_limit']}",
    ]
    client.send_text(group_guid, "\n".join(lines), helpers.get_message_id(message))
    return True


@permissions.require_level(permissions.Level.FULL_ADMIN)
def _set_warn_limit(client, message, group_guid, user_guid, arg):
    arg = arg.strip()
    if not arg.isdigit() or int(arg) <= 0:
        client.send_text(
            group_guid, "لطفاً یک عدد معتبر وارد کنید. مثال: تنظیم سقف اخطار 3",
            helpers.get_message_id(message),
        )
        return True
    db.update_setting(group_guid, "warn_limit", int(arg))
    client.send_text(
        group_guid, f"✅ سقف اخطار روی {arg} تنظیم شد.", helpers.get_message_id(message)
    )
    log.info(f"سقف اخطار گروه {group_guid} توسط {user_guid} روی {arg} تنظیم شد.")
    return True
