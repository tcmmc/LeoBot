# -*- coding: utf-8 -*-
"""
modules/welcome.py
--------------------
پیام خوشامدگویی برای اعضای جدید و دستور «قوانین».

دستورات:
    خوشامد [متن]           -> تنظیم متن خوشامدگویی (از {name} برای نام کاربر استفاده کنید)
    خوشامد فعال / خوشامد غیرفعال
    تنظیم قوانین [متن]
    قوانین                 -> نمایش قوانین گروه
"""

from core.logger import get_logger
from core import permissions
from database import database as db
from utils import helpers

log = get_logger("welcome")

DEFAULT_WELCOME = "سلام {name} 👋 به گروه خوش اومدی!"


def handle_command(client, message, group_guid, user_guid) -> bool:
    text = helpers.normalize_text(helpers.get_message_text(message))

    if helpers.command_matches(text, "خوشامد فعال"):
        return _toggle(client, message, group_guid, user_guid, True)

    if helpers.command_matches(text, "خوشامد غیرفعال"):
        return _toggle(client, message, group_guid, user_guid, False)

    arg = helpers.command_starts_with(text, "خوشامد ")
    if arg is not None and text != "خوشامد فعال" and text != "خوشامد غیرفعال":
        return _set_text(client, message, group_guid, user_guid, arg)

    arg = helpers.command_starts_with(text, "تنظیم قوانین ")
    if arg is not None:
        return _set_rules(client, message, group_guid, user_guid, arg)

    if helpers.command_matches(text, "قوانین"):
        return _show_rules(client, message, group_guid)

    return False


@permissions.require_level(permissions.Level.ADMIN)
def _toggle(client, message, group_guid, user_guid, enable):
    db.update_setting(group_guid, "welcome_enabled", 1 if enable else 0)
    state = "فعال" if enable else "غیرفعال"
    client.send_text(group_guid, f"✅ خوشامدگویی {state} شد.", helpers.get_message_id(message))
    return True


@permissions.require_level(permissions.Level.ADMIN)
def _set_text(client, message, group_guid, user_guid, new_text):
    db.update_setting(group_guid, "welcome_text", new_text)
    db.update_setting(group_guid, "welcome_enabled", 1)
    client.send_text(group_guid, "✅ متن خوشامدگویی ذخیره شد.", helpers.get_message_id(message))
    return True


@permissions.require_level(permissions.Level.ADMIN)
def _set_rules(client, message, group_guid, user_guid, new_text):
    db.update_setting(group_guid, "rules_text", new_text)
    client.send_text(group_guid, "✅ قوانین گروه ذخیره شد.", helpers.get_message_id(message))
    return True


def _show_rules(client, message, group_guid):
    settings = db.get_settings(group_guid)
    rules = settings["rules_text"] or "قوانینی برای این گروه تنظیم نشده است."
    client.send_text(group_guid, f"📜 قوانین گروه:\n\n{rules}", helpers.get_message_id(message))
    return True


def send_welcome(client, group_guid, user_guid, first_name):
    settings = db.get_settings(group_guid)
    if not settings["welcome_enabled"]:
        return
    template = settings["welcome_text"] or DEFAULT_WELCOME
    text = template.replace("{name}", first_name or "کاربر")
    client.send_text(group_guid, text)
    log.info(f"پیام خوشامد برای {user_guid} در گروه {group_guid} ارسال شد.")
