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
    chats_keyboard,
    chat_type_keyboard,
    content_type_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
)
from utils.helpers import (
    format_number,
    get_chat_type,
    extract_username,
    get_members_count,
)
from utils.logger import (
    bot_logger,
    activity_logger,
    error_logger,
)


# ==================== حالات ====================

WAITING_USERNAME = range(1)


# ==================== دوال مساعدة ====================

async def require_login(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    is_authorized = await telegram_service.manager.is_authorized(
        user_id
    )

    if not is_authorized:
        msg = (
            update.callback_query.message
            if update.callback_query
            else update.message
        )
        await msg.reply_text(
            "❌ يجب تسجيل الدخول أولاً\n"
            "استخدم /start",
            reply_markup=main_menu_keyboard(
                is_logged_in=False
            )
        )
        return False
    return True


# ==================== القنوات ====================

async def show_channels_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not await require_login(update, context):
        return

    wait_msg = await query.message.reply_text(
        "⏳ جاري تحميل قنواتك..."
    )

    result = await telegram_service.get_dialogs(user_id)

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not result["success"]:
        error = result.get("error", "")
        if error == "session_expired":
            await query.message.reply_text(
                "❌ انتهت الجلسة\n"
                "سجل دخول مجدداً /start"
            )
        else:
            await query.message.reply_text(
                f"❌ خطأ: {result.get('message', '')}"
            )
        return

    channels = result.get("channels", [])

    if not channels:
        await query.message.reply_text(
            "📢 لا توجد قنوات",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            )
        )
        return

    for chat in channels:
        await db.save_chat(
            owner_id      = user_id,
            chat_id       = chat["id"],
            chat_title    = chat["title"],
            chat_type     = "channel",
            chat_username = chat.get("username"),
            members_count = chat.get("members_count", 0),
        )

    context.user_data["channels"]  = channels
    context.user_data["chat_type"] = "channel"

    await query.message.reply_text(
        f"📢 **قنواتك** ({len(channels)})\n\n"
        f"اختر القناة التي تريد أرشفتها 👇",
        reply_markup=chats_keyboard(
            channels, "channel", page=0
        ),
        parse_mode="Markdown"
    )


# ==================== المجموعات ====================

async def show_groups_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not await require_login(update, context):
        return

    wait_msg = await query.message.reply_text(
        "⏳ جاري تحميل مجموعاتك..."
    )

    result = await telegram_service.get_dialogs(user_id)

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not result["success"]:
        await query.message.reply_text(
            f"❌ خطأ: {result.get('message', '')}"
        )
        return

    groups = result.get("groups", [])

    if not groups:
        await query.message.reply_text(
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
            members_count = chat.get("members_count", 0),
        )

    context.user_data["groups"]    = groups
    context.user_data["chat_type"] = "group"

    await query.message.reply_text(
        f"👥 **مجموعاتك** ({len(groups)})\n\n"
        f"اختر المجموعة التي تريد أرشفتها 👇",
        reply_markup=chats_keyboard(
            groups, "group", page=0
        ),
        parse_mode="Markdown"
    )


# ==================== الكل ====================

async def show_all_chats_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not await require_login(update, context):
        return

    wait_msg = await query.message.reply_text(
        "⏳ جاري تحميل كل محادثاتك..."
    )

    result = await telegram_service.get_dialogs(user_id)

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not result["success"]:
        await query.message.reply_text(
            f"❌ خطأ: {result.get('message', '')}"
        )
        return

    all_chats = (
        result.get("channels", []) +
        result.get("groups", [])
    )

    if not all_chats:
        await query.message.reply_text(
            "❌ لا توجد محادثات",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            )
        )
        return

    context.user_data["all_chats"] = all_chats
    context.user_data["chat_type"] = "all"

    await query.message.reply_text(
        f"📂 **كل محادثاتك** ({len(all_chats)})\n\n"
        f"اختر المحادثة 👇",
        reply_markup=chats_keyboard(
            all_chats, "all", page=0
        ),
        parse_mode="Markdown"
    )


# ==================== Pagination ====================

async def page_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts     = query.data.split("_")
    chat_type = parts[1]
    page      = int(parts[2])

    chats_key = {
        "channel": "channels",
        "group":   "groups",
        "all":     "all_chats",
    }.get(chat_type, "all_chats")

    chats = context.user_data.get(chats_key, [])

    if not chats:
        await query.message.reply_text(
            "❌ لا توجد بيانات\nابدأ من جديد"
        )
        return

    await query.message.reply_text(
        f"📂 **المحادثات** ({len(chats)})\n\n"
        f"اختر المحادثة 👇",
        reply_markup=chats_keyboard(
            chats, chat_type, page=page
        ),
        parse_mode="Markdown"
    )


# ==================== اختيار محادثة ====================

async def select_chat_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    parts     = query.data.split("_")
    chat_type = parts[2]
    index     = int(parts[3])

    chats_key = {
        "channel": "channels",
        "group":   "groups",
        "all":     "all_chats",
    }.get(chat_type, "all_chats")

    chats = context.user_data.get(chats_key, [])

    if index >= len(chats):
        await query.message.reply_text(
            "❌ خطأ في الاختيار\nحاول مجدداً"
        )
        return

    selected = chats[index]
    context.user_data["selected_chat"] = selected

    wait_msg = await query.message.reply_text(
        "⏳ جاري جلب معلومات المحادثة..."
    )

    chat_info = await telegram_service.get_chat_info(
        user_id, selected["entity"]
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    icon = (
        "📢" if chat_type == "channel" else "👥"
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
            details += f"📝 الوصف: `{desc[:100]}`\n"

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

    await query.message.reply_text(
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

async def search_username_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await require_login(update, context):
        return

    await query.message.reply_text(
        "🔍 **البحث عن قناة**\n\n"
        "أرسل يوزرنيم القناة أو المجموعة\n"
        "مثال: `@channel_name`",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )
    return WAITING_USERNAME


async def receive_username(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.message.text.strip()

    if not username.startswith("@"):
        username = f"@{username}"

    wait_msg = await update.message.reply_text(
        f"⏳ جاري البحث عن {username}..."
    )

    result = await telegram_service.get_entity_by_username(
        user_id, username
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not result or not result.get("success"):
        await update.message.reply_text(
            f"❌ لم يتم العثور على {username}",
            reply_markup=cancel_keyboard()
        )
        return WAITING_USERNAME

    context.user_data["selected_chat"] = result

    icon = (
        "📢" if result.get("type") == "channel"
        else "👥"
    )

    await update.message.reply_text(
        f"✅ **تم العثور على:**\n\n"
        f"{icon} **{result.get('title', '')}**\n"
        f"👥 الأعضاء: "
        f"`{format_number(result.get('members_count', 0))}`\n\n"
        f"📌 **اختر نوع المحتوى** 👇",
        reply_markup=content_type_keyboard(),
        parse_mode="Markdown"
    )

    return ConversationHandler.END


# ==================== ConversationHandler ====================

def get_chats_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                search_username_callback,
                pattern="^search_username$"
            ),
        ],
        states={
            WAITING_USERNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_username
                )
            ],
        },
        fallbacks=[
            CallbackQueryHandler(
                lambda u, c: None,
                pattern="^main_menu$"
            ),
        ],
        allow_reentry=True,
    )


# ==================== تسجيل الهاندلرز ====================

def register_chats_handlers(app):
    app.add_handler(get_chats_handler())

    app.add_handler(CallbackQueryHandler(
        show_channels_callback,
        pattern="^show_channels$"
    ))
    app.add_handler(CallbackQueryHandler(
        show_groups_callback,
        pattern="^show_groups$"
    ))
    app.add_handler(CallbackQueryHandler(
        show_all_chats_callback,
        pattern="^show_all_chats$"
    ))
    app.add_handler(CallbackQueryHandler(
        page_callback,
        pattern="^page_"
    ))
    app.add_handler(CallbackQueryHandler(
        select_chat_callback,
        pattern="^select_chat_"
    ))
