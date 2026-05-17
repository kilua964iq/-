import os
import re
import json
import humanize
import pytz
from datetime import datetime
from typing import Optional
from config import config


# ==================== تنسيق الأرقام ====================

def format_number(number: int) -> str:
    """تنسيق الأرقام الكبيرة"""
    if number is None:
        return "0"
    return humanize.intcomma(number)


def format_size(size_bytes: int) -> str:
    """تنسيق حجم الملف"""
    if size_bytes is None:
        return "0 B"
    return humanize.naturalsize(size_bytes, binary=True)


def format_date(dt: datetime,
                timezone: str = "Asia/Baghdad") -> str:
    """تنسيق التاريخ"""
    if not dt:
        return "غير معروف"
    try:
        tz = pytz.timezone(timezone)
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        local_dt = dt.astimezone(tz)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt)


def format_duration(seconds: int) -> str:
    """تنسيق المدة الزمنية"""
    return humanize.naturaldelta(seconds)


def time_ago(dt: datetime) -> str:
    """منذ كم وقت"""
    if not dt:
        return "غير معروف"
    try:
        return humanize.naturaltime(dt)
    except Exception:
        return str(dt)


# ==================== تصفية ذكية ====================

def extract_card_numbers(text: str) -> list:
    """استخراج أرقام البطاقات البنكية"""
    if not text:
        return []
    patterns = [
        r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b',
        r'\b\d{16}\b',
        r'\b\d{4}[\s\-]?\d{6}[\s\-]?\d{5}\b',
    ]
    results = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        results.extend(matches)
    return list(set(results))


def extract_phone_numbers(text: str) -> list:
    """استخراج أرقام الهواتف"""
    if not text:
        return []
    patterns = [
        r'\+?964\d{10}',
        r'\+?1?\d{10,11}',
        r'\b07\d{9}\b',
        r'\+\d{1,3}\s?\d{4,14}',
    ]
    results = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        results.extend(matches)
    return list(set(results))


def extract_emails(text: str) -> list:
    """استخراج الإيميلات"""
    if not text:
        return []
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return list(set(re.findall(pattern, text)))


def extract_urls(text: str) -> list:
    """استخراج الروابط"""
    if not text:
        return []
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return list(set(re.findall(pattern, text)))


def smart_extract(text: str,
                  extract_type: str = "all") -> dict:
    """استخراج ذكي للبيانات من النص"""
    if not text:
        return {}

    result = {}

    if extract_type in ["all", "cards"]:
        cards = extract_card_numbers(text)
        if cards:
            result["cards"] = cards

    if extract_type in ["all", "phones"]:
        phones = extract_phone_numbers(text)
        if phones:
            result["phones"] = phones

    if extract_type in ["all", "emails"]:
        emails = extract_emails(text)
        if emails:
            result["emails"] = emails

    if extract_type in ["all", "urls"]:
        urls = extract_urls(text)
        if urls:
            result["urls"] = urls

    return result


def clean_text(text: str) -> str:
    """تنظيف النص من الرموز الزائدة"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()


def format_extracted_data(data: dict,
                          chat_title: str = "") -> str:
    """تنسيق البيانات المستخرجة كنص"""
    if not data:
        return ""

    lines = []
    if chat_title:
        lines.append(f"القناة: {chat_title}")
        lines.append("=" * 40)

    if "cards" in data:
        lines.append("\n💳 أرقام البطاقات:")
        for card in data["cards"]:
            lines.append(f"  {card}")

    if "phones" in data:
        lines.append("\n📱 أرقام الهواتف:")
        for phone in data["phones"]:
            lines.append(f"  {phone}")

    if "emails" in data:
        lines.append("\n📧 الإيميلات:")
        for email in data["emails"]:
            lines.append(f"  {email}")

    if "urls" in data:
        lines.append("\n🔗 الروابط:")
        for url in data["urls"]:
            lines.append(f"  {url}")

    return "\n".join(lines)


# ==================== حفظ كـ TXT ====================

async def save_as_txt(
        texts: list,
        owner_id: int,
        chat_title: str,
        file_type: str = "messages") -> str:
    """حفظ النصوص كملف txt"""
    import aiofiles

    folder = os.path.join(
        config.DOWNLOAD_PATH,
        "txt",
        str(owner_id)
    )
    os.makedirs(folder, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', chat_title)
    file_name = f"{safe_title}_{file_type}_{timestamp}.txt"
    file_path = os.path.join(folder, file_name)

    content = (
        f"القناة: {chat_title}\n"
        f"النوع: {file_type}\n"
        f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"عدد العناصر: {len(texts)}\n"
        f"{'=' * 50}\n\n"
    )

    for i, text in enumerate(texts, 1):
        if isinstance(text, dict):
            content += f"[{i}]\n"
            content += format_extracted_data(text) + "\n"
        else:
            content += f"[{i}] {clean_text(str(text))}\n"
        content += "-" * 30 + "\n"

    async with aiofiles.open(
        file_path, "w", encoding="utf-8"
    ) as f:
        await f.write(content)

    return file_path


# ==================== تصنيف الرسائل ====================

def classify_message(msg) -> str:
    """تصنيف نوع الرسالة"""
    try:
        from telethon.tl.types import (
            MessageMediaPhoto,
            MessageMediaDocument,
            MessageMediaWebPage,
            DocumentAttributeVideo,
            DocumentAttributeAudio,
            DocumentAttributeSticker,
        )

        if msg.media is None:
            return "text"

        if isinstance(msg.media, MessageMediaPhoto):
            return "photos"

        if isinstance(msg.media, MessageMediaDocument):
            doc = msg.media.document
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeVideo):
                    return "videos"
                if isinstance(attr, DocumentAttributeAudio):
                    return "voice" if attr.voice else "audio"
                if isinstance(attr, DocumentAttributeSticker):
                    return "stickers"
            return "files"

        if isinstance(msg.media, MessageMediaWebPage):
            return "text"

        return "text"
    except Exception:
        return "text"


def get_file_extension(msg) -> str:
    """استخراج امتداد الملف"""
    try:
        from telethon.tl.types import (
            MessageMediaPhoto,
            MessageMediaDocument,
            DocumentAttributeFilename,
        )

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
            mime = getattr(doc, "mime_type", "")
            mime_map = {
                "video/mp4":       ".mp4",
                "video/avi":       ".avi",
                "audio/mpeg":      ".mp3",
                "audio/ogg":       ".ogg",
                "image/jpeg":      ".jpg",
                "image/png":       ".png",
                "application/pdf": ".pdf",
                "application/zip": ".zip",
            }
            return mime_map.get(mime, ".bin")
    except Exception:
        pass
    return ".bin"


def get_file_name(msg, message_type: str) -> str:
    """استخراج اسم الملف"""
    try:
        from telethon.tl.types import (
            MessageMediaDocument,
            DocumentAttributeFilename,
        )
        if isinstance(msg.media, MessageMediaDocument):
            doc = msg.media.document
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    return attr.file_name
    except Exception:
        pass

    ext = get_file_extension(msg)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{message_type}_{msg.id}_{timestamp}{ext}"


def get_download_path(
        owner_id: int,
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


async def check_permission(
        user_id: int,
        db,
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

def build_progress_bar(
        current: int,
        total: int,
        length: int = 10) -> str:
    """بناء شريط التقدم"""
    if total == 0:
        return "⬜" * length + " 0%"

    percent = min(int((current / total) * 100), 100)
    filled = min(int(length * current / total), length)
    empty = length - filled

    bar = "⬛" * filled + "⬜" * empty
    return f"{bar} {percent}%"


def build_stats_message(
        stats: dict,
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
        f"📊 إحصائيات"
        f"{f' - {chat_name}' if chat_name else ''}\n\n"
        f"📝 نصوص:         {format_number(text)}\n"
        f"🖼️ صور:           {format_number(photos)}\n"
        f"🎥 فيديوهات:     {format_number(videos)}\n"
        f"📁 ملفات:         {format_number(files)}\n"
        f"🎵 صوتيات:       {format_number(audio)}\n"
        f"🎤 رسائل صوتية: {format_number(voice)}\n"
        f"🎭 ملصقات:       {format_number(stickers)}\n"
        f"{'─' * 30}\n"
        f"📦 المجموع:      {format_number(total)}\n"
        f"💾 الحجم الكلي:  {format_size(size)}\n"
    )
    return msg


def build_fetch_progress_message(
        chat_title: str,
        current: int,
        total: int,
        content_type: str,
        stats: dict) -> str:
    """بناء رسالة تقدم الجلب"""
    bar = build_progress_bar(current, total)
    content_name = config.CONTENT_TYPES.get(
        content_type, content_type
    )

    msg = (
        f"🔄 جاري الجلب...\n\n"
        f"📢 القناة: {chat_title}\n"
        f"📌 النوع: {content_name}\n\n"
        f"التقدم:\n"
        f"{bar}\n"
        f"{format_number(current)}"
        f"{f' / {format_number(total)}' if total > 0 else ''}\n\n"
        f"📝 نصوص:  {stats.get('text', 0)}\n"
        f"🖼️ صور:    {stats.get('photos', 0)}\n"
        f"🎥 فيديو: {stats.get('videos', 0)}\n"
        f"📁 ملفات: {stats.get('files', 0)}\n"
    )
    return msg


def get_chat_type(entity) -> str:
    """تحديد نوع المحادثة"""
    try:
        from telethon.tl.types import Channel, Chat, User
        if isinstance(entity, Channel):
            return "channel" if entity.broadcast else "group"
        if isinstance(entity, Chat):
            return "group"
        if isinstance(entity, User):
            return "private"
    except Exception:
        pass
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


def safe_filename(filename: str) -> str:
    """تنظيف اسم الملف"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip('. ')
    return filename[:255] if len(filename) > 255 else filename


def chunk_list(lst: list, chunk_size: int) -> list:
    """تقسيم القائمة إلى أجزاء"""
    return [
        lst[i:i + chunk_size]
        for i in range(0, len(lst), chunk_size)
    ]
