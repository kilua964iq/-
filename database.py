import aiosqlite
import asyncio
import os
from datetime import datetime
from config import config
import json
import logging

logger = logging.getLogger(__name__)

DB_PATH = "data/bot.db"


def clean_datetime(dt):
    """تنظيف timezone من التاريخ"""
    if dt is None:
        return None
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def dt_to_str(dt):
    """تحويل datetime لنص"""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)


def str_to_dt(s):
    """تحويل نص لـ datetime"""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


class Database:
    def __init__(self):
        self._conn = None
        self._lock = asyncio.Lock()

    async def connect(self):
        try:
            os.makedirs("data", exist_ok=True)
            self._conn = await aiosqlite.connect(DB_PATH)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")
            await self.create_tables()
            print("✅ تم الاتصال بقاعدة البيانات", flush=True)
        except Exception as e:
            print(f"❌ خطأ في الاتصال: {e}", flush=True)
            raise

    async def disconnect(self):
        if self._conn:
            await self._conn.close()

    async def execute(self, sql, params=()):
        async with self._lock:
            await self._conn.execute(sql, params)
            await self._conn.commit()

    async def fetchone(self, sql, params=()):
        async with self._lock:
            async with self._conn.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None

    async def fetchall(self, sql, params=()):
        async with self._lock:
            async with self._conn.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def fetchval(self, sql, params=()):
        async with self._lock:
            async with self._conn.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
                return None

    async def insert(self, sql, params=()):
        async with self._lock:
            async with self._conn.execute(sql, params) as cursor:
                await self._conn.commit()
                return cursor.lastrowid

    async def create_tables(self):
        tables = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                is_banned INTEGER DEFAULT 0,
                joined_at TEXT DEFAULT (datetime('now')),
                last_active TEXT DEFAULT (datetime('now')),
                settings TEXT DEFAULT '{}'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                permissions TEXT DEFAULT '{}',
                added_by INTEGER,
                added_at TEXT DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                session_string TEXT,
                phone TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                last_used TEXT DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                chat_title TEXT,
                chat_type TEXT,
                chat_username TEXT,
                members_count INTEGER DEFAULT 0,
                last_fetched TEXT,
                total_messages INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(owner_id, chat_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                chat_title TEXT,
                content_type TEXT,
                total_messages INTEGER DEFAULT 0,
                fetched_messages INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                started_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT,
                settings TEXT DEFAULT '{}'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archive_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                message_type TEXT,
                text TEXT,
                file_path TEXT,
                file_size INTEGER DEFAULT 0,
                file_name TEXT,
                mime_type TEXT,
                date TEXT,
                sender_id INTEGER,
                sender_name TEXT,
                views INTEGER DEFAULT 0,
                forwards INTEGER DEFAULT 0,
                ai_summary TEXT,
                ai_category TEXT,
                metadata TEXT DEFAULT '{}',
                saved_at TEXT DEFAULT (datetime('now')),
                UNIQUE(archive_id, message_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                task_type TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                progress INTEGER DEFAULT 0,
                data TEXT DEFAULT '{}',
                result TEXT DEFAULT '{}',
                error TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                started_at TEXT,
                completed_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                smart_filter INTEGER DEFAULT 1,
                extract_cards INTEGER DEFAULT 1,
                extract_phones INTEGER DEFAULT 1,
                extract_emails INTEGER DEFAULT 1,
                extract_urls INTEGER DEFAULT 1,
                save_txt INTEGER DEFAULT 0,
                ai_summary INTEGER DEFAULT 0,
                ai_category INTEGER DEFAULT 0,
                voice_to_text INTEGER DEFAULT 0,
                language TEXT DEFAULT 'ar',
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT,
                details TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
            """,
            # Indexes
            "CREATE INDEX IF NOT EXISTS idx_messages_archive ON messages(archive_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_owner ON messages(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_archives_owner ON archives(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id)",
        ]

        for table in tables:
            await self._conn.execute(table)
        await self._conn.commit()
        print("✅ تم إنشاء الجداول", flush=True)

    # ==================== المستخدمين ====================

    async def get_user(self, telegram_id: int):
        return await self.fetchone(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )

    async def create_user(self, telegram_id: int,
                          username: str = None,
                          full_name: str = None):
        await self.execute("""
            INSERT INTO users (telegram_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name,
            last_active = datetime('now')
        """, (telegram_id, username, full_name))
        return await self.get_user(telegram_id)

    async def update_user(self, telegram_id: int, **kwargs):
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(telegram_id)
        await self.execute(
            f"UPDATE users SET {fields} WHERE telegram_id = ?",
            values
        )

    async def get_all_users(self, limit: int = 100,
                            offset: int = 0):
        return await self.fetchall(
            "SELECT * FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )

    async def count_users(self):
        return await self.fetchval(
            "SELECT COUNT(*) FROM users"
        )

    async def ban_user(self, telegram_id: int):
        await self.execute(
            "UPDATE users SET is_banned = 1 WHERE telegram_id = ?",
            (telegram_id,)
        )

    async def unban_user(self, telegram_id: int):
        await self.execute(
            "UPDATE users SET is_banned = 0 WHERE telegram_id = ?",
            (telegram_id,)
        )

    # ==================== الإعدادات ====================

    async def get_settings(self, telegram_id: int):
        settings = await self.fetchone(
            "SELECT * FROM user_settings WHERE telegram_id = ?",
            (telegram_id,)
        )
        if not settings:
            await self.execute(
                "INSERT OR IGNORE INTO user_settings (telegram_id) VALUES (?)",
                (telegram_id,)
            )
            settings = await self.fetchone(
                "SELECT * FROM user_settings WHERE telegram_id = ?",
                (telegram_id,)
            )
        return settings

    async def update_settings(self, telegram_id: int, **kwargs):
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(telegram_id)
        await self.execute(f"""
            INSERT OR IGNORE INTO user_settings (telegram_id) VALUES (?);
        """, (telegram_id,))
        await self.execute(
            f"UPDATE user_settings SET {fields} WHERE telegram_id = ?",
            values
        )

    # ==================== الأدمنية ====================

    async def get_admin(self, telegram_id: int):
        return await self.fetchone(
            "SELECT * FROM admins WHERE telegram_id = ?",
            (telegram_id,)
        )

    async def add_admin(self, telegram_id: int,
                        username: str, full_name: str,
                        added_by: int,
                        permissions: dict = None):
        if permissions is None:
            permissions = {
                "can_view_users":      True,
                "can_ban_users":       False,
                "can_view_archives":   True,
                "can_delete_archives": False,
                "can_view_stats":      True,
            }
        await self.execute("""
            INSERT INTO admins
            (telegram_id, username, full_name, added_by, permissions)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET is_active = 1
        """, (telegram_id, username, full_name,
              added_by, json.dumps(permissions)))
        return await self.get_admin(telegram_id)

    async def remove_admin(self, telegram_id: int):
        await self.execute(
            "UPDATE admins SET is_active = 0 WHERE telegram_id = ?",
            (telegram_id,)
        )

    async def get_all_admins(self):
        return await self.fetchall(
            "SELECT * FROM admins WHERE is_active = 1"
        )

    async def is_admin(self, telegram_id: int) -> bool:
        result = await self.fetchval(
            "SELECT COUNT(*) FROM admins WHERE telegram_id = ? AND is_active = 1",
            (telegram_id,)
        )
        return result > 0

    # ==================== الجلسات ====================

    async def save_session(self, telegram_id: int,
                           phone: str,
                           session_string: str = None):
        await self.execute("""
            INSERT OR IGNORE INTO user_sessions
            (telegram_id, phone, session_string)
            VALUES (?, ?, ?)
        """, (telegram_id, phone, session_string))

    async def get_session(self, telegram_id: int):
        return await self.fetchone("""
            SELECT * FROM user_sessions
            WHERE telegram_id = ? AND is_active = 1
            ORDER BY created_at DESC LIMIT 1
        """, (telegram_id,))

    async def delete_session(self, telegram_id: int):
        await self.execute(
            "UPDATE user_sessions SET is_active = 0 WHERE telegram_id = ?",
            (telegram_id,)
        )

    # ==================== القنوات ====================

    async def save_chat(self, owner_id: int,
                        chat_id: int, chat_title: str,
                        chat_type: str,
                        chat_username: str = None,
                        members_count: int = 0):
        await self.execute("""
            INSERT INTO chats
            (owner_id, chat_id, chat_title, chat_type,
             chat_username, members_count)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_id, chat_id) DO UPDATE SET
            chat_title = excluded.chat_title,
            members_count = excluded.members_count,
            last_fetched = datetime('now')
        """, (owner_id, chat_id, chat_title, chat_type,
              chat_username, members_count))

    async def get_user_chats(self, owner_id: int,
                             chat_type: str = None):
        if chat_type:
            return await self.fetchall(
                "SELECT * FROM chats WHERE owner_id = ? AND chat_type = ? ORDER BY chat_title",
                (owner_id, chat_type)
            )
        return await self.fetchall(
            "SELECT * FROM chats WHERE owner_id = ? ORDER BY chat_title",
            (owner_id,)
        )

    # ==================== الأرشيف ====================

    async def create_archive(self, owner_id: int,
                             chat_id: int,
                             chat_title: str,
                             content_type: str,
                             settings: dict = None):
        row_id = await self.insert("""
            INSERT INTO archives
            (owner_id, chat_id, chat_title,
             content_type, settings)
            VALUES (?, ?, ?, ?, ?)
        """, (owner_id, chat_id, chat_title,
              content_type,
              json.dumps(settings or {})))
        return await self.get_archive(row_id)

    async def update_archive(self, archive_id: int, **kwargs):
        # تحويل datetime لنص
        for k, v in kwargs.items():
            if isinstance(v, datetime):
                kwargs[k] = dt_to_str(v)

        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(archive_id)
        await self.execute(
            f"UPDATE archives SET {fields} WHERE id = ?",
            values
        )

    async def get_archive(self, archive_id: int):
        return await self.fetchone(
            "SELECT * FROM archives WHERE id = ?",
            (archive_id,)
        )

    async def get_user_archives(self, owner_id: int,
                                limit: int = 20,
                                offset: int = 0):
        rows = await self.fetchall("""
            SELECT * FROM archives
            WHERE owner_id = ?
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
        """, (owner_id, limit, offset))

        # تحويل النصوص لـ datetime
        for row in rows:
            if row.get("started_at"):
                row["started_at"] = str_to_dt(
                    row["started_at"]
                )
        return rows

    async def count_archives(self, owner_id: int = None):
        if owner_id:
            return await self.fetchval(
                "SELECT COUNT(*) FROM archives WHERE owner_id = ?",
                (owner_id,)
            )
        return await self.fetchval(
            "SELECT COUNT(*) FROM archives"
        )

    # ==================== الرسائل ====================

    async def save_message(self, archive_id: int,
                           owner_id: int, chat_id: int,
                           message_id: int,
                           message_type: str,
                           text: str = None,
                           file_path: str = None,
                           file_size: int = 0,
                           file_name: str = None,
                           mime_type: str = None,
                           date=None,
                           sender_id: int = None,
                           sender_name: str = None,
                           views: int = 0,
                           forwards: int = 0,
                           ai_summary: str = None,
                           ai_category: str = None,
                           metadata: dict = None):
        date = dt_to_str(clean_datetime(date))

        await self.execute("""
            INSERT OR IGNORE INTO messages (
                archive_id, owner_id, chat_id,
                message_id, message_type, text,
                file_path, file_size, file_name,
                mime_type, date, sender_id,
                sender_name, views, forwards,
                ai_summary, ai_category, metadata
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
        """, (archive_id, owner_id, chat_id,
              message_id, message_type, text,
              file_path, file_size, file_name,
              mime_type, date, sender_id,
              sender_name, views, forwards,
              ai_summary, ai_category,
              json.dumps(metadata or {})))

    async def get_archive_messages(self,
                                   archive_id: int,
                                   message_type: str = None,
                                   limit: int = 50,
                                   offset: int = 0):
        if message_type:
            return await self.fetchall("""
                SELECT * FROM messages
                WHERE archive_id = ? AND message_type = ?
                ORDER BY date DESC LIMIT ? OFFSET ?
            """, (archive_id, message_type, limit, offset))
        return await self.fetchall("""
            SELECT * FROM messages
            WHERE archive_id = ?
            ORDER BY date DESC LIMIT ? OFFSET ?
        """, (archive_id, limit, offset))

    async def search_messages(self, owner_id: int,
                              query: str,
                              limit: int = 50):
        return await self.fetchall("""
            SELECT * FROM messages
            WHERE owner_id = ? AND text LIKE ?
            ORDER BY date DESC LIMIT ?
        """, (owner_id, f"%{query}%", limit))

    async def search_all_chats(self, owner_id: int,
                               query: str):
        return await self.fetchall("""
            SELECT m.*, a.chat_title
            FROM messages m
            JOIN archives a ON m.archive_id = a.id
            WHERE m.owner_id = ? AND m.text LIKE ?
            ORDER BY m.date DESC LIMIT 100
        """, (owner_id, f"%{query}%"))

    async def count_messages(self,
                             archive_id: int = None,
                             owner_id: int = None):
        if archive_id:
            return await self.fetchval(
                "SELECT COUNT(*) FROM messages WHERE archive_id = ?",
                (archive_id,)
            )
        if owner_id:
            return await self.fetchval(
                "SELECT COUNT(*) FROM messages WHERE owner_id = ?",
                (owner_id,)
            )
        return await self.fetchval(
            "SELECT COUNT(*) FROM messages"
        )

    # ==================== الإحصائيات ====================

    async def get_stats(self, owner_id: int = None):
        if owner_id:
            return await self.fetchone("""
                SELECT
                    COUNT(DISTINCT a.id) as total_archives,
                    COUNT(m.id) as total_messages,
                    COALESCE(SUM(m.file_size), 0) as total_size,
                    COUNT(CASE WHEN m.file_path IS NOT NULL
                          THEN 1 END) as total_files
                FROM archives a
                LEFT JOIN messages m ON a.id = m.archive_id
                WHERE a.owner_id = ?
            """, (owner_id,))
        return await self.fetchone("""
            SELECT
                COUNT(DISTINCT u.id) as total_users,
                COUNT(DISTINCT a.id) as total_archives,
                COUNT(m.id) as total_messages,
                COALESCE(SUM(m.file_size), 0) as total_size
            FROM users u
            LEFT JOIN archives a ON u.telegram_id = a.owner_id
            LEFT JOIN messages m ON a.id = m.archive_id
        """)

    async def log_activity(self, user_id: int,
                           action: str,
                           details: dict = None):
        await self.execute("""
            INSERT INTO activity_log (user_id, action, details)
            VALUES (?, ?, ?)
        """, (user_id, action, json.dumps(details or {})))

    async def get_activity_log(self,
                               user_id: int = None,
                               limit: int = 50):
        if user_id:
            rows = await self.fetchall("""
                SELECT * FROM activity_log
                WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
        else:
            rows = await self.fetchall("""
                SELECT * FROM activity_log
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))

        for row in rows:
            if row.get("created_at"):
                row["created_at"] = str_to_dt(
                    row["created_at"]
                )
        return rows

    async def delete_archive_data(self, archive_id: int):
        await self.execute(
            "DELETE FROM messages WHERE archive_id = ?",
            (archive_id,)
        )
        await self.execute(
            "DELETE FROM archives WHERE id = ?",
            (archive_id,)
        )


# ==================== Instance ====================

db = Database()
