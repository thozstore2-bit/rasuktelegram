"""
BCC Cyber Suite — versi Python (pengganti dashboard HTML).
Semua fitur di dashboard lama (welcome, anti-link, anti-phone, filter kata kasar,
auto-ban spam, lock-chat mode, broadcast, kelola user/grup, admin tools, blacklist)
sekarang jalan sungguhan sebagai bot Telegram, bukan cuma tombol di browser.

Jalankan: python bot.py
"""
import asyncio
import functools
import logging

from telegram import ChatPermissions, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import database as db
import filters_logic as flt
from config import BOT_TOKEN, OWNER_IDS

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bcc-bot")


# ============================================================
# HELPERS
# ============================================================
def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


def owner_only(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        if not update.effective_user or not is_owner(update.effective_user.id):
            await update.effective_message.reply_text("❌ Command ini khusus Owner.")
            return
        return await func(update, context, *a, **kw)
    return wrapper


def fmt_bool(v: bool) -> str:
    return "✅ ON" if v else "❌ OFF"


async def track_group(update: Update):
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.add_group(chat.id, chat.title)


async def _auto_delete(context: ContextTypes.DEFAULT_TYPE, chat_id, message_id, delay=8):
    """Hapus pesan warning otomatis setelah beberapa detik (tanpa perlu job-queue extra)."""
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id, message_id)
    except TelegramError:
        pass


# ============================================================
# BASIC COMMANDS
# ============================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *BCC Cyber Suite* — Python Edition\n\n"
        "Bot moderasi & kontrol grup. Ketik /help untuk lihat semua perintah.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_own = update.effective_user and is_owner(update.effective_user.id)
    text = (
        "📖 *DAFTAR PERINTAH*\n\n"
        "👤 *Umum*\n"
        "/start — mulai\n"
        "/help — bantuan ini\n"
        "/stats — statistik bot (khusus owner)\n\n"
    )
    if is_own:
        text += (
            "👑 *Owner — Config*\n"
            "/status — lihat semua pengaturan aktif\n"
            "/togglewelcome — ON/OFF pesan welcome\n"
            "/setwelcometext <teks> — ubah teks welcome\n"
            "/togglelock — ON/OFF lock-chat mode (maintenance)\n"
            "/setlockmsg <teks> — ubah balasan saat lock aktif\n"
            "/toggleautoban — ON/OFF auto-ban spammer\n"
            "/setspamthreshold <angka> — batas pesan/menit sebelum di-ban\n"
            "/toggleantilink — ON/OFF hapus pesan berisi link\n"
            "/toggleantiphone — ON/OFF hapus pesan berisi nomor HP\n"
            "/togglefilterbad — ON/OFF sensor kata kasar\n\n"
            "👥 *Owner — Users & Groups*\n"
            "/ban <user_id> — ban user (reply pesan di grup = ban dari grup itu juga)\n"
            "/unban <user_id> — unban user\n"
            "/blacklist add|remove|list [id] — kelola blacklist\n"
            "/addgroup — daftarkan grup ini (jalankan di dalam grup)\n"
            "/groups — daftar grup terdaftar\n"
            "/leaveallgroups — bot keluar dari semua grup terdaftar\n"
            "/broadcast <pesan> — kirim pesan ke semua user yang pernah chat\n\n"
            "🛡️ *Owner — Admin Tools (jalankan di grup, reply ke user target)*\n"
            "/promote — jadikan admin\n"
            "/demote — turunkan dari admin\n"
            "/mute — bisukan user\n"
            "/unmute — buka bisu\n"
            "/pin — pin pesan yang di-reply\n"
            "/unpin — unpin pesan (reply) atau semua (tanpa reply)\n"
            "/admins — daftar admin grup ini\n"
            "/membercount — jumlah member grup ini\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@owner_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📊 *DASHBOARD*\n\n"
        f"👤 Total Users   : {db.count_users()}\n"
        f"👥 Total Groups  : {len(db.get_groups())}\n"
        f"💬 Total Pesan   : {db.total_messages()}\n"
        f"⛔ Total Banned  : {db.count_banned()}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@owner_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = db.get_settings()
    text = (
        "⚙️ *PENGATURAN AKTIF*\n\n"
        f"🔒 Lock Chat      : {fmt_bool(s['lockChat'])}\n"
        f"   ↳ Pesan        : {s['lockReplyMessage']}\n"
        f"🛡️ Auto Ban Spam  : {fmt_bool(s['autoBan'])}\n"
        f"   ↳ Threshold    : {s['spamThreshold']} pesan/menit\n"
        f"👋 Welcome        : {fmt_bool(s['welcome'])}\n"
        f"   ↳ Teks         : {s['welcomeText']}\n"
        f"🔗 Anti Link      : {fmt_bool(s['antiLink'])}\n"
        f"📱 Anti Phone     : {fmt_bool(s['antiPhone'])}\n"
        f"🔞 Filter Kasar   : {fmt_bool(s['filterBad'])}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ============================================================
# TOGGLE / CONFIG COMMANDS
# ============================================================
def make_toggle(key: str, label: str):
    @owner_only
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        s = db.get_settings()
        new_val = not s[key]
        db.update_setting(key, new_val)
        await update.message.reply_text(f"✅ {label}: {fmt_bool(new_val)}")
    return handler


cmd_toggle_welcome = make_toggle("welcome", "Welcome Message")
cmd_toggle_lock = make_toggle("lockChat", "Lock Chat Mode")
cmd_toggle_autoban = make_toggle("autoBan", "Auto Ban Spam")
cmd_toggle_antilink = make_toggle("antiLink", "Anti Link")
cmd_toggle_antiphone = make_toggle("antiPhone", "Anti Phone")
cmd_toggle_filterbad = make_toggle("filterBad", "Filter Kata Kasar")


@owner_only
async def cmd_set_welcome_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        return await update.message.reply_text("⚠️ Gunakan: /setwelcometext <teks>")
    db.update_setting("welcomeText", text)
    await update.message.reply_text("✅ Teks welcome diperbarui.")


@owner_only
async def cmd_set_lock_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        return await update.message.reply_text("⚠️ Gunakan: /setlockmsg <teks>")
    db.update_setting("lockReplyMessage", text)
    await update.message.reply_text("✅ Pesan lock-chat diperbarui.")


@owner_only
async def cmd_set_spam_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("⚠️ Gunakan: /setspamthreshold <angka>")
    val = max(1, int(context.args[0]))
    db.update_setting("spamThreshold", val)
    await update.message.reply_text(f"✅ Spam threshold diubah jadi {val} pesan/menit.")


# ============================================================
# BROADCAST
# ============================================================
@owner_only
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        return await update.message.reply_text("⚠️ Gunakan: /broadcast <pesan>")

    users = db.get_all_users()
    if not users:
        return await update.message.reply_text("⚠️ Belum ada user tercatat untuk di-broadcast.")

    status_msg = await update.message.reply_text(f"🚀 Mengirim ke 0/{len(users)}...")
    success, failed = 0, 0
    for i, u in enumerate(users, 1):
        try:
            await context.bot.send_message(chat_id=u["chat_id"], text=text)
            success += 1
        except TelegramError:
            failed += 1
        if i % 10 == 0 or i == len(users):
            try:
                await status_msg.edit_text(f"🚀 Mengirim ke {i}/{len(users)}...")
            except TelegramError:
                pass
        await asyncio.sleep(0.1)  # jaga rate limit Telegram (~1 pesan/detik per chat aman)

    await status_msg.edit_text(f"✅ Broadcast selesai. Berhasil: {success} | Gagal: {failed}")


# ============================================================
# BAN / BLACKLIST
# ============================================================
@owner_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])

    if not target_id:
        return await update.message.reply_text("⚠️ Gunakan: /ban <user_id> atau reply pesan user.")

    db.set_user_banned(target_id, True)
    db.add_blacklist(target_id)

    group_banned_note = ""
    if update.effective_chat.type in ("group", "supergroup"):
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target_id)
            group_banned_note = " (juga di-kick dari grup ini)"
        except TelegramError as e:
            group_banned_note = f" (gagal kick dari grup: {e})"

    await update.message.reply_text(f"🔨 User {target_id} berhasil di-ban{group_banned_note}.")


@owner_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])

    if not target_id:
        return await update.message.reply_text("⚠️ Gunakan: /unban <user_id> atau reply pesan user.")

    db.set_user_banned(target_id, False)
    db.remove_blacklist(target_id)

    if update.effective_chat.type in ("group", "supergroup"):
        try:
            await context.bot.unban_chat_member(update.effective_chat.id, target_id, only_if_banned=True)
        except TelegramError:
            pass

    await update.message.reply_text(f"✅ User {target_id} berhasil di-unban.")


@owner_only
async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(
            "⚠️ Gunakan:\n/blacklist add <id>\n/blacklist remove <id>\n/blacklist list"
        )
    sub = context.args[0].lower()
    if sub == "list":
        items = db.get_blacklist()
        text = "\n".join(items) if items else "Kosong."
        return await update.message.reply_text(f"📋 *Blacklist:*\n{text}", parse_mode=ParseMode.MARKDOWN)
    if sub in ("add", "remove"):
        if len(context.args) < 2 or not context.args[1].isdigit():
            return await update.message.reply_text(f"⚠️ Gunakan: /blacklist {sub} <user_id>")
        uid = context.args[1]
        if sub == "add":
            db.add_blacklist(uid)
            await update.message.reply_text(f"✅ {uid} ditambahkan ke blacklist.")
        else:
            db.remove_blacklist(uid)
            await update.message.reply_text(f"✅ {uid} dihapus dari blacklist.")
        return
    await update.message.reply_text("⚠️ Sub-command tidak dikenal. Gunakan add / remove / list.")


# ============================================================
# GROUPS
# ============================================================
@owner_only
async def cmd_addgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return await update.message.reply_text("⚠️ Jalankan perintah ini di dalam grup yang mau didaftarkan.")
    db.add_group(chat.id, chat.title)
    await update.message.reply_text(f"✅ Grup *{chat.title}* berhasil didaftarkan.", parse_mode=ParseMode.MARKDOWN)


@owner_only
async def cmd_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    groups = db.get_groups()
    if not groups:
        return await update.message.reply_text("📋 Belum ada grup terdaftar.")
    text = "\n".join(f"{i+1}. {g['title']} (`{g['id']}`)" for i, g in enumerate(groups))
    await update.message.reply_text(f"📋 *Daftar Grup:*\n{text}", parse_mode=ParseMode.MARKDOWN)


@owner_only
async def cmd_leaveallgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    groups = db.get_groups()
    if not groups:
        return await update.message.reply_text("📋 Tidak ada grup untuk ditinggalkan.")
    left = 0
    for g in groups:
        try:
            await context.bot.leave_chat(g["id"])
            db.remove_group(g["id"])
            left += 1
        except TelegramError:
            pass
        await asyncio.sleep(0.15)
    await update.message.reply_text(f"✅ Bot keluar dari {left}/{len(groups)} grup.")


# ============================================================
# GROUP ADMIN TOOLS (reply-based)
# ============================================================
def _get_reply_target(update: Update):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None


@owner_only
async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _get_reply_target(update)
    if not target:
        return await update.message.reply_text("⚠️ Reply pesan user yang mau dipromosikan.")
    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id, target.id,
            can_change_info=True, can_delete_messages=True, can_invite_users=True,
            can_restrict_members=True, can_pin_messages=True, can_promote_members=False,
        )
        await update.message.reply_text(f"✅ {target.first_name} sekarang admin.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal: {e}")


@owner_only
async def cmd_demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _get_reply_target(update)
    if not target:
        return await update.message.reply_text("⚠️ Reply pesan user yang mau diturunkan.")
    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id, target.id,
            can_change_info=False, can_delete_messages=False, can_invite_users=False,
            can_restrict_members=False, can_pin_messages=False, can_promote_members=False,
        )
        await update.message.reply_text(f"✅ {target.first_name} diturunkan jadi member biasa.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal: {e}")


@owner_only
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _get_reply_target(update)
    if not target:
        return await update.message.reply_text("⚠️ Reply pesan user yang mau di-mute.")
    perms = ChatPermissions(
        can_send_messages=False, can_send_audios=False, can_send_documents=False,
        can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
        can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
        can_add_web_page_previews=False,
    )
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, perms)
        await update.message.reply_text(f"🔇 {target.first_name} berhasil di-mute.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal: {e}")


@owner_only
async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _get_reply_target(update)
    if not target:
        return await update.message.reply_text("⚠️ Reply pesan user yang mau di-unmute.")
    perms = ChatPermissions(
        can_send_messages=True, can_send_audios=True, can_send_documents=True,
        can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
        can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
        can_add_web_page_previews=True,
    )
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, perms)
        await update.message.reply_text(f"🔊 {target.first_name} berhasil di-unmute.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal: {e}")


@owner_only
async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("⚠️ Reply pesan yang mau di-pin.")
    try:
        await context.bot.pin_chat_message(
            update.effective_chat.id, update.message.reply_to_message.message_id
        )
        await update.message.reply_text("📌 Pesan berhasil di-pin.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal: {e}")


@owner_only
async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.reply_to_message:
            await context.bot.unpin_chat_message(
                update.effective_chat.id, update.message.reply_to_message.message_id
            )
        else:
            await context.bot.unpin_all_chat_messages(update.effective_chat.id)
        await update.message.reply_text("📌 Berhasil unpin.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal: {e}")


@owner_only
async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        text = "\n".join(
            f"• {a.user.first_name} ({a.status})" + (f" @{a.user.username}" if a.user.username else "")
            for a in admins
        )
        await update.message.reply_text(f"👑 *Admin grup ini:*\n{text}", parse_mode=ParseMode.MARKDOWN)
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal: {e}")


@owner_only
async def cmd_membercount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = await context.bot.get_chat_member_count(update.effective_chat.id)
        await update.message.reply_text(f"👥 Total member: {count}")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Gagal: {e}")


# ============================================================
# MESSAGE HANDLER — moderasi otomatis (jalan di semua pesan teks)
# ============================================================
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not user or user.is_bot:
        return

    await track_group(update)
    settings = db.get_settings()

    # ---- Lock chat mode: balas custom lalu berhenti (mode maintenance total) ----
    if settings["lockChat"]:
        await msg.reply_text(settings["lockReplyMessage"])
        return

    # ---- Blacklist / banned user: abaikan total ----
    if db.is_blacklisted(user.id):
        return

    text = msg.text or msg.caption or ""

    # ---- Anti Link ----
    if settings["antiLink"] and flt.contains_link(text):
        try:
            await msg.delete()
        except TelegramError:
            pass
        warn = await context.bot.send_message(
            chat.id, f"🔗 Pesan dari {user.first_name} dihapus (mengandung link)."
        )
        asyncio.create_task(_auto_delete(context, chat.id, warn.message_id, delay=8))
        return

    # ---- Anti Phone ----
    if settings["antiPhone"] and flt.contains_phone(text):
        try:
            await msg.delete()
        except TelegramError:
            pass
        await context.bot.send_message(
            chat.id, f"📱 Pesan dari {user.first_name} dihapus (mengandung nomor HP)."
        )
        return

    # ---- Filter kata kasar ----
    if settings["filterBad"] and flt.contains_bad_word(text):
        try:
            await msg.delete()
        except TelegramError:
            pass
        await context.bot.send_message(
            chat.id, f"🔞 Pesan dari {user.first_name} dihapus (kata tidak pantas)."
        )
        return

    # ---- Anti Flood / Auto Ban ----
    if settings["autoBan"] and chat.type in ("group", "supergroup"):
        is_spam = flt.register_message_and_check_spam(chat.id, user.id, settings["spamThreshold"])
        if is_spam and not db.is_blacklisted(user.id):
            db.set_user_banned(user.id, True)
            db.add_blacklist(user.id)
            try:
                await context.bot.ban_chat_member(chat.id, user.id)
                await context.bot.send_message(chat.id, f"🔨 {user.first_name} di-ban otomatis (spam).")
            except TelegramError as e:
                log.warning("Auto-ban gagal: %s", e)
            return

    # ---- Tracking user & pesan ----
    db.upsert_user(user.id, user.first_name, user.last_name, user.username, chat.id)


async def on_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = db.get_settings()
    if not settings["welcome"]:
        return
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        await update.message.reply_text(
            f"👋 Selamat datang, {member.first_name}!\n\n{settings['welcomeText']}"
        )


# ============================================================
# MAIN
# ============================================================
def build_app() -> Application:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("status", cmd_status))

    app.add_handler(CommandHandler("togglewelcome", cmd_toggle_welcome))
    app.add_handler(CommandHandler("setwelcometext", cmd_set_welcome_text))
    app.add_handler(CommandHandler("togglelock", cmd_toggle_lock))
    app.add_handler(CommandHandler("setlockmsg", cmd_set_lock_msg))
    app.add_handler(CommandHandler("toggleautoban", cmd_toggle_autoban))
    app.add_handler(CommandHandler("setspamthreshold", cmd_set_spam_threshold))
    app.add_handler(CommandHandler("toggleantilink", cmd_toggle_antilink))
    app.add_handler(CommandHandler("toggleantiphone", cmd_toggle_antiphone))
    app.add_handler(CommandHandler("togglefilterbad", cmd_toggle_filterbad))

    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("blacklist", cmd_blacklist))

    app.add_handler(CommandHandler("addgroup", cmd_addgroup))
    app.add_handler(CommandHandler("groups", cmd_groups))
    app.add_handler(CommandHandler("leaveallgroups", cmd_leaveallgroups))

    app.add_handler(CommandHandler("promote", cmd_promote))
    app.add_handler(CommandHandler("demote", cmd_demote))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("pin", cmd_pin))
    app.add_handler(CommandHandler("unpin", cmd_unpin))
    app.add_handler(CommandHandler("admins", cmd_admins))
    app.add_handler(CommandHandler("membercount", cmd_membercount))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, on_message))

    return app


def main():
    db.init_db()
    app = build_app()
    log.info("🚀 BCC Bot (Python Edition) starting — polling mode...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
