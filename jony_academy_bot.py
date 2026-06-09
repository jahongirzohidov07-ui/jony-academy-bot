import os
import sqlite3
import csv
import io
import re
import logging
from datetime import datetime
from datetime import time as dt_time
from zoneinfo import ZoneInfo

from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    filters, ContextTypes, CallbackQueryHandler
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN      = os.environ.get("ACADEMY_BOT_TOKEN", "")
SALES_GROUP_ID = int(os.environ.get("ACADEMY_SALES_GROUP_ID", "0"))
ADMIN_IDS_RAW  = os.environ.get("ACADEMY_ADMIN_IDS", "")
ADMIN_IDS      = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().lstrip("-").isdigit()]
DB_PATH        = os.environ.get("ACADEMY_DB_PATH", "academy.db")

KURSLAR   = ["Ingliz tili", "Rus tili", "Turk tili", "Nemis tili"]
FILIALLAR = ["Zafar", "Bekobod Shahar", "Stretinko"]

NAME, PHONE, CLASS_GRADE, COURSE, BRANCH, CONFIRM = range(6)
BROADCAST_MSG = 10  # alohida range — reg_conv bilan toʼqnashmaydi


# ─ DB ────────────────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER,
            username         TEXT,
            name             TEXT,
            phone            TEXT,
            grade            TEXT,
            course           TEXT,
            branch           TEXT,
            status           TEXT DEFAULT 'pending',
            created_at       TEXT,
            updated_at       TEXT,
            group_message_id INTEGER
        )
    """)
    for col_def in [
        "status TEXT DEFAULT 'pending'",
        "updated_at TEXT",
        "group_message_id INTEGER",
    ]:
        try:
            c.execute(f"ALTER TABLE registrations ADD COLUMN {col_def}")
        except Exception:
            pass
    conn.commit()
    conn.close()


# ─ Telefon validatsiya ────────────────────────────────────────────────────────────────────────

def validate_phone(phone: str) -> bool:
    p = phone.strip().replace(" ", "").replace("-", "")
    return bool(re.match(r'^(\+998|998|0)[0-9]{9}$|^[0-9]{9}$', p))


def normalize_phone(phone: str) -> str:
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("+998"):
        return p
    if p.startswith("998"):
        return "+" + p
    if p.startswith("0") and len(p) == 10:
        return "+998" + p[1:]
    if len(p) == 9:
        return "+998" + p
    return phone


def phone_exists(phone: str) -> bool:
    normalized = normalize_phone(phone)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM registrations WHERE phone = ?", (normalized,))
    result = c.fetchone()
    conn.close()
    return result is not None


# ─ Roʼyxatdan oʼtish oqimi ─────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! *Jony Academy* ga xush kelibsiz!\n\n"
        "Roʼyxatdan oʼтish uchun *toʼliq ismingizni* kiriting:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAME


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "📱 *Telefon raqamingizni* kiriting:\n"
        "Masalan: +998901234567 yoki 901234567",
        parse_mode="Markdown"
    )
    return PHONE


async def ask_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()

    if not validate_phone(phone):
        await update.message.reply_text(
            "❌ Telefon raqam notoʼgʼri formatda!\n\n"
            "Toʼgʼri format: +998901234567 yoki 901234567\n"
            "Qaytadan kiriting:"
        )
        return PHONE

    normalized = normalize_phone(phone)

    if phone_exists(phone):
        await update.message.reply_text(
            "⚠️ Bu telefon raqam allaqachon roʼyxatdan oʼтgan!\n"
            "Agar muammo boʼлsa, adminimizga murojaat qiling: @jony_academy"
        )
        return ConversationHandler.END

    context.user_data["phone"] = normalized
    await update.message.reply_text(
        "🎒 *Yoshingiz yoki nechanchi sinfda* oʼqishingizni kiriting:\n"
        "Masalan: 14 yosh, 7-sinf",
        parse_mode="Markdown"
    )
    return CLASS_GRADE


async def ask_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["grade"] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton(k, callback_data=f"course:{k}")] for k in KURSLAR]
    await update.message.reply_text(
        "📚 Qaysi *kursga* yozilmoqchisiz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COURSE


async def ask_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["course"] = query.data.split(":", 1)[1]
    keyboard = [[InlineKeyboardButton(f, callback_data=f"branch:{f}")] for f in FILIALLAR]
    await query.edit_message_text(
        f"✅ Kurs tanlandi: *{context.user_data['course']}*\n\n"
        "📍 Qaysi *filialga* borishni xohlaysiz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BRANCH


async def ask_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["branch"] = query.data.split(":", 1)[1]
    d = context.user_data
    summary = (
        f"📋 *Maʼlumotlaringizni tekshiring:*\n\n"
        f"👤 Ism: {d['name']}\n"
        f"📱 Telefon: {d['phone']}\n"
        f"🎒 Yosh/sinf: {d['grade']}\n"
        f"📚 Kurs: {d['course']}\n"
        f"📍 Filial: {d['branch']}"
    )
    await query.edit_message_text(summary, parse_mode="Markdown")
    await query.message.reply_text(
        "Yuqoridagi maʼlumotlar toʼgʼrimi?",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Tasdiqlash", "❌ Bekor qilish"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return CONFIRM


async def confirm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    user = update.effective_user
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO registrations
           (user_id, username, name, phone, grade, course, branch, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (user.id, user.username or "", d["name"], d["phone"],
         d["grade"], d["course"], d["branch"], now, now)
    )
    reg_id = c.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "🎉 *Murojaatingiz muvaffaqiyatli qabul qilindi!*\n\n"
        f"📍 *{d['branch']}* filialimiz xodimlari tez orada siz bilan bogʼlanishadi.\n\n"
        "Savollar boʼлsa: @jony_academy\n"
        "Koʼrishguncha! 👋",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

    if SALES_GROUP_ID:
        uname = f"@{user.username}" if user.username else "—"
        dt_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        msg = (
            f"🔔 *YANGI MUROJAAT — Jony Academy*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Ism:* {d['name']}\n"
            f"📱 *Telefon:* `{d['phone']}`\n"
            f"🎒 *Yosh/sinf:* {d['grade']}\n"
            f"📚 *Kurs:* {d['course']}\n"
            f"📍 *Filial:* {d['branch']}\n"
            f"💬 *Telegram:* {uname}\n"
            f"🕐 *Vaqt:* {dt_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📞 Qoʼngʼiroq qilindi", callback_data=f"status:{reg_id}:called"),
                InlineKeyboardButton("✅ Keldi",               callback_data=f"status:{reg_id}:came"),
            ],
            [InlineKeyboardButton("❌ Kelmadi", callback_data=f"status:{reg_id}:not_came")],
        ])
        sent = await context.bot.send_message(
            chat_id=SALES_GROUP_ID, text=msg, parse_mode="Markdown", reply_markup=kb
        )
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE registrations SET group_message_id=? WHERE id=?", (sent.message_id, reg_id))
        conn.commit()
        conn.close()

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Bekor qilindi.\n/start orqali qayta boshlashingiz mumkin.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─ Sotuv guruh: holat tugmalari ─────────────────────────────────────────────────────────────────────────

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Xato!")
        return

    _, reg_id_str, new_status = parts
    reg_id = int(reg_id_str)

    labels = {
        "called":   "📞 Qoʼngʼiroq qilindi",
        "came":     "✅ Keldi",
        "not_came": "❌ Kelmadi",
    }
    label = labels.get(new_status, new_status)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE registrations SET status=?, updated_at=? WHERE id=?", (new_status, now, reg_id))
    conn.commit()
    c.execute("SELECT name FROM registrations WHERE id=?", (reg_id,))
    row = c.fetchone()
    conn.close()

    await query.answer(f"✅ {label}")

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    manager = query.from_user.full_name
    name = row[0] if row else "—"
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"🔄 *{name}* — {label}\n"
            f"👤 {manager} · 🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        ),
        parse_mode="Markdown",
        reply_to_message_id=query.message.message_id
    )


# ─ Broadcast ─────────────────────────────────────────────────────────────────────────────

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ADMIN_IDS:
        await update.message.reply_text(
            "⚠️ Broadcast ishlashi uchun Railway da "
            "`ACADEMY_ADMIN_IDS` ni sozlang.\n"
            "Telegram ID ni @userinfobot dan olishingiz mumkin.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Bu buyruq faqat adminlar uchun.")
        return ConversationHandler.END

    await update.message.reply_text(
        "📢 *Broadcast rejimi*\n\n"
        "Barcha roʼyxatdan oʼтgan foydalanuvchilarga "
        "yuboriladigan xabarni yozing.\n\n"
        "Bekor qilish: /cancel",
        parse_mode="Markdown"
    )
    return BROADCAST_MSG


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END

    text = update.message.text
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM registrations WHERE user_id != 0")
    user_ids = [r[0] for r in c.fetchall()]
    conn.close()

    sent = failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 *Jony Academy:*\n\n{text}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ *Broadcast tugadi!*\n\n"
        f"📨 Yuborildi: *{sent}*\n"
        f"❌ Yuborilmadi: *{failed}*",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ─ Admin buyruqlari ───────────────────────────────────────────────────────────────────────────

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM registrations")
    total = cur.fetchone()[0]
    cur.execute("SELECT status, COUNT(*) FROM registrations GROUP BY status")
    status_d = dict(cur.fetchall())
    cur.execute("SELECT course, COUNT(*) FROM registrations GROUP BY course ORDER BY 2 DESC")
    courses = cur.fetchall()
    cur.execute("SELECT branch, COUNT(*) FROM registrations GROUP BY branch ORDER BY 2 DESC")
    branches = cur.fetchall()
    conn.close()

    msg = (
        f"📊 *Statistika*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Jami: *{total}*\n\n"
        f"📈 *Holat:*\n"
        f"  ⏳ Kutilmoqda: {status_d.get('pending', 0)}\n"
        f"  📞 Qoʼngʼiroq: {status_d.get('called', 0)}\n"
        f"  ✅ Keldi: {status_d.get('came', 0)}\n"
        f"  ❌ Kelmadi: {status_d.get('not_came', 0)}\n\n"
        f"📚 *Kurslar:*\n" +
        "\n".join(f"  \u2022 {cn}: {n}" for cn, n in courses) +
        "\n\n📍 *Filiallar:*\n" +
        "\n".join(f"  \u2022 {bn}: {n}" for bn, n in branches)
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def royxat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, phone, grade, course, branch, status,
               created_at, updated_at, username
        FROM registrations ORDER BY id
    """)
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Ism", "Telefon", "Yosh/sinf", "Kurs", "Filial",
        "Holat", "Roʼyxat vaqti", "Yangilangan", "Telegram"
    ])
    writer.writerows(rows)
    output.seek(0)

    fname = f"jony_academy_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    await update.message.reply_document(
        document=output.getvalue().encode("utf-8-sig"),
        filename=fname,
        caption=f"📋 Jami {len(rows)} ta murojaat"
    )


# ─ Kunlik hisobot (job) ───────────────────────────────────────────────────────────────────────

async def daily_report(context: ContextTypes.DEFAULT_TYPE):
    if not SALES_GROUP_ID:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM registrations WHERE created_at LIKE ?", (f"{today}%",))
    today_total = cur.fetchone()[0]
    if today_total == 0:
        conn.close()
        return

    cur.execute(
        "SELECT status, COUNT(*) FROM registrations WHERE created_at LIKE ? GROUP BY status",
        (f"{today}%",)
    )
    s = dict(cur.fetchall())

    cur.execute(
        "SELECT course, COUNT(*) FROM registrations "
        "WHERE created_at LIKE ? GROUP BY course ORDER BY 2 DESC",
        (f"{today}%",)
    )
    courses = cur.fetchall()

    cur.execute(
        "SELECT branch, COUNT(*) FROM registrations "
        "WHERE created_at LIKE ? GROUP BY branch ORDER BY 2 DESC",
        (f"{today}%",)
    )
    branches = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM registrations")
    grand_total = cur.fetchone()[0]
    conn.close()

    msg = (
        f"📊 *KUNLIK HISOBOT — {datetime.now().strftime('%d.%m.%Y')}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 Bugun: *{today_total}* ta murojaat\n\n"
        f"*Holat:*\n"
        f"  ⏳ Kutilmoqda: {s.get('pending', 0)}\n"
        f"  📞 Qoʼngʼiroq qilindi: {s.get('called', 0)}\n"
        f"  ✅ Keldi: {s.get('came', 0)}\n"
        f"  ❌ Kelmadi: {s.get('not_came', 0)}\n\n"
        f"*Kurslar:*\n" +
        "\n".join(f"  \u2022 {cn}: {n}" for cn, n in courses) +
        "\n\n*Filiallar:*\n" +
        "\n".join(f"  \u2022 {bn}: {n}" for bn, n in branches) +
        f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Jami barcha vaqt: *{grand_total}*"
    )
    await context.bot.send_message(
        chat_id=SALES_GROUP_ID, text=msg, parse_mode="Markdown"
    )


# ─ Main ─────────────────────────────────────────────────────────────────────────────

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            PHONE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_grade)],
            CLASS_GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_course)],
            COURSE:      [CallbackQueryHandler(ask_branch, pattern=r"^course:")],
            BRANCH:      [CallbackQueryHandler(ask_confirm, pattern=r"^branch:")],
            CONFIRM: [
                MessageHandler(filters.Regex("^✅ Tasdiqlash$"), confirm_registration),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(broadcast_conv)
    app.add_handler(reg_conv)
    app.add_handler(CallbackQueryHandler(handle_status, pattern=r"^status:"))
    app.add_handler(CommandHandler("stat",     stat_command))
    app.add_handler(CommandHandler("royxat",   royxat_command))

    app.job_queue.run_daily(
        daily_report,
        time=dt_time(20, 0, tzinfo=ZoneInfo("Asia/Tashkent"))
    )

    logger.info("Jony Academy bot ishga tushdi")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
