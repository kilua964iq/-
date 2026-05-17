import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ===== تيليغرام =====
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))

    # ===== OpenAI =====
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # ===== مسارات =====
    DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", "downloads")
    SESSION_PATH = os.getenv("SESSION_PATH", "sessions")
    LOG_PATH = os.getenv("LOG_PATH", "logs")

    # ===== إعدادات البوت =====
    MAX_DOWNLOAD_SIZE = int(os.getenv("MAX_DOWNLOAD_SIZE", "2000"))
    MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))
    FLOOD_SLEEP_THRESHOLD = int(os.getenv("FLOOD_SLEEP_THRESHOLD", "60"))

    # ===== الأيقونات المضيئة =====
    ICONS = {
        "check":     "6023660820544623088",
        "cross":     "6037570896766438989",
        "fire":      "5999340396432333728",
        "lightning": "6026367225466720832",
        "diamond":   "6023660820544623088",
        "rocket":    "6282977077427702833",
        "stop":      "5420323339723881652",
        "warning":   "5420323339723881652",
        "note":      "6023660820544623088",
        "chart":     "5971837723676249096",
        "box":       "6066395745139824604",
        "list":      "5974235702701853774",
        "refresh":   "5971837723676249096",
        "clock":     "5971837723676249096",
        "globe":     "6026367225466720832",
        "target":    "5974235702701853774",
        "robot":     "6057466460886799210",
        "admin":     "4949560993840629085",
        "play":      "6285315214673975495",
        "star":      "5971944878815317190",
    }

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
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


create_directories()
