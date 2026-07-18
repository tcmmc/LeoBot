# -*- coding: utf-8 -*-
"""
utils/healthcheck.py
-----------------------
یک سرور HTTP بسیار سبک که فقط به مسیر «/» و «/health» با 200 OK پاسخ
می‌دهد. LeoBot ذاتاً یک Worker است (با Polling به روبیکا وصل می‌شود) و
به HTTP نیازی ندارد؛ اما Railway معمولاً برای سرویس‌های «web» یک پورت
باز شده انتظار دارد و/یا Healthcheck را روی آن انجام می‌دهد. این سرور
در یک ترد جدا و بدون تأثیر روی حلقه‌ی اصلی ربات اجرا می‌شود و اگر به هر
دلیلی نتواند بالا بیاید، فقط لاگ می‌کند و برنامه را متوقف نمی‌کند.
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core.logger import get_logger

log = get_logger("healthcheck")


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"LeoBot is running.")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # جلوگیری از شلوغ شدن لاگ اصلی با درخواست‌های Healthcheck
        pass


def start_healthcheck_server():
    """
    سرور را در یک ترد Daemon جدا اجرا می‌کند تا حلقه‌ی اصلی ربات را بلاک نکند.
    پورت از متغیر محیطی PORT خوانده می‌شود (Railway این مقدار را خودکار می‌فرستد).
    """
    port_str = os.environ.get("PORT")
    if not port_str:
        log.info("متغیر PORT تنظیم نشده؛ سرور Healthcheck اجرا نمی‌شود (نیازی هم نیست).")
        return None

    try:
        port = int(port_str)
        server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
        thread = threading.Thread(target=server.serve_forever, name="healthcheck", daemon=True)
        thread.start()
        log.info(f"سرور Healthcheck روی پورت {port} اجرا شد (مسیر: /health).")
        return server
    except Exception:
        log.exception("راه‌اندازی سرور Healthcheck ناموفق بود؛ ربات بدون آن ادامه می‌دهد.")
        return None
