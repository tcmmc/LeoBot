# -*- coding: utf-8 -*-
"""
modules/locks.py
------------------
مدیریت قفل‌های محتوایی گروه با دستورات فارسی مانند «قفل لینک» و «بازکردن لینک».
همچنین بررسی می‌کند که آیا یک پیام ورودی باید به‌خاطر قفل فعال حذف شود یا نه.
"""

from core.logger import get_logger
from core import permissions
from database import database as db
from utils import helpers

log = get_logger("locks")

LOCK_LABELS = {
    "link": "لینک",
    "text": "متن",
    "photo": "عکس",
    "video": "فیلم",
    "file": "فایل",
    "voice": "ویس",
    "music": "موزیک",
    "gif": "گیف",
    "sticker": "استیکر",
    "forward": "فوروارد",
    "location": "لوکیشن",
    "contact": "مخاطب",
    "poll": "نظرسنجی",
    "post": "پست",
    "story": "استوری",
    "ads": "تبلیغات",
    "words": "کلمات ممنوع",
}
LABEL_TO_KEY = {v: k for k, v in LOCK_LABELS.items()}

# نگاشت نوع پیام دریافتی به کلید قفل
MESSAGE_TYPE_TO_LOCK = {
    "Text": "text",
    "Image": "photo",
    "Video": "video",
    "File": "file",
    "Voice": "voice",
    "Music": "music",
    "Gif": "gif",
    "Sticker": "sticker",
    "Location": "location",
    "ContactMessage": "contact",
    "Poll": "poll",
}


def handle_lock_command(client, message, group_guid, user_guid) -> bool:
    text = helpers.get_message_text(message)

    arg = helpers.command_starts_with(text, "قفل ")
    if arg is not None:
        return _toggle_lock(client, message, group_guid, user_guid, arg, enable=True)

    arg = helpers.command_starts_with(text, "بازکردن ")
    if arg is not None:
        return _toggle_lock(client, message, group_guid, user_guid, arg, enable=False)

    if helpers.command_matches(text, "لیست قفل ها", "لیست قفل‌ها", "لیست قفلها"):
        return _show_locks(client, message, group_guid)

    return False


def _toggle_lock(client, message, group_guid, user_guid, label, enable) -> bool:
    if not permissions.has_level(group_guid, user_guid, permissions.Level.ADMIN):
        client.send_text(
            group_guid,
            "⛔️ فقط ادمین‌ها می‌توانند قفل‌ها را تغییر دهند.",
            helpers.get_message_id(message),
        )
        return True

    label = label.strip()
    key = LABEL_TO_KEY.get(label)
    if key is None:
        client.send_text(
            group_guid,
            f"❗️ نوع قفل «{label}» شناخته‌شده نیست.\nبرای دیدن لیست کامل بنویسید: لیست قفل ها",
            helpers.get_message_id(message),
        )
        return True

    db.toggle_lock(group_guid, key, enable)
    status = "فعال 🔒" if enable else "غیرفعال 🔓"
    client.send_text(
        group_guid,
        f"قفل «{label}» {status} شد.",
        helpers.get_message_id(message),
    )
    log.info(f"قفل {key} در گروه {group_guid} توسط {user_guid} به {enable} تغییر کرد.")
    return True


def _show_locks(client, message, group_guid) -> bool:
    locks = db.get_active_locks(group_guid)
    lines = ["🔐 وضعیت قفل‌های گروه:\n"]
    for key, label in LOCK_LABELS.items():
        state = "🔒 فعال" if locks.get(key) else "🔓 غیرفعال"
        lines.append(f"• {label}: {state}")
    client.send_text(group_guid, "\n".join(lines), helpers.get_message_id(message))
    return True


def check_message_against_locks(client, message, group_guid) -> bool:
    """
    اگر پیام ورودی به‌خاطر قفل فعال باید حذف شود، آن را حذف می‌کند و True برمی‌گرداند.
    """
    locks = db.get_active_locks(group_guid)
    text = helpers.get_message_text(message)
    msg_type = helpers.get_message_type(message)

    reasons = []

    if locks.get("forward") and helpers.is_forwarded(message):
        reasons.append("فوروارد")

    if locks.get("link") and helpers.contains_link(text):
        reasons.append("لینک")

    if locks.get("words"):
        banned = db.list_banned_words(group_guid)
        if helpers.contains_banned_word(text, banned):
            reasons.append("کلمه ممنوع")

    lock_key = MESSAGE_TYPE_TO_LOCK.get(msg_type)
    if lock_key and lock_key != "text" and locks.get(lock_key):
        reasons.append(LOCK_LABELS[lock_key])
    elif lock_key == "text" and locks.get("text") and text:
        # قفل «متن» یعنی هیچ پیام متنی مجاز نیست (برخلاف قفل لینک که فقط لینک را می‌گیرد)
        reasons.append("متن")

    if not reasons:
        return False

    message_id = helpers.get_message_id(message)
    if message_id:
        client.delete_message(group_guid, message_id)
    log.info(f"پیام در گروه {group_guid} به‌دلیل قفل‌های {reasons} حذف شد.")
    return True
