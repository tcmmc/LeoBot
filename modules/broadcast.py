# -*- coding: utf-8 -*-
"""
modules/broadcast.py
-----------------------
ارسال پیام همگانی به تمام کاربرانی که با ربات در PV شروع کرده‌اند.
این ماژول فقط توسط modules/owner_panel.py و بعد از احراز هویت کامل
مالک فراخوانی می‌شود.
"""

import time

from core.logger import get_logger
from database import database as db

log = get_logger("broadcast")


def send_broadcast(client, text: str) -> dict:
    users = db.list_bot_users()
    total = len(users)
    sent, failed = 0, 0

    for row in users:
        try:
            client.send_text(row["user_guid"], text)
            sent += 1
        except Exception as exc:
            failed += 1
            log.error(f"ارسال پیام همگانی به {row['user_guid']} ناموفق بود: {exc}")
            if "block" in str(exc).lower():
                db.mark_user_blocked(row["user_guid"])
        time.sleep(0.35)  # جلوگیری از محدودیت نرخ ارسال روبیکا

    log.info(f"ارسال همگانی پایان یافت. کل: {total}، موفق: {sent}، ناموفق: {failed}")
    return {"total": total, "sent": sent, "failed": failed}
