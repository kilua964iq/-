import asyncio
import telebot
from telebot.types import Message, CallbackQuery
from config import config
from utils.keyboards import (
    owner_panel_keyboard,
    admin_panel_keyboard,
    admins_list_keyboard,
    admin_manage_keyboard,
    admin_user_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
)
from utils.helpers import (
    is_owner,
    check_permission,
    format_number,
    format_size,
    time_ago,
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

STATE_WAITING_ADMIN_ID   = "waiting_admin_id"
STATE_WAITING_BROADCAST  = "waiting_broadcast"
STATE_WAITING_BAN_ID     = "waiting_ban_id"


# ==================== تسجيل الهاندلرز ====================

def register_admin_handlers(bot: telebot.TeleBot):
    """تسجيل كل هاندلرز الأدمن"""

    # ==================== /owner ====================

    @bot.message_handler(commands=["owner"])
    def owner_command(message: Message):
        asyncio.run(_owner_command(bot, message))

    async def _owner_command(
            bot: telebot.TeleBot,
            message: Message):
        from database import db

        user_id = message.from_user.id

        if not is_owner(user_id):
            bot.send_message(
                user_id,
                "🚫 هذا الأمر للمالك فقط"
            )
            return

        stats = await db.get_stats()

        bot.send_message(
            user_id,
            f"👑 **لوحة تحكم المالك**\n\n"
            f"👥 المستخدمين:  "
            f"`{format_number(stats['total_users'] or 0)}`\n"
            f"📦 الأرشيفات:  "
            f"`{format_number(stats['total_archives'] or 0)}`\n"
            f"💬 الرسائل:    "
            f"`{format_number(stats['total_messages'] or 0)}`\n"
            f"💾 التخزين:    "
            f"`{format_size(stats['total_size'] or 0)}`\n",
            reply_markup=owner_panel_keyboard(),
            parse_mode="Markdown"
        )

        activity_logger.log_admin_action(
            user_id, "OPEN_OWNER_PANEL"
        )

    # ==================== /admin ====================

    @bot.message_handler(commands=["admin"])
    def admin_command(message: Message):
        asyncio.run(_admin_command(bot, message))

    async def _admin_command(
            bot: telebot.TeleBot,
            message: Message):
        from database import db

        user_id = message.from_user.id

        if is_owner(user_id):
            await _owner_command(bot, message)
            return

        if await db.is_admin(user_id):
            stats = await db.get_stats()
            bot.send_message(
                user_id,
                f"🤵 **لوحة تحكم الأدمن**\n\n"
                f"👥 المستخدمين: "
                f"`{format_number(stats['total_users'] or 0)}`\n"
                f"📦 الأرشيفات: "
                f"`{format_number(stats['total_archives'] or 0)}`\n",
                reply_markup=admin_panel_keyboard(),
                parse_mode="Markdown"
            )
            return

        bot.send_message(
            user_id, "🚫 ليس لديك صلاحية"
        )

    # ==================== لوحة المالك ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "owner_panel"
    )
    def owner_panel_callback(call: CallbackQuery):
        asyncio.run(_owner_panel(bot, call))

    async def _owner_panel(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            bot.send_message(
                user_id, "🚫 هذا للمالك فقط"
            )
            return

        stats = await db.get_stats()

        bot.send_message(
            user_id,
            f"👑 **لوحة تحكم المالك**\n\n"
            f"👥 المستخدمين:  "
            f"`{format_number(stats['total_users'] or 0)}`\n"
            f"📦 الأرشيفات:  "
            f"`{format_number(stats['total_archives'] or 0)}`\n"
            f"💬 الرسائل:    "
            f"`{format_number(stats['total_messages'] or 0)}`\n"
            f"💾 التخزين:    "
            f"`{format_size(stats['total_size'] or 0)}`\n",
            reply_markup=owner_panel_keyboard(),
            parse_mode="Markdown"
        )

    # ==================== لوحة الأدمن ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "admin_panel"
    )
    def admin_panel_callback(call: CallbackQuery):
        asyncio.run(_admin_panel(bot, call))

    async def _admin_panel(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            if not await db.is_admin(user_id):
                bot.send_message(
                    user_id, "🚫 ليس لديك صلاحية"
                )
                return

        stats = await db.get_stats()

        bot.send_message(
            user_id,
            f"🤵 **لوحة تحكم الأدمن**\n\n"
            f"👥 المستخدمين:  "
            f"`{format_number(stats['total_users'] or 0)}`\n"
            f"📦 الأرشيفات:  "
            f"`{format_number(stats['total_archives'] or 0)}`\n"
            f"💬 الرسائل:    "
            f"`{format_number(stats['total_messages'] or 0)}`\n",
            reply_markup=admin_panel_keyboard(),
            parse_mode="Markdown"
        )

    # ==================== إدارة الأدمنية ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "owner_admins"
    )
    def owner_admins_callback(call: CallbackQuery):
        asyncio.run(_owner_admins(bot, call))

    async def _owner_admins(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            bot.send_message(
                user_id, "🚫 هذا للمالك فقط"
            )
            return

        admins      = await db.get_all_admins()
        admins_list = [dict(a) for a in admins]

        if not admins_list:
            from telebot.types import (
                InlineKeyboardMarkup,
                InlineKeyboardButton,
            )
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton(
                "➕ إضافة أدمن",
                callback_data="owner_add_admin"
            ))
            markup.row(InlineKeyboardButton(
                "🔙 رجوع",
                callback_data="owner_panel"
            ))

            bot.send_message(
                user_id,
                "👥 **الأدمنية**\n\nلا يوجد أدمنية بعد",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return

        bot.send_message(
            user_id,
            f"👥 **الأدمنية** ({len(admins_list)})\n\n"
            f"اختر أدمن لإدارته 👇",
            reply_markup=admins_list_keyboard(admins_list),
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(
        func=lambda c: c.data == "owner_add_admin"
    )
    def add_admin_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            bot.send_message(
                user_id, "🚫 هذا للمالك فقط"
            )
            return

        set_state(user_id, STATE_WAITING_ADMIN_ID)

        bot.send_message(
            user_id,
            "➕ **إضافة أدمن جديد**\n\n"
            "أرسل ID المستخدم\n\n"
            "💡 احصل على ID من @userinfobot",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )

    @bot.message_handler(
        func=lambda m: get_state(
            m.from_user.id
        ) == STATE_WAITING_ADMIN_ID
    )
    def receive_admin_id(message: Message):
        asyncio.run(_receive_admin_id(bot, message))

    async def _receive_admin_id(
            bot: telebot.TeleBot,
            message: Message):
        from database import db

        user_id = message.from_user.id
        text    = message.text.strip()

        try:
            new_admin_id = int(text)
        except ValueError:
            bot.send_message(
                user_id,
                "❌ ID غير صحيح\nأرسل رقم ID فقط",
                reply_markup=cancel_keyboard()
            )
            return

        target_user = await db.get_user(new_admin_id)
        if not target_user:
            bot.send_message(
                user_id,
                "❌ المستخدم غير موجود\n"
                "يجب أن يكون قد استخدم البوت أولاً",
                reply_markup=cancel_keyboard()
            )
            return

        existing = await db.get_admin(new_admin_id)
        if existing and existing["is_active"]:
            bot.send_message(
                user_id,
                "⚠️ هذا المستخدم أدمن بالفعل"
            )
            clear_state(user_id)
            return

        await db.add_admin(
            telegram_id = new_admin_id,
            username    = target_user["username"] or "",
            full_name   = target_user["full_name"] or "",
            added_by    = user_id,
        )

        try:
            bot.send_message(
                new_admin_id,
                "🎉 **تم تعيينك أدمناً في البوت!**\n\n"
                "استخدم /admin للوصول للوحة التحكم",
                parse_mode="Markdown"
            )
        except Exception:
            pass

        activity_logger.log_admin_action(
            user_id, "ADD_ADMIN", new_admin_id
        )

        clear_state(user_id)

        bot.send_message(
            user_id,
            f"✅ **تم إضافة الأدمن بنجاح**\n\n"
            f"👤 الاسم: `{target_user['full_name']}`\n"
            f"🆔 ID: `{new_admin_id}`",
            reply_markup=owner_panel_keyboard(),
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("owner_admin_")
        and not c.data.startswith("owner_admin_stats_")
        and not c.data.startswith("owner_edit_admin_")
        and not c.data.startswith("owner_remove_admin_")
    )
    def manage_admin_callback(call: CallbackQuery):
        asyncio.run(_manage_admin(bot, call))

    async def _manage_admin(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db
        import json

        user_id  = call.from_user.id
        bot.answer_callback_query(call.id)

        admin_id = int(
            call.data.replace("owner_admin_", "")
        )

        admin = await db.get_admin(admin_id)
        if not admin:
            bot.send_message(
                user_id, "❌ الأدمن غير موجود"
            )
            return

        permissions = admin["permissions"] or {}
        if isinstance(permissions, str):
            permissions = json.loads(permissions)

        perm_names = {
            "can_view_users":      "عرض المستخدمين",
            "can_ban_users":       "حظر المستخدمين",
            "can_view_archives":   "عرض الأرشيفات",
            "can_delete_archives": "حذف الأرشيفات",
            "can_view_stats":      "عرض الإحصائيات",
        }

        perm_text = ""
        for key, name in perm_names.items():
            icon = "✅" if permissions.get(key) else "❌"
            perm_text += f"{icon} {name}\n"

        bot.send_message(
            user_id,
            f"👤 **إدارة الأدمن**\n\n"
            f"الاسم: `{admin['full_name']}`\n"
            f"ID: `{admin['telegram_id']}`\n\n"
            f"**الصلاحيات:**\n{perm_text}",
            reply_markup=admin_manage_keyboard(admin_id),
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith(
            "owner_remove_admin_"
        )
    )
    def remove_admin_callback(call: CallbackQuery):
        asyncio.run(_remove_admin(bot, call))

    async def _remove_admin(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id  = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            bot.send_message(
                user_id, "🚫 هذا للمالك فقط"
            )
            return

        admin_id = int(
            call.data.replace("owner_remove_admin_", "")
        )

        await db.remove_admin(admin_id)

        try:
            bot.send_message(
                admin_id,
                "⚠️ تم إزالة صلاحياتك كأدمن"
            )
        except Exception:
            pass

        activity_logger.log_admin_action(
            user_id, "REMOVE_ADMIN", admin_id
        )

        bot.send_message(
            user_id,
            "✅ تم إزالة الأدمن بنجاح",
            reply_markup=owner_panel_keyboard()
        )

    # ==================== إدارة المستخدمين ====================

    @bot.callback_query_handler(
        func=lambda c: c.data in [
            "admin_users", "owner_users"
        ]
    )
    def admin_users_callback(call: CallbackQuery):
        asyncio.run(_admin_users(bot, call))

    async def _admin_users(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            if not await check_permission(
                user_id, db, "can_view_users"
            ):
                bot.send_message(
                    user_id, "🚫 ليس لديك صلاحية"
                )
                return

        users = await db.get_all_users(limit=20)
        total = await db.count_users()

        if not users:
            bot.send_message(
                user_id, "👥 لا يوجد مستخدمين"
            )
            return

        msg = (
            f"👥 **المستخدمين** "
            f"({format_number(total)})\n\n"
        )

        for user in users[:10]:
            status = "🚫" if user["is_banned"] else "✅"
            name   = user["full_name"] or "بدون اسم"
            msg   += (
                f"{status} `{user['telegram_id']}` - "
                f"{name}\n"
            )

        from telebot.types import (
            InlineKeyboardMarkup,
            InlineKeyboardButton,
        )
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(
            "🔙 رجوع",
            callback_data="admin_panel"
        ))

        bot.send_message(
            user_id,
            msg,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("admin_ban_")
    )
    def ban_user_callback(call: CallbackQuery):
        asyncio.run(_ban_user(bot, call))

    async def _ban_user(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id   = call.from_user.id
        bot.answer_callback_query(call.id)

        if not await check_permission(
            user_id, db, "can_ban_users"
        ):
            bot.send_message(
                user_id, "🚫 ليس لديك صلاحية"
            )
            return

        target_id = int(
            call.data.replace("admin_ban_", "")
        )

        await db.ban_user(target_id)

        try:
            bot.send_message(
                target_id,
                "🚫 تم حظرك من استخدام البوت"
            )
        except Exception:
            pass

        activity_logger.log_admin_action(
            user_id, "BAN_USER", target_id
        )

        bot.send_message(
            user_id,
            f"✅ تم حظر المستخدم `{target_id}`",
            reply_markup=admin_panel_keyboard(),
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("admin_unban_")
    )
    def unban_user_callback(call: CallbackQuery):
        asyncio.run(_unban_user(bot, call))

    async def _unban_user(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id   = call.from_user.id
        bot.answer_callback_query(call.id)

        target_id = int(
            call.data.replace("admin_unban_", "")
        )

        await db.unban_user(target_id)

        try:
            bot.send_message(
                target_id,
                "✅ تم رفع الحظر عنك"
            )
        except Exception:
            pass

        activity_logger.log_admin_action(
            user_id, "UNBAN_USER", target_id
        )

        bot.send_message(
            user_id,
            f"✅ تم رفع حظر `{target_id}`",
            reply_markup=admin_panel_keyboard(),
            parse_mode="Markdown"
        )

    # ==================== الإرسال للكل ====================

    @bot.callback_query_handler(
        func=lambda c: c.data in [
            "owner_broadcast", "admin_broadcast"
        ]
    )
    def broadcast_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            bot.send_message(
                user_id, "🚫 هذا للمالك فقط"
            )
            return

        set_state(user_id, STATE_WAITING_BROADCAST)

        bot.send_message(
            user_id,
            "📢 **إرسال رسالة للكل**\n\n"
            "أرسل الرسالة التي تريد إرسالها\n\n"
            "💡 يدعم Markdown",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )

    @bot.message_handler(
        func=lambda m: get_state(
            m.from_user.id
        ) == STATE_WAITING_BROADCAST
    )
    def receive_broadcast(message: Message):
        asyncio.run(_receive_broadcast(bot, message))

    async def _receive_broadcast(
            bot: telebot.TeleBot,
            message: Message):
        from database import db

        user_id      = message.from_user.id
        message_text = message.text

        users = await db.get_all_users(limit=9999)

        wait_msg = bot.send_message(
            user_id,
            f"⏳ جاري الإرسال لـ {len(users)} مستخدم..."
        )

        sent   = 0
        failed = 0

        for user in users:
            try:
                bot.send_message(
                    user["telegram_id"],
                    f"📢 **رسالة من الإدارة**\n\n"
                    f"{message_text}",
                    parse_mode="Markdown"
                )
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        clear_state(user_id)

        activity_logger.log_admin_action(
            user_id, "BROADCAST"
        )

        bot.send_message(
            user_id,
            f"✅ **اكتمل الإرسال**\n\n"
            f"✅ تم الإرسال: `{sent}`\n"
            f"❌ فشل:        `{failed}`",
            reply_markup=owner_panel_keyboard(),
            parse_mode="Markdown"
        )

    # ==================== السجلات ====================

    @bot.callback_query_handler(
        func=lambda c: c.data in [
            "admin_logs", "owner_logs"
        ]
    )
    def view_logs_callback(call: CallbackQuery):
        asyncio.run(_view_logs(bot, call))

    async def _view_logs(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        logs = await db.get_activity_log(limit=20)

        if not logs:
            bot.send_message(
                user_id, "📋 لا توجد سجلات"
            )
            return

        msg = "📋 **آخر النشاطات**\n\n"

        for log in logs[:15]:
            msg += (
                f"👤 `{log['user_id']}` | "
                f"`{log['action']}` | "
                f"{time_ago(log['created_at'])}\n"
            )

        bot.send_message(
            user_id,
            msg,
            reply_markup=admin_panel_keyboard(),
            parse_mode="Markdown"
        )

    # ==================== إحصائيات البوت ====================

    @bot.callback_query_handler(
        func=lambda c: c.data in [
            "owner_stats", "admin_stats"
        ]
    )
    def owner_stats_callback(call: CallbackQuery):
        asyncio.run(_owner_stats(bot, call))

    async def _owner_stats(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        stats       = await db.get_stats()
        queue_stats = __import__(
            "services.queue_service",
            fromlist=["queue_service"]
        ).queue_service.get_queue_stats()

        msg = (
            f"📊 **إحصائيات البوت الكاملة**\n\n"
            f"👥 المستخدمين:    "
            f"`{format_number(stats['total_users'] or 0)}`\n"
            f"📦 الأرشيفات:    "
            f"`{format_number(stats['total_archives'] or 0)}`\n"
            f"💬 الرسائل:      "
            f"`{format_number(stats['total_messages'] or 0)}`\n"
            f"💾 التخزين:      "
            f"`{format_size(stats['total_size'] or 0)}`\n\n"
            f"**الطابور:**\n"
            f"⏳ منتظرة:  `{queue_stats['pending']}`\n"
            f"🔄 جارية:   `{queue_stats['running']}`\n"
            f"✅ مكتملة:  `{queue_stats['completed']}`\n"
            f"❌ فاشلة:   `{queue_stats['failed']}`\n"
            f"👷 العمال:  `{queue_stats['workers']}`\n"
        )

        bot.send_message(
            user_id,
            msg,
            reply_markup=owner_panel_keyboard(),
            parse_mode="Markdown"
        )

    # ==================== إعادة التشغيل ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "owner_restart"
    )
    def restart_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            bot.send_message(
                user_id, "🚫 هذا للمالك فقط"
            )
            return

        from utils.keyboards import confirm_keyboard
        bot.send_message(
            user_id,
            "🔄 **إعادة التشغيل**\n\n"
            "هل تريد إعادة تشغيل البوت؟",
            reply_markup=confirm_keyboard("restart"),
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(
        func=lambda c: c.data == "confirm_restart"
    )
    def confirm_restart_callback(call: CallbackQuery):
        asyncio.run(_confirm_restart(bot, call))

    async def _confirm_restart(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            return

        bot.send_message(
            user_id,
            "🔄 جاري إعادة التشغيل..."
        )

        activity_logger.log_admin_action(
            user_id, "RESTART"
        )

        import os
        import sys
        os.execv(sys.executable, ["python"] + sys.argv)

    # ==================== البحث ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "search"
    )
    def search_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        from utils.keyboards import search_keyboard
        bot.send_message(
            user_id,
            "🔍 **البحث**\n\n"
            "اختر نوع البحث 👇",
            reply_markup=search_keyboard(),
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(
        func=lambda c: c.data == "search_all"
    )
    def search_all_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        from handlers.auth import STATE_IDLE
        set_state(user_id, "waiting_search")

        bot.send_message(
            user_id,
            "🔍 **بحث في كل القنوات**\n\n"
            "أرسل الكلمة التي تريد البحث عنها",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )

    @bot.message_handler(
        func=lambda m: get_state(
            m.from_user.id
        ) == "waiting_search"
    )
    def receive_search(message: Message):
        asyncio.run(_receive_search(bot, message))

    async def _receive_search(
            bot: telebot.TeleBot,
            message: Message):
        from database import db

        user_id = message.from_user.id
        query   = message.text.strip()

        clear_state(user_id)

        wait_msg = bot.send_message(
            user_id,
            f"⏳ جاري البحث عن `{query}`...",
            parse_mode="Markdown"
        )

        results = await db.search_all_chats(
            owner_id=user_id,
            query=query,
        )

        ## تكملة `handlers/admin.py`

```python
        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if not results:
            bot.send_message(
                user_id,
                f"❌ لم يتم العثور على نتائج لـ `{query}`",
                reply_markup=main_menu_keyboard(
                    is_logged_in=True
                ),
                parse_mode="Markdown"
            )
            return

        # حفظ النتائج كـ TXT
        import os
        import aiofiles
        from config import config

        folder = os.path.join(
            config.DOWNLOAD_PATH,
            "txt",
            str(user_id)
        )
        os.makedirs(folder, exist_ok=True)

        timestamp = __import__(
            "datetime"
        ).datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"search_{query}_{timestamp}.txt"
        file_path = os.path.join(folder, file_name)

        content = (
            f"{'=' * 50}\n"
            f"نتائج البحث عن: {query}\n"
            f"عدد النتائج: {len(results)}\n"
            f"{'=' * 50}\n\n"
        )

        for i, result in enumerate(results, 1):
            chat_title = result.get("chat_title", "")
            text       = result.get("text", "") or ""
            date       = result.get("date", "")

            content += (
                f"[{i}] 📢 {chat_title}\n"
                f"📅 {date}\n"
                f"{text[:500]}\n"
                f"{'─' * 40}\n"
            )

        async with aiofiles.open(
            file_path, "w", encoding="utf-8"
        ) as f:
            await f.write(content)

        # إرسال النتائج
        bot.send_message(
            user_id,
            f"✅ **نتائج البحث عن:** `{query}`\n\n"
            f"📊 عدد النتائج: `{len(results)}`\n\n"
            f"**أول 5 نتائج:**\n\n" +
            "\n".join([
                f"📢 `{r.get('chat_title', '')}` - "
                f"{(r.get('text', '') or '')[:100]}..."
                for r in results[:5]
            ]),
            parse_mode="Markdown"
        )

        # إرسال ملف TXT
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                bot.send_document(
                    user_id,
                    f,
                    caption=(
                        f"🔍 نتائج البحث عن: {query}\n"
                        f"📊 {len(results)} نتيجة"
                    )
                )

        activity_logger.log_search(
            user_id, query, len(results)
        )

    # ==================== الإعدادات ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "settings"
    )
    def settings_callback(call: CallbackQuery):
        asyncio.run(_settings(bot, call))

    async def _settings(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db
        from utils.keyboards import settings_keyboard

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        settings = await db.get_settings(user_id)
        settings_dict = dict(settings) if settings else {}

        bot.send_message(
            user_id,
            "⚙️ **الإعدادات**\n\n"
            "اضغط على أي إعداد لتفعيله أو إيقافه",
            reply_markup=settings_keyboard(settings_dict),
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("setting_")
    )
    def toggle_setting_callback(call: CallbackQuery):
        asyncio.run(_toggle_setting(bot, call))

    async def _toggle_setting(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db
        from utils.keyboards import settings_keyboard

        user_id = call.from_user.id

        setting = call.data.replace("setting_", "")

        current = await db.get_settings(user_id)
        current_dict = (
            dict(current) if current else {}
        )

        # تبديل الإعداد
        current_value = current_dict.get(setting, True)
        new_value     = not current_value

        await db.update_settings(
            user_id,
            **{setting: new_value}
        )

        status = "✅ مفعل" if new_value else "❌ معطل"
        bot.answer_callback_query(
            call.id,
            f"{status}",
            show_alert=False
        )

        # تحديث الأزرار
        updated = await db.get_settings(user_id)
        updated_dict = (
            dict(updated) if updated else {}
        )

        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=settings_keyboard(
                    updated_dict
                )
            )
        except Exception:
            pass

    # ==================== تنظيف ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "owner_cleanup"
    )
    def owner_cleanup_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        if not is_owner(user_id):
            bot.send_message(
                user_id, "🚫 هذا للمالك فقط"
            )
            return

        from utils.keyboards import confirm_keyboard
        bot.send_message(
            user_id,
            "🗑️ **تنظيف البيانات**\n\n"
            "سيتم حذف الملفات الأقدم من 30 يوم",
            reply_markup=confirm_keyboard("cleanup"),
            parse_mode="Markdown"
        )
