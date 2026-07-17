# -*- coding: utf-8 -*-
"""
core/events.py
----------------
مرکز مسیریابی رویدادها. هر پیام دریافتی از rubpy از اینجا عبور می‌کند و
بر اساس نوع چت (گروه/PV) و محتوا به ماژول مناسب فرستاده می‌شود.

ترتیب پردازش در گروه‌ها:
    1) ثبت عضویت/فعالیت کاربر در دیتابیس
    2) اجرای مدیریت پنل PV (اگر PV بود، جدا پردازش می‌شود)
    3) بررسی سکوت / آنتی‌اسپم / آنتی‌فلود  -> اگر پیام حذف شد، ادامه نده
    4) بررسی قفل‌های محتوایی               -> اگر پیام حذف شد، ادامه نده
    5) دستورات مدیریتی Reply-محور (بن/اخطار/سکوت/...)
    6) دستورات قفل، تنظیمات، آمار، فیلتر، خوشامد/خداحافظی
    7) پاسخ خودکار بر اساس فیلترها
"""

from core.logger import get_logger
from core import permissions
from database import database as db
from modules import (
    admin as admin_module,
    locks as locks_module,
    anti_spam as anti_spam_module,
    warnings as warnings_module,
    filters as filters_module,
    auto_reply as auto_reply_module,
    welcome as welcome_module,
    goodbye as goodbye_module,
    settings as settings_module,
    statistics as statistics_module,
    owner_panel as owner_panel_module,
)
from utils import helpers

log = get_logger("events")

# ترتیب اجرای دستورهای گروهی؛ هر تابع باید (client, message, group_guid, user_guid) بگیرد
# و در صورت پردازش پیام True برگرداند.
_GROUP_COMMAND_HANDLERS = [
    admin_module.handle_admin_command,
    warnings_module.handle_warning_command,
    locks_module.handle_lock_command,
    filters_module.handle_filter_command,
    auto_reply_module.handle_toggle_command,
    welcome_module.handle_command,
    goodbye_module.handle_command,
    settings_module.handle_command,
    statistics_module.handle_command,
]


def register_handlers(client):
    """
    ثبت handler اصلی روی کلاینت rubpy (BotClient بر پایه‌ی Bot Token).

    توجه: BotClient به‌صورت async کار می‌کند؛ core/client.py خودش
    Bridge لازم بین حلقه‌ی asyncio و پردازش Sync این فایل را انجام
    می‌دهد (ر.ک. RubikaClient.register_update_handler). این تابع فقط
    منطق Sync دیسپچ پیام را در اختیار آن قرار می‌دهد.
    """

    def _on_message(client_wrapper, message):
        try:
            _dispatch_message(client_wrapper, message)
        except Exception:
            log.exception("خطای مدیریت‌نشده هنگام پردازش پیام.")

    client.register_update_handler(_on_message)
    log.info("Event handler های LeoBot با موفقیت ثبت شدند.")


def _dispatch_message(client, message):
    chat_guid = helpers.get_chat_guid(message)
    user_guid = helpers.get_sender_guid(message)

    if not chat_guid or not user_guid:
        return

    is_group = chat_guid.startswith("g0")  # قرارداد GUID روبیکا برای گروه‌ها

    if not is_group:
        _handle_private_message(client, message, user_guid)
        return

    _handle_group_message(client, message, chat_guid, user_guid)


def _handle_private_message(client, message, user_guid):
    text = helpers.get_message_text(message)
    if helpers.normalize_text(text) in ("شروع", "start", "Start"):
        db.register_bot_user(user_guid)
        owner_panel_module.send_entry_point(client, user_guid)
        return

    db.register_bot_user(user_guid)
    owner_panel_module.handle_pv_command(client, message, user_guid)


def _handle_group_message(client, message, group_guid, user_guid):
    db.ensure_group(group_guid)

    first_name = getattr(message, "author_title", "") or ""
    db.upsert_member(group_guid, user_guid, first_name)

    # کاربران و ادمین‌های ربات از فیلترهای امنیتی مستثنی نیستند برای «بن» خودشان،
    # اما بررسی سکوت/آنتی‌اسپم/آنتی‌فلود اول از همه انجام می‌شود.
    if anti_spam_module.enforce(client, message, group_guid, user_guid):
        return

    if locks_module.check_message_against_locks(client, message, group_guid):
        return

    for handler in _GROUP_COMMAND_HANDLERS:
        try:
            if handler(client, message, group_guid, user_guid):
                return
        except Exception:
            log.exception(f"خطا در اجرای handler {handler.__name__}")

    auto_reply_module.try_auto_reply(client, message, group_guid)


def handle_member_joined(client, group_guid, user_guid, first_name=""):
    db.ensure_group(group_guid)
    db.upsert_member(group_guid, user_guid, first_name)
    welcome_module.send_welcome(client, group_guid, user_guid, first_name)


def handle_member_left(client, group_guid, user_guid, first_name=""):
    goodbye_module.send_goodbye(client, group_guid, user_guid, first_name)
    db.remove_member(group_guid, user_guid)
