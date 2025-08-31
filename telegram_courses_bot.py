import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ================= إعدادات عامة =================
#ADMIN_ID = int(os.getenv("ADMIN_ID", "5774252730"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "5774252730"))

#BOT_TOKEN = os.getenv("BOT_TOKEN", "8018747428:AAEkUmYZDimNuFp4pjnbpfTTSmwU-qyVIfM")
# بدّل السطر في الكود إلى:
BOT_TOKEN = os.environ["BOT_TOKEN"]  # بدون قيمة افتراضية

# لتخزين المستخدمين
users = set()

# إعداد اللوق
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ================= دوال البداية =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    users.add(chat_id)

    # رسالة ترحيب
    welcome_msg = (
        "السلام عليكم ورحمة الله وبركاته 🌹\n\n"
        "إذا وجدت أي نقص في البوت يُرجى التواصل في الخاص @BOT0ADMIN"
    )

    # أزرار المواد
    keyboard = [
        [InlineKeyboardButton("1️⃣ مبادئ تراسل البيانات والشبكات", callback_data="course_networks")],
        [InlineKeyboardButton("2️⃣ مقدمة إلى قواعد البيانات", callback_data="course_databases")],
        [InlineKeyboardButton("3️⃣ الرياضيات", callback_data="course_math")],
        [InlineKeyboardButton("4️⃣ البرمجة الموجهة بالكائنات (نظري)", callback_data="course_oop_theory")],
        [InlineKeyboardButton("5️⃣ البرمجة الموجهة بالكائنات (عملي)", callback_data="course_oop_practice")],
        [InlineKeyboardButton("6️⃣ تنظيم الحاسوب", callback_data="course_computer_org")],
    ]

    await update.message.reply_text(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard))

    # إشعار الأدمن
    msg = (
        f"👤 مستخدم جديد دخل البوت\n"
        f"الاسم: {user.first_name}\n"
        f"اليوزر: @{user.username}\n"
        f"الأيدي: {user.id}\n"
        f"عدد المستخدمين: {len(users)}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg)


# ================= دوال الكورسات =================
def course_menu(title, prefix):
    keyboard = [
        [InlineKeyboardButton("📘 التكاليف", callback_data=f"{prefix}_tasks")],
        [InlineKeyboardButton("📖 المحاضرة الأولى", callback_data=f"{prefix}_lec1")],
        [InlineKeyboardButton("➕ أضف محاضرة جديدة", callback_data=f"{prefix}_add")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard), f"📚 {title}"


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "main_menu":
        await start(update, context)
        return

    # الكورسات الرئيسية
    courses = {
        "course_networks": ("مبادئ تراسل البيانات والشبكات", "net"),
        "course_databases": ("مقدمة إلى قواعد البيانات", "db"),
        "course_math": ("الرياضيات", "math"),
        "course_oop_theory": ("OOP نظري", "oop_theory"),
        "course_oop_practice": ("OOP عملي", "oop_practice"),
        "course_computer_org": ("تنظيم الحاسوب", "org"),
    }

    if data in courses:
        title, prefix = courses[data]
        reply_markup, text = course_menu(title, prefix)
        await query.message.edit_text(text, reply_markup=reply_markup)


# ================= إدخال الأدمن =================
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    # الأدمن يرسل أي شيء → يتوزع للمستخدمين
    for uid in users:
        try:
            if update.message.text:
                await context.bot.send_message(chat_id=uid, text=update.message.text)
            elif update.message.document:
                await context.bot.send_document(chat_id=uid, document=update.message.document.file_id)
            elif update.message.photo:
                await context.bot.send_photo(chat_id=uid, photo=update.message.photo[-1].file_id)
        except Exception as e:
            logger.error(f"خطأ في الإرسال للمستخدم {uid}: {e}")


# ================= قائمة المستخدمين (خاصة بالأدمن) =================
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    msg = "📊 قائمة المستخدمين:\n"
    for u in users:
        msg += f"- {u}\n"
    msg += f"\nإجمالي: {len(users)}"
    await update.message.reply_text(msg)


# ================= التشغيل =================
async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("users", list_users))

    # الأزرار
    application.add_handler(CallbackQueryHandler(menu_handler))

    # استقبال رسائل الأدمن
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, handle_admin_input))

    # تشغيل البوت
    await application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
