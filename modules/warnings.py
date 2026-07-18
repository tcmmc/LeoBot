# -*- coding: utf-8 -*-
"""
modules/warnings.py
---------------------
سیستم اخطار: ثبت، نمایش، حذف و اقدام خودکار (بن) بعد از رسیدن به سقف اخطار.
"""

from core.logger import get_logger
from core import permissions
from database import database as db
from modules import admin as admin_module
from utils import helpers

log = get_logger("warnings")


def handle_warning_command(client, message, group_guid, user_guid) -> bool:
    text = helpers.get_message_text(message)
    normalized = helpers.normalize_text(text)

    arg = helpers.command_starts_with(normalized, "اخطار")
    if arg is not None and (normalized == "اخطار" or normalized.startswith("اخطار ")):
        return _cmd_add_warning(client, message, group_guid, user_guid, arg)

    if helpers.command_matches(normalized, "لیست اخطارها", "نمایش اخطارها", "اخطارهای کاربر"):
        return _cmd_list_warnings(client, message, group_guid, user_guid)

    if helpers.command_matches(normalized, "حذف اخطار"):
        return _cmd_remove_warning(client, message, group_guid, user_guid)

    if helpers.command_matches(normalized, "پاک کردن اخطارها"):
        return _cmd_clear_warnings(client, message, group_guid, user_guid)

    return False


@permissions.require_level(permissions.Level.ADMIN)
def _cmd_add_warning(client, message, group_guid, user_guid, reason):
    if not helpers.is_reply(message):
        client.send_text(group_guid, admin_module.NEED_REPLY_MSG, helpers.get_message_id(message))
        return True
    target = helpers.get_reply_target_guid(message)
    if not target:
        client.send_text(
            group_guid, "❗️ کاربر مقصد پیدا نشد.", helpers.get_message_id(message)
        )
        return True

    total = db.add_warning(group_guid, target, user_guid, reason or "بدون دلیل")
    settings = db.get_settings(group_guid)
    limit = settings["warn_limit"] or 3

    client.send_text(
        group_guid,
        f"⚠️ یک اخطار برای کاربر ثبت شد. ({total}/{limit})",
        helpers.get_message_id(message),
    )
    log.info(f"اخطار برای {target} در گروه {group_guid} ثبت شد ({total}/{limit}).")

    if total >= limit:
        client.ban_member(group_guid, target)
        db.remove_member(group_guid, target)
        db.clear_warnings(group_guid, target)
        client.send_text(
            group_guid,
            "🚫 کاربر به‌دلیل رسیدن به سقف اخطار، به‌صورت خودکار بن شد.",
            helpers.get_message_id(message),
        )
        log.info(f"کاربر {target} در گروه {group_guid} به‌دلیل سقف اخطار بن شد.")
    return True


def _cmd_list_warnings(client, message, group_guid, user_guid):
    if not helpers.is_reply(message):
        client.send_text(group_guid, admin_module.NEED_REPLY_MSG, helpers.get_message_id(message))
        return True
    target = helpers.get_reply_target_guid(message)
    if not target:
        return True
    rows = db.list_warnings(group_guid, target)
    if not rows:
        client.send_text(group_guid, "این کاربر هیچ اخطاری ندارد.", helpers.get_message_id(message))
        return True
    lines = [f"⚠️ اخطارهای کاربر ({len(rows)}):\n"]
    for row in rows:
        lines.append(f"• {helpers.human_time(row['created_at'])} — {row['reason']}")
    client.send_text(group_guid, "\n".join(lines), helpers.get_message_id(message))
    return True


@permissions.require_level(permissions.Level.ADMIN)
def _cmd_remove_warning(client, message, group_guid, user_guid):
    if not helpers.is_reply(message):
        client.send_text(group_guid, admin_module.NEED_REPLY_MSG, helpers.get_message_id(message))
        return True
    target = helpers.get_reply_target_guid(message)
    if not target:
        return True
    removed = db.remove_last_warning(group_guid, target)
    msg = "✅ آخرین اخطار کاربر حذف شد." if removed else "این کاربر اخطاری ندارد."
    client.send_text(group_guid, msg, helpers.get_message_id(message))
    return True


@permissions.require_level(permissions.Level.FULL_ADMIN)
def _cmd_clear_warnings(client, message, group_guid, user_guid):
    if not helpers.is_reply(message):
        client.send_text(group_guid, admin_module.NEED_REPLY_MSG, helpers.get_message_id(message))
        return True
    target = helpers.get_reply_target_guid(message)
    if not target:
        return True
    db.clear_warnings(group_guid, target)
    client.send_text(group_guid, "✅ تمام اخطارهای کاربر پاک شد.", helpers.get_message_id(message))
    return True
