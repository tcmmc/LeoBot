# -*- coding: utf-8 -*-
"""
modules/goodbye.py
--------------------
پیام خداحافظی هنگام خروج عضو از گروه.

دستورات:
    خداحافظی [متن]
    خداحافظی فعال / خداحافظی غیرفعال
"""

from core.logger import get_logger
from core import permissions
from database import database as db
from utils import helpers

log = get_logger("goodbye")

DEFAULT_GOODBYE = "{name} از گروه خارج شد. 👋"


def handle_command(client, message, group_guid, user_guid) -> bool:
    text = helpers.normalize_text(helpers.get_message_text(message))

    if helpers.command_matches(text, "خداحافظی فعال"):
        return _toggle(client, message, group_guid, user_guid, True)

    if helpers.command_matches(text, "خداحافظی غیرفعال"):
        return _toggle(client, message, group_guid, user_guid, False)

    arg = helpers.command_starts_with(text, "خداحافظی ")
    if arg is not None and text not in ("خداحافظی فعال", "خداحافظی غیرفعال"):
        return _set_text(client, message, group_guid, user_guid, arg)

    return False


@permissions.require_level(permissions.Level.ADMIN)
def _toggle(client, message, group_guid, user_guid, enable):
    db.update_setting(group_guid, "goodbye_enabled", 1 if enable else 0)
    state = "فعال" if enable else "غیرفعال"
    client.send_text(group_guid, f"✅ پیام خداحافظی {state} شد.", helpers.get_message_id(message))
    return True


@permissions.require_level(permissions.Level.ADMIN)
def _set_text(client, message, group_guid, user_guid, new_text):
    db.update_setting(group_guid, "goodbye_text", new_text)
    db.update_setting(group_guid, "goodbye_enabled", 1)
    client.send_text(group_guid, "✅ متن خداحافظی ذخیره شد.", helpers.get_message_id(message))
    return True


def send_goodbye(client, group_guid, user_guid, first_name):
    settings = db.get_settings(group_guid)
    if not settings["goodbye_enabled"]:
        return
    template = settings["goodbye_text"] or DEFAULT_GOODBYE
    text = template.replace("{name}", first_name or "کاربر")
    client.send_text(group_guid, text)
    log.info(f"پیام خداحافظی برای {user_guid} در گروه {group_guid} ارسال شد.")
