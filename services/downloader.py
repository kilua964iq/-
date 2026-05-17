import os
import asyncio
import aiofiles
import zipfile
import shutil
from typing import Optional, List
from datetime import datetime, timedelta
from config import config
from utils.logger import bot_logger, error_logger
from utils.helpers import (
    format_size,
    safe_filename,
    get_download_path,
)


# ==================== إدارة التحميل ====================

class DownloadManager:
    """إدارة تحميل وحفظ الملفات"""

    def __init__(self):
        self.active_downloads = {}
        self.download_stats = {}

    # ==================== حفظ النصوص ====================

    async def save_text(
            self,
            owner_id: int,
            chat_id: int,
            message_id: int,
            text: str,
            date: datetime = None) -> Optional[str]:
        """حفظ نص رسالة"""
        try:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                "text",
                str(owner_id),
                str(abs(chat_id))
            )
            os.makedirs(folder, exist_ok=True)

            file_name = f"msg_{message_id}.txt"
            file_path = os.path.join(folder, file_name)

            content = (
                f"تاريخ: {date}\n"
                f"{'─' * 40}\n"
                f"{text}\n"
            )

            async with aiofiles.open(
                file_path, "w", encoding="utf-8"
            ) as f:
                await f.write(content)

            return file_path

        except Exception as e:
            error_logger.log_exception(
                e, "save_text", owner_id
            )
            return None

    # ==================== حفظ الميديا ====================

    async def save_media(
            self,
            owner_id: int,
            chat_id: int,
            file_data: bytes,
            file_name: str,
            media_type: str) -> Optional[str]:
        """حفظ ملف ميديا"""
        try:
            # التحقق من الحجم
            size_mb = len(file_data) / (1024 * 1024)
            if size_mb > config.MAX_DOWNLOAD_SIZE:
                bot_logger.warning(
                    f"⚠️ الملف كبير جداً: {size_mb:.1f}MB"
                )
                return None

            folder = os.path.join(
                config.DOWNLOAD_PATH,
                media_type,
                str(owner_id),
                str(abs(chat_id))
            )
            os.makedirs(folder, exist_ok=True)

            safe_name = safe_filename(file_name)
            file_path = os.path.join(folder, safe_name)

            # تجنب التكرار
            if os.path.exists(file_path):
                return file_path

            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_data)

            bot_logger.debug(
                f"✅ تم حفظ {safe_name} "
                f"({format_size(len(file_data))})"
            )
            return file_path

        except Exception as e:
            error_logger.log_exception(
                e, "save_media", owner_id
            )
            return None

    # ==================== تحميل متوازي ====================

    async def download_multiple(
            self,
            tasks: List[dict],
            max_concurrent: int = 3,
            progress_callback=None) -> List[dict]:
        """تحميل عدة ملفات بشكل متوازي"""

        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        completed = 0

        async def download_one(task: dict) -> dict:
            nonlocal completed
            async with semaphore:
                try:
                    result = await self._process_download(task)
                    completed += 1

                    if progress_callback:
                        await progress_callback(
                            completed,
                            len(tasks)
                        )

                    return result
                except Exception as e:
                    error_logger.log_exception(
                        e, "download_one"
                    )
                    return {
                        "success": False,
                        "error": str(e),
                        "task": task
                    }

        download_tasks = [
            download_one(task) for task in tasks
        ]
        results = await asyncio.gather(*download_tasks)

        return list(results)

    async def _process_download(
            self, task: dict) -> dict:
        """معالجة تحميل واحد"""
        owner_id = task.get("owner_id")
        chat_id = task.get("chat_id")
        file_data = task.get("file_data")
        file_name = task.get("file_name")
        media_type = task.get("media_type", "files")

        if not file_data:
            return {"success": False, "error": "no_data"}

        file_path = await self.save_media(
            owner_id, chat_id,
            file_data, file_name, media_type
        )

        if file_path:
            return {
                "success": True,
                "file_path": file_path,
                "file_name": file_name,
                "size": len(file_data),
            }

        return {"success": False, "error": "save_failed"}

    # ==================== ضغط الملفات ====================

    async def create_zip(
            self,
            owner_id: int,
            archive_id: int,
            file_paths: List[str],
            zip_name: str = None) -> Optional[str]:
        """إنشاء ملف ZIP"""
        try:
            if not file_paths:
                return None

            folder = os.path.join(
                config.DOWNLOAD_PATH,
                "exports",
                str(owner_id)
            )
            os.makedirs(folder, exist_ok=True)

            if not zip_name:
                timestamp = datetime.now().strftime(
                    "%Y%m%d_%H%M%S"
                )
                zip_name = f"archive_{archive_id}_{timestamp}.zip"

            zip_path = os.path.join(folder, zip_name)

            def create_zip_sync():
                with zipfile.ZipFile(
                    zip_path, "w",
                    zipfile.ZIP_DEFLATED
                ) as zf:
                    for file_path in file_paths:
                        if os.path.exists(file_path):
                            arcname = os.path.basename(
                                file_path
                            )
                            zf.write(file_path, arcname)

            await asyncio.get_event_loop().run_in_executor(
                None, create_zip_sync
            )

            zip_size = os.path.getsize(zip_path)
            bot_logger.info(
                f"✅ تم إنشاء ZIP: {zip_name} "
                f"({format_size(zip_size)})"
            )

            return zip_path

        except Exception as e:
            error_logger.log_exception(
                e, "create_zip", owner_id
            )
            return None

    async def create_archive_zip(
            self,
            owner_id: int,
            chat_id: int,
            archive_id: int) -> Optional[str]:
        """ضغط كل ملفات أرشيف معين"""
        try:
            base_folder = os.path.join(
                config.DOWNLOAD_PATH
            )

            all_files = []
            media_types = [
                "photos", "videos", "files",
                "audio", "voice", "text"
            ]

            for media_type in media_types:
                folder = os.path.join(
                    base_folder,
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

            return await self.create_zip(
                owner_id, archive_id, all_files
            )

        except Exception as e:
            error_logger.log_exception(
                e, "create_archive_zip", owner_id
            )
            return None

    # ==================== إحصائيات التخزين ====================

    def get_folder_size(self, folder: str) -> int:
        """حساب حجم مجلد"""
        total = 0
        if not os.path.exists(folder):
            return 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total += os.path.getsize(filepath)
                except OSError:
                    pass
        return total

    def get_user_storage(self, owner_id: int) -> dict:
        """إحصائيات تخزين مستخدم"""
        stats = {}
        total = 0

        media_types = [
            "photos", "videos", "files",
            "audio", "voice", "text", "stickers"
        ]

        for media_type in media_types:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                media_type,
                str(owner_id)
            )
            size = self.get_folder_size(folder)
            count = self._count_files(folder)
            stats[media_type] = {
                "size": size,
                "size_formatted": format_size(size),
                "count": count,
            }
            total += size

        stats["total"] = {
            "size": total,
            "size_formatted": format_size(total),
        }

        return stats

    def _count_files(self, folder: str) -> int:
        """عد الملفات في مجلد"""
        if not os.path.exists(folder):
            return 0
        count = 0
        for _, _, files in os.walk(folder):
            count += len(files)
        return count

    def get_file_count(
            self,
            owner_id: int,
            media_type: str = None,
            chat_id: int = None) -> int:
        """عد الملفات"""
        if media_type and chat_id:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                media_type,
                str(owner_id),
                str(abs(chat_id))
            )
        elif media_type:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                media_type,
                str(owner_id)
            )
        else:
            folder = os.path.join(
                config.DOWNLOAD_PATH,
                str(owner_id)
            )
        return self._count_files(folder)

    # ==================== تنظيف الملفات ====================

    async def cleanup_old_files(
            self,
            owner_id: int,
            days: int = 30) -> dict:
        """حذف الملفات القديمة"""
        deleted_count = 0
        deleted_size = 0
        cutoff = datetime.now() - timedelta(days=days)

        base_folder = os.path.join(
            config.DOWNLOAD_PATH,
            "*",
            str(owner_id)
        )

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
                            deleted_size += size
                    except OSError:
                        pass

        bot_logger.info(
            f"🗑️ تم حذف {deleted_count} ملف "
            f"({format_size(deleted_size)}) "
            f"للمستخدم {owner_id}"
        )

        return {
            "deleted_count": deleted_count,
            "deleted_size": deleted_size,
            "deleted_size_formatted": format_size(deleted_size),
        }

    async def delete_archive_files(
            self,
            owner_id: int,
            chat_id: int) -> bool:
        """حذف كل ملفات أرشيف معين"""
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

            bot_logger.info(
                f"🗑️ تم حذف ملفات الأرشيف "
                f"chat={chat_id} user={owner_id}"
            )
            return True

        except Exception as e:
            error_logger.log_exception(
                e, "delete_archive_files", owner_id
            )
            return False

    # ==================== التحقق من الملفات ====================

    def file_exists(self, file_path: str) -> bool:
        """التحقق من وجود ملف"""
        return os.path.exists(file_path)

    def get_file_size(self, file_path: str) -> int:
        """حجم ملف"""
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0

    def is_size_allowed(self, size_bytes: int) -> bool:
        """التحقق من حجم الملف"""
        size_mb = size_bytes / (1024 * 1024)
        return size_mb <= config.MAX_DOWNLOAD_SIZE

    async def get_all_files(
            self,
            owner_id: int,
            archive_id: int,
            chat_id: int,
            media_type: str = None) -> List[str]:
        """جلب كل مسارات الملفات"""
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
