import sys
import os

sys.stdout.reconfigure(line_buffering=True)
print("=== بدء تشغيل البوت ===", flush=True)

import asyncio
import threading
import telebot
from config import config

print("✅ تم استيراد المكتبات", flush=True)


# ==================== إنشاء البوت ====================

bot = telebot.TeleBot(
    config.BOT_TOKEN,
    parse_mode=None,
    threaded=False,
)

print("✅ تم إنشاء البوت", flush=True)


# ==================== تسجيل الهاندلرز ====================

def register_handlers():
    """تسجيل كل الهاندلرز"""
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


# ==================== تشغيل async ====================

async def startup():
    """تشغيل الخدمات الأساسية"""
    print("⏳ جاري تشغيل الخدمات...", flush=True)

    # الاتصال بقاعدة البيانات
    from database import db
    await db.connect()
    print("✅ قاعدة البيانات", flush=True)

    # تشغيل الطابور
    from services.queue_service import queue_service
    await queue_service.start(
        num_workers=config.MAX_CONCURRENT_TASKS
    )
    print("✅ نظام الطابور", flush=True)

    # إشعار المالك
    try:
        bot.send_message(
            config.OWNER_ID,
            f"🚀 **تم تشغيل البوت بنجاح!**\n\n"
            f"⚙️ الإصدار: `2.0.0`\n"
            f"👷 العمال: `{config.MAX_CONCURRENT_TASKS}`\n"
            f"📅 التاريخ: "
            f"`{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
            f"👑 المطور: {config.DEVELOPER_NAME}\n"
            f"📱 {config.DEVELOPER_USERNAME}",
            parse_mode="Markdown"
        )
        print("✅ تم إشعار المالك", flush=True)
    except Exception as e:
        print(f"⚠️ لم يتم إشعار المالك: {e}", flush=True)

    print("🚀 البوت يعمل بنجاح!", flush=True)


async def shutdown():
    """إيقاف الخدمات"""
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
        print("✅ تم قطع الاتصال بقاعدة البيانات", flush=True)
    except Exception:
        pass

    try:
        from services.telegram_client import telegram_service
        await telegram_service.manager.disconnect_all()
        print("✅ تم قطع اتصالات Telethon", flush=True)
    except Exception:
        pass

    try:
        bot.send_message(
            config.OWNER_ID,
            "⛔ **تم إيقاف البوت**",
            parse_mode="Markdown"
        )
    except Exception:
        pass


# ==================== تشغيل الـ async في thread ====================

def run_async_startup():
    """تشغيل startup في thread منفصل"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(startup())


# ==================== التحقق من المتغيرات ====================

def check_env_vars():
    """التحقق من المتغيرات المطلوبة"""
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
    """تشغيل البوت"""
    print("🚀 جاري تشغيل البوت...", flush=True)

    # التحقق من المتغيرات
    check_env_vars()

    # تسجيل الهاندلرز
    register_handlers()

    # تشغيل الخدمات الأساسية
    startup_thread = threading.Thread(
        target=run_async_startup,
        daemon=True
    )
    startup_thread.start()
    startup_thread.join(timeout=30)

    print("✅ البوت جاهز للتشغيل", flush=True)

    # تشغيل البوت
    try:
        print("🤖 البوت يستمع للرسائل...", flush=True)
        bot.infinity_polling(
            timeout=10,
            long_polling_timeout=5,
            logger_level=None,
            allowed_updates=None,
        )
    except KeyboardInterrupt:
        print("⛔ تم إيقاف البوت", flush=True)
    except Exception as e:
        print(f"❌ خطأ: {e}", flush=True)
    finally:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(shutdown())


if __name__ == "__main__":
    main()
