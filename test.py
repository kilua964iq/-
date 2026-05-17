import asyncio
import os
import sys

print("=== بدء الاختبار ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"BOT_TOKEN موجود: {bool(os.getenv('BOT_TOKEN'))}", flush=True)
print(f"API_ID: {os.getenv('API_ID', 'NOT FOUND')}", flush=True)
print(f"DATABASE_URL موجود: {bool(os.getenv('DATABASE_URL'))}", flush=True)
print(f"OWNER_ID: {os.getenv('OWNER_ID', 'NOT FOUND')}", flush=True)

async def test():
    try:
        import asyncpg
        conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
        print("✅ قاعدة البيانات شغالة", flush=True)
        await conn.close()
    except Exception as e:
        print(f"❌ قاعدة البيانات: {e}", flush=True)

    try:
        from telegram import Bot
        bot = Bot(token=os.getenv('BOT_TOKEN'))
        me = await bot.get_me()
        print(f"✅ البوت شغال: {me.username}", flush=True)
    except Exception as e:
        print(f"❌ البوت: {e}", flush=True)

    print("=== انتهى الاختبار ===", flush=True)

asyncio.run(test()
