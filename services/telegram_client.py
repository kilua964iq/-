import asyncio
import os
from typing import Optional, AsyncGenerator
from telethon import TelegramClient
from telethon.tl.types import (
    Channel, Chat, User,
    MessageMediaPhoto,
    MessageMediaDocument,
)
from telethon.errors import (
    FloodWaitError,
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    AuthKeyUnregisteredError,
)
from config import config
from utils.logger import (
    bot_logger,
    activity_logger,
    error_logger,
)
from utils.helpers import (
    get_chat_type,
    get_members_count,
    extract_username,
    classify_message,
    get_file_name,
    get_download_path,
)


# ==================== إدارة العملاء ====================

class ClientManager:
    """إدارة عملاء Telethon لكل مستخدم"""

    def __init__(self):
        self._clients = {}

    def get_session_path(self, user_id: int) -> str:
        os.makedirs(config.SESSION_PATH, exist_ok=True)
        return os.path.join(
            config.SESSION_PATH,
            f"user_{user_id}"
        )

    async def get_client(
            self, user_id: int) -> TelegramClient:
        """الحصول على client أو إنشاء جديد"""
        if user_id in self._clients:
            client = self._clients[user_id]
            if client.is_connected():
                return client
            await client.connect()
            return client

        session_path = self.get_session_path(user_id)
        client = TelegramClient(
            session_path,
            config.API_ID,
            config.API_HASH,
            flood_sleep_threshold=config.FLOOD_SLEEP_THRESHOLD,
            connection_retries=5,
            retry_delay=1,
            auto_reconnect=True,
        )
        await client.connect()
        self._clients[user_id] = client
        return client

    async def disconnect_client(self, user_id: int):
        """قطع اتصال client"""
        if user_id in self._clients:
            client = self._clients[user_id]
            if client.is_connected():
                await client.disconnect()
            del self._clients[user_id]

    async def is_authorized(
            self, user_id: int) -> bool:
        """التحقق من تسجيل الدخول"""
        try:
            client = await self.get_client(user_id)
            return await client.is_user_authorized()
        except Exception:
            return False

    async def disconnect_all(self):
        """قطع كل الاتصالات"""
        for user_id in list(self._clients.keys()):
            await self.disconnect_client(user_id)


# ==================== خدمة تيليغرام ====================

class TelegramService:
    """خدمة تيليغرام الكاملة"""

    def __init__(self):
        self.manager = ClientManager()

    # ==================== تسجيل الدخول ====================

    async def send_code(
            self,
            user_id: int,
            phone: str) -> dict:
        """إرسال كود التحقق"""
        try:
            client = await self.manager.get_client(user_id)
            result = await client.send_code_request(phone)
            bot_logger.info(
                f"✅ تم إرسال الكود للمستخدم {user_id}"
            )
            return {
                "success": True,
                "phone_code_hash": result.phone_code_hash
            }
        except PhoneNumberInvalidError:
            return {
                "success": False,
                "error": "phone_invalid",
                "message": "رقم الهاتف غير صحيح"
            }
        except FloodWaitError as e:
            error_logger.log_flood_wait(e.seconds, user_id)
            return {
                "success": False,
                "error": "flood_wait",
                "message": f"انتظر {e.seconds} ثانية",
                "seconds": e.seconds
            }
        except Exception as e:
            error_logger.log_exception(
                e, "send_code", user_id
            )
            return {
                "success": False,
                "error": "unknown",
                "message": str(e)
            }

    async def sign_in(
            self,
            user_id: int,
            phone: str,
            code: str,
            phone_code_hash: str) -> dict:
        """تسجيل الدخول بالكود"""
        try:
            client = await self.manager.get_client(user_id)
            user = await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
            activity_logger.log_login(user_id, phone)
            return {
                "success": True,
                "user": user,
                "needs_password": False
            }
        except SessionPasswordNeededError:
            return {
                "success": False,
                "error": "needs_password",
                "needs_password": True,
                "message": "يحتاج كلمة مرور ثنائية"
            }
        except PhoneCodeInvalidError:
            return {
                "success": False,
                "error": "code_invalid",
                "message": "الكود غير صحيح أو منتهي"
            }
        except FloodWaitError as e:
            error_logger.log_flood_wait(e.seconds, user_id)
            return {
                "success": False,
                "error": "flood_wait",
                "message": f"انتظر {e.seconds} ثانية",
                "seconds": e.seconds
            }
        except Exception as e:
            error_logger.log_exception(
                e, "sign_in", user_id
            )
            return {
                "success": False,
                "error": "unknown",
                "message": str(e)
            }

    async def sign_in_password(
            self,
            user_id: int,
            password: str) -> dict:
        """تسجيل الدخول بكلمة المرور الثنائية"""
        try:
            client = await self.manager.get_client(user_id)
            user = await client.sign_in(password=password)
            return {"success": True, "user": user}
        except Exception as e:
            error_logger.log_exception(
                e, "sign_in_password", user_id
            )
            return {
                "success": False,
                "error": "wrong_password",
                "message": "كلمة المرور غير صحيحة"
            }

    async def logout(self, user_id: int) -> bool:
        """تسجيل الخروج"""
        try:
            client = await self.manager.get_client(user_id)
            await client.log_out()
            await self.manager.disconnect_client(user_id)

            session_path = (
                self.manager.get_session_path(user_id)
                + ".session"
            )
            if os.path.exists(session_path):
                os.remove(session_path)

            activity_logger.log_logout(user_id)
            return True
        except Exception as e:
            error_logger.log_exception(
                e, "logout", user_id
            )
            return False

    async def get_me(
            self, user_id: int) -> Optional[dict]:
        """معلومات الحساب الحالي"""
        try:
            client = await self.manager.get_client(user_id)
            me = await client.get_me()
            return {
                "id":         me.id,
                "first_name": me.first_name,
                "last_name":  me.last_name or "",
                "username":   me.username or "",
                "phone":      me.phone or "",
                "full_name":  (
                    f"{me.first_name} "
                    f"{me.last_name or ''}".strip()
                ),
            }
        except Exception as e:
            error_logger.log_exception(
                e, "get_me", user_id
            )
            return None

    # ==================== جلب القنوات ====================

    async def get_dialogs(
            self, user_id: int) -> dict:
        """جلب كل القنوات والمجموعات"""
        try:
            client = await self.manager.get_client(user_id)
            dialogs = await client.get_dialogs()

            channels = []
            groups   = []
            private  = []

            for dialog in dialogs:
                entity    = dialog.entity
                chat_type = get_chat_type(entity)

                chat_data = {
                    "id":            entity.id,
                    "title":         dialog.name or "بدون اسم",
                    "type":          chat_type,
                    "username":      extract_username(entity),
                    "members_count": get_members_count(entity),
                    "entity":        entity,
                }

                if chat_type == "channel":
                    channels.append(chat_data)
                elif chat_type == "group":
                    groups.append(chat_data)
                elif chat_type == "private":
                    private.append(chat_data)

            return {
                "success":  True,
                "channels": channels,
                "groups":   groups,
                "private":  private,
                "total":    len(dialogs),
            }

        except AuthKeyUnregisteredError:
            await self.manager.disconnect_client(user_id)
            return {
                "success": False,
                "error":   "session_expired",
                "message": "انتهت الجلسة، سجل دخول مجدداً"
            }
        except Exception as e:
            error_logger.log_exception(
                e, "get_dialogs", user_id
            )
            return {
                "success": False,
                "error":   "unknown",
                "message": str(e)
            }

    async def get_entity_by_username(
            self,
            user_id: int,
            username: str) -> Optional[dict]:
        """جلب قناة بالـ username"""
        try:
            client = await self.manager.get_client(user_id)
            entity    = await client.get_entity(username)
            chat_type = get_chat_type(entity)

            return {
                "success":       True,
                "id":            entity.id,
                "title":         getattr(entity, "title", username),
                "type":          chat_type,
                "username":      extract_username(entity),
                "members_count": get_members_count(entity),
                "entity":        entity,
            }
        except Exception as e:
            error_logger.log_exception(
                e, "get_entity_by_username", user_id
            )
            return {
                "success": False,
                "error":   "not_found",
                "message": "لم يتم العثور على القناة"
            }

    # ==================== جلب الرسائل ====================

    async def fetch_messages(
            self,
            user_id: int,
            entity,
            content_type: str = "all",
            limit: int = 100,
            offset_date=None,
            offset_id: int = 0,
            progress_callback=None) -> AsyncGenerator:
        """جلب الرسائل مع معالجة FloodWait"""

        client  = await self.manager.get_client(user_id)
        fetched = 0
        stats   = {
            "text":       0,
            "photos":     0,
            "videos":     0,
            "files":      0,
            "audio":      0,
            "voice":      0,
            "stickers":   0,
            "total":      0,
        }

        try:
            async for message in client.iter_messages(
                entity,
                limit      = limit if limit > 0 else None,
                offset_date = offset_date,
                offset_id   = offset_id,
                reverse     = False,
            ):
                if not message or not message.id:
                    continue

                msg_type = classify_message(message)

                if (content_type != "all" and
                        msg_type != content_type):
                    continue

                stats[msg_type] = (
                    stats.get(msg_type, 0) + 1
                )
                stats["total"] += 1
                fetched        += 1

                if (progress_callback and
                        fetched % 10 == 0):
                    await progress_callback(
                        fetched, stats
                    )

                yield {
                    "message": message,
                    "type":    msg_type,
                    "stats":   stats,
                }

                await asyncio.sleep(0.05)

        except FloodWaitError as e:
            error_logger.log_flood_wait(e.seconds, user_id)
            bot_logger.warning(
                f"⚠️ FloodWait {e.seconds}s "
                f"للمستخدم {user_id}"
            )
            await asyncio.sleep(e.seconds)

        except Exception as e:
            error_logger.log_exception(
                e, "fetch_messages", user_id
            )

        activity_logger.log_fetch(
            user_id,
            getattr(entity, "id", 0),
            content_type,
            fetched
        )

    async def count_messages(
            self,
            user_id: int,
            entity,
            content_type: str = "all") -> int:
        """حساب عدد الرسائل"""
        try:
            client = await self.manager.get_client(user_id)

            if content_type == "all":
                count = await client.get_messages(
                    entity, limit=0
                )
                return count.total

            count = 0
            async for msg in client.iter_messages(
                entity, limit=None
            ):
                if classify_message(msg) == content_type:
                    count += 1
            return count

        except Exception as e:
            error_logger.log_exception(
                e, "count_messages", user_id
            )
            return 0

    # ==================== تحميل الملفات ====================

    async def download_media(
            self,
            user_id: int,
            message,
            msg_type: str,
            chat_id: int) -> Optional[str]:
        """تحميل ملف من رسالة"""
        try:
            if not message.media:
                return None

            client    = await self.manager.get_client(user_id)
            file_name = get_file_name(message, msg_type)
            file_path = get_download_path(
                user_id, chat_id, msg_type, file_name
            )

            if os.path.exists(file_path):
                return file_path

            downloaded = await client.download_media(
                message,
                file=file_path,
            )

            if downloaded:
                return downloaded

            return None

        except FloodWaitError as e:
            error_logger.log_flood_wait(e.seconds, user_id)
            await asyncio.sleep(e.seconds)
            return None

        except Exception as e:
            error_logger.log_download_error(
                user_id, str(message.id), str(e)
            )
            return None

    # ==================== معلومات القناة ====================

    async def get_chat_info(
            self,
            user_id: int,
            entity) -> Optional[dict]:
        """معلومات تفصيلية عن قناة"""
        try:
            client = await self.manager.get_client(user_id)
            full   = await client.get_entity(entity)

            total_messages = await client.get_messages(
                entity, limit=0
            )

            return {
                "id":             full.id,
                "title":          getattr(full, "title", ""),
                "username":       extract_username(full),
                "members_count":  get_members_count(full),
                "total_messages": total_messages.total,
                "type":           get_chat_type(full),
                "description":    getattr(
                    full, "about", ""
                ) or "",
            }

        except Exception as e:
            error_logger.log_exception(
                e, "get_chat_info", user_id
            )
            return None


# ==================== Instance ====================

telegram_service = TelegramService()
