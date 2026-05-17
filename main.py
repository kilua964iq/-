import sys
import os

sys.stdout.reconfigure(line_buffering=True)
print("=== بدء تشغيل البوت ===", flush=True)

import asyncio
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

print("✅ تم استيراد المكتبات الأساسية", flush=True)

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

print("✅ تم استيراد telegram", flush=True)

from config import config
print("✅ تم استيراد config", flush=True)

from database import db
print("✅ تم استيراد database", flush=True)

from utils.logger import setup_logger, bot_logger
print("✅ تم استيراد logger", flush=True)


# ==================== تشغيل البوت ====================

async def post_init(application):
    """يعمل بعد تشغيل البوت مباشرة"""
    try:
        print("⏳ جاري الاتصال بقاعدة البيانات...", flush=True)
        await db.connect()
        print("✅ تم الاتصال بقاعدة البيانات", flush=True)

        print("⏳ جاري تشغيل نظام الطابور...", flush=True)
        from services.queue_service import queue_service
        await queue_service.start(
            num_workers=config.MAX_CONCURRENT_TASKS
        )
        print("✅ تم تشغيل نظام الطابور", flush=True)

        try:
            await application.bot.send_message(
                chat_id=config.OWNER_ID,
                text=(
                    "🚀 **تم تشغيل البوت بنجاح!**\n\n"
                    f"⚙️ الإصدار: `1.0.0`\n"
                    f"👷 العمال: "
                    f"`{config.MAX_CONCURRENT_TASKS}`\n"
                    f"📅 التاريخ: "
                    f"`{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
                ),
                parse_mode="Markdown",
            )
            print("✅ تم إشعار المالك", flush=True)
        except Exception as e:
            print(f"⚠️ لم يتم إشعار المالك: {e}", flush=True)

        print("🚀 البوت يعمل بنجاح!", flush=True)

    except Exception as e:
        print(f"❌ خطأ في التشغيل: {e}", flush=True)
        raise


async def post_shutdown(application):
    """يعمل عند إيقاف البوت"""
    try:
        from services.queue_service import queue_service
        await queue_service.stop()
        print("✅ تم إيقاف الطابور", flush=True)

        await db.disconnect()
        print("✅ تم قطع الاتصال بقاعدة البيانات", flush=True)

        from services.telegram_client import telegram_service
        await telegram_service.manager.disconnect_all()
        print("✅ تم قطع كل اتصالات Telethon", flush=True)

        try:
            await application.bot.send_message(
                chat_id=config.OWNER_ID,
                text="⛔ **تم إيقاف البوت**",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    except Exception as e:
        print(f"❌ خطأ في الإيقاف: {e}", flush=True)


# ==================== معالجة الأخطاء ====================

async def error_handler(
        update: object,
        context) -> None:
    """معالجة الأخطاء العامة"""
    from telegram.error import (
        NetworkError,
        TimedOut,
        TelegramError,
    )

    error = context.error

    if isinstance(error, (NetworkError, TimedOut)):
        print(f"⚠️ خطأ شبكة: {error}", flush=True)
        return

    print(f"❌ خطأ غير متوقع: {error}", flush=True)

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
            print(f"❌ Traceback:\n{tb}", flush=True)
            await context.bot.send_message(
                chat_id=config.OWNER_ID,
                text=(
                    f"⚠️ **خطأ في البوت**\n\n"
                    f"`{str(error)[:500]}`"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass


# ==================== تسجيل الهاندلرز ====================

def register_all_handlers(app: Application):
    """تسجيل كل الهاندلرز"""

    print("⏳ جاري تسجيل الهاندلرز...", flush=True)

    # ===== Auth =====
    from handlers.auth import (
        get_auth_handler,
        logout_callback,
        confirm_logout_callback,
        cancel_callback,
        help_command,
        status_command,
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
    print("✅ تم تسجيل Auth handlers", flush=True)

    # ===== Chats =====
    from handlers.chats import register_chats_handlers
    register_chats_handlers(app)
    print("✅ تم تسجيل Chats handlers", flush=True)

    # ===== Archive =====
    from handlers.archive import register_archive_handlers
    register_archive_handlers(app)
    print("✅ تم تسجيل Archive handlers", flush=True)

    # ===== Stats =====
    from handlers.stats import register_stats_handlers
    register_stats_handlers(app)
    print("✅ تم تسجيل Stats handlers", flush=True)

    # ===== Admin =====
    from handlers.admin import register_admin_handlers
    register_admin_handlers(app)
    print("✅ تم تسجيل Admin handlers", flush=True)

    # ===== معالج الأخطاء =====
    app.add_error_handler(error_handler)

    print("✅ تم تسجيل كل الهاندلرز", flush=True)


# ==================== بناء التطبيق ====================

def build_application() -> Application:
    """بناء تطبيق البوت"""
    print("⏳ جاري بناء التطبيق...", flush=True)

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    register_all_handlers(app)

    print("✅ تم بناء التطبيق", flush=True)
    return app


# ==================== نقطة التشغيل ====================

def main():
    """تشغيل البوت"""
    print("🚀 جاري تشغيل البوت...", flush=True)

    required_vars = [
        "API_ID",
        "API_HASH",
        "BOT_TOKEN",
        "OWNER_ID",
        "DATABASE_URL",
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        print(
            f"❌ متغيرات مفقودة: {', '.join(missing)}",
            flush=True
        )
        sys.exit(1)

    print("✅ كل المتغيرات موجودة", flush=True)

    app = build_application()

    print("✅ البوت جاهز للتشغيل", flush=True)

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
