# -*- coding: utf-8 -*-
"""
modules/admin.py
------------------
دستورات مدیریتی Reply-محور: بن، آنبن (رفع بن)، سکوت، رفع سکوت، حذف پیام
و همچنین مدیریت سطح دسترسی داخلی LeoBot (ادمین کن / ادمین کامل کن / حذف ادمین).

طبق درخواست، هیچ دستوری به‌سبک اسلش (/ban ,/kick) استفاده نمی‌شود؛
همه‌چیز فارسی و Reply-محور است.

نکته‌ی فنی مهم (بعد از سوییچ به Bot Token رسمی):
    Bot API رسمی روبیکا هیچ متدی برای حذف واقعی عضو از گروه یا
    محدود کردن یک عضو خاص ندارد (ر.ک. توضیح کامل در core/client.py).
    به همین دلیل «بن» و «سکوت» در LeoBot به‌صورت نرم‌افزاری (Soft) در
    دیتابیس ثبت می‌شوند و modules/anti_spam.py هر پیام بعدی این کاربر
    را با متد رسمی deleteMessage حذف می‌کند. «حذف» چون از متد رسمی
    deleteMessage استفاده می‌کند، کاملاً واقعی است.
"""

from core.logger import get_logger
from core import permissions
from database import database as db
from utils import helpers

log = get_logger("admin")

NEED_REPLY_MSG = "لطفاً روی پیام کاربر Reply کنید."


def _require_reply_target(client, message, group_guid):
    if not helpers.is_reply(message):
        client.send_text(group_guid, NEED_REPLY_MSG, helpers.get_message_id(message))
        return None
    target = helpers.get_reply_target_guid(message)
    if not target:
        client.send_text(
            group_guid,
            "❗️ نتوانستم کاربر مقصد را از پیام Reply‌شده تشخیص دهم.",
            helpers.get_message_id(message),
        )
        return None
    return target


def handle_admin_command(client, message, group_guid, user_guid) -> bool:
    text = helpers.get_message_text(message)
    normalized = helpers.normalize_text(text)

    if helpers.command_matches(normalized, "بن"):
        return _cmd_ban(client, message, group_guid, user_guid)

    if helpers.command_matches(normalized, "رفع بن", "آنبن"):
        return _cmd_unban(client, message, group_guid, user_guid)

    if helpers.command_matches(normalized, "سکوت"):
        return _cmd_mute(client, message, group_guid, user_guid)

    if helpers.command_matches(normalized, "رفع سکوت"):
        return _cmd_unmute(client, message, group_guid, user_guid)

    if helpers.command_matches(normalized, "حذف"):
        return _cmd_delete(client, message, group_guid, user_guid)

    if helpers.command_matches(normalized, "ادمین کن"):
        return _cmd_set_admin(client, message, group_guid, user_guid, level="admin")

    if helpers.command_matches(normalized, "ادمین کامل کن"):
        return _cmd_set_admin(client, message, group_guid, user_guid, level="full_admin")

    if helpers.command_matches(normalized, "حذف ادمین"):
        return _cmd_remove_admin(client, message, group_guid, user_guid)

    if helpers.command_matches(normalized, "لیست ادمین ها", "لیست ادمین‌ها"):
        return _cmd_list_admins(client, message, group_guid, user_guid)

    return False


@permissions.require_level(permissions.Level.ADMIN)
def _cmd_ban(client, message, group_guid, user_guid):
    target = _require_reply_target(client, message, group_guid)
    if not target:
        return True
    if permissions.get_user_level(group_guid, target) >= permissions.get_user_level(
        group_guid, user_guid
    ) and target != user_guid:
        client.send_text(
            group_guid, "⛔️ نمی‌توانید کاربری با سطح دسترسی برابر یا بالاتر را بن کنید.",
            helpers.get_message_id(message),
        )
        return True
    db.add_ban(group_guid, target, banned_by=user_guid)
    db.remove_member(group_guid, target)
    client.send_text(
        group_guid,
        "✅ کاربر بن شد. پیام‌های بعدی این کاربر در گروه به‌صورت خودکار حذف می‌شوند.\n"
        "(توجه: چون بات با توکن رسمی کار می‌کند، حذف کامل عضو از گروه باید توسط "
        "یک ادمین انسانی در خود اپ روبیکا انجام شود.)",
        helpers.get_message_id(message),
    )
    log.info(f"کاربر {target} در گروه {group_guid} توسط {user_guid} بن (نرم) شد.")
    return True


@permissions.require_level(permissions.Level.ADMIN)
def _cmd_unban(client, message, group_guid, user_guid):
    target = _require_reply_target(client, message, group_guid)
    if not target:
        return True
    db.remove_ban(group_guid, target)
    client.send_text(group_guid, "✅ کاربر آنبن (رفع بن) شد.", helpers.get_message_id(message))
    log.info(f"کاربر {target} در گروه {group_guid} توسط {user_guid} آنبن شد.")
    return True


@permissions.require_level(permissions.Level.ADMIN)
def _cmd_mute(client, message, group_guid, user_guid):
    target = _require_reply_target(client, message, group_guid)
    if not target:
        return True
    db.mute_user(group_guid, target, user_guid)
    client.send_text(
        group_guid,
        "🔇 کاربر سکوت شد. پیام‌های ارسالی این کاربر به‌صورت خودکار حذف می‌شوند.",
        helpers.get_message_id(message),
    )
    log.info(f"کاربر {target} در گروه {group_guid} توسط {user_guid} سکوت شد.")
    return True


@permissions.require_level(permissions.Level.ADMIN)
def _cmd_unmute(client, message, group_guid, user_guid):
    target = _require_reply_target(client, message, group_guid)
    if not target:
        return True
    db.unmute_user(group_guid, target)
    client.send_text(group_guid, "🔊 سکوت کاربر رفع شد.", helpers.get_message_id(message))
    log.info(f"سکوت کاربر {target} در گروه {group_guid} توسط {user_guid} رفع شد.")
    return True


@permissions.require_level(permissions.Level.ADMIN)
def _cmd_delete(client, message, group_guid, user_guid):
    if not helpers.is_reply(message):
        client.send_text(group_guid, NEED_REPLY_MSG, helpers.get_message_id(message))
        return True
    reply_id = helpers.get_reply_message_id(message)
    client.delete_message(group_guid, reply_id)
    client.delete_message(group_guid, helpers.get_message_id(message))
    log.info(f"پیام {reply_id} در گروه {group_guid} توسط {user_guid} حذف شد.")
    return True


@permissions.require_level(permissions.Level.FULL_ADMIN)
def _cmd_set_admin(client, message, group_guid, user_guid, level):
    """
    توجه: این دستور فقط سطح دسترسی داخلی LeoBot را تغییر می‌دهد (اینکه کاربر
    بتواند دستورات مدیریتی بات را اجرا کند)، نه نشان ادمین واقعی روبیکا؛
    چون Bot API رسمی متدی برای «تنظیم ادمین گروه» ندارد.
    """
    target = _require_reply_target(client, message, group_guid)
    if not target:
        return True
    db.set_admin_level(group_guid, target, level, added_by=user_guid)
    label = "ادمین کامل" if level == "full_admin" else "ادمین"
    client.send_text(
        group_guid,
        f"✅ کاربر به‌عنوان {label} LeoBot تنظیم شد (این دسترسی فقط داخل بات است).",
        helpers.get_message_id(message),
    )
    log.info(f"سطح دسترسی {target} در گروه {group_guid} به {level} تغییر کرد (توسط {user_guid}).")
    return True


@permissions.require_level(permissions.Level.FULL_ADMIN)
def _cmd_remove_admin(client, message, group_guid, user_guid):
    target = _require_reply_target(client, message, group_guid)
    if not target:
        return True
    db.remove_admin_level(group_guid, target)
    client.send_text(group_guid, "✅ دسترسی ادمینی کاربر در LeoBot حذف شد.", helpers.get_message_id(message))
    log.info(f"دسترسی ادمین {target} در گروه {group_guid} توسط {user_guid} حذف شد.")
    return True


def _cmd_list_admins(client, message, group_guid, user_guid):
    admins = db.list_admins(group_guid)
    if not admins:
        client.send_text(group_guid, "هیچ ادمینی ثبت نشده است.", helpers.get_message_id(message))
        return True
    lines = ["👮‍♂️ لیست ادمین‌های گروه:\n"]
    label_map = {"admin": "ادمین", "full_admin": "ادمین کامل", "creator": "سازنده"}
    for row in admins:
        lines.append(f"• {row['user_guid']} — {label_map.get(row['level'], row['level'])}")
    client.send_text(group_guid, "\n".join(lines), helpers.get_message_id(message))
    return True
