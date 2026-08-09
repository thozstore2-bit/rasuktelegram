# BCC Cyber Suite — Python Edition

Bot Telegram moderasi & kontrol grup, port dari dashboard HTML lama.
Bedanya: ini **bot Python beneran** yang jalan terus di server/VPS kamu (bukan
cuma UI di browser yang manggil Telegram API dan berhenti kalau tab ditutup),
dan datanya disimpan permanen di SQLite (`bcc.db`).

## Fitur

- 👋 Welcome message otomatis untuk member baru
- 🔗 Anti-Link — auto hapus pesan berisi link
- 📱 Anti-Phone — auto hapus pesan berisi nomor HP
- 🔞 Filter kata kasar — auto hapus pesan berisi kata tidak pantas
- 🛡️ Auto-Ban Spam — ban otomatis kalau pesan/menit melebihi threshold
- 🔒 Lock Chat Mode — mode maintenance, semua chat masuk dibalas pesan custom
- 📢 Broadcast — kirim pesan ke semua user yang pernah chat ke bot
- 👥 Kelola grup — daftar, keluar dari semua grup terdaftar
- 🛠️ Admin tools — promote/demote/mute/unmute/pin/unpin/list admin/member count
- ⛔ Ban / Unban / Blacklist user
- 📊 Statistik (total user, grup, pesan, banned)

Semua pengaturan (ON/OFF fitur, teks welcome, dll) disimpan di database dan
diubah lewat command Telegram — tidak perlu dashboard web sama sekali.

## Instalasi

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```env
BOT_TOKEN=isi_token_dari_botfather
OWNER_IDS=id_telegram_kamu
```

Cara dapat token: chat **@BotFather** di Telegram → `/mybots` (atau
`/newbot` untuk bikin baru) → **API Token**.

Cara cari ID Telegram sendiri: chat **@userinfobot**.

## Menjalankan

```bash
python bot.py
```

Bot langsung jalan pakai mode polling (tidak perlu domain/HTTPS/webhook).
Biarkan proses ini tetap berjalan (pakai `pm2`, `screen`, `tmux`, systemd,
atau Pterodactyl/panel VPS) supaya bot online 24 jam.

## Daftar Command

Ketik `/help` di chat bot — daftar command owner otomatis muncul kalau ID
kamu ada di `OWNER_IDS`.

Ringkasan:

| Command | Fungsi |
|---|---|
| `/stats` | Statistik dashboard |
| `/status` | Lihat semua pengaturan aktif |
| `/togglewelcome`, `/setwelcometext <teks>` | Atur welcome message |
| `/togglelock`, `/setlockmsg <teks>` | Atur lock-chat mode |
| `/toggleautoban`, `/setspamthreshold <n>` | Atur auto-ban spam |
| `/toggleantilink` / `/toggleantiphone` / `/togglefilterbad` | Atur filter konten |
| `/broadcast <pesan>` | Kirim pesan ke semua user |
| `/ban <id>` / `/unban <id>` | Ban/unban (bisa reply pesan juga) |
| `/blacklist add\|remove\|list [id]` | Kelola blacklist |
| `/addgroup`, `/groups`, `/leaveallgroups` | Kelola grup terdaftar |
| `/promote` `/demote` `/mute` `/unmute` `/pin` `/unpin` `/admins` `/membercount` | Admin tools grup (reply ke user target) |

## Catatan Keamanan

- Semua command sensitif (config, ban, broadcast, admin tools) dibatasi
  hanya untuk ID di `OWNER_IDS` — orang lain yang chat bot cuma bisa
  `/start` dan `/help`.
- Jangan commit file `.env` ke Git / bagikan ke publik — isinya token bot.
- File `bcc.db` berisi daftar user & grup yang pernah interaksi dengan bot;
  perlakukan sebagai data pribadi.

## Struktur Project

```
pybot/
├── bot.py             # Entry point + semua command handler
├── database.py        # Lapisan SQLite (users, groups, blacklist, settings)
├── filters_logic.py   # Anti-link, anti-phone, filter kata kasar, anti-flood
├── config.py           # Loader BOT_TOKEN & OWNER_IDS dari .env
├── requirements.txt
├── .env.example
└── README.md
```

## Menambah Fitur

- **Tambah kata kasar** → edit `BAD_WORDS` di `filters_logic.py`.
- **Tambah command baru** → buat fungsi `async def cmd_xxx(update, context)`
  di `bot.py`, lalu daftarkan dengan
  `app.add_handler(CommandHandler("xxx", cmd_xxx))` di `build_app()`.
- **Deploy sebagai webhook (bukan polling)** → ganti `app.run_polling(...)`
  di `main()` jadi `app.run_webhook(listen="0.0.0.0", port=..., webhook_url=...)`
  (butuh domain HTTPS).
