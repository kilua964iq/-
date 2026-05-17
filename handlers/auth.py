from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config import config
from services.telegram_client import telegram_service
from utils.keyboards import (
    main_menu_keyboard,
    cancel_keyboard,
    login_keyboard,
    help_keyboard,
    confirm_keyboard,
)
from utils.helpers import is_owner
from utils.logger import (
    bot_logger,
    activity_logger,
    error_logger,
)


# ==================== حالات المحادثة ====================

(
    WAITING_PHONE,
    WAITING_CODE,
    WAITING_PASSWORD,
) = range(3)


# ==================== /start ====================

async def start_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    user    = update.effective_user
    user_id = user.id

    await db.create_user(
        telegram_id = user_id,
        username    = user.username,
        full_name   = user.full_name,
    )

    user_data = await db.get_user(user_id)
    if user_data and user_data["is_banned"]:
        await update.message.reply_text(
            "🚫 أنت محظور من استخدام البوت"
        )
        return ConversationHandler.END

    await db.log_activity(
        user_id, "START",
        {"username": user.username}
    )

    is_authorized = await telegram_service.manager.is_authorized(
        user_id
    )

    if is_authorized:
        me = await telegram_service.get_me(user_id)
        name = (
            me.get("full_name", user.full_name)
            if me else user.full_name
        )
        await update.message.reply_text(
            f"👋 أهلاً مجدداً **{name}**!\n\n"
            f"اختر ما تريد من القائمة 👇",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            ),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"👋 مرحباً **{user.full_name}**!\n\n"
            f"🤖 أنا بوت أرشفة تيليغرام\n\n"
            f"**ماذا أستطيع أن أفعل؟**\n"
            f"📋 جلب وأرشفة محتوى قنواتك\n"
            f"🖼️ حفظ الصور والفيديوهات والملفات\n"
            f"🤖 تلخيص وتصنيف المحتوى بالذكاء الاصطناعي\n"
            f"📊 إحصائيات تفصيلية\n"
            f"🔍 بحث ذكي في المحتوى المحفوظ\n"
            f"💳 استخراج ذكي للبيانات\n"
            f"🧠 أوامر طبيعية بالعربي\n\n"
            f"📱 ابدأ بتسجيل الدخول بحسابك 👇",
            reply_markup=main_menu_keyboard(
                is_logged_in=False
            ),
            parse_mode="Markdown"
        )

    return ConversationHandler.END


# ==================== /help ====================

async def help_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ **المساعدة**\n\n"
        "**الأوامر المتاحة:**\n"
        "/start - بدء البوت\n"
        "/help - المساعدة\n"
        "/status - حالة الحساب\n"
        "/cancel - إلغاء العملية\n\n"
        "**كيفية الاستخدام:**\n"
        "1️⃣ سجل دخول بحسابك\n"
        "2️⃣ اختر قناة أو مجموعة\n"
        "3️⃣ اختر نوع المحتوى\n"
        "4️⃣ اختر الكمية\n"
        "5️⃣ انتظر اكتمال الجلب\n\n"
        f"👑 المطور: {config.DEVELOPER_NAME}\n"
        f"📱 {config.DEVELOPER_USERNAME}",
        reply_markup=help_keyboard(),
        parse_mode="Markdown"
    )


# ==================== /status ====================

async def status_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    user_id = update.effective_user.id
    is_authorized = await telegram_service.manager.is_authorized(
        user_id
    )

    if is_authorized:
        me    = await telegram_service.get_me(user_id)
        stats = await db.get_stats(user_id)
        await update.message.reply_text(
            f"✅ **حالة الحساب**\n\n"
            f"👤 الاسم: `{me.get('full_name', '')}`\n"
            f"📱 الهاتف: `{me.get('phone', '')}`\n"
            f"📦 الأرشيفات: "
            f"`{stats['total_archives'] or 0}`\n"
            f"💬 الرسائل: "
            f"`{stats['total_messages'] or 0}`\n",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            ),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ غير مسجل دخول\nاستخدم /start",
            reply_markup=login_keyboard()
        )


# ==================== login ====================

async def login_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📱 **تسجيل الدخول**\n\n"
        "أرسل رقم هاتفك مع رمز الدولة\n"
        "مثال: `+9647701234567`",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )
    return WAITING_PHONE


# ==================== استقبال الهاتف ====================

async def receive_phone(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    phone   = update.message.text.strip()

    if not phone.startswith("+") or len(phone) < 10:
        await update.message.reply_text(
            "❌ رقم غير صحيح\n"
            "مثال: `+9647701234567`",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )
        return WAITING_PHONE

    wait_msg = await update.message.reply_text(
        "⏳ جاري إرسال كود التحقق..."
    )

    result = await telegram_service.send_code(
        user_id, phone
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if result["success"]:
        context.user_data["phone"] = phone
        context.user_data["phone_code_hash"] = (
            result["phone_code_hash"]
        )

        await update.message.reply_text(
            f"✅ تم إرسال كود التحقق إلى\n"
            f"`{phone}`\n\n"
            f"🔢 أرسل الكود المكون من 5 أرقام",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )
        return WAITING_CODE

    error = result.get("error", "")

    if error == "flood_wait":
        seconds = result.get("seconds", 60)
        await update.message.reply_text(
            f"⚠️ انتظر {seconds} ثانية وحاول مجدداً",
            reply_markup=login_keyboard()
        )
    elif error == "phone_invalid":
        await update.message.reply_text(
            "❌ رقم الهاتف غير صحيح",
            reply_markup=cancel_keyboard()
        )
        return WAITING_PHONE
    else:
        await update.message.reply_text(
            f"❌ خطأ: {result.get('message', '')}",
            reply_markup=login_keyboard()
        )

    return ConversationHandler.END


# ==================== استقبال الكود ====================

async def receive_code(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    user_id = update.effective_user.id
    code    = update.message.text.strip().replace(
        " ", ""
    ).replace("-", "")

    if not code.isdigit() or len(code) != 5:
        await update.message.reply_text(
            "❌ الكود يجب أن يكون 5 أرقام",
            reply_markup=cancel_keyboard()
        )
        return WAITING_CODE

    phone           = context.user_data.get("phone", "")
    phone_code_hash = context.user_data.get(
        "phone_code_hash", ""
    )

    wait_msg = await update.message.reply_text(
        "⏳ جاري التحقق..."
    )

    result = await telegram_service.sign_in(
        user_id, phone, code, phone_code_hash
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if result["success"]:
        await _handle_login_success(
            update, context, user_id, phone, db
        )
        return ConversationHandler.END

    error = result.get("error", "")

    if result.get("needs_password"):
        await update.message.reply_text(
            "🔐 **التحقق بخطوتين**\n\n"
            "أرسل كلمة المرور الثنائية",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )
        return WAITING_PASSWORD

    if error == "code_invalid":
        await update.message.reply_text(
            "❌ الكود غير صحيح أو منتهي\n"
            "أرسل الكود مجدداً",
            reply_markup=cancel_keyboard()
        )
        return WAITING_CODE

    await update.message.reply_text(
        f"❌ خطأ: {result.get('message', '')}",
        reply_markup=login_keyboard()
    )
    return ConversationHandler.END


# ==================== كلمة المرور ====================

async def receive_password(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    user_id  = update.effective_user.id
    password = update.message.text.strip()

    try:
        await update.message.delete()
    except Exception:
        pass

    wait_msg = await update.effective_chat.send_message(
        "⏳ جاري التحقق..."
    )

    result = await telegram_service.sign_in_password(
        user_id, password
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if result["success"]:
        phone = context.user_data.get("phone", "")
        await _handle_login_success(
            update, context, user_id, phone, db
        )
        return ConversationHandler.END

    await update.effective_chat.send_message(
        "❌ كلمة المرور غير صحيحة\n"
        "أرسل كلمة المرور مجدداً",
        reply_markup=cancel_keyboard()
    )
    return WAITING_PASSWORD


async def _handle_login_success(
        update, context, user_id, phone, db):
    me = await telegram_service.get_me(user_id)
    full_name = (
        me.get("full_name", "") if me else ""
    )
    phone = me.get("phone", phone) if me else phone

    await db.update_user(user_id, phone=phone)
    await db.save_session(user_id, phone)
    await db.log_activity(
        user_id, "LOGIN_SUCCESS",
        {"phone": phone}
    )

    context.user_data.clear()

    await update.effective_chat.send_message(
        f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
        f"👤 الاسم: `{full_name}`\n"
        f"📱 الهاتف: `{phone}`\n\n"
        f"اختر ما تريد من القائمة 👇",
        reply_markup=main_menu_keyboard(
            is_logged_in=True
        ),
        parse_mode="Markdown"
    )


# ==================== تسجيل الخروج ====================

async def logout_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "⚠️ هل تريد تسجيل الخروج؟",
        reply_markup=confirm_keyboard("logout")
    )


async def confirm_logout_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    wait_msg = await query.message.reply_text(
        "⏳ جاري تسجيل الخروج..."
    )

    success = await telegram_service.logout(user_id)
    await db.delete_session(user_id)
    await db.log_activity(user_id, "LOGOUT")

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if success:
        await query.message.reply_text(
            "✅ تم تسجيل الخروج بنجاح\n\n"
            "استخدم /start للدخول مجدداً",
            reply_markup=login_keyboard()
        )
    else:
        await query.message.reply_text(
            "❌ حدث خطأ أثناء تسجيل الخروج",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            )
        )


# ==================== إلغاء ====================

async def cancel_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    context.user_data.clear()

    is_authorized = await telegram_service.manager.is_authorized(
        user_id
    )

    await query.message.reply_text(
        "❌ تم الإلغاء",
        reply_markup=main_menu_keyboard(
            is_logged_in=is_authorized
        )
    )
    return ConversationHandler.END


# ==================== القائمة الرئيسية ====================

async def main_menu_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    is_authorized = await telegram_service.manager.is_authorized(
        user_id
    )

    await query.message.reply_text(
        "🏠 **القائمة الرئيسية**\n\n"
        "اختر ما تريد 👇",
        reply_markup=main_menu_keyboard(
            is_logged_in=is_authorized
        ),
        parse_mode="Markdown"
    )


# ==================== المطور ====================

async def developer_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        f"👑 **معلومات المطور**\n\n"
        f"👤 الاسم: `{config.DEVELOPER_NAME}`\n"
        f"📱 يوزر: {config.DEVELOPER_USERNAME}\n\n"
        f"🤖 تم تطوير هذا البوت بواسطة\n"
        f"**{config.DEVELOPER_NAME}**",
        parse_mode="Markdown"
    )


# ==================== مساعدة ====================

async def help_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "❓ **المساعدة**\n\n"
        "**الأوامر المتاحة:**\n"
        "/start - بدء البوت\n"
        "/help - المساعدة\n"
        "/status - حالة الحساب\n"
        "/cancel - إلغاء العملية\n\n"
        "**كيفية الاستخدام:**\n"
        "1️⃣ سجل دخول بحسابك\n"
        "2️⃣ اختر قناة أو مجموعة\n"
        "3️⃣ اختر نوع المحتوى\n"
        "4️⃣ اختر الكمية\n"
        "5️⃣ انتظر اكتمال الجلب\n\n"
        f"👑 المطور: {config.DEVELOPER_NAME}\n"
        f"📱 {config.DEVELOPER_USERNAME}",
        reply_markup=help_keyboard(),
        parse_mode="Markdown"
    )


# ==================== ConversationHandler ====================

def get_auth_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(
                login_callback, pattern="^login$"
            ),
        ],
        states={
            WAITING_PHONE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_phone
                )
            ],
            WAITING_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_code
                )
            ],
            WAITING_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_password
                )
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(
                cancel_callback, pattern="^cancel$"
            ),
        ],
        allow_reentry=True,
    )
