import asyncio
import telebot
from telebot.types import Message, CallbackQuery
from config import config
from services.telegram_client import telegram_service
from utils.keyboards import (
    main_menu_keyboard,
    cancel_keyboard,
    login_keyboard,
    help_keyboard,
)
from utils.helpers import (
    is_owner,
    build_progress_bar,
)
from utils.logger import (
    bot_logger,
    activity_logger,
    error_logger,
)

# ==================== حالات المحادثة ====================

# تخزين حالات المستخدمين
user_states = {}

STATE_IDLE          = "idle"
STATE_WAITING_PHONE = "waiting_phone"
STATE_WAITING_CODE  = "waiting_code"
STATE_WAITING_PASS  = "waiting_password"


# ==================== دوال مساعدة ====================

def get_state(user_id: int) -> str:
    return user_states.get(user_id, {}).get(
        "state", STATE_IDLE
    )


def set_state(user_id: int, state: str, **kwargs):
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]["state"] = state
    user_states[user_id].update(kwargs)


def clear_state(user_id: int):
    user_states.pop(user_id, None)


def get_user_data(user_id: int, key: str):
    return user_states.get(user_id, {}).get(key)


# ==================== تسجيل الهاندلرز ====================

def register_auth_handlers(bot: telebot.TeleBot):
    """تسجيل كل هاندلرز المصادقة"""

    # ==================== /start ====================

    @bot.message_handler(commands=["start"])
    def start_command(message: Message):
        asyncio.run(_start_command(bot, message))

    async def _start_command(
            bot: telebot.TeleBot,
            message: Message):
        from database import db

        user_id   = message.from_user.id
        full_name = message.from_user.full_name

        # تسجيل المستخدم
        await db.create_user(
            telegram_id = user_id,
            username    = message.from_user.username,
            full_name   = full_name,
        )

        # التحقق من الحظر
        user = await db.get_user(user_id)
        if user and user["is_banned"]:
            bot.send_message(
                user_id,
                "🚫 أنت محظور من استخدام البوت"
            )
            return

        await db.log_activity(
            user_id, "START",
            {"username": message.from_user.username}
        )

        # التحقق من تسجيل الدخول
        is_authorized = await telegram_service.manager.is_authorized(
            user_id
        )

        if is_authorized:
            me = await telegram_service.get_me(user_id)
            name = (
                me.get("full_name", full_name)
                if me else full_name
            )
            bot.send_message(
                user_id,
                f"👋 أهلاً مجدداً **{name}**!\n\n"
                f"اختر ما تريد من القائمة 👇",
                reply_markup=main_menu_keyboard(
                    is_logged_in=True
                ),
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                user_id,
                f"👋 مرحباً **{full_name}**!\n\n"
                f"🤖 أنا بوت أرشفة تيليغرام\n\n"
                f"**ماذا أستطيع أن أفعل؟**\n"
                f"📋 جلب وأرشفة محتوى قنواتك\n"
                f"🖼️ حفظ الصور والفيديوهات والملفات\n"
                f"🤖 تلخيص وتصنيف المحتوى بالذكاء الاصطناعي\n"
                f"📊 إحصائيات تفصيلية\n"
                f"🔍 بحث في المحتوى المحفوظ\n"
                f"💳 استخراج ذكي للبيانات\n\n"
                f"📱 ابدأ بتسجيل الدخول بحسابك 👇",
                reply_markup=main_menu_keyboard(
                    is_logged_in=False
                ),
                parse_mode="Markdown"
            )

    # ==================== /help ====================

    @bot.message_handler(commands=["help"])
    def help_command(message: Message):
        bot.send_message(
            message.from_user.id,
            "❓ **المساعدة**\n\n"
            "**الأوامر المتاحة:**\n"
            "/start - بدء البوت\n"
            "/help - المساعدة\n"
            "/status - حالة الحساب\n"
            "/cancel - إلغاء العملية الحالية\n\n"
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

    @bot.message_handler(commands=["status"])
    def status_command(message: Message):
        asyncio.run(_status_command(bot, message))

    async def _status_command(
            bot: telebot.TeleBot,
            message: Message):
        from database import db

        user_id       = message.from_user.id
        is_authorized = await telegram_service.manager.is_authorized(
            user_id
        )

        if is_authorized:
            me    = await telegram_service.get_me(user_id)
            stats = await db.get_stats(user_id)

            bot.send_message(
                user_id,
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
            bot.send_message(
                user_id,
                "❌ غير مسجل دخول\n"
                "استخدم /start",
                reply_markup=login_keyboard()
            )

    # ==================== /cancel ====================

    @bot.message_handler(commands=["cancel"])
    def cancel_command(message: Message):
        user_id = message.from_user.id
        clear_state(user_id)
        bot.send_message(
            user_id,
            "❌ تم إلغاء العملية الحالية",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            )
        )

    # ==================== callback: login ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "login"
    )
    def login_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        set_state(user_id, STATE_WAITING_PHONE)

        bot.send_message(
            user_id,
            "📱 **تسجيل الدخول**\n\n"
            "أرسل رقم هاتفك مع رمز الدولة\n"
            "مثال: `+9647701234567`",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )

    # ==================== استقبال الرسائل ====================

    @bot.message_handler(
        func=lambda m: get_state(
            m.from_user.id
        ) == STATE_WAITING_PHONE
    )
    def receive_phone(message: Message):
        asyncio.run(_receive_phone(bot, message))

    async def _receive_phone(
            bot: telebot.TeleBot,
            message: Message):
        user_id = message.from_user.id
        phone   = message.text.strip()

        if (not phone.startswith("+") or
                len(phone) < 10):
            bot.send_message(
                user_id,
                "❌ رقم غير صحيح\n"
                "أرسل الرقم مع رمز الدولة\n"
                "مثال: `+9647701234567`",
                reply_markup=cancel_keyboard(),
                parse_mode="Markdown"
            )
            return

        wait_msg = bot.send_message(
            user_id,
            "⏳ جاري إرسال كود التحقق..."
        )

        result = await telegram_service.send_code(
            user_id, phone
        )

        try:
            bot.delete_message(user_id, wait_msg.message_id)
        except Exception:
            pass

        if result["success"]:
            set_state(
                user_id,
                STATE_WAITING_CODE,
                phone=phone,
                phone_code_hash=result["phone_code_hash"]
            )

            bot.send_message(
                user_id,
                f"✅ تم إرسال كود التحقق إلى\n"
                f"`{phone}`\n\n"
                f"🔢 أرسل الكود المكون من 5 أرقام",
                reply_markup=cancel_keyboard(),
                parse_mode="Markdown"
            )
        else:
            error = result.get("error", "")
            clear_state(user_id)

            if error == "flood_wait":
                seconds = result.get("seconds", 60)
                bot.send_message(
                    user_id,
                    f"⚠️ انتظر {seconds} ثانية وحاول مجدداً",
                    reply_markup=login_keyboard()
                )
            elif error == "phone_invalid":
                bot.send_message(
                    user_id,
                    "❌ رقم الهاتف غير صحيح",
                    reply_markup=cancel_keyboard()
                )
                set_state(user_id, STATE_WAITING_PHONE)
            else:
                bot.send_message(
                    user_id,
                    f"❌ خطأ: {result.get('message', '')}",
                    reply_markup=login_keyboard()
                )

    @bot.message_handler(
        func=lambda m: get_state(
            m.from_user.id
        ) == STATE_WAITING_CODE
    )
    def receive_code(message: Message):
        asyncio.run(_receive_code(bot, message))

    async def _receive_code(
            bot: telebot.TeleBot,
            message: Message):
        from database import db

        user_id = message.from_user.id
        code    = message.text.strip().replace(
            " ", ""
        ).replace("-", "")

        if not code.isdigit() or len(code) != 5:
            bot.send_message(
                user_id,
                "❌ الكود يجب أن يكون 5 أرقام",
                reply_markup=cancel_keyboard()
            )
            return

        phone           = get_user_data(user_id, "phone")
        phone_code_hash = get_user_data(
            user_id, "phone_code_hash"
        )

        wait_msg = bot.send_message(
            user_id, "⏳ جاري التحقق..."
        )

        result = await telegram_service.sign_in(
            user_id, phone, code, phone_code_hash
        )

        try:
            bot.delete_message(user_id, wait_msg.message_id)
        except Exception:
            pass

        if result["success"]:
            await _handle_login_success(
                bot, user_id, phone, db
            )
            clear_state(user_id)
            return

        error = result.get("error", "")

        if result.get("needs_password"):
            set_state(user_id, STATE_WAITING_PASS)
            bot.send_message(
                user_id,
                "🔐 **التحقق بخطوتين**\n\n"
                "أرسل كلمة المرور الثنائية لحسابك",
                reply_markup=cancel_keyboard(),
                parse_mode="Markdown"
            )
            return

        if error == "code_invalid":
            bot.send_message(
                user_id,
                "❌ الكود غير صحيح أو منتهي\n"
                "أرسل الكود مجدداً",
                reply_markup=cancel_keyboard()
            )
            return

        clear_state(user_id)
        bot.send_message(
            user_id,
            f"❌ خطأ: {result.get('message', '')}",
            reply_markup=login_keyboard()
        )

    @bot.message_handler(
        func=lambda m: get_state(
            m.from_user.id
        ) == STATE_WAITING_PASS
    )
    def receive_password(message: Message):
        asyncio.run(_receive_password(bot, message))

    async def _receive_password(
            bot: telebot.TeleBot,
            message: Message):
        from database import db

        user_id  = message.from_user.id
        password = message.text.strip()

        # حذف رسالة كلمة المرور للأمان
        try:
            bot.delete_message(
                user_id, message.message_id
            )
        except Exception:
            pass

        wait_msg = bot.send_message(
            user_id, "⏳ جاري التحقق..."
        )

        result = await telegram_service.sign_in_password(
            user_id, password
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if result["success"]:
            phone = get_user_data(user_id, "phone") or ""
            await _handle_login_success(
                bot, user_id, phone, db
            )
            clear_state(user_id)
            return

        bot.send_message(
            user_id,
            "❌ كلمة المرور غير صحيحة\n"
            "أرسل كلمة المرور مجدداً",
            reply_markup=cancel_keyboard()
        )

    async def _handle_login_success(
            bot: telebot.TeleBot,
            user_id: int,
            phone: str,
            db):
        """معالجة نجاح تسجيل الدخول"""
        me = await telegram_service.get_me(user_id)
        full_name = (
            me.get("full_name", "") if me else ""
        )
        phone = me.get("phone", phone) if me else phone

        await db.update_user(
            user_id,
            phone=phone,
        )
        await db.save_session(user_id, phone)
        await db.log_activity(
            user_id, "LOGIN_SUCCESS",
            {"phone": phone}
        )

        bot_logger.info(
            f"✅ تسجيل دخول ناجح للمستخدم {user_id}"
        )

        bot.send_message(
            user_id,
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

    @bot.callback_query_handler(
        func=lambda c: c.data == "logout"
    )
    def logout_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        from utils.keyboards import confirm_keyboard
        bot.send_message(
            user_id,
            "⚠️ هل تريد تسجيل الخروج؟",
            reply_markup=confirm_keyboard("logout")
        )

    @bot.callback_query_handler(
        func=lambda c: c.data == "confirm_logout"
    )
    def confirm_logout_callback(call: CallbackQuery):
        asyncio.run(_confirm_logout(bot, call))

    async def _confirm_logout(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id  = call.from_user.id
        bot.answer_callback_query(call.id)

        wait_msg = bot.send_message(
            user_id, "⏳ جاري تسجيل الخروج..."
        )

        success = await telegram_service.logout(user_id)
        await db.delete_session(user_id)
        await db.log_activity(user_id, "LOGOUT")

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if success:
            bot.send_message(
                user_id,
                "✅ تم تسجيل الخروج بنجاح\n\n"
                "استخدم /start للدخول مجدداً",
                reply_markup=login_keyboard()
            )
        else:
            bot.send_message(
                user_id,
                "❌ حدث خطأ أثناء تسجيل الخروج",
                reply_markup=main_menu_keyboard(
                    is_logged_in=True
                )
            )

    # ==================== إلغاء ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "cancel"
    )
    def cancel_callback(call: CallbackQuery):
        asyncio.run(_cancel_callback(bot, call))

    async def _cancel_callback(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)
        clear_state(user_id)

        is_authorized = await telegram_service.manager.is_authorized(
            user_id
        )

        bot.send_message(
            user_id,
            "❌ تم الإلغاء",
            reply_markup=main_menu_keyboard(
                is_logged_in=is_authorized
            )
        )

    # ==================== المطور ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "developer"
    )
    def developer_callback(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.from_user.id,
            f"👑 **معلومات المطور**\n\n"
            f"👤 الاسم: `{config.DEVELOPER_NAME}`\n"
            f"📱 يوزر: {config.DEVELOPER_USERNAME}\n\n"
            f"🤖 تم تطوير هذا البوت بواسطة\n"
            f"**{config.DEVELOPER_NAME}**",
            parse_mode="Markdown"
        )

    # ==================== مساعدة ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "help"
    )
    def help_callback(call: CallbackQuery):
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.from_user.id,
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

    # ==================== القائمة الرئيسية ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "main_menu"
    )
    def main_menu_callback(call: CallbackQuery):
        asyncio.run(_main_menu_callback(bot, call))

    async def _main_menu_callback(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        is_authorized = await telegram_service.manager.is_authorized(
            user_id
        )

        bot.send_message(
            user_id,
            "🏠 **القائمة الرئيسية**\n\n"
            "اختر ما تريد 👇",
            reply_markup=main_menu_keyboard(
                is_logged_in=is_authorized
            ),
            parse_mode="Markdown"
        )
