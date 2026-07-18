# -*- coding: utf-8 -*-
"""
core/logger.py
---------------
سیستم لاگ مرکزی LeoBot.
همه ماژول‌ها باید از get_logger() برای ثبت رخداد استفاده کنند.
لاگ‌ها هم در فایل (در صورت امکان) و هم (اختیاری) در دیتابیس ذخیره می‌شوند.

نکات مخصوص Railway / محیط‌های PaaS:
    - stdout به‌صورت Line-Buffered تنظیم می‌شود تا لاگ‌ها بلافاصله در
      داشبورد Railway دیده شوند (بدون این کار، پایتون در محیط غیر-TTY
      خروجی را Block-Buffer می‌کند و ممکن است لاگ‌ها دیر یا اصلاً دیده
      نشوند).
    - اگر فایل‌سیستم فقط‌خواندنی یا غیرقابل‌نوشتن باشد (بعضی پلن‌های
      Railway بدون Volume چنین محدودیتی ندارند، ولی برای اطمینان کامل)،
      راه‌اندازی File Handler در try/except قرار گرفته و در صورت خطا
      فقط لاگ کنسول فعال می‌ماند؛ برنامه هرگز به‌خاطر مشکل لاگ کرش نمی‌کند.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

import config

_LOGGERS = {}
_DB_SINK = None  # بعدا توسط database.database تزریق می‌شود تا وابستگی چرخه‌ای پیش نیاید

# --- خروجی بی‌درنگ برای محیط‌های PaaS مثل Railway ---
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass  # نسخه‌های قدیمی پایتون ممکن است reconfigure نداشته باشند


def attach_db_sink(callback):
    """
    database.database این تابع را با یک callback(level, module, message) صدا می‌زند
    تا لاگ‌های مهم در جدول logs هم ذخیره شوند.
    """
    global _DB_SINK
    _DB_SINK = callback


class DBHandler(logging.Handler):
    def emit(self, record):
        if _DB_SINK is None:
            return
        try:
            _DB_SINK(record.levelname, record.name, self.format(record))
        except Exception:
            # لاگ نباید هرگز باعث کرش برنامه شود
            pass


class FlushingStreamHandler(logging.StreamHandler):
    """StreamHandler که بعد از هر پیام flush می‌کند تا در لاگ‌های Railway فوراً دیده شود."""

    def emit(self, record):
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass


def get_logger(name: str) -> logging.Logger:
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = FlushingStreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        logger.addHandler(console_handler)

        try:
            file_handler = RotatingFileHandler(
                config.LOG_FILE_PATH, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        except Exception as exc:
            # روی برخی محیط‌های PaaS ممکن است مسیر لاگ قابل‌نوشتن نباشد؛
            # در این حالت فقط از کنسول (که Railway آن را جمع‌آوری می‌کند) استفاده می‌شود.
            console_handler.emit(
                logging.LogRecord(
                    name, logging.WARNING, __file__, 0,
                    f"راه‌اندازی لاگ فایل ناموفق بود ({exc})؛ فقط از لاگ کنسول استفاده می‌شود.",
                    None, None,
                )
            )

        db_handler = DBHandler()
        db_handler.setFormatter(fmt)
        db_handler.setLevel(logging.WARNING)  # فقط رخدادهای مهم در دیتابیس
        logger.addHandler(db_handler)

    _LOGGERS[name] = logger
    return logger
