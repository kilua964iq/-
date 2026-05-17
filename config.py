import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ===== تيليغرام =====
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))

    # ===== قاعدة البيانات =====
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    # ===== OpenAI =====
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # ===== المطور =====
    DEVELOPER_NAME     = "Mustafa"
    DEVELOPER_USERNAME = "@o8380"

    # ===== مسارات =====
    DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", "downloads")
    SESSION_PATH  = os.getenv("SESSION_PATH", "sessions")
    LOG_PATH      = os.getenv("LOG_PATH", "logs")

    # ===== إعدادات =====
    MAX_DOWNLOAD_SIZE    = int(os.getenv("MAX_DOWNLOAD_SIZE", "2000"))
    MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))
    FLOOD_SLEEP_THRESHOLD = int(os.getenv("FLOOD_SLEEP_THRESHOLD", "60"))

    # ===== أنواع المحتوى =====
    CONTENT_TYPES = {
        "text":     "📝 النصوص",
        "photos":   "🖼️ الصور",
        "videos":   "🎥 الفيديوهات",
        "files":    "📁 الملفات",
        "audio":    "🎵 الصوتيات",
        "voice":    "🎤 الرسائل الصوتية",
        "stickers": "🎭 الملصقات",
        "all":      "📦 كل المحتوى",
    }

    # ===== حدود الجلب =====
    FETCH_LIMITS = [10, 50, 100, 500, 1000, 0]


config = Config()


# ===== إنشاء المجلدات =====
def create_directories():
    dirs = [
        config.DOWNLOAD_PATH,
        config.SESSION_PATH,
        config.LOG_PATH,
        f"{config.DOWNLOAD_PATH}/photos",
        f"{config.DOWNLOAD_PATH}/videos",
        f"{config.DOWNLOAD_PATH}/files",
        f"{config.DOWNLOAD_PATH}/audio",
        f"{config.DOWNLOAD_PATH}/voice",
        f"{config.DOWNLOAD_PATH}/stickers",
        f"{config.DOWNLOAD_PATH}/txt",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


create_directories()
