"""
Lapisan database SQLite — menggantikan window.storage (browser) versi HTML lama.
Semua data (users, groups, banned, blacklist, config) disimpan permanen di file .db,
jadi tetap ada walau bot di-restart / dipindah server.
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

from config import DB_PATH

_lock = threading.Lock()

DEFAULT_SETTINGS = {
    "lockChat": False,
    "lockReplyMessage": "Bot sedang dalam mode maintenance 🔒",
    "autoBan": True,
    "welcome": True,
    "welcomeText": "Selamat datang di bot kami! 🎉",
    "antiLink": False,
    "antiPhone": False,
    "filterBad": True,
    "rateLimit": 5,
    "spamThreshold": 3,
}


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _lock, get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                chat_id TEXT,
                message_count INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                last_seen TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                title TEXT,
                added_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id TEXT PRIMARY KEY
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
        # Pastikan baris settings default ada
        c.execute("SELECT value FROM kv WHERE key = 'settings'")
        if c.fetchone() is None:
            c.execute("INSERT INTO kv (key, value) VALUES ('settings', ?)",
                      (json.dumps(DEFAULT_SETTINGS),))


# ============ SETTINGS ============
def get_settings():
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key = 'settings'").fetchone()
        if not row:
            return dict(DEFAULT_SETTINGS)
        data = json.loads(row["value"])
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        return merged


def save_settings(settings: dict):
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO kv (key, value) VALUES ('settings', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (json.dumps(settings),),
        )


def update_setting(key, value):
    settings = get_settings()
    settings[key] = value
    save_settings(settings)
    return settings


# ============ USERS ============
def upsert_user(user_id, first_name, last_name, username, chat_id):
    now = datetime.now().isoformat(timespec="seconds")
    with _lock, get_conn() as conn:
        existing = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE users SET first_name=?, last_name=?, username=?, chat_id=?,
                   message_count = message_count + 1, last_seen=? WHERE id=?""",
                (first_name, last_name or "", username or "", str(chat_id), now, user_id),
            )
            is_new = False
        else:
            conn.execute(
                """INSERT INTO users (id, first_name, last_name, username, chat_id,
                   message_count, is_banned, last_seen) VALUES (?,?,?,?,?,1,0,?)""",
                (user_id, first_name, last_name or "", username or "", str(chat_id), now),
            )
            is_new = True
        return is_new


def get_all_users():
    with _lock, get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY last_seen DESC")]


def get_user(user_id):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def set_user_banned(user_id, banned: bool):
    with _lock, get_conn() as conn:
        conn.execute("UPDATE users SET is_banned = ? WHERE id = ?", (1 if banned else 0, user_id))


def count_users():
    with _lock, get_conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]


def count_banned():
    with _lock, get_conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM users WHERE is_banned = 1").fetchone()["c"]


def total_messages():
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT COALESCE(SUM(message_count),0) s FROM users").fetchone()
        return row["s"]


# ============ GROUPS ============
def add_group(chat_id, title):
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO groups (id, title, added_at) VALUES (?,?,?)",
            (str(chat_id), title or str(chat_id), datetime.now().isoformat(timespec="seconds")),
        )


def remove_group(chat_id):
    with _lock, get_conn() as conn:
        conn.execute("DELETE FROM groups WHERE id = ?", (str(chat_id),))


def get_groups():
    with _lock, get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM groups ORDER BY added_at DESC")]


def is_group_registered(chat_id):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT id FROM groups WHERE id = ?", (str(chat_id),)).fetchone()
        return row is not None


# ============ BLACKLIST ============
def add_blacklist(user_id):
    with _lock, get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO blacklist (user_id) VALUES (?)", (str(user_id),))


def remove_blacklist(user_id):
    with _lock, get_conn() as conn:
        conn.execute("DELETE FROM blacklist WHERE user_id = ?", (str(user_id),))


def get_blacklist():
    with _lock, get_conn() as conn:
        return [r["user_id"] for r in conn.execute("SELECT user_id FROM blacklist")]


def is_blacklisted(user_id):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT user_id FROM blacklist WHERE user_id = ?", (str(user_id),)).fetchone()
        return row is not None
