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


def _as_mapping(obj):
    """اگر obj شبیه دیکشنری/آبجکت باشد، یک دیکشنری از فیلدهای آن برمی‌گرداند."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        try:
            return vars(obj)
        except Exception:
            return {}
    return {}


def _deep_find(obj, key_names, _depth=0, _seen=None):
    """
    جست‌وجوی یک مقدار زیر هر کدام از key_names، هم به‌صورت attribute
    (سبک آبجکت‌های rubpy) و هم به‌صورت کلید دیکشنری (سبک JSON خام Bot API
    رسمی روبیکا که فیلدها را زیر new_message/inline_message تو در تو
    می‌گذارد: مثلاً update['new_message']['sender_id']).
    فقط دو سطح تو در تو بررسی می‌شود تا کند نشود.
    """
    if obj is None or _depth > 2:
        return None
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen:
        return None
    _seen.add(obj_id)

    mapping = _as_mapping(obj) if not isinstance(obj, dict) else obj

    # ۱) بررسی مستقیم روی همین سطح (هم attribute هم dict key)
    for key in key_names:
        if isinstance(obj, dict) and key in obj and obj[key]:
            return obj[key]
        value = getattr(obj, key, None)
        if value:
            return value

    # ۲) بررسی داخل زیرساختارهای رایج Bot API رسمی (new_message/inline_message/update)
    for nested_key in ("new_message", "inline_message", "message", "update", "data"):
        nested = mapping.get(nested_key) if isinstance(mapping, dict) else getattr(obj, nested_key, None)
        if nested is not None and nested is not obj:
            result = _deep_find(nested, key_names, _depth + 1, _seen)
            if result:
                return result

    return None


# ---------------------------------------------------------------------------
# استخراج اطلاعات از پیام Reply شده
# ---------------------------------------------------------------------------
def get_reply_target_guid(message) -> str:
    """
    rubpy بسته به نسخه، اطلاعات پیام Reply شده را در فیلدهای مختلفی
    قرار می‌دهد. این تابع چند مسیر رایج و ساختار تو در تو را بررسی می‌کند.
    اگر پیدا نشد، None برمی‌گرداند و ماژول باید به کاربر اعلام کند
    که باید روی پیام Reply بزند.
    """
    reply_obj = _deep_find(message, ("reply_to_message", "reply_message", "reply_object"))
    if reply_obj is not None:
        target = _deep_find(
            reply_obj,
            ("author_object_guid", "sender_guid", "author_guid", "sender_id", "from_guid"),
        )
        if target:
            return target
    # بعضی نسخه‌ها شناسه‌ی فرستنده‌ی پیام Reply‌شده را مستقیم روی خود پیام می‌گذارند
    return _deep_find(message, ("reply_to_author_guid", "reply_sender_guid"))


def get_reply_message_id(message) -> str:
    direct = _deep_find(message, ("reply_to_message_id", "reply_message_id"))
    if direct:
        return direct
    reply_obj = _deep_find(message, ("reply_to_message", "reply_message", "reply_object"))
    if reply_obj is not None:
        return _deep_find(reply_obj, ("message_id", "id"))
    return None


def is_reply(message) -> bool:
    return bool(get_reply_message_id(message))


def get_sender_guid(message) -> str:
    return _deep_find(
        message,
        ("author_object_guid", "author_guid", "sender_guid", "from_guid", "sender_id", "user_id"),
    )


def get_chat_guid(message) -> str:
    return _deep_find(
        message,
        ("object_guid", "chat_guid", "group_guid", "chat_id"),
    )


def get_message_text(message) -> str:
    return _deep_find(message, ("text", "message_text", "raw_text")) or ""


def get_message_id(message) -> str:
    return _deep_find(message, ("message_id", "id"))


def get_message_type(message) -> str:
    """
    مقادیر رایج: Text, Image, Video, File, Voice, Music, Gif, Sticker,
    Location, ContactMessage, Poll, ForwardedMessage
    """
    return _deep_find(message, ("type", "message_type")) or "Text"


def is_forwarded(message) -> bool:
    return bool(_deep_find(message, ("forwarded_from", "is_forward", "forwarded_no")))


def get_button_id(message) -> str:
    """
    شناسه‌ی دکمه‌ای که کاربر زده (کلیک روی Inline Keypad). طبق مستندات
    رسمی Bot API روبیکا، این مقدار زیر ``aux_data.button_id`` قرار دارد؛
    اما چون ساختار دقیق بسته به نسخه‌ی rubpy ممکن است فرق کند، چند حالت
    رایج بررسی می‌شود.
    """
    aux = _deep_find(message, ("aux_data", "button_data", "callback_data"))
    if aux is None:
        return None
    if isinstance(aux, dict):
        return aux.get("button_id") or aux.get("id")
    return getattr(aux, "button_id", None) or getattr(aux, "id", None) or aux


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
