"""
Logika filter konten (bukan `telegram.ext.filters`, sengaja dikasih nama beda
supaya tidak bentrok import). Berisi: anti-link, anti-nomor-HP, filter kata kasar,
dan pelacak spam per user per chat.
"""
import re
import time

LINK_RE = re.compile(r"https?://\S+|t\.me/\S+|www\.\S+", re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?\d[\d\-\s]{9,14}\d)")

# Daftar kata kasar dasar (Bahasa Indonesia). Silakan tambah/ubah sesuai kebutuhan grup kamu.
BAD_WORDS = [
    "anjing", "babi", "bangsat", "goblok", "tolol", "kontol",
    "memek", "asu", "jancok", "ngentot", "bego", "idiot",
]


def contains_link(text: str) -> bool:
    return bool(text and LINK_RE.search(text))


def contains_phone(text: str) -> bool:
    return bool(text and PHONE_RE.search(text))


def contains_bad_word(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(w in lowered for w in BAD_WORDS)


# ============ ANTI FLOOD / SPAM TRACKER (in-memory, per proses) ============
_spam_tracker = {}  # (chat_id, user_id) -> {"minute": int, "count": int}


def register_message_and_check_spam(chat_id, user_id, threshold: int) -> bool:
    """Catat 1 pesan dari user di chat ini, return True kalau sudah melebihi threshold/menit."""
    key = (chat_id, user_id)
    current_minute = int(time.time() // 60)
    entry = _spam_tracker.get(key)
    if not entry or entry["minute"] != current_minute:
        entry = {"minute": current_minute, "count": 1}
    else:
        entry["count"] += 1
    _spam_tracker[key] = entry
    return entry["count"] > threshold
