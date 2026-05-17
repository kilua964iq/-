import asyncio
import telebot
from telebot.types import Message, CallbackQuery
from config import config
from services.telegram_client import telegram_service
from utils.keyboards import (
    chats_keyboard,
    chat_type_keyboard,
    content_type_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
)
from utils.helpers import (
    format_number,
    is_owner,
    get_chat_type,
    extract_username,
    get_members_count,
)
from utils.logger import (
    bot_logger,
    activity_logger,
    error_logger,
)
from handlers.auth import (
    get_state,
    set_state,
    clear_state,
    get_user_data,
    STATE_IDLE,
)

# ==================== حالات ====================

STATE_WAITING_USERNAME = "waiting_username"


# ==================== دوال مساعدة ====================

async def require_login(
        bot: telebot.TeleBot,
        user_id: int) -> bool:
    """التحقق من تسجيل الدخول"""
    is_authorized = await telegram_service.manager.is_authorized(
        user_id
    )
    if not is_authorized:
        bot.send_message(
            user_id,
            "❌ يجب تسجيل الدخول أولاً\n"
            "استخدم /start",
            reply_markup=main_menu_keyboard(
                is_logged_in=False
            )
        )
        return False
    return True


# ==================== تسجيل الهاندلرز ====================

def register_chats_handlers(bot: telebot.TeleBot):
    """تسجيل كل هاندلرز القنوات"""

    # ==================== عرض القنوات ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "show_channels"
    )
    def show_channels_callback(call: CallbackQuery):
        asyncio.run(_show_channels(bot, call))

    async def _show_channels(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not await require_login(bot, user_id):
            return

        wait_msg = bot.send_message(
            user_id,
            "⏳ جاري تحميل قنواتك..."
        )

        result = await telegram_service.get_dialogs(
            user_id
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if not result["success"]:
            error = result.get("error", "")
            if error == "session_expired":
                bot.send_message(
                    user_id,
                    "❌ انتهت الجلسة\n"
                    "سجل دخول مجدداً /start"
                )
            else:
                bot.send_message(
                    user_id,
                    f"❌ خطأ: {result.get('message', '')}"
                )
            return

        channels = result.get("channels", [])

        if not channels:
            bot.send_message(
                user_id,
                "📢 لا توجد قنوات\n\n"
                "تأكد أنك مشترك في قنوات",
                reply_markup=main_menu_keyboard(
                    is_logged_in=True
                )
            )
            return

        # حفظ في قاعدة البيانات
        for chat in channels:
            await db.save_chat(
                owner_id      = user_id,
                chat_id       = chat["id"],
                chat_title    = chat["title"],
                chat_type     = "channel",
                chat_username = chat.get("username"),
                members_count = chat.get(
                    "members_count", 0
                ),
            )

        # حفظ في الحالة
        set_state(
            user_id,
            STATE_IDLE,
            channels=channels,
            chat_type="channel"
        )

        bot.send_message(
            user_id,
            f"📢 **قنواتك** ({len(channels)})\n\n"
            f"اختر القناة التي تريد أرشفتها 👇",
            reply_markup=chats_keyboard(
                channels, "channel", page=0
            ),
            parse_mode="Markdown"
        )

    # ==================== عرض المجموعات ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "show_groups"
    )
    def show_groups_callback(call: CallbackQuery):
        asyncio.run(_show_groups(bot, call))

    async def _show_groups(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not await require_login(bot, user_id):
            return

        wait_msg = bot.send_message(
            user_id,
            "⏳ جاري تحميل مجموعاتك..."
        )

        result = await telegram_service.get_dialogs(
            user_id
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if not result["success"]:
            bot.send_message(
                user_id,
                f"❌ خطأ: {result.get('message', '')}"
            )
            return

        groups = result.get("groups", [])

        if not groups:
            bot.send_message(
                user_id,
                "👥 لا توجد مجموعات",
                reply_markup=main_menu_keyboard(
                    is_logged_in=True
                )
            )
            return

        for chat in groups:
            await db.save_chat(
                owner_id      = user_id,
                chat_id       = chat["id"],
                chat_title    = chat["title"],
                chat_type     = "group",
                chat_username = chat.get("username"),
                members_count = chat.get(
                    "members_count", 0
                ),
            )

        set_state(
            user_id,
            STATE_IDLE,
            groups=groups,
            chat_type="group"
        )

        bot.send_message(
            user_id,
            f"👥 **مجموعاتك** ({len(groups)})\n\n"
            f"اختر المجموعة التي تريد أرشفتها 👇",
            reply_markup=chats_keyboard(
                groups, "group", page=0
            ),
            parse_mode="Markdown"
        )

    # ==================== عرض الكل ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "show_all_chats"
    )
    def show_all_chats_callback(call: CallbackQuery):
        asyncio.run(_show_all_chats(bot, call))

    async def _show_all_chats(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not await require_login(bot, user_id):
            return

        wait_msg = bot.send_message(
            user_id,
            "⏳ جاري تحميل كل محادثاتك..."
        )

        result = await telegram_service.get_dialogs(
            user_id
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if not result["success"]:
            bot.send_message(
                user_id,
                f"❌ خطأ: {result.get('message', '')}"
            )
            return

        all_chats = (
            result.get("channels", []) +
            result.get("groups", [])
        )

        if not all_chats:
            bot.send_message(
                user_id,
                "❌ لا توجد محادثات",
                reply_markup=main_menu_keyboard(
                    is_logged_in=True
                )
            )
            return

        set_state(
            user_id,
            STATE_IDLE,
            all_chats=all_chats,
            chat_type="all"
        )

        bot.send_message(
            user_id,
            f"📂 **كل محادثاتك** ({len(all_chats)})\n\n"
            f"اختر المحادثة 👇",
            reply_markup=chats_keyboard(
                all_chats, "all", page=0
            ),
            parse_mode="Markdown"
        )

    # ==================== Pagination ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("page_")
    )
    def page_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        parts     = call.data.split("_")
        chat_type = parts[1]
        page      = int(parts[2])

        chats_key = {
            "channel": "channels",
            "group":   "groups",
            "all":     "all_chats",
        }.get(chat_type, "all_chats")

        chats = get_user_data(user_id, chats_key) or []

        if not chats:
            bot.send_message(
                user_id,
                "❌ لا توجد بيانات\nابدأ من جديد"
            )
            return

        bot.send_message(
            user_id,
            f"📂 **المحادثات** ({len(chats)})\n\n"
            f"اختر المحادثة 👇",
            reply_markup=chats_keyboard(
                chats, chat_type, page=page
            ),
            parse_mode="Markdown"
        )

    # ==================== اختيار محادثة ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("select_chat_")
    )
    def select_chat_callback(call: CallbackQuery):
        asyncio.run(_select_chat(bot, call))

    async def _select_chat(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        parts     = call.data.split("_")
        chat_type = parts[2]
        index     = int(parts[3])

        chats_key = {
            "channel": "channels",
            "group":   "groups",
            "all":     "all_chats",
        }.get(chat_type, "all_chats")

        chats = get_user_data(user_id, chats_key) or []

        if index >= len(chats):
            bot.send_message(
                user_id,
                "❌ خطأ في الاختيار\nحاول مجدداً"
            )
            return

        selected = chats[index]

        # حفظ المحادثة المختارة
        set_state(
            user_id,
            STATE_IDLE,
            selected_chat=selected,
        )

        wait_msg = bot.send_message(
            user_id,
            "⏳ جاري جلب معلومات المحادثة..."
        )

        chat_info = await telegram_service.get_chat_info(
            user_id, selected["entity"]
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        icon = (
            "📢" if chat_type == "channel"
            else "👥"
        )

        if chat_info:
            total   = chat_info.get("total_messages", 0)
            members = chat_info.get("members_count", 0)
            desc    = chat_info.get("description", "")

            details = (
                f"{icon} **{selected['title']}**\n\n"
                f"👥 الأعضاء: `{format_number(members)}`\n"
                f"💬 الرسائل: `{format_number(total)}`\n"
            )

            if desc:
                details += (
                    f"📝 الوصف: `{desc[:100]}`\n"
                )

            if selected.get("username"):
                details += (
                    f"🔗 اليوزرنيم: "
                    f"`{selected['username']}`\n"
                )
        else:
            details = (
                f"{icon} **{selected['title']}**\n\n"
            )

        details += "\n📌 **اختر نوع المحتوى** 👇"

        bot.send_message(
            user_id,
            details,
            reply_markup=content_type_keyboard(),
            parse_mode="Markdown"
        )

        activity_logger.log(
            user_id,
            "SELECT_CHAT",
            f"chat={selected['title']}"
        )

    # ==================== البحث بـ Username ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "search_username"
    )
    def search_username_callback(call: CallbackQuery):
        asyncio.run(_search_username(bot, call))

    async def _search_username(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not await require_login(bot, user_id):
            return

        set_state(user_id, STATE_WAITING_USERNAME)

        bot.send_message(
            user_id,
            "🔍 **البحث عن قناة**\n\n"
            "أرسل يوزرنيم القناة أو المجموعة\n"
            "مثال: `@channel_name`",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )

    @bot.message_handler(
        func=lambda m: get_state(
            m.from_user.id
        ) == STATE_WAITING_USERNAME
    )
    def receive_username(message: Message):
        asyncio.run(_receive_username(bot, message))

    async def _receive_username(
            bot: telebot.TeleBot,
            message: Message):
        user_id  = message.from_user.id
        username = message.text.strip()

        if not username.startswith("@"):
            username = f"@{username}"

        wait_msg = bot.send_message(
            user_id,
            f"⏳ جاري البحث عن {username}..."
        )

        result = await telegram_service.get_entity_by_username(
            user_id, username
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if not result or not result.get("success"):
            bot.send_message(
                user_id,
                f"❌ لم يتم العثور على {username}\n\n"
                "تأكد من الـ username وحاول مجدداً",
                reply_markup=cancel_keyboard()
            )
            return

        set_state(
            user_id,
            STATE_IDLE,
            selected_chat=result,
        )

        icon = (
            "📢" if result.get("type") == "channel"
            else "👥"
        )

        bot.send_message(
            user_id,
            f"✅ **تم العثور على:**\n\n"
            f"{icon} **{result.get('title', '')}**\n"
            f"👥 الأعضاء: "
            f"`{format_number(result.get('members_count', 0))}`\n\n"
            f"📌 **اختر نوع المحتوى** 👇",
            reply_markup=content_type_keyboard(),
            parse_mode="Markdown"
        )

        clear_state(user_id)

    # ==================== أنواع المحادثات ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "show_chat_types"
    )
    def show_chat_types_callback(call: CallbackQuery):
        asyncio.run(_show_chat_types(bot, call))

    async def _show_chat_types(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not await require_login(bot, user_id):
            return

        bot.send_message(
            user_id,
            "📂 **اختر نوع المحادثة**\n\n"
            "من أي مكان تريد جلب المحتوى؟",
            reply_markup=chat_type_keyboard(),
            parse_mode="Markdown"
        )
