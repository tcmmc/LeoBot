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

log = get_logger("main")


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
