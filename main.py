# -*- coding: utf-8 -*-
"""
main.py
--------
نقطه ورود اجرای LeoBot.

اجرا:
    python main.py

LeoBot با Bot Token رسمی روبیکا (BOT_TOKEN در .env) به شبکه متصل می‌شود؛
هیچ لاگین با شماره تلفن یا Session شخصی لازم نیست. اگر اتصال قطع شود،
ربات به‌صورت خودکار و با فاصله‌ی زمانی افزایشی (Exponential Backoff)
دوباره تلاش می‌کند.
"""

import sys
import time

import config
from core.logger import get_logger
from core.client import get_client
from core import events
from database import database as db
from utils.healthcheck import start_healthcheck_server

log = get_logger("main")


def _log_startup_diagnostics():
    """
    اطلاعات محیط اجرا را در لاگ چاپ می‌کند — مخصوصاً برای عیب‌یابی روی
    Railway که دسترسی مستقیم به کنسول سرور ندارید و لاگ تنها ابزار شماست.
    """
    log.info(f"نسخه پایتون: {sys.version.split()[0]}")
    log.info(f"سطح لاگ: {config.LOG_LEVEL}")
    log.info(f"مسیر دیتابیس: {config.DATABASE_PATH}")
    if config.RAILWAY_ENVIRONMENT:
        log.info(
            f"در حال اجرا روی Railway | Environment: {config.RAILWAY_ENVIRONMENT} "
            f"| Service: {config.RAILWAY_SERVICE_NAME}"
        )
    else:
        log.info("متغیر RAILWAY_ENVIRONMENT پیدا نشد؛ اجرا خارج از Railway یا بدون این متغیر است.")
    masked_token = (
        config.BOT_TOKEN[:6] + "…" + config.BOT_TOKEN[-4:]
        if len(config.BOT_TOKEN) > 12 else "***"
    )
    log.info(f"BOT_TOKEN بارگذاری شد ({masked_token}) — طول: {len(config.BOT_TOKEN)} کاراکتر")
    log.info(f"OWNER_ID: {config.OWNER_ID}")
    log.info(f"تعداد مدیران مجاز پنل (PANEL_ADMIN_IDS): {len(config.PANEL_ADMIN_IDS)}")


def _run_once():
    """
    یک بار تلاش برای راه‌اندازی و اجرای ربات. اگر اتصال قطع/خطا رخ دهد
    برمی‌گردد تا حلقه‌ی بیرونی تصمیم به تلاش مجدد بگیرد.
    """
    try:
        client = get_client(config.BOT_TOKEN)
    except ImportError as exc:
        log.error(str(exc))
        sys.exit(1)

    events.register_handlers(client)
    log.info(f"{config.BOT_NAME} با موفقیت روشن شد و در حال گوش‌دادن به پیام‌هاست.")
    client.run_forever()


def main():
    log.info(f"در حال راه‌اندازی {config.BOT_NAME} نسخه {config.BOT_VERSION} ...")

    db.init_db()
    _log_startup_diagnostics()
    start_healthcheck_server()

    delay = config.RECONNECT_DELAY_SECONDS
    while True:
        try:
            _run_once()
            # اگر run_forever بدون خطا برگردد (مثلاً قطع عادی اتصال)، دوباره تلاش کن
            log.warning("اتصال ربات به‌صورت عادی قطع شد؛ در حال تلاش مجدد ...")
            delay = config.RECONNECT_DELAY_SECONDS
        except KeyboardInterrupt:
            log.info("درخواست توقف دریافت شد. در حال خاموش کردن ربات ...")
            break
        except Exception:
            log.exception(
                f"خطای غیرمنتظره در حلقه‌ی اصلی ربات. تلاش مجدد بعد از {delay} ثانیه ..."
            )
            time.sleep(delay)
            delay = min(delay * 2, config.RECONNECT_MAX_DELAY_SECONDS)
            continue


if __name__ == "__main__":
    main()
