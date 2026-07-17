# -*- coding: utf-8 -*-
"""
core/logger.py
---------------
سیستم لاگ مرکزی LeoBot.
همه ماژول‌ها باید از get_logger() برای ثبت رخداد استفاده کنند.
لاگ‌ها هم در فایل و هم (اختیاری) در دیتابیس ذخیره می‌شوند.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

import config

_LOGGERS = {}
_DB_SINK = None  # بعدا توسط database.database تزریق می‌شود تا وابستگی چرخه‌ای پیش نیاید


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

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        logger.addHandler(console_handler)

        file_handler = RotatingFileHandler(
            config.LOG_FILE_PATH, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

        db_handler = DBHandler()
        db_handler.setFormatter(fmt)
        db_handler.setLevel(logging.WARNING)  # فقط رخدادهای مهم در دیتابیس
        logger.addHandler(db_handler)

    _LOGGERS[name] = logger
    return logger
