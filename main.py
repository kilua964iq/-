import sys
import os

sys.stdout.reconfigure(line_buffering=True)
print("=== بدء تشغيل البوت ===", flush=True)

import asyncio
import concurrent.futures
import telebot
from config import config

print("✅ تم استيراد المكتبات", flush=True)


# ==================== إنشاء البوت ====================

bot = telebot.TeleBot(
    config.BOT_TOKEN,
    parse_mode=None,
    threaded=True,
)

print("✅ تم إنشاء البوت", flush=True)


# ==================== تشغيل async ====================

def run_async_safe(coro):
    """تشغيل coroutine بشكل آمن"""
    def run_in_thread():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1
    )
    future = executor.submit(run_in_thread)
    try:
        return future.result(timeout=60)
    except Exception as e:
        print(f"❌ خطأ: {e}", flush=True)
        return None
    finally:
        executor.shutdown(wait=False)


# ==================== تسجيل الهاندلرز ====================

def register_handlers():
    print("⏳ جاري تسجيل الهاندلرز...", flush=True)

    from handlers.auth import register_auth_handlers
    register_auth_handlers(bot)
    print("✅ Auth handlers", flush=True)

    from handlers.chats import register_chats_handlers
    register_chats_handlers(bot)
    print("✅ Chats handlers", flush=True)

    from handlers.archive import register_archive_handlers
    register_archive_handlers(bot)
    print("✅ Archive handlers", flush=True)

    from handlers.stats import register_stats_handlers
    register_stats_handlers(bot)
    print("✅ Stats handlers", flush=True)

    from handlers.admin import register_admin_handlers
    register_admin_handlers(bot)
    print("✅ Admin handlers", flush=True)

    print("✅ تم تسجيل كل الهاندلرز", flush=True)


# ==================== startup ====================

async def startup():
    print("⏳ جاري تشغيل الخدمات...", flush=True)

    from database import db
    await db.connect()
    print("✅ قاعدة البيانات", flush=True)

    from services.queue_service import queue_service
    await queue_service.start(
        num_workers=config.MAX_CONCURRENT_TASKS
    )
    print("✅ نظام الطابور", flush=True)

    print("🚀 البوت يعمل بنجاح!", flush=True)


async def shutdown():
    try:
        from services.queue_service import queue_service
        await queue_service.stop()
    except Exception:
        pass

    try:
        from database import db
        await db.disconnect()
    except Exception:
        pass

    try:
        from services.telegram_client import telegram_service
        await telegram_service.manager.disconnect_all()
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

    # تشغيل الخدمات أولاً
    run_async_safe(startup())

    # تسجيل الهاندلرز
    register_handlers()

    # إشعار المالك
    try:
        bot.send_message(
            config.OWNER_ID,
            f"🚀 **تم تشغيل البوت بنجاح!**\n\n"
            f"👑 المطور: {config.DEVELOPER_NAME}\n"
            f"📱 {config.DEVELOPER_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"⚠️ {e}", flush=True)

    print("✅ البوت جاهز للتشغيل", flush=True)

    try:
        print("🤖 البوت يستمع للرسائل...", flush=True)
        bot.infinity_polling(
            timeout=10,
            long_polling_timeout=5,
            logger_level=None,
            skip_pending=True,
            allowed_updates=[
                "message",
                "callback_query",
            ],
        )
    except KeyboardInterrupt:
        print("⛔ تم إيقاف البوت", flush=True)
    except Exception as e:
        print(f"❌ خطأ: {e}", flush=True)
    finally:
        run_async_safe(shutdown())


if __name__ == "__main__":
    main()
