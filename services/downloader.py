import os
import asyncio
import aiofiles
import zipfile
import shutil
import re
from typing import Optional, List
from datetime import datetime, timedelta
from config import config
from utils.logger import bot_logger, error_logger
from utils.helpers import (
    format_size,
    safe_filename,
    smart_extract,
    format_extracted_data,
    clean_text,
)


class DownloadManager:

    # ==================== تصدير TXT ====================

    async def export_messages_as_txt(
            self,
            owner_id: int,
            archive_id: int,
            chat_title: str,
            messages: list,
            extract_smart: bool = False) -> Optional[str]:
        try:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                "txt",
                str(owner_id)
            )
            os.makedirs(folder, exist_ok=True)

            timestamp  = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
            safe_title = safe_filename(chat_title)
            file_name  = (
                f"{safe_title}_{archive_id}"
                f"_{timestamp}.txt"
            )
            file_path = os.path.join(folder, file_name)

            content = (
                f"{'=' * 50}\n"
                f"القناة: {chat_title}\n"
                f"الأرشيف: {archive_id}\n"
                f"التاريخ: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"عدد الرسائل: {len(messages)}\n"
                f"{'=' * 50}\n\n"
            )

            for i, msg in enumerate(messages, 1):
                text = msg.get("text", "") or ""
                date = msg.get("date", "")

                if not text:
                    continue

                content += f"[{i}] {date}\n"
                content += f"{clean_text(text)}\n"

                if extract_smart and text:
                    extracted = smart_extract(text)
                    if extracted:
                        content += "\n📌 بيانات مستخرجة:\n"
                        content += format_extracted_data(
                            extracted
                        )
                        content += "\n"

                content += "─" * 40 + "\n"

            async with aiofiles.open(
                file_path, "w", encoding="utf-8"
            ) as f:
                await f.write(content)

            return file_path

        except Exception as e:
            error_logger.log_exception(
                e, "export_messages_as_txt", owner_id
            )
            return None

    # ==================== استخراج ذكي ====================

    async def extract_and_export(
            self,
            owner_id: int,
            archive_id: int,
            chat_title: str,
            messages: list,
            extract_type: str = "all") -> Optional[str]:
        try:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                "txt",
                str(owner_id)
            )
            os.makedirs(folder, exist_ok=True)

            timestamp  = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
            safe_title = safe_filename(chat_title)
            file_name  = (
                f"{safe_title}_extracted"
                f"_{timestamp}.txt"
            )
            file_path = os.path.join(folder, file_name)

            all_cards  = []
            all_phones = []
            all_emails = []
            all_urls   = []

            for msg in messages:
                text = msg.get("text", "") or ""
                if not text:
                    continue

                extracted = smart_extract(text, extract_type)

                if "cards" in extracted:
                    all_cards.extend(extracted["cards"])
                if "phones" in extracted:
                    all_phones.extend(extracted["phones"])
                if "emails" in extracted:
                    all_emails.extend(extracted["emails"])
                if "urls" in extracted:
                    all_urls.extend(extracted["urls"])

            all_cards  = list(set(all_cards))
            all_phones = list(set(all_phones))
            all_emails = list(set(all_emails))
            all_urls   = list(set(all_urls))

            content = (
                f"{'=' * 50}\n"
                f"القناة: {chat_title}\n"
                f"نوع الاستخراج: {extract_type}\n"
                f"التاريخ: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{'=' * 50}\n\n"
            )

            if all_cards:
                content += (
                    f"💳 أرقام البطاقات "
                    f"({len(all_cards)}):\n"
                    f"{'─' * 30}\n"
                )
                for card in all_cards:
                    content += f"{card}\n"
                content += "\n"

            if all_phones:
                content += (
                    f"📱 أرقام الهواتف "
                    f"({len(all_phones)}):\n"
                    f"{'─' * 30}\n"
                )
                for phone in all_phones:
                    content += f"{phone}\n"
                content += "\n"

            if all_emails:
                content += (
                    f"📧 الإيميلات "
                    f"({len(all_emails)}):\n"
                    f"{'─' * 30}\n"
                )
                for email in all_emails:
                    content += f"{email}\n"
                content += "\n"

            if all_urls:
                content += (
                    f"🔗 الروابط "
                    f"({len(all_urls)}):\n"
                    f"{'─' * 30}\n"
                )
                for url in all_urls:
                    content += f"{url}\n"
                content += "\n"

            if not any([
                all_cards, all_phones,
                all_emails, all_urls
            ]):
                content += "❌ لم يتم العثور على بيانات\n"

            async with aiofiles.open(
                file_path, "w", encoding="utf-8"
            ) as f:
                await f.write(content)

            return file_path

        except Exception as e:
            error_logger.log_exception(
                e, "extract_and_export", owner_id
            )
            return None

    # ==================== ضغط الملفات ====================

    async def create_archive_zip(
            self,
            owner_id: int,
            chat_id: int,
            archive_id: int) -> Optional[str]:
        try:
            all_files   = []
            media_types = [
                "photos", "videos", "files",
                "audio", "voice", "text"
            ]

            for media_type in media_types:
                folder = os.path.join(
                    config.DOWNLOAD_PATH,
                    media_type,
                    str(owner_id),
                    str(abs(chat_id))
                )
                if os.path.exists(folder):
                    for f in os.listdir(folder):
                        all_files.append(
                            os.path.join(folder, f)
                        )

            if not all_files:
                return None

            folder = os.path.join(
                config.DOWNLOAD_PATH,
                "exports",
                str(owner_id)
            )
            os.makedirs(folder, exist_ok=True)

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
            zip_name = (
                f"archive_{archive_id}_{timestamp}.zip"
            )
            zip_path = os.path.join(folder, zip_name)

            def create_zip_sync():
                with zipfile.ZipFile(
                    zip_path, "w",
                    zipfile.ZIP_DEFLATED
                ) as zf:
                    for file_path in all_files:
                        if os.path.exists(file_path):
                            arcname = os.path.basename(
                                file_path
                            )
                            zf.write(file_path, arcname)

            await asyncio.get_event_loop().run_in_executor(
                None, create_zip_sync
            )

            return zip_path

        except Exception as e:
            error_logger.log_exception(
                e, "create_archive_zip", owner_id
            )
            return None

    # ==================== إحصائيات ====================

    def get_folder_size(self, folder: str) -> int:
        total = 0
        if not os.path.exists(folder):
            return 0
        for dirpath, _, filenames in os.walk(folder):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total += os.path.getsize(filepath)
                except OSError:
                    pass
        return total

    def get_user_storage(self, owner_id: int) -> dict:
        stats = {}
        total = 0

        media_types = [
            "photos", "videos", "files",
            "audio", "voice", "text",
            "stickers", "txt"
        ]

        for media_type in media_types:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                media_type,
                str(owner_id)
            )
            size  = self.get_folder_size(folder)
            count = self._count_files(folder)
            stats[media_type] = {
                "size":           size,
                "size_formatted": format_size(size),
                "count":          count,
            }
            total += size

        stats["total"] = {
            "size":           total,
            "size_formatted": format_size(total),
        }
        return stats

    def _count_files(self, folder: str) -> int:
        if not os.path.exists(folder):
            return 0
        count = 0
        for _, _, files in os.walk(folder):
            count += len(files)
        return count

    def get_file_size(self, file_path: str) -> int:
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0

    # ==================== تنظيف ====================

    async def cleanup_old_files(
            self,
            owner_id: int,
            days: int = 30) -> dict:
        deleted_count = 0
        deleted_size  = 0
        cutoff = datetime.now() - timedelta(days=days)

        media_types = [
            "photos", "videos", "files",
            "audio", "voice", "text"
        ]

        for media_type in media_types:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                media_type,
                str(owner_id)
            )
            if not os.path.exists(folder):
                continue

            for dirpath, _, filenames in os.walk(folder):
                for filename in filenames:
                    filepath = os.path.join(
                        dirpath, filename
                    )
                    try:
                        mtime = datetime.fromtimestamp(
                            os.path.getmtime(filepath)
                        )
                        if mtime < cutoff:
                            size = os.path.getsize(filepath)
                            os.remove(filepath)
                            deleted_count += 1
                            deleted_size  += size
                    except OSError:
                        pass

        return {
            "deleted_count":          deleted_count,
            "deleted_size":           deleted_size,
            "deleted_size_formatted": format_size(
                deleted_size
            ),
        }

    async def delete_archive_files(
            self,
            owner_id: int,
            chat_id: int) -> bool:
        try:
            media_types = [
                "photos", "videos", "files",
                "audio", "voice", "text", "stickers"
            ]

            for media_type in media_types:
                folder = os.path.join(
                    config.DOWNLOAD_PATH,
                    media_type,
                    str(owner_id),
                    str(abs(chat_id))
                )
                if os.path.exists(folder):
                    shutil.rmtree(folder)

            return True

        except Exception as e:
            error_logger.log_exception(
                e, "delete_archive_files", owner_id
            )
            return False

    async def get_all_files(
            self,
            owner_id: int,
            chat_id: int,
            media_type: str = None) -> List[str]:
        files = []
        media_types = (
            [media_type] if media_type
            else [
                "photos", "videos", "files",
                "audio", "voice", "text"
            ]
        )

        for mt in media_types:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                mt,
                str(owner_id),
                str(abs(chat_id))
            )
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    full_path = os.path.join(folder, f)
                    if os.path.isfile(full_path):
                        files.append(full_path)

        return files


# ==================== Instance ====================

download_manager = DownloadManager()
