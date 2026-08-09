"""
Konfigurasi bot, dimuat dari environment variable / file .env.
Copy .env.example -> .env lalu isi BOT_TOKEN dan OWNER_IDS sebelum menjalankan bot.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

_owner_raw = os.getenv("OWNER_IDS", "").strip()
OWNER_IDS = {int(x) for x in _owner_raw.split(",") if x.strip().isdigit()}

DB_PATH = os.getenv("DB_PATH", "bcc.db").strip() or "bcc.db"

if not BOT_TOKEN:
    raise SystemExit(
        "❌ BOT_TOKEN belum diisi. Copy .env.example ke .env lalu isi token dari @BotFather."
    )

if not OWNER_IDS:
    print("⚠️  Peringatan: OWNER_IDS kosong. Tidak ada yang bisa akses command owner "
          "(broadcast, ban, config, dll) sampai kamu isi OWNER_IDS di .env.")
