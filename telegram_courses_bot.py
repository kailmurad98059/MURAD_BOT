#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
telegram_courses_bot.py
=======================
بوت تليجرام تعليمي بأزرار فرعية ومحتوى ديناميكي + جاهز للنشر على Render (24/7)

المزايا:
- 6 مواد رئيسية (وتفرّعان لمادة الرياضيات)
- داخل كل مادة: زر "التكاليف" + أزرار "المحاضرات" بعدد غير معلوم (مع زر إضافة محاضرة)
- استقبال أي نوع محتوى من *المشرف* (نص/صور/PDF/ملفات/صوت/فيديو..) وتخزينه ضمن الخانة المحددة ثم:
  • يُرسل للمستخدمين عند ضغطهم على الخانة.
  • ويمكن بثّه فورًا لكل المستخدمين (اختياريًا).
- أزرار رجوع/رئيسية في كل القوائم.
- إشعار المشرف عند دخول أي مستخدم: الاسم، اليوزر، الهاتف (اختياري)، الآيدي، وعدد المشاركين.
- زر/أمر للمشرف للاستعلام عن المستخدمين مع تصدير CSV.
- تخزين بالحالة باستخدام PicklePersistence (ملف .pkl).
- يدعم التشغيل محليًا (polling) أو عبر Webhook لبيئات مثل Render.

⚠️ أمان: التوكن سرّي جدًا. نُفّذ حسب طلبك بإدراجه صراحة، لكن الأفضل *دائمًا* استخدام متغيّرات بيئية (ENV VARS).

تعليمات النشر على Render (مختصر):
1) ارفع هذا الملف وملفات المتطلبات إلى GitHub.
2) أنشئ خدمة Web Service على Render تربط مستودع GitHub.
3) أضف المتغيّرات البيئية: BOT_TOKEN, ADMIN_ID, WEBHOOK_URL, WEBHOOK_SECRET.
4) أمر التشغيل (Start Command):  python telegram_courses_bot.py
5) سيعمل البوت 24/7 (حسب خطة Render)، مع Webhook.

ملفات إضافية (موجود محتواها أسفل هذا الملف كتعليقات لتنسخها):
- requirements.txt
- render.yaml (اختياري: نشر بـ Blueprint)

"""

import os
import asyncio
from io import BytesIO
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputFile,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    PicklePersistence,
)

# =====================
# إعدادات المشرف والتوكن
# =====================
# طُلب إدراج التوكن والآيدي صراحة — مع ذلك نوفّر إمكانية override عبر ENV إن رغبت لاحقًا.
#ADMIN_ID = int(os.getenv("ADMIN_ID", "5774252730"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "5774252730"))

#BOT_TOKEN = os.getenv("BOT_TOKEN", "8018747428:AAEkUmYZDimNuFp4pjnbpfTTSmwU-qyVIfM")
# بدّل السطر في الكود إلى:
BOT_TOKEN = os.environ["BOT_TOKEN"]  # بدون قيمة افتراضية


# إعدادات الويب هوك لبيئات مثل Render
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # مثال: https://your-app.onrender.com/
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret-path")  # مسار سري للويبهوك
PORT = int(os.getenv("PORT", "10000"))  # Render يمرّر PORT تلقائيًا
USE_WEBHOOK = bool(WEBHOOK_URL)  # إن توفر URL سنفعل الويبهوك

WELCOME_TEXT = (
    "السلام عليكم ورحمة الله وبركاته\n\n"
    "إذا وجدت أي نقص في البوت يُرجى التواصل في الخاص @BOT0ADMIN"
)

# =====================
# هيكلية المواد والمواضيع
# =====================
SUBJECTS = {
    "مبادئ تراسُل البيانات والشبكات": ["عام"],
    "مقدمة الى قواعد البيانات": ["عام"],
    "الرياضيات": ["الهياكل المقاطعة", "الإحصاء والاحتمالات"],
    "البرمجه الموجهه بالكائنات (نظري)": ["عام"],
    "البرمجه الموجهه بالكائنات (عملي)": ["عام"],
    "تنظيم الحاسوب": ["عام"],
}

ASSIGNMENTS = "التكاليف"
DEFAULT_LECTURE = "المحاضرة 1"

@dataclass
class Material:
    kind: str  # 'text', 'photo', 'document', 'video', 'audio', 'voice', ...
    file_id: Optional[str] = None
    caption: Optional[str] = None
    text: Optional[str] = None


# =====================
# أدوات مساعدة
# =====================

def ensure_subject_structure(bot_data: Dict):
    content = bot_data.setdefault("content", {})
    for sub, topics in SUBJECTS.items():
        sub_dict = content.setdefault(sub, {})
        for topic in topics:
            node = sub_dict.setdefault(topic, {})
            node.setdefault("assignments", [])  # List[Material]
            lectures = node.setdefault("lectures", {})  # Dict[str, List[Material]]
            if not lectures:
                lectures[DEFAULT_LECTURE] = []


def main_menu_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for i, s in enumerate(SUBJECTS.keys(), start=1):
        rows.append([InlineKeyboardButton(f"{i}. {s}", callback_data=f"sub|{s}")])
    return InlineKeyboardMarkup(rows)


def topics_kb(subject: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(t, callback_data=f"topic|{subject}|{t}")] for t in SUBJECTS[subject]]
    rows.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def section_kb(subject: str, topic: str, is_admin: bool, bot_data: Dict) -> InlineKeyboardMarkup:
    node = bot_data["content"][subject][topic]
    lectures = list(node["lectures"].keys())

    rows: List[List[InlineKeyboardButton]] = []

    # التكاليف + زر إدخال/بث محتوى (للمشرف)
    rows.append([
        InlineKeyboardButton(ASSIGNMENTS, callback_data=f"show|{subject}|{topic}|assignments"),
        InlineKeyboardButton("📤 إدخال/بث", callback_data=f"pushsel|{subject}|{topic}|assignments"),
    ])

    # المحاضرات
    for lec in lectures:
        rows.append([
            InlineKeyboardButton(lec, callback_data=f"show|{subject}|{topic}|lec|{lec}"),
            InlineKeyboardButton("📤", callback_data=f"pushsel|{subject}|{topic}|lec|{lec}"),
        ])

    if is_admin:
        rows.append([InlineKeyboardButton("➕ إضافة محاضرة", callback_data=f"addlec|{subject}|{topic}")])

    rows.append([
        InlineKeyboardButton("🔙 رجوع", callback_data=f"back|{subject}"),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="home"),
    ])

    return InlineKeyboardMarkup(rows)


async def send_node_materials(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              subject: str, topic: str, section: str,
                              lec_name: Optional[str] = None):
    node = context.bot_data["content"][subject][topic]
    title = ASSIGNMENTS if section == "assignments" else lec_name

    if section == "assignments":
        materials = node["assignments"]
    else:
        materials = node["lectures"].get(lec_name, [])

    if not materials:
        await update.effective_chat.send_message(
            f"لا يوجد محتوى بعد في \u2068{subject} / {topic} / {title}\u2069.\n"
            f"يمكن للمشرف إضافة محتوى عبر أزرار (📤/➕)."
        )
        return

    await update.effective_chat.send_message(f"سيتم إرسال محتوى \u2068{subject} / {topic} / {title}\u2069:")

    for m in materials:
        try:
            if m.kind == "text" and m.text:
                await update.effective_chat.send_message(m.text)
            elif m.kind == "photo" and m.file_id:
                await update.effective_chat.send_photo(m.file_id, caption=m.caption)
            elif m.kind == "document" and m.file_id:
                await update.effective_chat.send_document(m.file_id, caption=m.caption)
            elif m.kind == "video" and m.file_id:
                await update.effective_chat.send_video(m.file_id, caption=m.caption)
            elif m.kind == "audio" and m.file_id:
                await update.effective_chat.send_audio(m.file_id, caption=m.caption)
            elif m.kind == "voice" and m.file_id:
                await update.effective_chat.send_voice(m.file_id, caption=m.caption)
        except Exception as e:
            await update.effective_chat.send_message(f"تعذّر إرسال عنصر بسبب خطأ: {e}")


# =====================
# Handlers
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_subject_structure(context.bot_data)

    user = update.effective_user
    chat = update.effective_chat

    # حفظ المستخدمين الفريدين
    users = context.bot_data.setdefault("users", {})  # user_id -> dict
    udata = users.setdefault(user.id, {
        "name": (user.full_name or "")[:128],
        "username": (user.username or "")[:128],
        "phone": "",
    })

    # لوحة مشاركة الهاتف (اختياري)
    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 مشاركة رقم الهاتف", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        selective=True,
        input_field_placeholder="(اختياري) شارك رقم هاتفك"
    )

    await chat.send_message(WELCOME_TEXT, reply_markup=kb)
    await chat.send_message("اختر مادة من القائمة:", reply_markup=main_menu_kb())

    # إشعار المشرف بالدخول
    count = len(users)
    phone = udata.get("phone") or "غير مرفق"
    try:
        await context.bot.send_message(
            ADMIN_ID,
            (
                "👤 دخول مستخدم جديد:\n"
                f"الاسم: {user.full_name}\n"
                f"المعرف: @{user.username if user.username else 'بدون'}\n"
                f"الآيدي: {user.id}\n"
                f"الهاتف: {phone}\n"
                f"إجمالي المشاركين: {count}"
            ),
        )
    except Exception:
        pass


async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.contact:
        return
    contact = update.message.contact
    users = context.bot_data.setdefault("users", {})
    u = users.setdefault(update.effective_user.id, {})
    u["phone"] = contact.phone_number
    await update.message.reply_text("شكرًا، تم حفظ رقم هاتفك.", reply_markup=ReplyKeyboardRemove())


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.effective_chat.send_message("هذا الأمر للمشرف فقط.")
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 الاستعلام عن المستخدمين", callback_data="admin|users")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")],
    ])
    await update.effective_chat.send_message("لوحة المشرف:", reply_markup=kb)


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = context.bot_data.get("users", {})
    count = len(users)
    # أنشئ CSV
    csv_io = BytesIO()
    csv_io.write("user_id,name,username,phone\n".encode("utf-8"))
    for uid, data in users.items():
        row = f"{uid},\"{data.get('name','')}\",\"{data.get('username','')}\",\"{data.get('phone','')}\"\n"
        csv_io.write(row.encode("utf-8"))
    csv_io.seek(0)

    await update.effective_message.reply_document(
        document=InputFile(csv_io, filename="users.csv"),
        caption=f"عدد المستخدمين الحالي: {count}"
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_subject_structure(context.bot_data)
    q = update.callback_query
    await q.answer()

    data = q.data or ""

    if data == "home":
        await q.edit_message_text("اختر مادة من القائمة:", reply_markup=main_menu_kb())
        return

    if data == "admin|users":
        if q.from_user.id != ADMIN_ID:
            await q.edit_message_text("هذا الزر للمشرف فقط.")
            return
        await q.message.reply_text("جارٍ تجهيز ملف المستخدمين...")
        await admin_users(update, context)
        return

    if data.startswith("sub|"):
        _, subject = data.split("|", 1)
        await q.edit_message_text(f"اختر فرعًا في \u2068{subject}\u2069:", reply_markup=topics_kb(subject))
        return

    if data.startswith("back|"):
        _, subject = data.split("|", 1)
        await q.edit_message_text(f"اختر فرعًا في \u2068{subject}\u2069:", reply_markup=topics_kb(subject))
        return

    if data.startswith("topic|"):
        _, subject, topic = data.split("|", 2)
        is_admin = (q.from_user.id == ADMIN_ID)
        kb = section_kb(subject, topic, is_admin, context.bot_data)
        await q.edit_message_text(
            f"\u2068{subject}\u2069 / \u2068{topic}\u2069 — اختر قسمًا:",
            reply_markup=kb,
        )
        return

    if data.startswith("addlec|"):
        if q.from_user.id != ADMIN_ID:
            await q.edit_message_text("هذا الزر للمشرف فقط.")
            return
        _, subject, topic = data.split("|", 2)
        node = context.bot_data["content"][subject][topic]
        # تحديد رقم المحاضرة التالية
        existing = list(node["lectures"].keys())
        next_num = 1
        for name in existing:
            if name.startswith("المحاضرة "):
                try:
                    n = int(name.split(" ")[-1])
                    next_num = max(next_num, n + 1)
                except Exception:
                    pass
        new_name = f"المحاضرة {next_num}"
        node["lectures"][new_name] = []
        await q.edit_message_text(
            f"تمت إضافة \u2068{new_name}\u2069 في \u2068{subject}\u2069 / \u2068{topic}\u2069."
        )
        kb = section_kb(subject, topic, True, context.bot_data)
        await q.message.reply_text(
            f"\u2068{subject}\u2069 / \u2068{topic}\u2069 — الأقسام:", reply_markup=kb
        )
        return

    if data.startswith("pushsel|"):
        # وضع انتظار لاستقبال محتوى من المشرف لهذه الخانة
        if q.from_user.id != ADMIN_ID:
            await q.edit_message_text("هذا الزر للمشرف فقط.")
            return
        parts = data.split("|")
        subject, topic = parts[1], parts[2]
        section = parts[3]
        lec_name = parts[4] if len(parts) > 4 else None
        context.user_data["awaiting_content_for"] = (subject, topic, section, lec_name)
        await q.edit_message_text(
            (
                "أرسل الآن *أي نوع محتوى* (نص/صورة/PDF/ملف/فيديو/صوت...).\n"
                "سيتم حفظه ضمن الخانة المحددة، \n"
                "ويمكنك اختيار بثّه لكل المستخدمين مباشرة بالرسالة التالية."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        # وضع فلاغ للخطوة التالية إن أراد بثًا مباشرًا
        context.user_data["ask_broadcast_next"] = True
        return


async def handle_admin_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # يقبل أي نوع رسالة من المشرف عند انتظار المحتوى
    if update.effective_user.id != ADMIN_ID:
        return

    slot: Optional[Tuple[str, str, str, Optional[str]]] = context.user_data.get("awaiting_content_for")
    if not slot:
        return

    subject, topic, section, lec_name = slot
    ensure_subject_structure(context.bot_data)
    node = context.bot_data["content"][subject][topic]

    # تحديد نوع المادة وحفظ file_id أو النص
    msg = update.effective_message
    m = None
    if msg.text and not msg.via_bot and not msg.entities:
        m = Material(kind="text", text=msg.text)
    elif msg.photo:
        m = Material(kind="photo", file_id=msg.photo[-1].file_id, caption=msg.caption)
    elif msg.document:
        m = Material(kind="document", file_id=msg.document.file_id, caption=msg.caption)
    elif msg.video:
        m = Material(kind="video", file_id=msg.video.file_id, caption=msg.caption)
    elif msg.audio:
        m = Material(kind="audio", file_id=msg.audio.file_id, caption=msg.caption)
    elif msg.voice:
        m = Material(kind="voice", file_id=msg.voice.file_id, caption=msg.caption)
    else:
        await msg.reply_text("نوع الرسالة غير مدعوم للحفظ حاليًا، أرسل نصًا/صورة/ملفًا/صوتًا/فيديو.")
        return

    if section == "assignments":
        node["assignments"].append(m)
        place = ASSIGNMENTS
    else:
        node["lectures"].setdefault(lec_name or DEFAULT_LECTURE, []).append(m)
        place = lec_name or DEFAULT_LECTURE

    await msg.reply_text(
        f"✅ تم الحفظ في \u2068{subject} / {topic} / {place}\u2069.\n"
        "أرسل كلمة \"بث\" الآن لبث نفس المحتوى لكل المستخدمين، أو تجاهل للإنهاء."
    )

    # بعد استلام أول محتوى، يمكن السماح بكلمة "بث"
    context.user_data["last_saved_material"] = (subject, topic, section, lec_name, m)

    # إطفاء وضع انتظار الخانة حتى لا تُجمع رسائل أخرى عن طريق الخطأ
    context.user_data.pop("awaiting_content_for", None)


async def maybe_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if (update.message and update.message.text and update.message.text.strip().lower() == "بث"):
        data = context.user_data.get("last_saved_material")
        if not data:
            await update.message.reply_text("لا يوجد محتوى محفوظ للبث.")
            return
        subject, topic, section, lec_name, m = data
        users = list(context.bot_data.get("users", {}).keys())
        sent = 0
        for uid in users:
            try:
                if m.kind == "text" and m.text:
                    await context.bot.send_message(uid, m.text)
                elif m.kind == "photo" and m.file_id:
                    await context.bot.send_photo(uid, m.file_id, caption=m.caption)
                elif m.kind == "document" and m.file_id:
                    await context.bot.send_document(uid, m.file_id, caption=m.caption)
                elif m.kind == "video" and m.file_id:
                    await context.bot.send_video(uid, m.file_id, caption=m.caption)
                elif m.kind == "audio" and m.file_id:
                    await context.bot.send_audio(uid, m.file_id, caption=m.caption)
                elif m.kind == "voice" and m.file_id:
                    await context.bot.send_voice(uid, m.file_id, caption=m.caption)
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f"🔔 تم البث إلى {sent} مستخدم(ين).")
        # لا نحذف last_saved_material ليمكن إعادة البث لاحقًا إن رغبت


async def on_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إن لم يكن هناك حالة إدارية، تجاهل
    await handle_admin_content(update, context)
    await maybe_broadcast(update, context)


async def on_callback_show(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           subject: str, topic: str, section: str, lec_name: Optional[str]):
    await send_node_materials(update, context, subject, topic, section, lec_name)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    if data.startswith("show|"):
        parts = data.split("|")
        subject, topic = parts[1], parts[2]
        section = parts[3]
        lec_name = parts[4] if len(parts) > 4 else None
        await q.answer()
        await on_callback_show(update, context, subject, topic, section, lec_name)
        return
    # خلاف ذلك، سلّم للمعالج العام
    await on_callback(update, context)


# =====================
# الإقلاع
# =====================

def build_app() -> Application:
    persistence = PicklePersistence(filepath="bot_data.pkl")
    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()

    # أوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("users", admin_users))  # اختصار للمشرف

    # مشاركة جهة الاتصال
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))

    # ردود الأزرار (callback)
    app.add_handler(CallbackQueryHandler(callback_router))

    # أي رسالة (بعد أزرار الإدخال/البث)
    app.add_handler(MessageHandler(~filters.COMMAND & ~filters.StatusUpdate.ALL, on_any_message))

    return app


async def run():
    app = build_app()

    if USE_WEBHOOK:
        # تشغيل كخدمة ويب (مناسب لـ Render)
        await app.initialize()
        await app.start()

        # تعيين الويبهوك
        url = WEBHOOK_URL.rstrip("/") + "/" + WEBHOOK_SECRET.strip("/")
        await app.bot.set_webhook(url)

        print(f"Webhook set to: {url}")
        # خادم ويب مدمج عبر PTB
        await app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=WEBHOOK_SECRET,
        )
    else:
        # تشغيل محليًا عبر Polling
        print("Running in polling mode...")
        await app.run_polling(close_loop=False)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass


# =============================
# requirements.txt (انسخ لمِلَف مستقل)
# =============================
# python-telegram-bot==21.4
# aiohttp==3.9.5
# certifi
#
# (Render يثبّت تلقائيًا اعتمادًا على هذا الملف)


# =============================
# render.yaml (اختياري — نشر Blueprint)
# =============================
# services:
#   - type: web
#     name: telegram-courses-bot
#     env: python
#     plan: starter  # أو basic/pro — لضمان 24/7
#     buildCommand: "pip install -r requirements.txt"
#     startCommand: "python telegram_courses_bot.py"
#     envVars:
#       - key: BOT_TOKEN
#         sync: false  # أدخله يدويًا من داشبورد Render (سِرّي)
#       - key: ADMIN_ID
#         value: "5774252730"
#       - key: WEBHOOK_URL
#         value: "https://your-app.onrender.com"  # عدّلها بعد إنشاء الخدمة
#       - key: WEBHOOK_SECRET
#         value: "secret-path"  # مسار سري مثل: x9Abc_123
#     autoDeploy: true

# =============================
# ملاحظات مهمة
# =============================
# • للتجربة محليًا: أزِل WEBHOOK_URL من المتغيرات البيئية وشغّل:  python telegram_courses_bot.py
# • على Render: أضِف WEBHOOK_URL (رابط خدمتك) وWEBHOOK_SECRET (أي نص سري)، وسيعمل بالويبهوك تلقائيًا.
# • التخزين Pickle محليًا (bot_data.pkl). على Render قد يكون التخزين مؤقتًا؛ إن رغبت بالدوام، استخدم قاعدة بيانات (Redis/SQL) لاحقًا.
# • تم تنفيذ بث فوري اختياري: بعد حفظ محتوى بالقسم، أرسل كلمة "بث" في رسالة منفصلة لبث آخر عنصر محفوظ إلى جميع المستخدمين.
