# -*- coding: utf-8 -*-
"""
utils/helpers.py
------------------
توابع کمکی مشترک بین ماژول‌ها. هیچ منطق دیتابیسی یا مدیریتی اینجا نیست؛
فقط ابزارهای عمومی متن/پیام/کیبورد.
"""

import re
import time

LINK_PATTERN = re.compile(
    r"((https?://)|(www\.)|(\brubika\.ir/)|(@[\w\d_]{4,}))", re.IGNORECASE
)


def normalize_text(text: str) -> str:
    return (text or "").strip()


def extract_first_word(text: str) -> str:
    text = normalize_text(text)
    return text.split(" ", 1)[0] if text else ""


def command_matches(text: str, *keywords) -> bool:
    """
    بررسی می‌کند آیا متن دقیقاً برابر یکی از دستورات فارسی است (بدون‌حساس بودن به فاصله اضافه).
    """
    normalized = normalize_text(text)
    return normalized in keywords


def command_starts_with(text: str, *keywords):
    """
    اگر متن با یکی از دستورات شروع شود، بقیه‌ی متن (آرگومان) را برمی‌گرداند؛
    در غیر این صورت None.
    """
    normalized = normalize_text(text)
    for kw in keywords:
        if normalized.startswith(kw):
            remainder = normalized[len(kw):].strip()
            return remainder
    return None


def contains_link(text: str) -> bool:
    if not text:
        return False
    return bool(LINK_PATTERN.search(text))


def contains_banned_word(text: str, banned_words) -> bool:
    if not text or not banned_words:
        return False
    lowered = text.lower()
    return any(word in lowered for word in banned_words)


# ---------------------------------------------------------------------------
# استخراج اطلاعات از پیام Reply شده
# ---------------------------------------------------------------------------
def get_reply_target_guid(message) -> str:
    """
    rubpy بسته به نسخه، اطلاعات پیام Reply شده را در فیلدهای مختلفی
    قرار می‌دهد. این تابع چند مسیر رایج را امتحان می‌کند.
    اگر پیدا نشد، None برمی‌گرداند و ماژول باید به کاربر اعلام کند
    که باید روی پیام Reply بزند.
    """
    candidates = [
        lambda: message.reply_to_message.author_object_guid,
        lambda: message.reply_to_message.sender_guid,
        lambda: message.reply_message.author_guid,
        lambda: message.reply_object.author_guid,
    ]
    for getter in candidates:
        try:
            value = getter()
            if value:
                return value
        except AttributeError:
            continue
    return None


def get_reply_message_id(message) -> str:
    candidates = [
        lambda: message.reply_to_message_id,
        lambda: message.reply_to_message.message_id,
        lambda: message.reply_message_id,
    ]
    for getter in candidates:
        try:
            value = getter()
            if value:
                return value
        except AttributeError:
            continue
    return None


def is_reply(message) -> bool:
    return bool(get_reply_message_id(message))


def get_sender_guid(message) -> str:
    for attr in ("author_object_guid", "author_guid", "sender_guid", "from_guid"):
        value = getattr(message, attr, None)
        if value:
            return value
    return None


def get_chat_guid(message) -> str:
    for attr in ("object_guid", "chat_guid", "group_guid"):
        value = getattr(message, attr, None)
        if value:
            return value
    return None


def get_message_text(message) -> str:
    for attr in ("text", "message_text", "raw_text"):
        value = getattr(message, attr, None)
        if value:
            return value
    return ""


def get_message_id(message) -> str:
    for attr in ("message_id", "id"):
        value = getattr(message, attr, None)
        if value:
            return value
    return None


def get_message_type(message) -> str:
    """
    مقادیر رایج: Text, Image, Video, File, Voice, Music, Gif, Sticker,
    Location, ContactMessage, Poll, ForwardedMessage
    """
    for attr in ("type", "message_type"):
        value = getattr(message, attr, None)
        if value:
            return value
    return "Text"


def is_forwarded(message) -> bool:
    return bool(getattr(message, "forwarded_from", None) or getattr(message, "is_forward", False))


# ---------------------------------------------------------------------------
# قالب‌بندی متن
# ---------------------------------------------------------------------------
def bold(text: str) -> str:
    return f"**{text}**"


def code(text: str) -> str:
    return f"`{text}`"


def human_time(ts: int) -> str:
    if not ts:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def build_keypad_row(buttons):
    """
    ساخت یک ردیف کیبورد شیشه‌ای ساده به شکل دیکشنری قابل استفاده
    توسط rubpy برای ارسال Inline Keypad.
    """
    return [{"id": btn_id, "type": "Simple", "button_text": text} for btn_id, text in buttons]


def build_inline_keypad(rows):
    return {"rows": [{"buttons": row} for row in rows]}
