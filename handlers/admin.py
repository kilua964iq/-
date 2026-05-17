import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
from config import config
from utils.keyboards import (
    owner_panel_keyboard,
    admin_panel_keyboard,
    admin_user_keyboard,
    admins_list_keyboard,
    admin_manage_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
)
from utils.helpers import (
    is_owner,
    check_permission,
    format_number,
    format_size,
    format_date,
    time_ago,
)
from utils.logger import (
    bot_logger,
    activity_logger,
    error_logger,
)


# ==================== حالات المحادثة ====================

(
    WAITING_ADMIN_ID,
    WAITING_BROADCAST,
    WAITING_BAN_ID,
    WAITING_ADMIN_PERMISSIONS,
) = range(4)


# ==================== التحقق من الصلاحيات ====================

async def require_owner(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> bool:
    """التحقق من أن المستخدم هو المالك"""
    user_id = update.effective_user.id
    if not is_owner(user_id):
        msg = (
            update.callback_query.message
            if update.callback_query
            else update.message
        )
        await msg.reply_text(
            "🚫 هذا الأمر للمالك فقط"
        )
        return False
    return True


async def require_admin(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        permission: str = None) -> bool:
    """التحقق من أن المستخدم أدمن"""
    from database import db
    user_id = update.effective_user.id

    if is_owner(user_id):
        return True

    has_permission = await check_permission(
        user_id, db, permission
    )

    if not has_permission:
        msg = (
            update.callback_query.message
            if update.callback_query
            else update.message
        )
        await msg.reply_text(
            "🚫 ليس لديك صلاحية للقيام بهذا"
        )
        return False
    return True


# ==================== لوحة المالك ====================

async def owner_panel_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """أمر /owner"""
    if not await require_owner(update, context):
        return

    from database import db
    stats = await db.get_stats()

    await update.message.reply_text(
        f"👑 **لوحة تحكم المالك**\n\n"
        f"👥 المستخدمين:  "
        f"`{format_number(stats['total_users'] or 0)}`\n"
        f"📦 الأرشيفات:  "
        f"`{format_number(stats['total_archives'] or 0)}`\n"
        f"💬 الرسائل:    "
        f"`{format_number(stats['total_messages'] or 0)}`\n"
        f"💾 التخزين:    "
        f"`{format_size(stats['total_size'] or 0)}`\n",
        reply_markup = owner_panel_keyboard(),
        parse_mode   = "Markdown",
    )

    activity_logger.log_admin_action(
        update.effective_user.id,
        "OPEN_OWNER_PANEL"
    )


async def owner_panel_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """فتح لوحة المالك"""
    query = update.callback_query
    await query.answer()

    if not await require_owner(update, context):
        return

    from database import db
    stats = await db.get_stats()

    await query.message.reply_text(
        f"👑 **لوحة تحكم المالك**\n\n"
        f"👥 المستخدمين:  "
        f"`{format_number(stats['total_users'] or 0)}`\n"
        f"📦 الأرشيفات:  "
        f"`{format_number(stats['total_archives'] or 0)}`\n"
        f"💬 الرسائل:    "
        f"`{format_number(stats['total_messages'] or 0)}`\n"
        f"💾 التخزين:    "
        f"`{format_size(stats['total_size'] or 0)}`\n",
        reply_markup = owner_panel_keyboard(),
        parse_mode   = "Markdown",
    )


# ==================== لوحة الأدمن ====================

async def admin_panel_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """فتح لوحة الأدمن"""
    query = update.callback_query
    await query.answer()

    if not await require_admin(update, context):
        return

    from database import db
    stats = await db.get_stats()

    await query.message.reply_text(
        f"🤵 **لوحة تحكم الأدمن**\n\n"
        f"📊 إحصائيات البوت:\n"
        f"👥 المستخدمين:  "
        f"`{format_number(stats['total_users'] or 0)}`\n"
        f"📦 الأرشيفات:  "
        f"`{format_number(stats['total_archives'] or 0)}`\n"
        f"💬 الرسائل:    "
        f"`{format_number(stats['total_messages'] or 0)}`\n",
        reply_markup = admin_panel_keyboard(),
        parse_mode   = "Markdown",
    )


# ==================== إدارة الأدمنية ====================

async def owner_admins_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة الأدمنية"""
    query = update.callback_query
    await query.answer()

    if not await require_owner(update, context):
        return

    from database import db
    admins = await db.get_all_admins()
    admins_list = [dict(a) for a in admins]

    if not admins_list:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "➕ إضافة أدمن",
                callback_data = "owner_add_admin"
            )],
            [InlineKeyboardButton(
                "🔙 رجوع",
                callback_data = "owner_panel"
            )],
        ])
        await query.message.reply_text(
            "👥 **الأدمنية**\n\n"
            "لا يوجد أدمنية بعد",
            reply_markup = keyboard,
            parse_mode   = "Markdown",
        )
        return

    await query.message.reply_text(
        f"👥 **الأدمنية** ({len(admins_list)})\n\n"
        f"اختر أدمن لإدارته 👇",
        reply_markup = admins_list_keyboard(admins_list),
        parse_mode   = "Markdown",
    )


async def add_admin_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة أدمن"""
    query = update.callback_query
    await query.answer()

    if not await require_owner(update, context):
        return

    await query.message.reply_text(
        "➕ **إضافة أدمن جديد**\n\n"
        "أرسل ID المستخدم الذي تريد تعيينه أدمناً\n\n"
        "💡 يمكنك الحصول على ID من @userinfobot",
        reply_markup = cancel_keyboard(),
        parse_mode   = "Markdown",
    )
    return WAITING_ADMIN_ID


async def receive_admin_id(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """استقبال ID الأدمن الجديد"""
    from database import db

    user_id = update.effective_user.id
    text    = update.message.text.strip()

    try:
        new_admin_id = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ ID غير صحيح\n"
            "أرسل رقم ID فقط",
            reply_markup = cancel_keyboard(),
        )
        return WAITING_ADMIN_ID

    # التحقق من وجود المستخدم
    target_user = await db.get_user(new_admin_id)
    if not target_user:
        await update.message.reply_text(
            "❌ المستخدم غير موجود في قاعدة البيانات\n"
            "يجب أن يكون قد استخدم البوت أولاً",
            reply_markup = cancel_keyboard(),
        )
        return WAITING_ADMIN_ID

    # التحقق إذا كان أدمن مسبقاً
    existing_admin = await db.get_admin(new_admin_id)
    if existing_admin and existing_admin["is_active"]:
        await update.message.reply_text(
            "⚠️ هذا المستخدم أدمن بالفعل"
        )
        return ConversationHandler.END

    # إضافة الأدمن
    await db.add_admin(
        telegram_id = new_admin_id,
        username    = target_user["username"] or "",
        full_name   = target_user["full_name"] or "",
        added_by    = user_id,
    )

    # إشعار الأدمن الجديد
    try:
        await context.bot.send_message(
            chat_id = new_admin_id,
            text    = (
                "🎉 **تم تعيينك أدمناً في البوت!**\n\n"
                "استخدم /admin للوصول للوحة التحكم"
            ),
            parse_mode = "Markdown",
        )
    except Exception:
        pass

    activity_logger.log_admin_action(
        user_id, "ADD_ADMIN", new_admin_id
    )

    await update.message.reply_text(
        f"✅ **تم إضافة الأدمن بنجاح**\n\n"
        f"👤 الاسم: `{target_user['full_name']}`\n"
        f"🆔 ID: `{new_admin_id}`",
        reply_markup = owner_panel_keyboard(),
        parse_mode   = "Markdown",
    )
    return ConversationHandler.END


async def manage_admin_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """إدارة أدمن معين"""
    query    = update.callback_query
    await query.answer()

    if not await require_owner(update, context):
        return

    from database import db
    admin_id = int(
        query.data.replace("owner_admin_", "")
    )

    admin = await db.get_admin(admin_id)
    if not admin:
        await query.message.reply_text(
            "❌ الأدمن غير موجود"
        )
        return

    permissions = admin["permissions"] or {}
    if isinstance(permissions, str):
        import json
        permissions = json.loads(permissions)

    perm_text = ""
    perm_names = {
        "can_view_users":    "عرض المستخدمين",
        "can_ban_users":     "حظر المستخدمين",
        "can_view_archives": "عرض الأرشيفات",
        "can_delete_archives": "حذف الأرشيفات",
        "can_view_stats":    "عرض الإحصائيات",
    }

    for key, name in perm_names.items():
        icon = "✅" if permissions.get(key) else "❌"
        perm_text += f"{icon} {name}\n"

    await query.message.reply_text(
        f"👤 **إدارة الأدمن**\n\n"
        f"الاسم: `{admin['full_name']}`\n"
        f"ID: `{admin['telegram_id']}`\n\n"
        f"**الصلاحيات:**\n{perm_text}",
        reply_markup = admin_manage_keyboard(admin_id),
        parse_mode   = "Markdown",
    )


async def remove_admin_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """إزالة أدمن"""
    query    = update.callback_query
    await query.answer()

    if not await require_owner(update, context):
        return

    from database import db
    admin_id = int(
        query.data.replace("owner_remove_admin_", "")
    )

    await db.remove_admin(admin_id)

    # إشعار الأدمن المُزال
    try:
        await context.bot.send_message(
            chat_id = admin_id,
            text    = "⚠️ تم إزالة صلاحياتك كأدمن",
        )
    except Exception:
        pass

    activity_logger.log_admin_action(
        update.effective_user.id,
        "REMOVE_ADMIN",
        admin_id
    )

    await query.message.reply_text(
        "✅ تم إزالة الأدمن بنجاح",
        reply_markup = owner_panel_keyboard(),
    )


# ==================== إدارة المستخدمين ====================

async def admin_users_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المستخدمين"""
    query = update.callback_query
    await query.answer()

    if not await require_admin(
        update, context, "can_view_users"
    ):
        return

    from database import db
    users = await db.get_all_users(limit=20)
    total = await db.count_users()

    if not users:
        await query.message.reply_text(
            "👥 لا يوجد مستخدمين"
        )
        return

    msg = (
        f"👥 **المستخدمين** ({format_number(total)})\n\n"
    )

    for user in users[:10]:
        status = "🚫" if user["is_banned"] else "✅"
        name   = user["full_name"] or "بدون اسم"
        msg   += (
            f"{status} `{user['telegram_id']}` - "
            f"{name}\n"
        )

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔍 بحث عن مستخدم",
                callback_data = "admin_search_user"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 رجوع",
                callback_data = "admin_panel"
            ),
        ],
    ])

    await query.message.reply_text(
        msg,
        reply_markup = keyboard,
        parse_mode   = "Markdown",
    )


async def ban_user_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """حظر مستخدم"""
    query = update.callback_query
    await query.answer()

    if not await require_admin(
        update, context, "can_ban_users"
    ):
        return

    from database import db
    target_id = int(
        query.data.replace("admin_ban_", "")
    )

    await db.ban_user(target_id)

    # إشعار المستخدم
    try:
        await context.bot.send_message(
            chat_id = target_id,
            text    = "🚫 تم حظرك من استخدام البوت",
        )
    except Exception:
        pass

    activity_logger.log_admin_action(
        update.effective_user.id,
        "BAN_USER",
        target_id
    )

    await query.message.reply_text(
        f"✅ تم حظر المستخدم `{target_id}`",
        reply_markup = admin_panel_keyboard(),
        parse_mode   = "Markdown",
    )


async def unban_user_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """رفع حظر مستخدم"""
    query = update.callback_query
    await query.answer()

    if not await require_admin(
        update, context, "can_ban_users"
    ):
        return

    from database import db
    target_id = int(
        query.data.replace("admin_unban_", "")
    )

    await db.unban_user(target_id)

    # إشعار المستخدم
    try:
        await context.bot.send_message(
            chat_id = target_id,
            text    = "✅ تم رفع الحظر عنك",
        )
    except Exception:
        pass

    activity_logger.log_admin_action(
        update.effective_user.id,
        "UNBAN_USER",
        target_id
    )

    await query.message.reply_text(
        f"✅ تم رفع حظر المستخدم `{target_id}`",
        reply_markup = admin_panel_keyboard(),
        parse_mode   = "Markdown",
    )


# ==================== الإرسال للكل ====================

async def broadcast_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """بدء الإرسال للكل"""
    query = update.callback_query
    await query.answer()

    if not await require_owner(update, context):
        return

    await query.message.reply_text(
        "📢 **إرسال رسالة للكل**\n\n"
        "أرسل الرسالة التي تريد إرسالها لكل المستخدمين\n\n"
        "💡 يدعم Markdown",
        reply_markup = cancel_keyboard(),
        parse_mode   = "Markdown",
    )
    return WAITING_BROADCAST


async def receive_broadcast(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """استقبال رسالة البث"""
    from database import db

    user_id      = update.effective_user.id
    message_text = update.message.text

    users = await db.get_all_users(limit=9999)

    wait_msg = await update.message.reply_text(
        f"⏳ جاري الإرسال لـ {len(users)} مستخدم..."
    )

    sent   = 0
    failed = 0

    for user in users:
        try:
            await context.bot.send_message(
                chat_id    = user["telegram_id"],
                text       = (
                    f"📢 **رسالة من الإدارة**\n\n"
                    f"{message_text}"
                ),
                parse_mode = "Markdown",
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    try:
        await wait_msg.delete()
    except Exception:
        pass

    activity_logger.log_admin_action(
        user_id, "BROADCAST"
    )

    await update.message.reply_text(
        f"✅ **اكتمل الإرسال**\n\n"
        f"✅ تم الإرسال: `{sent}`\n"
        f"❌ فشل:        `{failed}`",
        reply_markup = owner_panel_keyboard(),
        parse_mode   = "Markdown",
    )
    return ConversationHandler.END


# ==================== السجلات ====================

async def view_logs_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """عرض سجل النشاط"""
    query = update.callback_query
    await query.answer()

    if not await require_admin(update, context):
        return

    from database import db
    logs = await db.get_activity_log(limit=20)

    if not logs:
        await query.message.reply_text(
            "📋 لا توجد سجلات"
        )
        return

    msg = "📋 **آخر النشاطات**\n\n"

    for log in logs[:15]:
        time_str = time_ago(log["created_at"])
        msg     += (
            f"👤 `{log['user_id']}` | "
            f"`{log['action']}` | "
            f"{time_str}\n"
        )

    await query.message.reply_text(
        msg,
        reply_markup = admin_panel_keyboard(),
        parse_mode   = "Markdown",
    )


# ==================== إحصائيات البوت ====================

async def owner_stats_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات كاملة للبوت"""
    query = update.callback_query
    await query.answer()

    if not await require_owner(update, context):
        return

    from database import db
    stats = await db.get_stats()

    from services.queue_service import queue_service
    queue_stats = queue_service.get_queue_stats()

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

    await query.message.reply_text(
        msg,
        reply_markup = owner_panel_keyboard(),
        parse_mode   = "Markdown",
    )


# ==================== إعادة التشغيل ====================

async def restart_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """إعادة تشغيل البوت"""
    query = update.callback_query
    await query.answer()

    if not await require_owner(update, context):
        return

    await query.message.reply_text(
        "🔄 **إعادة التشغيل**\n\n"
        "هل تريد إعادة تشغيل البوت؟",
        reply_markup = __import__(
            "utils.keyboards",
            fromlist=["confirm_keyboard"]
        ).confirm_keyboard("restart"),
        parse_mode = "Markdown",
    )


async def confirm_restart_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """تأكيد إعادة التشغيل"""
    query = update.callback_query
    await query.answer()

    if not await require_owner(update, context):
        return

    await query.message.reply_text(
        "🔄 جاري إعادة التشغيل..."
    )

    activity_logger.log_admin_action(
        update.effective_user.id, "RESTART"
    )

    import os
    import sys
    os.execv(sys.executable, ["python"] + sys.argv)


# ==================== /admin ====================

async def admin_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """أمر /admin"""
    from database import db

    user_id = update.effective_user.id

    if is_owner(user_id):
        await owner_panel_command(update, context)
        return

    if await db.is_admin(user_id):
        stats = await db.get_stats()
        await update.message.reply_text(
            f"🤵 **لوحة تحكم الأدمن**\n\n"
            f"👥 المستخدمين: "
            f"`{format_number(stats['total_users'] or 0)}`\n"
            f"📦 الأرشيفات: "
            f"`{format_number(stats['total_archives'] or 0)}`\n",
            reply_markup = admin_panel_keyboard(),
            parse_mode   = "Markdown",
        )
        return

    await update.message.reply_text(
        "🚫 ليس لديك صلاحية"
    )


# ==================== ConversationHandler ====================

def get_admin_handler() -> ConversationHandler:
    """إنشاء ConversationHandler للأدمن"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                add_admin_callback,
                pattern = "^owner_add_admin$"
            ),
            CallbackQueryHandler(
                broadcast_callback,
                pattern = "^owner_broadcast$|^admin_broadcast$"
            ),
        ],
        states={
            WAITING_ADMIN_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_admin_id
                )
            ],
            WAITING_BROADCAST: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_broadcast
                )
            ],
        },
        fallbacks=[
            CallbackQueryHandler(
                owner_panel_callback,
                pattern = "^owner_panel$"
            ),
        ],
        allow_reentry = True,
    )


# ==================== تسجيل الهاندلرز ====================

def register_admin_handlers(app):
    """تسجيل كل هاندلرز الأدمن"""

    app.add_handler(CommandHandler(
        "owner", owner_panel_command
    ))
    app.add_handler(CommandHandler(
        "admin", admin_command
    ))

    app.add_handler(get_admin_handler())

    app.add_handler(CallbackQueryHandler(
        owner_panel_callback,
        pattern = "^owner_panel$"
    ))
    app.add_handler(CallbackQueryHandler(
        admin_panel_callback,
        pattern = "^admin_panel$"
    ))
    app.add_handler(CallbackQueryHandler(
        owner_admins_callback,
        pattern = "^owner_admins$"
    ))
    app.add_handler(CallbackQueryHandler(
        manage_admin_callback,
        pattern = "^owner_admin_"
    ))
    app.add_handler(CallbackQueryHandler(
        remove_admin_callback,
        pattern = "^owner_remove_admin_"
    ))
    app.add_handler(CallbackQueryHandler(
        admin_users_callback,
        pattern = "^admin_users$|^owner_users$"
    ))
    app.add_handler(CallbackQueryHandler(
        ban_user_callback,
        pattern = "^admin_ban_"
    ))
    app.add_handler(CallbackQueryHandler(
        unban_user_callback,
        pattern = "^admin_unban_"
    ))
    app.add_handler(CallbackQueryHandler(
        view_logs_callback,
        pattern = "^admin_logs$|^owner_logs$"
    ))
    app.add_handler(CallbackQueryHandler(
        owner_stats_callback,
        pattern = "^owner_stats$|^admin_stats$"
    ))
    app.add_handler(CallbackQueryHandler(
        restart_callback,
        pattern = "^owner_restart$"
    ))
    app.add_handler(CallbackQueryHandler(
        confirm_restart_callback,
        pattern = "^confirm_restart$"
    ))
