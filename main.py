import sys
import os

sys.stdout.reconfigure(line_buffering=True)
print("=== بدء تشغيل البوت ===", flush=True)

import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from config import config

print("✅ تم استيراد المكتبات", flush=True)


# ==================== تسجيل الهاندلرز ====================

def register_handlers(app: Application):
    print("⏳ جاري تسجيل الهاندلرز...", flush=True)

    # ===== Auth =====
    from handlers.auth import (
        get_auth_handler,
        logout_callback,
        confirm_logout_callback,
        cancel_callback,
        help_command,
        status_command,
        developer_callback,
        help_callback,
        main_menu_callback,
    )

    app.add_handler(get_auth_handler())

    app.add_handler(CommandHandler(
        "help", help_command
    ))
    app.add_handler(CommandHandler(
        "status", status_command
    ))
    app.add_handler(CallbackQueryHandler(
        logout_callback,
        pattern="^logout$"
    ))
    app.add_handler(CallbackQueryHandler(
        confirm_logout_callback,
        pattern="^confirm_logout$"
    ))
    app.add_handler(CallbackQueryHandler(
        cancel_callback,
        pattern="^cancel$"
    ))
    app.add_handler(CallbackQueryHandler(
        developer_callback,
        pattern="^developer$"
    ))
    app.add_handler(CallbackQueryHandler(
        help_callback,
        pattern="^help$"
    ))
    app.add_handler(CallbackQueryHandler(
        main_menu_callback,
        pattern="^main_menu$"
    ))
    print("✅ Auth handlers", flush=True)

    # ===== Chats =====
    from handlers.chats import register_chats_handlers
    register_chats_handlers(app)
    print("✅ Chats handlers", flush=True)

    # ===== Archive =====
    from handlers.archive import register_archive_handlers
    register_archive_handlers(app)
    print("✅ Archive handlers", flush=True)

    # ===== Stats =====
    from handlers.stats import register_stats_handlers
    register_stats_handlers(app)
    print("✅ Stats handlers", flush=True)

    # ===== Admin =====
    from handlers.admin import register_admin_handlers
    register_admin_handlers(app)
    print("✅ Admin handlers", flush=True)

    print("✅ تم تسجيل كل الهاندلرز", flush=True)


# ==================== startup ====================

async def post_init(application: Application):
    print("⏳ جاري تشغيل الخدمات...", flush=True)

    from database import db
    await db.connect()
    print("✅ قاعدة البيانات", flush=True)

    from services.queue_service import queue_service
    await queue_service.start(
        num_workers=config.MAX_CONCURRENT_TASKS
    )
    print("✅ نظام الطابور", flush=True)

    try:
        await application.bot.send_message(
            chat_id    = config.OWNER_ID,
            text       = (
                f"🚀 **تم تشغيل البوت بنجاح!**\n\n"
                f"👑 المطور: {config.DEVELOPER_NAME}\n"
                f"📱 {config.DEVELOPER_USERNAME}"
            ),
            parse_mode = "Markdown"
        )
        print("✅ تم إشعار المالك", flush=True)
    except Exception as e:
        print(f"⚠️ لم يتم إشعار المالك: {e}", flush=True)

    print("🚀 البوت يعمل بنجاح!", flush=True)


async def post_shutdown(application: Application):
    print("⏳ جاري إيقاف الخدمات...", flush=True)

    try:
        from services.queue_service import queue_service
        await queue_service.stop()
        print("✅ تم إيقاف الطابور", flush=True)
    except Exception:
        pass

    try:
        from database import db
        await db.disconnect()
        print("✅ تم قطع قاعدة البيانات", flush=True)
    except Exception:
        pass

    try:
        from services.telegram_client import telegram_service
        await telegram_service.manager.disconnect_all()
        print("✅ تم قطع اتصالات Telethon", flush=True)
    except Exception:
        pass

    try:
        await application.bot.send_message(
            chat_id    = config.OWNER_ID,
            text       = "⛔ **تم إيقاف البوت**",
            parse_mode = "Markdown"
        )
    except Exception:
        pass


# ==================== معالجة الأخطاء ====================

async def error_handler(
        update: object,
        context) -> None:
    from telegram.error import (
        NetworkError,
        TimedOut,
        TelegramError,
    )
    from utils.logger import error_logger

    error = context.error

    if isinstance(error, (NetworkError, TimedOut)):
        print(f"⚠️ خطأ شبكة: {error}", flush=True)
        return

    print(f"❌ خطأ: {error}", flush=True)

    if isinstance(update, Update):
        try:
            msg = (
                update.callback_query.message
                if update.callback_query
                else update.message
            )
            if msg:
                await msg.reply_text(
                    "❌ حدث خطأ غير متوقع\n"
                    "حاول مجدداً أو استخدم /start"
                )
        except Exception:
            pass

    if not isinstance(error, TelegramError):
        try:
            import traceback
            tb = "".join(
                traceback.format_exception(
                    type(error),
                    error,
                    error.__traceback__
                )
            )
            print(f"Traceback:\n{tb}", flush=True)

            await context.bot.send_message(
                chat_id    = config.OWNER_ID,
                text       = (
                    f"⚠️ **خطأ في البوت**\n\n"
                    f"`{str(error)[:500]}`"
                ),
                parse_mode = "Markdown"
            )
        except Exception:
            pass


# ==================== التحقق من المتغيرات ====================

def check_env_vars():
    required = [
        "API_ID",
        "API_HASH",
        "BOT_TOKEN",
        "OWNER_ID",
        "DATABASE_URL",
    ]

    missing = []
    for var in required:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        print(
            f"❌ متغيرات مفقودة: {', '.join(missing)}",
            flush=True
        )
        sys.exit(1)

    print("✅ كل المتغيرات موجودة", flush=True)


# ==================== نقطة التشغيل ====================

def main():
    print("🚀 جاري تشغيل البوت...", flush=True)

    check_env_vars()

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    register_handlers(app)

    app.add_error_handler(error_handler)

    print("✅ البوت جاهز للتشغيل", flush=True)

    app.run_polling(
        allowed_updates = Update.ALL_TYPES,
        drop_pending_updates = True,
    )


if __name__ == "__main__":
    main()
