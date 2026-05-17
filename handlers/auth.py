import asyncio
from telegram import Update
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
)
from utils.helpers import (
    is_owner,
    build_welcome_message,
    safe_edit_message,
    safe_delete_message,
)
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


# ==================== دوال مساعدة ====================

async def check_banned(update: Update, db) -> bool:
    """التحقق إذا كان المستخدم محظور"""
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    if user and user["is_banned"]:
        await update.effective_message.reply_text(
            "🚫 أنت محظور من استخدام البوت"
        )
        return True
    return False


async def ensure_user(update: Update, db):
    """التأكد من وجود المستخدم في قاعدة البيانات"""
    user = update.effective_user
    await db.create_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )


# ==================== /start ====================

async def start_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """أمر البدء"""
    from database import db

    user    = update.effective_user
    user_id = user.id

    # تسجيل المستخدم
    await ensure_user(update, db)

    # التحقق من الحظر
    if await check_banned(update, db):
        return ConversationHandler.END

    # تسجيل النشاط
    await db.log_activity(
        user_id, "START",
        {"username": user.username}
    )

    # التحقق من تسجيل الدخول
    is_authorized = await telegram_service.manager.is_authorized(
        user_id
    )

    if is_authorized:
        me = await telegram_service.get_me(user_id)
        full_name = (
            me.get("full_name", user.full_name)
            if me else user.full_name
        )

        await update.message.reply_text(
            build_welcome_message(full_name, is_new=False),
            reply_markup=main_menu_keyboard(is_logged_in=True),
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    # غير مسجل دخول
    await update.message.reply_text(
        build_welcome_message(user.full_name, is_new=True),
        reply_markup=login_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ==================== تسجيل الدخول ====================

async def login_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """بدء تسجيل الدخول"""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📱 **تسجيل الدخول**\n\n"
        "أرسل رقم هاتفك مع رمز الدولة\n"
        "مثال: `+9647701234567`",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )
    return WAITING_PHONE


async def receive_phone(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """استقبال رقم الهاتف"""
    user_id = update.effective_user.id
    phone   = update.message.text.strip()

    # التحقق من صيغة الرقم
    if not phone.startswith("+") or len(phone) < 10:
        await update.message.reply_text(
            "❌ رقم غير صحيح\n"
            "أرسل الرقم مع رمز الدولة\n"
            "مثال: `+9647701234567`",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown",
        )
        return WAITING_PHONE

    # حفظ الرقم
    context.user_data["phone"] = phone

    # إرسال رسالة انتظار
    wait_msg = await update.message.reply_text(
        "⏳ جاري إرسال كود التحقق..."
    )

    # إرسال الكود
    result = await telegram_service.send_code(
        user_id, phone
    )

    await safe_delete_message(wait_msg)

    if result["success"]:
        context.user_data["phone_code_hash"] = (
            result["phone_code_hash"]
        )

        await update.message.reply_text(
            f"✅ تم إرسال كود التحقق إلى\n"
            f"`{phone}`\n\n"
            f"🔢 أرسل الكود المكون من 5 أرقام",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown",
        )
        return WAITING_CODE

    # معالجة الأخطاء
    error = result.get("error", "")

    if error == "flood_wait":
        seconds = result.get("seconds", 60)
        await update.message.reply_text(
            f"⚠️ انتظر {seconds} ثانية وحاول مجدداً",
            reply_markup=login_keyboard(),
        )
    elif error == "phone_invalid":
        await update.message.reply_text(
            "❌ رقم الهاتف غير صحيح\n"
            "تأكد من الرقم وحاول مجدداً",
            reply_markup=cancel_keyboard(),
        )
        return WAITING_PHONE
    else:
        await update.message.reply_text(
            f"❌ خطأ: {result.get('message', 'غير معروف')}\n"
            "حاول مجدداً /start",
            reply_markup=login_keyboard(),
        )

    return ConversationHandler.END


async def receive_code(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """استقبال كود التحقق"""
    user_id = update.effective_user.id
    code    = update.message.text.strip()

    # تنظيف الكود
    code = code.replace(" ", "").replace("-", "")

    if not code.isdigit() or len(code) != 5:
        await update.message.reply_text(
            "❌ الكود يجب أن يكون 5 أرقام\n"
            "أرسل الكود مجدداً",
            reply_markup=cancel_keyboard(),
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

    await safe_delete_message(wait_msg)

    if result["success"]:
        await _handle_login_success(
            update, context, user_id
        )
        return ConversationHandler.END

    error = result.get("error", "")

    if result.get("needs_password"):
        await update.message.reply_text(
            "🔐 **التحقق بخطوتين**\n\n"
            "أرسل كلمة المرور الثنائية لحسابك",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown",
        )
        return WAITING_PASSWORD

    if error == "code_invalid":
        await update.message.reply_text(
            "❌ الكود غير صحيح أو منتهي الصلاحية\n"
            "أرسل الكود مجدداً",
            reply_markup=cancel_keyboard(),
        )
        return WAITING_CODE

    if error == "flood_wait":
        seconds = result.get("seconds", 60)
        await update.message.reply_text(
            f"⚠️ انتظر {seconds} ثانية وحاول مجدداً"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"❌ خطأ: {result.get('message', 'غير معروف')}\n"
        "حاول مجدداً /start"
    )
    return ConversationHandler.END


async def receive_password(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """استقبال كلمة المرور الثنائية"""
    user_id  = update.effective_user.id
    password = update.message.text.strip()

    # حذف رسالة كلمة المرور فوراً للأمان
    await safe_delete_message(update.message)

    wait_msg = await update.effective_chat.send_message(
        "⏳ جاري التحقق..."
    )

    result = await telegram_service.sign_in_password(
        user_id, password
    )

    await safe_delete_message(wait_msg)

    if result["success"]:
        await _handle_login_success(
            update, context, user_id
        )
        return ConversationHandler.END

    await update.effective_chat.send_message(
        "❌ كلمة المرور غير صحيحة\n"
        "أرسل كلمة المرور مجدداً",
        reply_markup=cancel_keyboard(),
    )
    return WAITING_PASSWORD


async def _handle_login_success(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int):
    """معالجة نجاح تسجيل الدخول"""
    from database import db

    me = await telegram_service.get_me(user_id)
    full_name = (
        me.get("full_name", "")
        if me else
        update.effective_user.full_name
    )
    phone = me.get("phone", "") if me else ""

    # تحديث قاعدة البيانات
    await db.update_user(
        user_id,
        phone=phone,
        last_active=__import__(
            "datetime"
        ).datetime.now()
    )

    await db.save_session(user_id, phone)

    await db.log_activity(
        user_id, "LOGIN_SUCCESS",
        {"phone": phone}
    )

    bot_logger.info(
        f"✅ تسجيل دخول ناجح للمستخدم {user_id}"
    )

    await update.effective_chat.send_message(
        f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
        f"👤 الاسم: `{full_name}`\n"
        f"📱 الهاتف: `{phone}`\n\n"
        f"اختر ما تريد من القائمة 👇",
        reply_markup=main_menu_keyboard(is_logged_in=True),
        parse_mode="Markdown",
    )

    # تنظيف البيانات المؤقتة
    context.user_data.clear()


# ==================== تسجيل الخروج ====================

async def logout_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """تسجيل الخروج"""
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # تأكيد تسجيل الخروج
    from utils.keyboards import confirm_keyboard
    await query.message.reply_text(
        "⚠️ هل تريد تسجيل الخروج؟",
        reply_markup=confirm_keyboard("logout"),
    )


async def confirm_logout_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """تأكيد تسجيل الخروج"""
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

    await safe_delete_message(wait_msg)

    if success:
        await query.message.reply_text(
            "✅ تم تسجيل الخروج بنجاح\n\n"
            "استخدم /start للدخول مجدداً",
            reply_markup=login_keyboard(),
        )
    else:
        await query.message.reply_text(
            "❌ حدث خطأ أثناء تسجيل الخروج\n"
            "حاول مجدداً",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            ),
        )


# ==================== إلغاء ====================

async def cancel_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية الحالية"""
    query = update.callback_query
    await query.answer()

    user_id       = update.effective_user.id
    is_authorized = await telegram_service.manager.is_authorized(
        user_id
    )

    context.user_data.clear()

    await query.message.reply_text(
        "❌ تم الإلغاء",
        reply_markup=main_menu_keyboard(
            is_logged_in=is_authorized
        ),
    )
    return ConversationHandler.END


# ==================== /help ====================

async def help_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """أمر المساعدة"""
    from utils.keyboards import help_keyboard

    await update.message.reply_text(
        "❓ **المساعدة**\n\n"
        "**الأوامر المتاحة:**\n"
        "/start - بدء البوت\n"
        "/help - المساعدة\n"
        "/status - حالة الحساب\n\n"
        "**كيفية الاستخدام:**\n"
        "1️⃣ سجل دخول بحسابك\n"
        "2️⃣ اختر قناة أو مجموعة\n"
        "3️⃣ اختر نوع المحتوى\n"
        "4️⃣ اختر الكمية\n"
        "5️⃣ انتظر اكتمال الجلب\n",
        reply_markup=help_keyboard(),
        parse_mode="Markdown",
    )


# ==================== /status ====================

async def status_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """حالة الحساب"""
    from database import db

    user_id       = update.effective_user.id
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
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "❌ غير مسجل دخول\n"
            "استخدم /start",
            reply_markup=login_keyboard(),
        )


# ==================== ConversationHandler ====================

def get_auth_handler() -> ConversationHandler:
    """إنشاء ConversationHandler لتسجيل الدخول"""
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
