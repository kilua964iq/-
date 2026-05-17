import os
import re
import json
import humanize
import pytz
from datetime import datetime
from typing import Optional
from config import config
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
    DocumentAttributeVideo,
    DocumentAttributeAudio,
    DocumentAttributeSticker,
    DocumentAttributeFilename,
)


# ==================== تنسيق الأرقام ====================

def format_number(number: int) -> str:
    """تنسيق الأرقام الكبيرة"""
    return humanize.intcomma(number)


def format_size(size_bytes: int) -> str:
    """تنسيق حجم الملف"""
    return humanize.naturalsize(size_bytes, binary=True)


def format_date(dt: datetime,
                timezone: str = "Asia/Baghdad") -> str:
    """تنسيق التاريخ"""
    if not dt:
        return "غير معروف"
    tz = pytz.timezone(timezone)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    local_dt = dt.astimezone(tz)
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: int) -> str:
    """تنسيق المدة الزمنية"""
    return humanize.naturaldelta(seconds)


def time_ago(dt: datetime) -> str:
    """منذ كم وقت"""
    return humanize.naturaltime(dt)


# ==================== تصنيف الرسائل ====================

def classify_message(msg) -> str:
    """تصنيف نوع الرسالة"""
    if msg.media is None:
        if msg.text:
            return "text"
        return "text"

    if isinstance(msg.media, MessageMediaPhoto):
        return "photos"

    if isinstance(msg.media, MessageMediaDocument):
        doc = msg.media.document
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                return "videos"
            if isinstance(attr, DocumentAttributeAudio):
                if attr.voice:
                    return "voice"
                return "audio"
            if isinstance(attr, DocumentAttributeSticker):
                return "stickers"
        return "files"

    if isinstance(msg.media, MessageMediaWebPage):
        return "text"

    return "text"


def get_file_extension(msg) -> str:
    """استخراج امتداد الملف"""
    if not msg.media:
        return ".txt"

    if isinstance(msg.media, MessageMediaPhoto):
        return ".jpg"

    if isinstance(msg.media, MessageMediaDocument):
        doc = msg.media.document
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                ext = os.path.splitext(attr.file_name)[1]
                if ext:
                    return ext
        # من mime_type
        mime = getattr(doc, "mime_type", "")
        mime_map = {
            "video/mp4":        ".mp4",
            "video/avi":        ".avi",
            "video/mkv":        ".mkv",
            "audio/mpeg":       ".mp3",
            "audio/ogg":        ".ogg",
            "audio/wav":        ".wav",
            "image/jpeg":       ".jpg",
            "image/png":        ".png",
            "image/gif":        ".gif",
            "application/pdf":  ".pdf",
            "application/zip":  ".zip",
        }
        return mime_map.get(mime, ".bin")

    return ".bin"


def get_file_name(msg, message_type: str) -> str:
    """استخراج اسم الملف"""
    if isinstance(msg.media, MessageMediaDocument):
        doc = msg.media.document
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                return attr.file_name

    ext = get_file_extension(msg)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{message_type}_{msg.id}_{timestamp}{ext}"


def get_download_path(owner_id: int,
                      chat_id: int,
                      message_type: str,
                      file_name: str) -> str:
    """بناء مسار حفظ الملف"""
    folder = os.path.join(
        config.DOWNLOAD_PATH,
        message_type,
        str(owner_id),
        str(abs(chat_id))
    )
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, file_name)


# ==================== التحقق من الصلاحيات ====================

def is_owner(user_id: int) -> bool:
    """التحقق إذا كان المالك"""
    return user_id == config.OWNER_ID


async def check_permission(user_id: int, db,
                           permission: str = None) -> bool:
    """التحقق من صلاحيات المستخدم"""
    if is_owner(user_id):
        return True

    admin = await db.get_admin(user_id)
    if not admin:
        return False

    if permission is None:
        return True

    permissions = admin.get("permissions", {})
    if isinstance(permissions, str):
        permissions = json.loads(permissions)

    return permissions.get(permission, False)


# ==================== بناء الرسائل ====================

def build_stats_message(stats: dict,
                        chat_name: str = "") -> str:
    """بناء رسالة الإحصائيات"""
    total = stats.get("total", 0)
    text = stats.get("text", 0)
    photos = stats.get("photos", 0)
    videos = stats.get("videos", 0)
    files = stats.get("files", 0)
    audio = stats.get("audio", 0)
    voice = stats.get("voice", 0)
    stickers = stats.get("stickers", 0)
    size = stats.get("total_size", 0)

    msg = (
        f"📊 **إحصائيات**"
        f"{f' - {chat_name}' if chat_name else ''}\n\n"
        f"📝 نصوص:          `{format_number(text)}`\n"
        f"🖼️ صور:            `{format_number(photos)}`\n"
        f"🎥 فيديوهات:      `{format_number(videos)}`\n"
        f"📁 ملفات:          `{format_number(files)}`\n"
        f"🎵 صوتيات:        `{format_number(audio)}`\n"
        f"🎤 رسائل صوتية:  `{format_number(voice)}`\n"
        f"🎭 ملصقات:        `{format_number(stickers)}`\n"
        f"{'─' * 30}\n"
        f"📦 المجموع:       `{format_number(total)}`\n"
        f"💾 الحجم الكلي:   `{format_size(size)}`\n"
    )
    return msg


def build_progress_bar(current: int, total: int,
                       length: int = 10) -> str:
    """بناء شريط التقدم"""
    if total == 0:
        return "⬜" * length + " 0%"

    percent = min(int((current / total) * 100), 100)
    filled = int(length * current / total)
    filled = min(filled, length)
    empty = length - filled

    bar = "⬛" * filled + "⬜" * empty
    return f"{bar} {percent}%"


def build_fetch_progress_message(
        chat_name: str,
        current: int,
        total: int,
        content_type: str,
        stats: dict) -> str:
    """بناء رسالة تقدم الجلب"""
    bar = build_progress_bar(current, total)
    content_name = config.CONTENT_TYPES.get(content_type, content_type)

    msg = (
        f"🔄 **جاري الجلب...**\n\n"
        f"📢 القناة: `{chat_name}`\n"
        f"📌 النوع: `{content_name}`\n\n"
        f"**التقدم:**\n"
        f"{bar}\n"
        f"`{format_number(current)}` / `{format_number(total)}`\n\n"
        f"📝 نصوص:    `{stats.get('text', 0)}`\n"
        f"🖼️ صور:      `{stats.get('photos', 0)}`\n"
        f"🎥 فيديو:   `{stats.get('videos', 0)}`\n"
        f"📁 ملفات:   `{stats.get('files', 0)}`\n"
    )
    return msg


def build_archive_summary(archive: dict) -> str:
    """بناء ملخص الأرشيف"""
    status_map = {
        "completed": "✅ مكتمل",
        "pending":   "⏳ في الانتظار",
        "running":   "🔄 جاري",
        "failed":    "❌ فشل",
    }
    status = status_map.get(archive.get("status", ""), "❓")
    content_name = config.CONTENT_TYPES.get(
        archive.get("content_type", ""), "غير معروف"
    )

    msg = (
        f"📦 **تفاصيل الأرشيف**\n\n"
        f"📢 القناة:    `{archive.get('chat_title', '')}`\n"
        f"📌 النوع:     `{content_name}`\n"
        f"📊 الحالة:    {status}\n"
        f"💬 الرسائل:  "
        f"`{format_number(archive.get('fetched_messages', 0))}`\n"
        f"📅 التاريخ:  "
        f"`{format_date(archive.get('started_at'))}`\n"
    )
    return msg


def build_welcome_message(full_name: str,
                          is_new: bool = True) -> str:
    """بناء رسالة الترحيب"""
    if is_new:
        return (
            f"👋 مرحباً **{full_name}**!\n\n"
            f"🤖 أنا بوت أرشفة تيليغرام\n\n"
            f"**ماذا أستطيع أن أفعل؟**\n"
            f"📋 جلب وأرشفة محتوى قنواتك\n"
            f"🖼️ حفظ الصور والفيديوهات والملفات\n"
            f"🤖 تلخيص وتصنيف المحتوى بالذكاء الاصطناعي\n"
            f"📊 إحصائيات تفصيلية\n"
            f"🔍 بحث في المحتوى المحفوظ\n\n"
            f"📱 ابدأ بتسجيل الدخول بحسابك 👇"
        )
    return (
        f"👋 أهلاً مجدداً **{full_name}**!\n\n"
        f"اختر ما تريد من القائمة 👇"
    )


# ==================== دوال مساعدة ====================

def clean_text(text: str) -> str:
    """تنظيف النص"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def truncate_text(text: str, max_length: int = 100) -> str:
    """اختصار النص الطويل"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def safe_filename(filename: str) -> str:
    """تنظيف اسم الملف من الرموز غير المسموحة"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip('. ')
    return filename[:255] if len(filename) > 255 else filename


def chunk_list(lst: list, chunk_size: int) -> list:
    """تقسيم القائمة إلى أجزاء"""
    return [
        lst[i:i + chunk_size]
        for i in range(0, len(lst), chunk_size)
    ]


def get_chat_type(entity) -> str:
    """تحديد نوع المحادثة"""
    from telethon.tl.types import Channel, Chat, User
    if isinstance(entity, Channel):
        return "channel" if entity.broadcast else "group"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, User):
        return "private"
    return "unknown"


def extract_username(entity) -> Optional[str]:
    """استخراج يوزرنيم"""
    username = getattr(entity, "username", None)
    if username:
        return f"@{username}"
    return None


def get_members_count(entity) -> int:
    """استخراج عدد الأعضاء"""
    return getattr(
        entity,
        "participants_count",
        getattr(entity, "members_count", 0)
    ) or 0


async def safe_edit_message(message, text: str,
                            reply_markup=None,
                            parse_mode: str = "Markdown"):
    """تعديل رسالة بشكل آمن"""
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception:
        try:
            await message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception:
            pass


async def safe_delete_message(message):
    """حذف رسالة بشكل آمن"""
    try:
        await message.delete()
    except Exception:
        pass
