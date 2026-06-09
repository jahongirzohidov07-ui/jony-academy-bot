"""
============================================================
    Jony Academy — RO'YXATDAN O'TISH BOTI
============================================================
Sozlash uchun quyidagilarni to'ldiring:
    BOT_TOKEN        — @BotFather dan olingan token
    SALES_GROUP_ID   — Sotuv menejerlar guruhi ID
"""

import logging
import sqlite3
import os
import datetime

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ──────────────────────────────────────────────
# SOZLAMALAR
# ──────────────────────────────────────────────
BOT_TOKEN      = os.environ.get("ACADEMY_BOT_TOKEN", "")
SALES_GROUP_ID = int(os.environ.get("ACADEMY_SALES_GROUP_ID", "0"))
DB_PATH        = os.environ.get("ACADEMY_DB_PATH", "academy.db")

KURSLAR   = ["Ingliz tili", "Rus tili", "Turk tili", "Nemis tili"]
FILIALLAR = ["Zafar", "Bekobod Shahar", "Stretinko"]

# ConversationHandler holatlari
NAME, PHONE, CLASS_GRADE, COURSE, BRANCH, CONFIRM = range(6)

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

# ──────────────────────────────────────────────
# DATABASE
# ──────────────────────────────────────────────
def db_init():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            name        TEXT,
            phone       TEXT,
            grade       TEXT,
            course      TEXT,
            branch      TEXT,
            created_at  TEXT
        )
    """)
    con.commit()
    con.close()

def db_save(user_id, name, phone, grade, course, branch):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO applications (user_id,name,phone,grade,course,branch,created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, name, phone, grade, course, branch, datetime.datetime.now().isoformat())
    )
    con.commit()
    con.close()

def db_count():
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT COUNT(*) FROM applications").fetchone()
    con.close()
    return row[0] if row else 0

def db_all():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT name, phone, grade, course, branch, created_at FROM applications ORDER BY id DESC"
    ).fetchall()
    con.close()
    return rows

# ──────────────────────────────────────────────
# /start
# ──────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 *Jony Academy*'ga xush kelibsiz!\n\n"
        "Bu bot orqali kursimizga ro'yxatdan o'tishingiz mumkin.\n\n"
        "📝 Ro'yxatdan o'tish uchun bir necha savollarga javob bering.\n\n"
        "Ismingizni kiriting (to'liq ism-familya):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return NAME

# ──────────────────────────────────────────────
# ISM
# ──────────────────────────────────────────────
async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("❗ Iltimos, to'liq ism-familyangizni kiriting:")
        return NAME

    context.user_data["name"] = name

    phone_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        f"✅ *{name}*\n\n"
        "📱 Endi telefon raqamingizni yuboring:",
        parse_mode="Markdown",
        reply_markup=phone_kb,
    )
    return PHONE

# ──────────────────────────────────────────────
# TELEFON
# ──────────────────────────────────────────────
async def ask_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone
    else:
        phone = update.message.text.strip()

    context.user_data["phone"] = phone

    await update.message.reply_text(
        "✅ Telefon saqlandi!\n\n"
        "🎒 Yoshingiz yoki sinfingizni kiriting:\n"
        "_(masalan: 15 yosh, 9-sinf, talaba va h.k.)_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return CLASS_GRADE

# ──────────────────────────────────────────────
# SINF/YOSH
# ──────────────────────────────────────────────
async def ask_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    grade = update.message.text.strip()
    if len(grade) < 1:
        await update.message.reply_text("❗ Iltimos, yosh yoki sinfingizni kiriting:")
        return CLASS_GRADE

    context.user_data["grade"] = grade

    # Kurslar inline keyboard
    buttons = [[InlineKeyboardButton(k, callback_data=f"course:{k}")] for k in KURSLAR]
    await update.message.reply_text(
        "📚 Qaysi kursga qiziqasiz?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return COURSE

# ──────────────────────────────────────────────
# KURS (inline callback)
# ──────────────────────────────────────────────
async def ask_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    course = query.data.replace("course:", "")
    context.user_data["course"] = course

    await query.edit_message_text(f"✅ Kurs: *{course}*", parse_mode="Markdown")

    # Filiallar inline keyboard
    buttons = [[InlineKeyboardButton(f, callback_data=f"branch:{f}")] for f in FILIALLAR]
    await query.message.reply_text(
        "📍 Qaysi filialga kelishingiz qulay?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return BRANCH

# ──────────────────────────────────────────────
# FILIAL (inline callback)
# ──────────────────────────────────────────────
async def ask_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    branch = query.data.replace("branch:", "")
    context.user_data["branch"] = branch

    await query.edit_message_text(f"✅ Filial: *{branch}*", parse_mode="Markdown")

    d = context.user_data
    confirm_kb = ReplyKeyboardMarkup(
        [["✅ Tasdiqlash", "❌ Bekor qilish"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await query.message.reply_text(
        "📋 *Ma'lumotlaringizni tekshiring:*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Ism:* {d['name']}\n"
        f"📱 *Telefon:* {d['phone']}\n"
        f"🎒 *Yosh/sinf:* {d['grade']}\n"
        f"📚 *Kurs:* {d['course']}\n"
        f"📍 *Filial:* {d['branch']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Ma'lumotlar to'g'rimi?",
        parse_mode="Markdown",
        reply_markup=confirm_kb,
    )
    return CONFIRM

# ──────────────────────────────────────────────
# TASDIQLASH
# ──────────────────────────────────────────────
async def confirm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data

    # DB ga saqlash
    db_save(
        user_id=update.effective_user.id,
        name=d["name"],
        phone=d["phone"],
        grade=d["grade"],
        course=d["course"],
        branch=d["branch"],
    )

    # Sotuv menejerlar guruhiga yuborish
    if SALES_GROUP_ID:
        try:
            tg_user = update.effective_user
            username = f"@{tg_user.username}" if tg_user.username else "username yo'q"
            await context.bot.send_message(
                chat_id=SALES_GROUP_ID,
                text=(
                    "🔔 *YANGI MUROJAAT — Jony Academy*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *Ism:* {d['name']}\n"
                    f"📱 *Telefon:* {d['phone']}\n"
                    f"🎒 *Yosh/sinf:* {d['grade']}\n"
                    f"📚 *Kurs:* {d['course']}\n"
                    f"📍 *Filial:* {d['branch']}\n"
                    f"💬 *Telegram:* {username}\n"
                    f"🕐 *Vaqt:* {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    "━━━━━━━━━━━━━━━━━━━━"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logging.error(f"Guruhga yuborishda xato: {e}")

    await update.message.reply_text(
        "🎉 *Ro'yxatdan muvaffaqiyatli o'tdingiz!*\n\n"
        "✅ Ma'lumotlaringiz qabul qilindi.\n"
        "📞 Tez orada menejerimiz siz bilan bog'lanadi!\n\n"
        "Savollar uchun: @jonyacademyadmin\n\n"
        "_Jony Academy'ga qiziqganingiz uchun rahmat!_ 🙏",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END

# ──────────────────────────────────────────────
# BEKOR QILISH
# ──────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Ro'yxatdan o'tish bekor qilindi.\n"
        "Qayta boshlash uchun /start bosing.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

# ──────────────────────────────────────────────
# ADMIN: /stat — statistika
# ──────────────────────────────────────────────
async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = db_count()
    rows = db_all()

    course_counts = {}
    branch_counts = {}
    for name, phone, grade, course, branch, created_at in rows:
        course_counts[course] = course_counts.get(course, 0) + 1
        branch_counts[branch] = branch_counts.get(branch, 0) + 1

    kurs_lines   = "\n".join(f"  • {k}: {v} ta" for k, v in sorted(course_counts.items(), key=lambda x: -x[1]))
    filial_lines = "\n".join(f"  • {k}: {v} ta" for k, v in sorted(branch_counts.items(), key=lambda x: -x[1]))
    no_data      = "  — hali yo'q"

    await update.message.reply_text(
        f"📊 *Jony Academy — Statistika*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 *Jami murojaatlar:* {total} ta\n\n"
        f"📚 *Kurslar bo'yicha:*\n{kurs_lines or no_data}\n\n"
        f"📍 *Filiallar bo'yicha:*\n{filial_lines or no_data}",
        parse_mode="Markdown",
    )

# ──────────────────────────────────────────────
# ADMIN: /royxat — ro'yxat Excel
# ──────────────────────────────────────────────
async def royxat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import csv, io
    rows = db_all()
    if not rows:
        await update.message.reply_text("Hali murojaat yo'q.")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ism", "Telefon", "Yosh/Sinf", "Kurs", "Filial", "Vaqt"])
    for row in rows:
        writer.writerow(row)

    output.seek(0)
    file_bytes = output.getvalue().encode("utf-8-sig")
    file_like = io.BytesIO(file_bytes)
    file_like.name = f"jony_academy_{datetime.datetime.now().strftime('%Y%m%d')}.csv"

    await update.message.reply_document(
        document=file_like,
        caption=f"📋 Jony Academy murojaatlar ro'yxati — {len(rows)} ta",
    )

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    db_init()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone),
            ],
            PHONE: [
                MessageHandler(filters.CONTACT, ask_grade),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_grade),
            ],
            CLASS_GRADE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_course),
            ],
            COURSE: [
                CallbackQueryHandler(ask_branch, pattern="^course:"),
            ],
            BRANCH: [
                CallbackQueryHandler(ask_confirm, pattern="^branch:"),
            ],
            CONFIRM: [
                MessageHandler(filters.Regex("^✅ Tasdiqlash$"), confirm_registration),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("stat",   stat_command))
    app.add_handler(CommandHandler("royxat", royxat_command))

    logging.info("Jony Academy boti ishga tushdi...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
