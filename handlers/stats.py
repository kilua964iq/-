from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
)
from config import config
from services.downloader import download_manager
from utils.keyboards import (
    main_menu_keyboard,
    stats_keyboard,
    confirm_keyboard,
)
from utils.helpers import (
    format_number,
    format_size,
    format_date,
    time_ago,
    build_stats_message,
)
from utils.logger import error_logger


# ==================== دوال مساعدة ====================

def build_mini_bar(
        value: int,
        max_value: int,
        length: int = 8) -> str:
    if max_value == 0:
        return "⬜" * length
    filled = min(
        int(length * value / max_value), length
    )
    empty  = length - filled
    return "⬛" * filled + "⬜" * empty


def build_text_chart(data: dict) -> str:
    if not data:
        return "لا توجد بيانات"

    total = sum(data.values())
    result = ""

    content_icons = {
        "text":     "📝",
        "photos":   "🖼️",
        "videos":   "🎥",
        "files":    "📁",
        "audio":    "🎵",
        "voice":    "🎤",
        "stickers": "🎭",
        "all":      "📦",
    }

    for key, value in sorted(
        data.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        if value == 0:
            continue
        icon       = content_icons.get(key, "📌")
        percentage = (
            (value / total * 100) if total > 0 else 0
        )
        bar        = build_mini_bar(value, total)
        result    += (
            f"{icon} {bar} "
            f"`{value}` ({percentage:.0f}%)\n"
        )

    return result


# ==================== إحصائيات عامة ====================

async def show_stats_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    wait_msg = await query.message.reply_text(
        "⏳ جاري تحميل الإحصائيات..."
    )

    try:
        stats    = await db.get_stats(owner_id=user_id)
        storage  = download_manager.get_user_storage(user_id)
        chats    = await db.get_user_chats(user_id)
        archives = await db.get_user_archives(
            owner_id=user_id, limit=1
        )

        last_archive = archives[0] if archives else None

        msg = (
            f"📊 **إحصائياتك**\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📦 الأرشيفات:   "
            f"`{format_number(stats['total_archives'] or 0)}`\n"
            f"💬 الرسائل:     "
            f"`{format_number(stats['total_messages'] or 0)}`\n"
            f"📁 الملفات:     "
            f"`{format_number(stats['total_files'] or 0)}`\n"
            f"📢 القنوات:     "
            f"`{format_number(len(chats))}`\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💾 **التخزين**\n\n"
            f"🖼️ صور:         "
            f"`{storage['photos']['size_formatted']}`\n"
            f"🎥 فيديو:       "
            f"`{storage['videos']['size_formatted']}`\n"
            f"📁 ملفات:       "
            f"`{storage['files']['size_formatted']}`\n"
            f"🎵 صوتيات:     "
            f"`{storage['audio']['size_formatted']}`\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💿 المجموع:     "
            f"`{storage['total']['size_formatted']}`\n"
        )

        if last_archive:
            msg += (
                f"\n📅 **آخر أرشيف**\n"
                f"`{last_archive['chat_title']}`\n"
                f"{time_ago(last_archive['started_at'])}"
            )

        try:
            await wait_msg.delete()
        except Exception:
            pass

        await query.message.reply_text(
            msg,
            reply_markup=stats_keyboard(),
            parse_mode="Markdown"
        )

    except Exception as e:
        error_logger.log_exception(
            e, "show_stats", user_id
        )
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await query.message.reply_text(
            "❌ خطأ في تحميل الإحصائيات"
        )


# ==================== إحصائيات مفصلة ====================

async def detailed_stats_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    archives = await db.get_user_archives(
        owner_id=user_id, limit=100
    )

    if not archives:
        await query.message.reply_text(
            "❌ لا توجد أرشيفات بعد"
        )
        return

    type_stats   = {}
    status_stats = {
        "completed": 0,
        "failed":    0,
        "running":   0,
        "pending":   0,
        "cancelled": 0,
    }
    total_messages = 0

    for archive in archives:
        content_type = archive["content_type"]
        type_stats[content_type] = (
            type_stats.get(content_type, 0) + 1
        )
        status = archive["status"]
        status_stats[status] = (
            status_stats.get(status, 0) + 1
        )
        total_messages += (
            archive["fetched_messages"] or 0
        )

    chart = build_text_chart(type_stats)

    msg = (
        f"📊 **إحصائيات مفصلة**\n\n"
        f"📦 **الأرشيفات:** `{len(archives)}`\n"
        f"💬 **الرسائل:** `{format_number(total_messages)}`\n\n"
        f"**حسب النوع:**\n"
        f"{chart}\n"
        f"**حسب الحالة:**\n"
        f"✅ مكتملة:  `{status_stats['completed']}`\n"
        f"🔄 جارية:   `{status_stats['running']}`\n"
        f"⏳ منتظرة:  `{status_stats['pending']}`\n"
        f"❌ فاشلة:   `{status_stats['failed']}`\n"
        f"⚠️ ملغية:   `{status_stats['cancelled']}`\n"
    )

    await query.message.reply_text(
        msg,
        reply_markup=stats_keyboard(),
        parse_mode="Markdown"
    )


# ==================== تقرير أسبوعي ====================

async def weekly_stats_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    wait_msg = await query.message.reply_text(
        "⏳ جاري إعداد التقرير الأسبوعي..."
    )

    try:
        week_ago = datetime.now() - timedelta(days=7)
        archives = await db.get_user_archives(
            owner_id=user_id, limit=100
        )

        weekly_archives = [
            a for a in archives
            if a["started_at"] and
            a["started_at"] >= week_ago
        ]

        weekly_messages = sum(
            a["fetched_messages"] or 0
            for a in weekly_archives
        )

        daily_stats = {}
        for i in range(7):
            day     = datetime.now() - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            daily_stats[day_str] = {
                "archives": 0,
                "messages": 0,
            }

        for archive in weekly_archives:
            if archive["started_at"]:
                day_str = archive[
                    "started_at"
                ].strftime("%Y-%m-%d")
                if day_str in daily_stats:
                    daily_stats[day_str]["archives"] += 1
                    daily_stats[day_str]["messages"] += (
                        archive["fetched_messages"] or 0
                    )

        max_msgs = max(
            d["messages"]
            for d in daily_stats.values()
        ) or 1

        daily_chart = ""
        for day_str, data in sorted(
            daily_stats.items(), reverse=True
        ):
            bar = build_mini_bar(
                data["messages"], max_msgs
            )
            daily_chart += (
                f"`{day_str}` {bar} "
                f"`{format_number(data['messages'])}`\n"
            )

        msg = (
            f"📅 **التقرير الأسبوعي**\n\n"
            f"📆 الفترة: آخر 7 أيام\n\n"
            f"📦 أرشيفات جديدة: "
            f"`{len(weekly_archives)}`\n"
            f"💬 رسائل محفوظة:  "
            f"`{format_number(weekly_messages)}`\n\n"
            f"**النشاط اليومي:**\n"
            f"{daily_chart}"
        )

        try:
            from services.ai_service import ai_service
            ai_report = await ai_service.generate_report(
                stats={
                    "weekly_archives": len(weekly_archives),
                    "weekly_messages": weekly_messages,
                },
                chat_name="حسابك"
            )
            if ai_report:
                msg += (
                    f"\n\n🤖 **تحليل AI:**\n{ai_report}"
                )
        except Exception:
            pass

        try:
            await wait_msg.delete()
        except Exception:
            pass

        await query.message.reply_text(
            msg,
            reply_markup=stats_keyboard(),
            parse_mode="Markdown"
        )

    except Exception as e:
        error_logger.log_exception(
            e, "weekly_stats", user_id
        )
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await query.message.reply_text(
            "❌ خطأ في إعداد التقرير"
        )


# ==================== إحصائيات التخزين ====================

async def storage_stats_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    storage = download_manager.get_user_storage(user_id)

    media_types = {
        "photos":   "🖼️ الصور",
        "videos":   "🎥 الفيديوهات",
        "files":    "📁 الملفات",
        "audio":    "🎵 الصوتيات",
        "voice":    "🎤 الرسائل الصوتية",
        "text":     "📝 النصوص",
        "stickers": "🎭 الملصقات",
        "txt":      "📄 ملفات TXT",
    }

    total_size = storage["total"]["size"]
    msg        = "💾 **إحصائيات التخزين**\n\n"

    for key, name in media_types.items():
        data  = storage.get(key, {})
        size  = data.get("size", 0)
        count = data.get("count", 0)

        if size > 0:
            percentage = (
                (size / total_size * 100)
                if total_size > 0 else 0
            )
            bar = build_mini_bar(size, total_size)
            msg += (
                f"{name}\n"
                f"{bar} `{data['size_formatted']}` "
                f"({percentage:.1f}%) "
                f"| `{format_number(count)}` ملف\n\n"
            )

    msg += (
        f"━━━━━━━━━━━━━━━━\n"
        f"💿 **المجموع:** "
        f"`{storage['total']['size_formatted']}`\n"
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🗑️ تنظيف القديم",
            callback_data="cleanup_storage"
        )],
        [InlineKeyboardButton(
            "🔙 رجوع",
            callback_data="show_stats"
        )],
    ])

    await query.message.reply_text(
        msg,
        reply_markup=markup,
        parse_mode="Markdown"
    )


# ==================== مقارنة الأرشيفات ====================

async def compare_stats_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    archives = await db.get_user_archives(
        owner_id=user_id, limit=10
    )

    if len(archives) < 2:
        await query.message.reply_text(
            "❌ تحتاج أرشيفين على الأقل للمقارنة"
        )
        return

    sorted_archives = sorted(
        archives,
        key=lambda x: x["fetched_messages"] or 0,
        reverse=True,
    )

    max_messages = (
        sorted_archives[0]["fetched_messages"] or 1
    )

    msg = "📊 **مقارنة الأرشيفات**\n\n"

    for i, archive in enumerate(
        sorted_archives[:5], 1
    ):
        messages = archive["fetched_messages"] or 0
        bar      = build_mini_bar(messages, max_messages)
        status_icon = {
            "completed": "✅",
            "failed":    "❌",
            "running":   "🔄",
            "pending":   "⏳",
            "cancelled": "⚠️",
        }.get(archive["status"], "📦")

        msg += (
            f"{i}. {status_icon} "
            f"`{archive['chat_title'][:20]}`\n"
            f"   {bar} "
            f"`{format_number(messages)}`\n\n"
        )

    await query.message.reply_text(
        msg,
        reply_markup=stats_keyboard(),
        parse_mode="Markdown"
    )


# ==================== تنظيف التخزين ====================

async def cleanup_storage_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "🗑️ **تنظيف التخزين**\n\n"
        "سيتم حذف الملفات الأقدم من 30 يوم\n"
        "هل تريد المتابعة؟",
        reply_markup=confirm_keyboard("cleanup"),
        parse_mode="Markdown"
    )


async def confirm_cleanup_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    wait_msg = await query.message.reply_text(
        "⏳ جاري التنظيف..."
    )

    result = await download_manager.cleanup_old_files(
        owner_id=user_id, days=30
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    await query.message.reply_text(
        f"✅ **اكتمل التنظيف**\n\n"
        f"🗑️ الملفات المحذوفة: "
        f"`{format_number(result['deleted_count'])}`\n"
        f"💾 المساحة المحررة:  "
        f"`{result['deleted_size_formatted']}`",
        reply_markup=main_menu_keyboard(
            is_logged_in=True
        ),
        parse_mode="Markdown"
    )


# ==================== تسجيل الهاندلرز ====================

def register_stats_handlers(app):
    app.add_handler(CallbackQueryHandler(
        show_stats_callback,
        pattern="^show_stats$"
    ))
    app.add_handler(CallbackQueryHandler(
        detailed_stats_callback,
        pattern="^stats_detailed$"
    ))
    app.add_handler(CallbackQueryHandler(
        weekly_stats_callback,
        pattern="^stats_weekly$"
    ))
    app.add_handler(CallbackQueryHandler(
        storage_stats_callback,
        pattern="^stats_storage$"
    ))
    app.add_handler(CallbackQueryHandler(
        compare_stats_callback,
        pattern="^stats_compare$"
    ))
    app.add_handler(CallbackQueryHandler(
        cleanup_storage_callback,
        pattern="^cleanup_storage$"
    ))
    app.add_handler(CallbackQueryHandler(
        confirm_cleanup_callback,
        pattern="^confirm_cleanup$"
    ))
