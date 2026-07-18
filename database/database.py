# -*- coding: utf-8 -*-
"""
database/database.py
---------------------
تمام تعامل با SQLite از این فایل انجام می‌شود.
این ماژول عمداً بدون هیچ منطق تلگرامی/روبیکایی است؛ فقط CRUD خالص.
Thread-safe با استفاده از یک Lock سراسری، چون رابط ربات چند-نخی است.
"""

import json
import shutil
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import config
from core.logger import get_logger, attach_db_sink

log = get_logger("database")

_lock = threading.RLock()


def _connect():
    conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


_conn = _connect()


SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    guid TEXT PRIMARY KEY,
    title TEXT,
    owner_guid TEXT,
    created_at INTEGER,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS group_settings (
    group_guid TEXT PRIMARY KEY,
    lock_link INTEGER DEFAULT 0,
    lock_text INTEGER DEFAULT 0,
    lock_photo INTEGER DEFAULT 0,
    lock_video INTEGER DEFAULT 0,
    lock_file INTEGER DEFAULT 0,
    lock_voice INTEGER DEFAULT 0,
    lock_music INTEGER DEFAULT 0,
    lock_gif INTEGER DEFAULT 0,
    lock_sticker INTEGER DEFAULT 0,
    lock_forward INTEGER DEFAULT 0,
    lock_location INTEGER DEFAULT 0,
    lock_contact INTEGER DEFAULT 0,
    lock_poll INTEGER DEFAULT 0,
    lock_post INTEGER DEFAULT 0,
    lock_story INTEGER DEFAULT 0,
    lock_ads INTEGER DEFAULT 0,
    lock_words INTEGER DEFAULT 0,
    anti_spam INTEGER DEFAULT 1,
    anti_flood INTEGER DEFAULT 1,
    welcome_enabled INTEGER DEFAULT 0,
    welcome_text TEXT DEFAULT '',
    goodbye_enabled INTEGER DEFAULT 0,
    goodbye_text TEXT DEFAULT '',
    rules_text TEXT DEFAULT '',
    auto_reply_enabled INTEGER DEFAULT 1,
    warn_limit INTEGER DEFAULT 3,
    FOREIGN KEY (group_guid) REFERENCES groups(guid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admins (
    group_guid TEXT NOT NULL,
    user_guid TEXT NOT NULL,
    level TEXT NOT NULL,           -- creator / full_admin / admin
    added_by TEXT,
    added_at INTEGER,
    PRIMARY KEY (group_guid, user_guid)
);

CREATE TABLE IF NOT EXISTS members (
    group_guid TEXT NOT NULL,
    user_guid TEXT NOT NULL,
    first_name TEXT,
    joined_at INTEGER,
    last_activity INTEGER,
    message_count INTEGER DEFAULT 0,
    PRIMARY KEY (group_guid, user_guid)
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_guid TEXT NOT NULL,
    user_guid TEXT NOT NULL,
    reason TEXT,
    admin_guid TEXT,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS mutes (
    group_guid TEXT NOT NULL,
    user_guid TEXT NOT NULL,
    muted_by TEXT,
    muted_at INTEGER,
    until INTEGER,               -- NULL یعنی نامحدود
    PRIMARY KEY (group_guid, user_guid)
);

CREATE TABLE IF NOT EXISTS filters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_guid TEXT NOT NULL,
    keyword TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at INTEGER,
    UNIQUE(group_guid, keyword)
);

CREATE TABLE IF NOT EXISTS banned_words (
    group_guid TEXT NOT NULL,
    word TEXT NOT NULL,
    PRIMARY KEY (group_guid, word)
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,
    module TEXT,
    message TEXT,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS bot_users (
    user_guid TEXT PRIMARY KEY,
    first_name TEXT,
    first_started_at INTEGER,
    last_activity INTEGER,
    is_blocked INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS panel_sessions (
    user_guid TEXT PRIMARY KEY,
    authenticated INTEGER DEFAULT 0,
    failed_attempts INTEGER DEFAULT 0,
    locked_until INTEGER DEFAULT 0,
    last_auth_at INTEGER
);

CREATE TABLE IF NOT EXISTS message_history (
    group_guid TEXT NOT NULL,
    user_guid TEXT NOT NULL,
    text_hash TEXT,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS banned_users (
    group_guid TEXT NOT NULL,
    user_guid TEXT NOT NULL,
    banned_by TEXT,
    banned_at INTEGER,
    reason TEXT,
    PRIMARY KEY (group_guid, user_guid)
);

CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def init_db():
    with _lock:
        _conn.executescript(SCHEMA)
        _conn.commit()
    attach_db_sink(_log_to_db)
    log.info("دیتابیس با موفقیت مقداردهی اولیه شد.")


def _log_to_db(level, module, message):
    with _lock:
        _conn.execute(
            "INSERT INTO logs (level, module, message, created_at) VALUES (?, ?, ?, ?)",
            (level, module, message, int(time.time())),
        )
        _conn.commit()


def _now():
    return int(time.time())


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
def ensure_group(guid: str, title: str = "", owner_guid: str = ""):
    with _lock:
        cur = _conn.execute("SELECT 1 FROM groups WHERE guid = ?", (guid,))
        if cur.fetchone() is None:
            _conn.execute(
                "INSERT INTO groups (guid, title, owner_guid, created_at) VALUES (?, ?, ?, ?)",
                (guid, title, owner_guid, _now()),
            )
            default_antispam = get_bot_setting("default_antispam", "1")
            default_antiflood = get_bot_setting("default_antiflood", "1")
            _conn.execute(
                """INSERT INTO group_settings (group_guid, anti_spam, anti_flood)
                   VALUES (?, ?, ?)""",
                (guid, int(default_antispam), int(default_antiflood)),
            )
            _conn.commit()
            log.info(f"گروه جدید ثبت شد: {guid} ({title})")
        else:
            if title:
                _conn.execute(
                    "UPDATE groups SET title = ? WHERE guid = ?", (title, guid)
                )
                _conn.commit()


def get_group(guid: str):
    with _lock:
        cur = _conn.execute("SELECT * FROM groups WHERE guid = ?", (guid,))
        return cur.fetchone()


def list_groups():
    with _lock:
        cur = _conn.execute("SELECT * FROM groups WHERE is_active = 1")
        return cur.fetchall()


def deactivate_group(guid: str):
    with _lock:
        _conn.execute("UPDATE groups SET is_active = 0 WHERE guid = ?", (guid,))
        _conn.commit()


# ---------------------------------------------------------------------------
# Group settings
# ---------------------------------------------------------------------------
def get_settings(group_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM group_settings WHERE group_guid = ?", (group_guid,)
        )
        row = cur.fetchone()
        if row is None:
            ensure_group(group_guid)
            cur = _conn.execute(
                "SELECT * FROM group_settings WHERE group_guid = ?", (group_guid,)
            )
            row = cur.fetchone()
        return row


def update_setting(group_guid: str, key: str, value):
    allowed_columns = {
        "lock_link", "lock_text", "lock_photo", "lock_video", "lock_file",
        "lock_voice", "lock_music", "lock_gif", "lock_sticker", "lock_forward",
        "lock_location", "lock_contact", "lock_poll", "lock_post", "lock_story",
        "lock_ads", "lock_words", "anti_spam", "anti_flood",
        "welcome_enabled", "welcome_text", "goodbye_enabled", "goodbye_text",
        "rules_text", "auto_reply_enabled", "warn_limit",
    }
    if key not in allowed_columns:
        raise ValueError(f"ستون تنظیمات نامعتبر: {key}")
    with _lock:
        get_settings(group_guid)  # اطمینان از وجود ردیف
        _conn.execute(
            f"UPDATE group_settings SET {key} = ? WHERE group_guid = ?",
            (value, group_guid),
        )
        _conn.commit()


def toggle_lock(group_guid: str, lock_name: str, enable: bool):
    column = f"lock_{lock_name}"
    update_setting(group_guid, column, 1 if enable else 0)


def get_active_locks(group_guid: str):
    row = get_settings(group_guid)
    locks = {}
    for key in row.keys():
        if key.startswith("lock_"):
            locks[key[5:]] = bool(row[key])
    return locks


# ---------------------------------------------------------------------------
# Admins & permission levels
# ---------------------------------------------------------------------------
def set_admin_level(group_guid: str, user_guid: str, level: str, added_by: str = ""):
    with _lock:
        _conn.execute(
            """INSERT INTO admins (group_guid, user_guid, level, added_by, added_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(group_guid, user_guid) DO UPDATE SET level=excluded.level""",
            (group_guid, user_guid, level, added_by, _now()),
        )
        _conn.commit()


def remove_admin_level(group_guid: str, user_guid: str):
    with _lock:
        _conn.execute(
            "DELETE FROM admins WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        _conn.commit()


def get_admin_level(group_guid: str, user_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT level FROM admins WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        row = cur.fetchone()
        return row["level"] if row else None


def list_admins(group_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM admins WHERE group_guid = ?", (group_guid,)
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
def upsert_member(group_guid: str, user_guid: str, first_name: str = ""):
    with _lock:
        cur = _conn.execute(
            "SELECT message_count FROM members WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        row = cur.fetchone()
        if row is None:
            _conn.execute(
                """INSERT INTO members
                   (group_guid, user_guid, first_name, joined_at, last_activity, message_count)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (group_guid, user_guid, first_name, _now(), _now()),
            )
        else:
            _conn.execute(
                """UPDATE members SET first_name = ?, last_activity = ?,
                   message_count = message_count + 1
                   WHERE group_guid = ? AND user_guid = ?""",
                (first_name, _now(), group_guid, user_guid),
            )
        _conn.commit()


def get_member(group_guid: str, user_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM members WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        return cur.fetchone()


def remove_member(group_guid: str, user_guid: str):
    with _lock:
        _conn.execute(
            "DELETE FROM members WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        _conn.commit()


def count_members(group_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT COUNT(*) as c FROM members WHERE group_guid = ?", (group_guid,)
        )
        return cur.fetchone()["c"]


def top_active_members(group_guid: str, limit: int = 10):
    with _lock:
        cur = _conn.execute(
            """SELECT * FROM members WHERE group_guid = ?
               ORDER BY message_count DESC LIMIT ?""",
            (group_guid, limit),
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------
def add_warning(group_guid: str, user_guid: str, admin_guid: str, reason: str = ""):
    with _lock:
        _conn.execute(
            """INSERT INTO warnings (group_guid, user_guid, reason, admin_guid, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (group_guid, user_guid, reason, admin_guid, _now()),
        )
        _conn.commit()
        return count_warnings(group_guid, user_guid)


def count_warnings(group_guid: str, user_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT COUNT(*) as c FROM warnings WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        return cur.fetchone()["c"]


def list_warnings(group_guid: str, user_guid: str):
    with _lock:
        cur = _conn.execute(
            """SELECT * FROM warnings WHERE group_guid = ? AND user_guid = ?
               ORDER BY created_at DESC""",
            (group_guid, user_guid),
        )
        return cur.fetchall()


def clear_warnings(group_guid: str, user_guid: str):
    with _lock:
        _conn.execute(
            "DELETE FROM warnings WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        _conn.commit()


def remove_last_warning(group_guid: str, user_guid: str):
    with _lock:
        cur = _conn.execute(
            """SELECT id FROM warnings WHERE group_guid = ? AND user_guid = ?
               ORDER BY created_at DESC LIMIT 1""",
            (group_guid, user_guid),
        )
        row = cur.fetchone()
        if row:
            _conn.execute("DELETE FROM warnings WHERE id = ?", (row["id"],))
            _conn.commit()
            return True
        return False


# ---------------------------------------------------------------------------
# Mutes
# ---------------------------------------------------------------------------
def mute_user(group_guid: str, user_guid: str, muted_by: str, until: int = None):
    with _lock:
        _conn.execute(
            """INSERT INTO mutes (group_guid, user_guid, muted_by, muted_at, until)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(group_guid, user_guid) DO UPDATE SET
                   muted_by=excluded.muted_by, muted_at=excluded.muted_at, until=excluded.until""",
            (group_guid, user_guid, muted_by, _now(), until),
        )
        _conn.commit()


def unmute_user(group_guid: str, user_guid: str):
    with _lock:
        _conn.execute(
            "DELETE FROM mutes WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        _conn.commit()


def is_muted(group_guid: str, user_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT until FROM mutes WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        row = cur.fetchone()
        if row is None:
            return False
        if row["until"] and row["until"] < _now():
            unmute_user(group_guid, user_guid)
            return False
        return True


# ---------------------------------------------------------------------------
# Banned users (بن نرم‌افزاری — چون Bot API رسمی متد حذف عضو ندارد)
# ---------------------------------------------------------------------------
def add_ban(group_guid: str, user_guid: str, banned_by: str, reason: str = ""):
    with _lock:
        _conn.execute(
            """INSERT INTO banned_users (group_guid, user_guid, banned_by, banned_at, reason)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(group_guid, user_guid) DO UPDATE SET
                   banned_by=excluded.banned_by, banned_at=excluded.banned_at, reason=excluded.reason""",
            (group_guid, user_guid, banned_by, _now(), reason),
        )
        _conn.commit()


def remove_ban(group_guid: str, user_guid: str):
    with _lock:
        _conn.execute(
            "DELETE FROM banned_users WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        _conn.commit()


def is_banned(group_guid: str, user_guid: str) -> bool:
    with _lock:
        cur = _conn.execute(
            "SELECT 1 FROM banned_users WHERE group_guid = ? AND user_guid = ?",
            (group_guid, user_guid),
        )
        return cur.fetchone() is not None


def list_banned(group_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM banned_users WHERE group_guid = ?", (group_guid,)
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Filters (auto reply) & banned words
# ---------------------------------------------------------------------------
def add_filter(group_guid: str, keyword: str, response: str):
    with _lock:
        _conn.execute(
            """INSERT INTO filters (group_guid, keyword, response, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(group_guid, keyword) DO UPDATE SET response=excluded.response""",
            (group_guid, keyword, response, _now()),
        )
        _conn.commit()


def remove_filter(group_guid: str, keyword: str):
    with _lock:
        _conn.execute(
            "DELETE FROM filters WHERE group_guid = ? AND keyword = ?",
            (group_guid, keyword),
        )
        _conn.commit()


def list_filters(group_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM filters WHERE group_guid = ?", (group_guid,)
        )
        return cur.fetchall()


def add_banned_word(group_guid: str, word: str):
    with _lock:
        _conn.execute(
            "INSERT OR IGNORE INTO banned_words (group_guid, word) VALUES (?, ?)",
            (group_guid, word.strip().lower()),
        )
        _conn.commit()


def remove_banned_word(group_guid: str, word: str):
    with _lock:
        _conn.execute(
            "DELETE FROM banned_words WHERE group_guid = ? AND word = ?",
            (group_guid, word.strip().lower()),
        )
        _conn.commit()


def list_banned_words(group_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT word FROM banned_words WHERE group_guid = ?", (group_guid,)
        )
        return [r["word"] for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Bot users (برای Broadcast)
# ---------------------------------------------------------------------------
def register_bot_user(user_guid: str, first_name: str = ""):
    with _lock:
        cur = _conn.execute(
            "SELECT 1 FROM bot_users WHERE user_guid = ?", (user_guid,)
        )
        if cur.fetchone() is None:
            _conn.execute(
                """INSERT INTO bot_users (user_guid, first_name, first_started_at, last_activity)
                   VALUES (?, ?, ?, ?)""",
                (user_guid, first_name, _now(), _now()),
            )
        else:
            _conn.execute(
                "UPDATE bot_users SET last_activity = ?, first_name = ? WHERE user_guid = ?",
                (_now(), first_name, user_guid),
            )
        _conn.commit()


def get_bot_user_row(user_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM bot_users WHERE user_guid = ?", (user_guid,)
        )
        return cur.fetchone()


def list_bot_users():
    with _lock:
        cur = _conn.execute("SELECT * FROM bot_users WHERE is_blocked = 0")
        return cur.fetchall()


def count_bot_users():
    with _lock:
        cur = _conn.execute("SELECT COUNT(*) as c FROM bot_users")
        return cur.fetchone()["c"]


def mark_user_blocked(user_guid: str):
    with _lock:
        _conn.execute(
            "UPDATE bot_users SET is_blocked = 1 WHERE user_guid = ?", (user_guid,)
        )
        _conn.commit()


def total_message_count() -> int:
    """مجموع پیام‌های ثبت‌شده در همه‌ی گروه‌ها (برای «آمار استفاده» پنل ادمین)."""
    with _lock:
        cur = _conn.execute("SELECT COALESCE(SUM(message_count), 0) as c FROM members")
        return cur.fetchone()["c"]


# ---------------------------------------------------------------------------
# Bot settings (تنظیمات سراسری ربات — قابل تغییر از پنل ادمین)
# ---------------------------------------------------------------------------
def get_bot_setting(key: str, default: str = None):
    with _lock:
        cur = _conn.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default


def set_bot_setting(key: str, value: str):
    with _lock:
        _conn.execute(
            """INSERT INTO bot_settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, str(value)),
        )
        _conn.commit()


# ---------------------------------------------------------------------------
# Panel sessions (احراز هویت پنل مالک)
# ---------------------------------------------------------------------------
def get_panel_session(user_guid: str):
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM panel_sessions WHERE user_guid = ?", (user_guid,)
        )
        row = cur.fetchone()
        if row is None:
            _conn.execute(
                "INSERT INTO panel_sessions (user_guid) VALUES (?)", (user_guid,)
            )
            _conn.commit()
            cur = _conn.execute(
                "SELECT * FROM panel_sessions WHERE user_guid = ?", (user_guid,)
            )
            row = cur.fetchone()
        return row


def set_panel_authenticated(user_guid: str, ok: bool):
    with _lock:
        _conn.execute(
            """UPDATE panel_sessions SET authenticated = ?, last_auth_at = ?,
               failed_attempts = 0 WHERE user_guid = ?""",
            (1 if ok else 0, _now(), user_guid),
        )
        _conn.commit()


def register_failed_panel_login(user_guid: str, max_attempts: int, lockout_seconds: int):
    with _lock:
        session = get_panel_session(user_guid)
        attempts = session["failed_attempts"] + 1
        locked_until = 0
        if attempts >= max_attempts:
            locked_until = _now() + lockout_seconds
            attempts = 0
        _conn.execute(
            """UPDATE panel_sessions SET failed_attempts = ?, locked_until = ?
               WHERE user_guid = ?""",
            (attempts, locked_until, user_guid),
        )
        _conn.commit()
        return locked_until


def is_panel_locked(user_guid: str):
    session = get_panel_session(user_guid)
    if session["locked_until"] and session["locked_until"] > _now():
        return session["locked_until"]
    return 0


# ---------------------------------------------------------------------------
# Message history (برای تشخیص پیام تکراری / فلود)
# ---------------------------------------------------------------------------
def add_message_history(group_guid: str, user_guid: str, text_hash: str):
    with _lock:
        _conn.execute(
            """INSERT INTO message_history (group_guid, user_guid, text_hash, created_at)
               VALUES (?, ?, ?, ?)""",
            (group_guid, user_guid, text_hash, _now()),
        )
        _conn.commit()


def recent_message_history(group_guid: str, user_guid: str, window_seconds: int):
    with _lock:
        since = _now() - window_seconds
        cur = _conn.execute(
            """SELECT text_hash, created_at FROM message_history
               WHERE group_guid = ? AND user_guid = ? AND created_at >= ?
               ORDER BY created_at DESC""",
            (group_guid, user_guid, since),
        )
        return cur.fetchall()


def prune_message_history(older_than_seconds: int = 3600):
    with _lock:
        threshold = _now() - older_than_seconds
        _conn.execute("DELETE FROM message_history WHERE created_at < ?", (threshold,))
        _conn.commit()


# ---------------------------------------------------------------------------
# Logs (خواندن برای پنل)
# ---------------------------------------------------------------------------
def get_recent_logs(limit: int = 20):
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------
def create_backup() -> str:
    with _lock:
        _conn.commit()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(config.BACKUP_DIR) / f"leobot_backup_{timestamp}.db"
        shutil.copyfile(config.DATABASE_PATH, backup_path)
        log.info(f"بکاپ دیتابیس ساخته شد: {backup_path}")
        return str(backup_path)


def restore_backup(backup_path: str) -> bool:
    global _conn
    backup_file = Path(backup_path)
    if not backup_file.exists():
        log.error(f"فایل بکاپ پیدا نشد: {backup_path}")
        return False
    with _lock:
        _conn.close()
        shutil.copyfile(backup_file, config.DATABASE_PATH)
        _conn = _connect()
        log.info(f"دیتابیس از بکاپ بازیابی شد: {backup_path}")
        return True


def list_backups():
    backups = sorted(Path(config.BACKUP_DIR).glob("leobot_backup_*.db"), reverse=True)
    return [str(p) for p in backups]
