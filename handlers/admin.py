import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config import config
from utils.keyboards import (
    owner_panel_keyboard,
    admin_panel_keyboard,
    admins_list_keyboard,
    admin_manage_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
    confirm_keyboard,
    search_keyboard,
    settings_keyboard,
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


# ==================== حالات ====================

(
    WAITING_ADMIN_ID,
    WAITING_BROADCAST,
    WAITING_SEARCH,
) = range(3)


# ==================== /owner ====================

async def owner_panel_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    user_id = update.effective_user.id

    if not is_owner(user_id):
        await update.message.reply_text(
            "🚫 هذا الأمر للمالك فقط"
        )
        return

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
        reply_markup=owner_panel_keyboard(),
        parse_mode="Markdown"
    )

    activity_logger.log_admin_action(
        user_id, "OPEN_OWNER_PANEL"
    )


# ==================== /admin ====================

async def admin_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
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
            reply_markup=admin_panel_keyboard(),
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "🚫 ليس لديك صلاحية"
    )


# ==================== لوحة المالك ====================

async def owner_panel_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await query.message.reply_text(
            "🚫 هذا للمالك فقط"
        )
        return

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
        reply_markup=owner_panel_keyboard(),
        parse_mode="Markdown"
    )


# ==================== لوحة الأدمن ====================

async def admin_panel_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_owner(user_id):
        if not await db.is_admin(user_id):
            await query.message.reply_text(
                "🚫 ليس لديك صلاحية"
            )
            return

    stats = await db.get_stats()

    await query.message.reply_text(
        f"🤵 **لوحة تحكم الأدمن**\n\n"
        f"👥 المستخدمين:  "
        f"`{format_number(stats['total_users'] or 0)}`\n"
        f"📦 الأرشيفات:  "
        f"`{format_number(stats['total_archives'] or 0)}`\n",
        reply_markup=admin_panel_keyboard(),
        parse_mode="Markdown"
    )


# ==================== إدارة الأدمنية ====================

async def owner_admins_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await query.message.reply_text(
            "🚫 هذا للمالك فقط"
        )
        return

    admins      = await db.get_all_admins()
    admins_list = [dict(a) for a in admins]

    if not admins_list:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "➕ إضافة أدمن",
                callback_data="owner_add_admin"
            )],
            [InlineKeyboardButton(
                "🔙 رجوع",
                callback_data="owner_panel"
            )],
        ])
        await query.message.reply_text(
            "👥 **الأدمنية**\n\nلا يوجد أدمنية بعد",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    await query.message.reply_text(
        f"👥 **الأدمنية** ({len(admins_list)})\n\n"
        f"اختر أدمن لإدارته 👇",
        reply_markup=admins_list_keyboard(admins_list),
        parse_mode="Markdown"
    )


async def add_admin_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await query.message.reply_text(
            "🚫 هذا للمالك فقط"
        )
        return

    await query.message.reply_text(
        "➕ **إضافة أدمن جديد**\n\n"
        "أرسل ID المستخدم\n\n"
        "💡 احصل على ID من @userinfobot",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )
    return WAITING_ADMIN_ID


async def receive_admin_id(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    user_id = update.effective_user.id
    text    = update.message.text.strip()

    try:
        new_admin_id = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ ID غير صحيح\nأرسل رقم ID فقط",
            reply_markup=cancel_keyboard()
        )
        return WAITING_ADMIN_ID

    target_user = await db.get_user(new_admin_id)
    if not target_user:
        await update.message.reply_text(
            "❌ المستخدم غير موجود\n"
            "يجب أن يكون قد استخدم البوت أولاً",
            reply_markup=cancel_keyboard()
        )
        return WAITING_ADMIN_ID

    existing = await db.get_admin(new_admin_id)
    if existing and existing["is_active"]:
        await update.message.reply_text(
            "⚠️ هذا المستخدم أدمن بالفعل"
        )
        return ConversationHandler.END

    await db.add_admin(
        telegram_id = new_admin_id,
        username    = target_user["username"] or "",
        full_name   = target_user["full_name"] or "",
        added_by    = user_id,
    )

    try:
        await context.bot.send_message(
            chat_id    = new_admin_id,
            text       = (
                "🎉 **تم تعيينك أدمناً في البوت!**\n\n"
                "استخدم /admin للوصول للوحة التحكم"
            ),
            parse_mode = "Markdown"
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
        reply_markup=owner_panel_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def manage_admin_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db
    import json

    query    = update.callback_query
    await query.answer()
    user_id  = update.effective_user.id

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

    await query.message.reply_text(
        f"👤 **إدارة الأدمن**\n\n"
        f"الاسم: `{admin['full_name']}`\n"
        f"ID: `{admin['telegram_id']}`\n\n"
        f"**الصلاحيات:**\n{perm_text}",
        reply_markup=admin_manage_keyboard(admin_id),
        parse_mode="Markdown"
    )


async def remove_admin_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query    = update.callback_query
    await query.answer()
    user_id  = update.effective_user.id

    if not is_owner(user_id):
        await query.message.reply_text(
            "🚫 هذا للمالك فقط"
        )
        return

    admin_id = int(
        query.data.replace("owner_remove_admin_", "")
    )

    await db.remove_admin(admin_id)

    try:
        await context.bot.send_message(
            chat_id = admin_id,
            text    = "⚠️ تم إزالة صلاحياتك كأدمن"
        )
    except Exception:
        pass

    activity_logger.log_admin_action(
        user_id, "REMOVE_ADMIN", admin_id
    )

    await query.message.reply_text(
        "✅ تم إزالة الأدمن بنجاح",
        reply_markup=owner_panel_keyboard()
    )


# ==================== إدارة المستخدمين ====================

async def admin_users_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_owner(user_id):
        if not await check_permission(
            user_id, db, "can_view_users"
        ):
            await query.message.reply_text(
                "🚫 ليس لديك صلاحية"
            )
            return

    users = await db.get_all_users(limit=20)
    total = await db.count_users()

    if not users:
        await query.message.reply_text(
            "👥 لا يوجد مستخدمين"
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

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🔙 رجوع",
            callback_data="admin_panel"
        )],
    ])

    await query.message.reply_text(
        msg,
        reply_markup=markup,
        parse_mode="Markdown"
    )


async def ban_user_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query     = update.callback_query
    await query.answer()
    user_id   = update.effective_user.id
    target_id = int(
        query.data.replace("admin_ban_", "")
    )

    if not await check_permission(
        user_id, db, "can_ban_users"
    ):
        await query.message.reply_text(
            "🚫 ليس لديك صلاحية"
        )
        return

    await db.ban_user(target_id)

    try:
        await context.bot.send_message(
            chat_id = target_id,
            text    = "🚫 تم حظرك من استخدام البوت"
        )
    except Exception:
        pass

    activity_logger.log_admin_action(
        user_id, "BAN_USER", target_id
    )

    await query.message.reply_text(
        f"✅ تم حظر المستخدم `{target_id}`",
        reply_markup=admin_panel_keyboard(),
        parse_mode="Markdown"
    )


async def unban_user_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query     = update.callback_query
    await query.answer()
    user_id   = update.effective_user.id
    target_id = int(
        query.data.replace("admin_unban_", "")
    )

    await db.unban_user(target_id)

    try:
        await context.bot.send_message(
            chat_id = target_id,
            text    = "✅ تم رفع الحظر عنك"
        )
    except Exception:
        pass

    activity_logger.log_admin_action(
        user_id, "UNBAN_USER", target_id
    )

    await query.message.reply_text(
        f"✅ تم رفع حظر `{target_id}`",
        reply_markup=admin_panel_keyboard(),
        parse_mode="Markdown"
    )


# ==================== الإرسال للكل ====================

async def broadcast_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await query.message.reply_text(
            "🚫 هذا للمالك فقط"
        )
        return

    await query.message.reply_text(
        "📢 **إرسال رسالة للكل**\n\n"
        "أرسل الرسالة التي تريد إرسالها\n\n"
        "💡 يدعم Markdown",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )
    return WAITING_BROADCAST


async def receive_broadcast(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
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
                parse_mode = "Markdown"
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
        reply_markup=owner_panel_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ==================== السجلات ====================

async def view_logs_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    logs = await db.get_activity_log(limit=20)

    if not logs:
        await query.message.reply_text(
            "📋 لا توجد سجلات"
        )
        return

    msg = "📋 **آخر النشاطات**\n\n"

    for log in logs[:15]:
        msg += (
            f"👤 `{log['user_id']}` | "
            f"`{log['action']}` | "
            f"{time_ago(log['created_at'])}\n"
        )

    await query.message.reply_text(
        msg,
        reply_markup=admin_panel_keyboard(),
        parse_mode="Markdown"
    )


# ==================== إحصائيات البوت ====================

async def owner_stats_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    stats       = await db.get_stats()
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
        reply_markup=owner_panel_keyboard(),
        parse_mode="Markdown"
    )


# ==================== إعادة التشغيل ====================

async def restart_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await query.message.reply_text(
            "🚫 هذا للمالك فقط"
        )
        return

    await query.message.reply_text(
        "🔄 **إعادة التشغيل**\n\n"
        "هل تريد إعادة تشغيل البوت؟",
        reply_markup=confirm_keyboard("restart"),
        parse_mode="Markdown"
    )


async def confirm_restart_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_owner(user_id):
        return

    await query.message.reply_text(
        "🔄 جاري إعادة التشغيل..."
    )

    activity_logger.log_admin_action(
        user_id, "RESTART"
    )

    import os
    import sys
    os.execv(sys.executable, ["python"] + sys.argv)


# ==================== البحث ====================

async def search_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "🔍 **البحث**\n\n"
        "اختر نوع البحث 👇",
        reply_markup=search_keyboard(),
        parse_mode="Markdown"
    )


async def search_all_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "🔍 **بحث في كل القنوات**\n\n"
        "أرسل الكلمة التي تريد البحث عنها",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )
    return WAITING_SEARCH


async def receive_search(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db
    import aiofiles

    user_id = update.effective_user.id
    query   = update.message.text.strip()

    wait_msg = await update.message.reply_text(
        f"⏳ جاري البحث عن `{query}`...",
        parse_mode="Markdown"
    )

    results = await db.search_all_chats(
        owner_id=user_id,
        query=query,
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not results:
        await update.message.reply_text(
            f"❌ لم يتم العثور على نتائج لـ `{query}`",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            ),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # حفظ كـ TXT
    import os
    from config import config

    folder = os.path.join(
        config.DOWNLOAD_PATH, "txt", str(user_id)
    )
    os.makedirs(folder, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

    await update.message.reply_text(
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

    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            await update.message.reply_document(
                document = f,
                caption  = (
                    f"🔍 نتائج البحث عن: {query}\n"
                    f"📊 {len(results)} نتيجة"
                )
            )

    activity_logger.log_search(
        user_id, query, len(results)
    )

    return ConversationHandler.END


# ==================== الإعدادات ====================

async def settings_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    settings      = await db.get_settings(user_id)
    settings_dict = dict(settings) if settings else {}

    await query.message.reply_text(
        "⚙️ **الإعدادات**\n\n"
        "اضغط على أي إعداد لتفعيله أو إيقافه",
        reply_markup=settings_keyboard(settings_dict),
        parse_mode="Markdown"
    )


async def toggle_setting_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    user_id = update.effective_user.id
    setting = query.data.replace("setting_", "")

    current      = await db.get_settings(user_id)
    current_dict = dict(current) if current else {}

    current_value = current_dict.get(setting, True)
    new_value     = not current_value

    await db.update_settings(
        user_id, **{setting: new_value}
    )

    status = "✅ مفعل" if new_value else "❌ معطل"
    await query.answer(status, show_alert=False)

    updated      = await db.get_settings(user_id)
    updated_dict = dict(updated) if updated else {}

    try:
        await query.edit_message_reply_markup(
            reply_markup=settings_keyboard(updated_dict)
        )
    except Exception:
        pass


# ==================== تنظيف ====================

async def owner_cleanup_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await query.message.reply_text(
            "🚫 هذا للمالك فقط"
        )
        return

    await query.message.reply_text(
        "🗑️ **تنظيف البيانات**\n\n"
        "سيتم حذف الملفات الأقدم من 30 يوم",
        reply_markup=confirm_keyboard("cleanup"),
        parse_mode="Markdown"
    )


# ==================== ConversationHandler ====================

def get_admin_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                add_admin_callback,
                pattern="^owner_add_admin$"
            ),
            CallbackQueryHandler(
                broadcast_callback,
                pattern="^owner_broadcast$|^admin_broadcast$"
            ),
            CallbackQueryHandler(
                search_all_callback,
                pattern="^search_all$"
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
            WAITING_SEARCH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_search
                )
            ],
        },
        fallbacks=[
            CallbackQueryHandler(
                owner_panel_callback,
                pattern="^owner_panel$"
            ),
        ],
        allow_reentry=True,
    )


# ==================== تسجيل الهاندلرز ====================

def register_admin_handlers(app):

    app.add_handler(CommandHandler(
        "owner", owner_panel_command
    ))
    app.add_handler(CommandHandler(
        "admin", admin_command
    ))

    app.add_handler(get_admin_handler())

    app.add_handler(CallbackQueryHandler(
        owner_panel_callback,
        pattern="^owner_panel$"
    ))
    app.add_handler(CallbackQueryHandler(
        admin_panel_callback,
        pattern="^admin_panel$"
    ))
    app.add_handler(CallbackQueryHandler(
        owner_admins_callback,
        pattern="^owner_admins$"
    ))
    app.add_handler(CallbackQueryHandler(
        manage_admin_callback,
        pattern="^owner_admin_(?!stats_|edit_|remove_)"
    ))
    app.add_handler(CallbackQueryHandler(
        remove_admin_callback,
        pattern="^owner_remove_admin_"
    ))
    app.add_handler(CallbackQueryHandler(
        admin_users_callback,
        pattern="^admin_users$|^owner_users$"
    ))
    app.add_handler(CallbackQueryHandler(
        ban_user_callback,
        pattern="^admin_ban_"
    ))
    app.add_handler(CallbackQueryHandler(
        unban_user_callback,
        pattern="^admin_unban_"
    ))
    app.add_handler(CallbackQueryHandler(
        view_logs_callback,
        pattern="^admin_logs$|^owner_logs$"
    ))
    app.add_handler(CallbackQueryHandler(
        owner_stats_callback,
        pattern="^owner_stats$|^admin_stats$"
    ))
    app.add_handler(CallbackQueryHandler(
        restart_callback,
        pattern="^owner_restart$"
    ))
    app.add_handler(CallbackQueryHandler(
        confirm_restart_callback,
        pattern="^confirm_restart$"
    ))
    app.add_handler(CallbackQueryHandler(
        search_callback,
        pattern="^search$"
    ))
    app.add_handler(CallbackQueryHandler(
        settings_callback,
        pattern="^settings$"
    ))
    app.add_handler(CallbackQueryHandler(
        toggle_setting_callback,
        pattern="^setting_"
    ))
    app.add_handler(CallbackQueryHandler(
        owner_cleanup_callback,
        pattern="^owner_cleanup$"
    ))
