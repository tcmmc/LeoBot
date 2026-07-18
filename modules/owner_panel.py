# -*- coding: utf-8 -*-
"""
modules/owner_panel.py
-------------------------
پنل مدیریت خصوصی داخل PV ربات. فقط برای مدیرانی که شناسه‌شان در
config.PANEL_ADMIN_IDS (مالک + مدیران اضافه‌شده در .env) باشد در دسترس است.

روند:
    1) مدیر در PV پیام می‌دهد؛ دکمه‌ی «🔐 پنل ادمین» نمایش داده می‌شود
       (یا دستور متنی «پنل ادمین» را می‌فرستد).
    2) ربات رمز عبور را درخواست می‌کند.
    3) اگر رمز درست بود پنل دکمه‌ای نمایش داده می‌شود.
    4) اگر رمز اشتباه بود، دسترسی رد و در Log ثبت می‌شود (با محدودیت تعداد تلاش).

امنیت:
    - شناسه‌ی فرستنده همیشه با config.PANEL_ADMIN_IDS مقایسه می‌شود
      (نه صرفاً «کسی که رمز را می‌داند»)؛ کاربران عادی حتی دکمه‌ی ورود
      به پنل را هم نمی‌بینند.
    - رمز هرگز در کد نیست؛ فقط هش آن در .env نگه‌داری می‌شود
      (core/security.py، مقدار پیش‌فرض طبق نیاز پروژه: GG777mahi).
    - وضعیت ورود (state machine) در حافظه نگه‌داری می‌شود، نه در دیتابیس دائمی.
"""

import config
from core.logger import get_logger
from core import security
from database import database as db
from modules import broadcast as broadcast_module
from utils import helpers

log = get_logger("owner_panel")

# state machine ساده برای هر کاربر:
# {"stage": "await_password" | "await_broadcast" | "await_greeting" | None}
_SESSION_STATE = {}

MENU_BUTTONS = [
    [("bc", "📢 اطلاع‌رسانی همگانی")],
    [("users_count", "👥 تعداد کاربران"), ("users_list", "📋 لیست کاربران")],
    [("usage_stats", "📈 آمار استفاده"), ("groups", "🏘 گروه‌های بات")],
    [("logs", "📝 لاگ‌ها"), ("backup", "💾 بکاپ")],
    [("settings", "⚙ تنظیمات بات"), ("logout", "🔒 خروج")],
]

SETTINGS_BUTTONS = [
    [("toggle_antispam", "آنتی‌اسپم پیش‌فرض"), ("toggle_antiflood", "آنتی‌فلود پیش‌فرض")],
    [("edit_greeting", "✏️ تغییر پیام خوش‌آمد PV")],
    [("back", "🔙 بازگشت به منو")],
]

ENTRY_BUTTON_ID = "open_panel"


def is_panel_admin(user_guid: str) -> bool:
    return user_guid in config.PANEL_ADMIN_IDS


def send_entry_point(client, user_guid: str):
    """
    وقتی کاربری ربات را در PV Start می‌کند این تابع صدا زده می‌شود.
    دکمه‌ی ورود به پنل فقط به مدیرانِ مجاز نمایش داده می‌شود؛ کاربران
    عادی فقط پیام خوش‌آمد ساده می‌بینند و هیچ دسترسی مدیریتی ندارند.
    """
    greeting = db.get_bot_setting("pv_greeting") or f"سلام 👋 به {config.BOT_NAME} خوش آمدید."
    client.send_text(user_guid, greeting)

    if not is_panel_admin(user_guid):
        return

    keypad = helpers.build_inline_keypad(
        [[{"id": ENTRY_BUTTON_ID, "type": "Simple", "button_text": "🔐 پنل ادمین"}]]
    )
    result = client.send_keypad(user_guid, "برای مدیریت ربات دکمه زیر را بزنید:", inline_keypad=keypad)
    if result is None:
        client.send_text(user_guid, "برای مدیریت ربات بنویسید: پنل ادمین")


def handle_pv_command(client, message, user_guid) -> bool:
    """
    پردازش پیام‌های متنی/دکمه‌ای PV مربوط به پنل. اگر پیام مربوط به پنل نبود False.
    """
    if not is_panel_admin(user_guid):
        return False  # پنل فقط برای مدیران مجاز است؛ سایر پیام‌های PV نادیده گرفته می‌شوند

    text = helpers.normalize_text(helpers.get_message_text(message))
    state = _SESSION_STATE.get(user_guid, {})

    # ورودی پنل
    if text in ("پنل ادمین", "panel") or _is_button(message, ENTRY_BUTTON_ID):
        return _start_login(client, message, user_guid)

    # مرحله انتظار رمز
    if state.get("stage") == "await_password":
        return _check_password(client, message, user_guid, text)

    # مرحله انتظار متن اطلاع‌رسانی
    if state.get("stage") == "await_broadcast":
        return _do_broadcast(client, message, user_guid, text)

    # مرحله انتظار متن جدید خوش‌آمدگویی PV
    if state.get("stage") == "await_greeting":
        return _set_greeting(client, message, user_guid, text)

    # دکمه‌های منو (فقط اگر قبلاً با رمز وارد شده باشد)
    if security.is_panel_authenticated(user_guid):
        button_id = _extract_button_id(message)
        if button_id:
            return _handle_menu_button(client, message, user_guid, button_id)

    return False


def _is_button(message, expected_id) -> bool:
    button_id = helpers.get_button_id(message)
    return button_id == expected_id


def _extract_button_id(message):
    return helpers.get_button_id(message)


def _start_login(client, message, user_guid):
    locked_until = db.is_panel_locked(user_guid)
    if locked_until:
        remaining = security.panel_lock_remaining_seconds(user_guid)
        client.send_text(
            user_guid, f"🔒 به‌دلیل تلاش‌های ناموفق، دسترسی موقتاً قفل است. ({remaining} ثانیه دیگر تلاش کنید)"
        )
        log.warning(f"تلاش ورود به پنل در حالی که قفل است: {user_guid}")
        return True

    _SESSION_STATE[user_guid] = {"stage": "await_password"}
    client.send_text(user_guid, "🔑 لطفاً رمز عبور پنل ادمین را ارسال کنید:")
    return True


def _check_password(client, message, user_guid, raw_password):
    ok = security.verify_panel_password(user_guid, raw_password)
    if ok:
        _SESSION_STATE[user_guid] = {"stage": None}
        _send_menu(client, user_guid)
    else:
        locked_until = db.is_panel_locked(user_guid)
        if locked_until:
            _SESSION_STATE[user_guid] = {"stage": None}
            client.send_text(user_guid, "❌ رمز اشتباه بود و دسترسی موقتاً قفل شد.")
        else:
            client.send_text(user_guid, "❌ رمز اشتباه است. دوباره تلاش کنید:")
    return True


def _send_keypad_or_fallback(client, user_guid, text, rows):
    keypad = helpers.build_inline_keypad(
        [[{"id": bid, "type": "Simple", "button_text": label} for bid, label in row] for row in rows]
    )
    result = client.send_keypad(user_guid, text, inline_keypad=keypad)
    if result is None:
        options = "\n".join(f"- {label}" for row in rows for _, label in row)
        client.send_text(user_guid, f"{text}\n\n{options}")


def _send_menu(client, user_guid):
    _send_keypad_or_fallback(client, user_guid, "🔐 پنل مدیریت LeoBot:", MENU_BUTTONS)


def _send_settings_menu(client, user_guid):
    antispam = "فعال" if db.get_bot_setting("default_antispam", "1") == "1" else "غیرفعال"
    antiflood = "فعال" if db.get_bot_setting("default_antiflood", "1") == "1" else "غیرفعال"
    text = (
        "⚙ تنظیمات سراسری بات:\n\n"
        f"• آنتی‌اسپم پیش‌فرض گروه‌های جدید: {antispam}\n"
        f"• آنتی‌فلود پیش‌فرض گروه‌های جدید: {antiflood}\n\n"
        "برای تغییر هرکدام، دکمه‌ی مربوطه را بزنید:"
    )
    _send_keypad_or_fallback(client, user_guid, text, SETTINGS_BUTTONS)


def _handle_menu_button(client, message, user_guid, button_id):
    if button_id == "bc":
        _SESSION_STATE[user_guid] = {"stage": "await_broadcast"}
        client.send_text(user_guid, "✍️ متن پیام همگانی را ارسال کنید:")
        return True

    if button_id == "users_count":
        total = db.count_bot_users()
        client.send_text(user_guid, f"👥 تعداد کل کاربرانی که بات را Start کرده‌اند: {total}")
        return True

    if button_id == "users_list":
        rows = db.list_bot_users()
        if not rows:
            client.send_text(user_guid, "هنوز کاربری بات را Start نکرده است.")
            return True
        preview = rows[:30]
        lines = [f"• {r['first_name'] or 'بدون‌نام'} — {r['user_guid']}" for r in preview]
        more = f"\n\n... و {len(rows) - len(preview)} کاربر دیگر" if len(rows) > len(preview) else ""
        client.send_text(user_guid, "📋 لیست کاربران (حداکثر ۳۰ مورد):\n\n" + "\n".join(lines) + more)
        return True

    if button_id == "usage_stats":
        groups = db.list_groups()
        client.send_text(
            user_guid,
            "📈 آمار استفاده:\n\n"
            f"• گروه‌های فعال: {len(groups)}\n"
            f"• کاربران PV: {db.count_bot_users()}\n"
            f"• مجموع پیام‌های ثبت‌شده در گروه‌ها: {db.total_message_count()}",
        )
        return True

    if button_id == "groups":
        groups = db.list_groups()
        if not groups:
            client.send_text(user_guid, "بات هنوز داخل هیچ گروهی نیست.")
            return True
        lines = [f"• {g['title'] or 'بدون‌نام'} — {g['guid']}" for g in groups]
        client.send_text(user_guid, "🏘 گروه‌های فعال بات:\n\n" + "\n".join(lines))
        return True

    if button_id == "logs":
        rows = db.get_recent_logs(15)
        if not rows:
            client.send_text(user_guid, "لاگی ثبت نشده است.")
            return True
        lines = [f"[{r['level']}] {helpers.human_time(r['created_at'])} — {r['message'][:80]}" for r in rows]
        client.send_text(user_guid, "📝 آخرین لاگ‌ها:\n\n" + "\n".join(lines))
        return True

    if button_id == "backup":
        path = db.create_backup()
        client.send_text(user_guid, f"💾 بکاپ با موفقیت ساخته شد:\n{path}")
        return True

    if button_id == "settings":
        _send_settings_menu(client, user_guid)
        return True

    if button_id == "toggle_antispam":
        current = db.get_bot_setting("default_antispam", "1")
        db.set_bot_setting("default_antispam", "0" if current == "1" else "1")
        _send_settings_menu(client, user_guid)
        return True

    if button_id == "toggle_antiflood":
        current = db.get_bot_setting("default_antiflood", "1")
        db.set_bot_setting("default_antiflood", "0" if current == "1" else "1")
        _send_settings_menu(client, user_guid)
        return True

    if button_id == "edit_greeting":
        _SESSION_STATE[user_guid] = {"stage": "await_greeting"}
        client.send_text(user_guid, "✍️ متن جدید پیام خوش‌آمدگویی PV را ارسال کنید:")
        return True

    if button_id == "back":
        _send_menu(client, user_guid)
        return True

    if button_id == "logout":
        security.logout_panel(user_guid)
        _SESSION_STATE[user_guid] = {"stage": None}
        client.send_text(user_guid, "🔒 از پنل خارج شدید.")
        return True

    return False


def _set_greeting(client, message, user_guid, text):
    if not text:
        client.send_text(user_guid, "متن نمی‌تواند خالی باشد. دوباره ارسال کنید:")
        return True
    db.set_bot_setting("pv_greeting", text)
    _SESSION_STATE[user_guid] = {"stage": None}
    client.send_text(user_guid, "✅ پیام خوش‌آمدگویی PV بروزرسانی شد.")
    log.info(f"پیام خوش‌آمد PV توسط {user_guid} تغییر کرد.")
    return True


def _do_broadcast(client, message, user_guid, text):
    if not text:
        client.send_text(user_guid, "متن نمی‌تواند خالی باشد. دوباره ارسال کنید:")
        return True
    _SESSION_STATE[user_guid] = {"stage": None}
    client.send_text(user_guid, "⏳ در حال ارسال پیام همگانی ...")
    result = broadcast_module.send_broadcast(client, text)
    client.send_text(
        user_guid,
        f"✅ ارسال پایان یافت.\nکل: {result['total']}\nموفق: {result['sent']}\nناموفق: {result['failed']}",
    )
    return True
