import asyncio
import logging
import os
import sys
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from config import config
from utils.logger import setup_logger, bot_logger
from database import db


# ==================== إعداد السجلات ====================

logger = setup_logger("main")


# ==================== تشغيل البوت ====================

async def post_init(application):
    """يعمل بعد تشغيل البوت مباشرة"""
    try:
        # الاتصال بقاعدة البيانات
        await db.connect()
        bot_logger.info("✅ تم الاتصال بقاعدة البيانات")

        # تشغيل نظام الطابور
        from services.queue_service import queue_service
        await queue_service.start(
            num_workers = config.MAX_CONCURRENT_TASKS
        )
        bot_logger.info("✅ تم تشغيل نظام الطابور")

        # إشعار المالك
        try:
            await application.bot.send_message(
                chat_id    = config.OWNER_ID,
                text       = (
                    "🚀 **تم تشغيل البوت بنجاح!**\n\n"
                    f"⚙️ الإصدار: `1.0.0`\n"
                    f"👷 العمال: "
                    f"`{config.MAX_CONCURRENT_TASKS}`\n"
                    f"📅 التاريخ: "
                    f"`{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
                ),
                parse_mode = "Markdown",
            )
        except Exception as e:
            bot_logger.warning(
                f"⚠️ لم يتم إشعار المالك: {e}"
            )

        bot_logger.info("🚀 البوت يعمل بنجاح!")

    except Exception as e:
        bot_logger.error(f"❌ خطأ في التشغيل: {e}")
        raise


async def post_shutdown(application):
    """يعمل عند إيقاف البوت"""
    try:
        # إيقاف الطابور
        from services.queue_service import queue_service
        await queue_service.stop()
        bot_logger.info("✅ تم إيقاف الطابور")

        # قطع الاتصال بقاعدة البيانات
        await db.disconnect()
        bot_logger.info("✅ تم قطع الاتصال بقاعدة البيانات")

        # قطع كل اتصالات Telethon
        from services.telegram_client import telegram_service
        await telegram_service.manager.disconnect_all()
        bot_logger.info("✅ تم قطع كل اتصالات Telethon")

        # إشعار المالك
        try:
            await application.bot.send_message(
                chat_id = config.OWNER_ID,
                text    = "⛔ **تم إيقاف البوت**",
                parse_mode = "Markdown",
            )
        except Exception:
            pass

    except Exception as e:
        bot_logger.error(f"❌ خطأ في الإيقاف: {e}")


# ==================== معالجة الأخطاء ====================

async def error_handler(
        update: object,
        context) -> None:
    """معالجة الأخطاء العامة"""
    from utils.logger import error_logger
    from telegram.error import (
        NetworkError,
        TimedOut,
        TelegramError,
    )

    error = context.error

    # أخطاء الشبكة - تجاهل
    if isinstance(error, (NetworkError, TimedOut)):
        bot_logger.warning(
            f"⚠️ خطأ شبكة: {error}"
        )
        return

    # تسجيل الخطأ
    error_logger.log_exception(
        error,
        "error_handler",
        getattr(
            getattr(update, "effective_user", None),
            "id", None
        )
    )

    bot_logger.error(f"❌ خطأ غير متوقع: {error}")

    # إشعار المستخدم
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

    # إشعار المالك بالأخطاء الكبيرة
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
            await context.bot.send_message(
                chat_id = config.OWNER_ID,
                text    = (
                    f"⚠️ **خطأ في البوت**\n\n"
                    f"`{str(error)[:500]}`"
                ),
                parse_mode = "Markdown",
            )
        except Exception:
            pass


# ==================== تسجيل الهاندلرز ====================

def register_all_handlers(app: Application):
    """تسجيل كل الهاندلرز"""

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
        pattern = "^logout$"
    ))
    app.add_handler(CallbackQueryHandler(
        confirm_logout_callback,
        pattern = "^confirm_logout$"
    ))
    app.add_handler(CallbackQueryHandler(
        cancel_callback,
        pattern = "^cancel$"
    ))

    # ===== Chats =====
    from handlers.chats import register_chats_handlers
    register_chats_handlers(app)

    # ===== Archive =====
    from handlers.archive import register_archive_handlers
    register_archive_handlers(app)

    # ===== Stats =====
    from handlers.stats import register_stats_handlers
    register_stats_handlers(app)

    # ===== Admin =====
    from handlers.admin import register_admin_handlers
    register_admin_handlers(app)

    # ===== معالج الأخطاء =====
    app.add_error_handler(error_handler)

    bot_logger.info("✅ تم تسجيل كل الهاندلرز")


# ==================== بناء التطبيق ====================

def build_application() -> Application:
    """بناء تطبيق البوت"""

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    register_all_handlers(app)

    return app


# ==================== نقطة التشغيل ====================

def main():
    """تشغيل البوت"""

    bot_logger.info("🚀 جاري تشغيل البوت...")
