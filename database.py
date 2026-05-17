import asyncpg
import asyncio
from datetime import datetime
from config import config
import json
import logging

logger = logging.getLogger(__name__)


def clean_datetime(dt):
    """تنظيف timezone من التاريخ"""
    if dt is None:
        return None
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(
                config.DATABASE_URL,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            await self.create_tables()
            logger.info("✅ تم الاتصال بقاعدة البيانات")
            print("✅ تم الاتصال بقاعدة البيانات", flush=True)
        except Exception as e:
            logger.error(f"❌ خطأ في الاتصال: {e}")
            print(f"❌ خطأ في الاتصال: {e}", flush=True)
            raise

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(255),
                    full_name VARCHAR(255),
                    phone VARCHAR(20),
                    role VARCHAR(20) DEFAULT 'user',
                    is_active BOOLEAN DEFAULT TRUE,
                    is_banned BOOLEAN DEFAULT FALSE,
                    joined_at TIMESTAMP DEFAULT NOW(),
                    last_active TIMESTAMP DEFAULT NOW(),
                    settings JSONB DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS admins (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(255),
                    full_name VARCHAR(255),
                    permissions JSONB DEFAULT '{}',
                    added_by BIGINT,
                    added_at TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
                );

                CREATE TABLE IF NOT EXISTS user_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    session_string TEXT,
                    phone VARCHAR(20),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_used TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS chats (
                    id BIGSERIAL PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    chat_title VARCHAR(255),
                    chat_type VARCHAR(20),
                    chat_username VARCHAR(255),
                    members_count INTEGER DEFAULT 0,
                    last_fetched TIMESTAMP,
                    total_messages INTEGER DEFAULT 0,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(owner_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS archives (
                    id BIGSERIAL PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    chat_title VARCHAR(255),
                    content_type VARCHAR(20),
                    total_messages INTEGER DEFAULT 0,
                    fetched_messages INTEGER DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    started_at TIMESTAMP DEFAULT NOW(),
                    completed_at TIMESTAMP,
                    settings JSONB DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    archive_id BIGINT NOT NULL,
                    owner_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    message_id INTEGER NOT NULL,
                    message_type VARCHAR(20),
                    text TEXT,
                    file_path VARCHAR(500),
                    file_size BIGINT DEFAULT 0,
                    file_name VARCHAR(255),
                    mime_type VARCHAR(100),
                    date TIMESTAMP,
                    sender_id BIGINT,
                    sender_name VARCHAR(255),
                    views INTEGER DEFAULT 0,
                    forwards INTEGER DEFAULT 0,
                    ai_summary TEXT,
                    ai_category VARCHAR(100),
                    metadata JSONB DEFAULT '{}',
                    saved_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(archive_id, message_id)
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id BIGSERIAL PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    task_type VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    progress INTEGER DEFAULT 0,
                    data JSONB DEFAULT '{}',
                    result JSONB DEFAULT '{}',
                    error TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS statistics (
                    id BIGSERIAL PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    date DATE DEFAULT CURRENT_DATE,
                    total_archives INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    total_files INTEGER DEFAULT 0,
                    total_size BIGINT DEFAULT 0,
                    ai_requests INTEGER DEFAULT 0,
                    metadata JSONB DEFAULT '{}',
                    UNIQUE(owner_id, date)
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id BIGSERIAL PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    alert_type VARCHAR(50),
                    keywords TEXT[],
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_triggered TIMESTAMP,
                    trigger_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS activity_log (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    action VARCHAR(100),
                    details JSONB DEFAULT '{}',
                    ip_address VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_messages_archive
                    ON messages(archive_id);
                CREATE INDEX IF NOT EXISTS idx_messages_owner
                    ON messages(owner_id);
                CREATE INDEX IF NOT EXISTS idx_messages_type
                    ON messages(message_type);
                CREATE INDEX IF NOT EXISTS idx_archives_owner
                    ON archives(owner_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_status
                    ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_activity_user
                    ON activity_log(user_id);
            """)
            print("✅ تم إنشاء الجداول", flush=True)

    # ==================== المستخدمين ====================

    async def get_user(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1",
                telegram_id
            )

    async def create_user(
            self,
            telegram_id: int,
            username: str = None,
            full_name: str = None):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                INSERT INTO users (telegram_id, username, full_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (telegram_id) DO UPDATE
                SET username = $2, full_name = $3,
                    last_active = NOW()
                RETURNING *
            """, telegram_id, username, full_name)

    async def update_user(
            self, telegram_id: int, **kwargs):
        fields = ", ".join(
            [f"{k} = ${i+2}"
             for i, k in enumerate(kwargs.keys())]
        )
        values = list(kwargs.values())
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE users SET {fields} "
                f"WHERE telegram_id = $1",
                telegram_id, *values
            )

    async def get_all_users(
            self,
            limit: int = 100,
            offset: int = 0):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT * FROM users
                ORDER BY joined_at DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)

    async def count_users(self):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM users"
            )

    async def ban_user(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET is_banned = TRUE
                WHERE telegram_id = $1
            """, telegram_id)

    async def unban_user(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET is_banned = FALSE
                WHERE telegram_id = $1
            """, telegram_id)

    # ==================== الأدمنية ====================

    async def get_admin(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM admins "
                "WHERE telegram_id = $1",
                telegram_id
            )

    async def add_admin(
            self,
            telegram_id: int,
            username: str,
            full_name: str,
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
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                INSERT INTO admins
                (telegram_id, username, full_name,
                 added_by, permissions)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (telegram_id) DO UPDATE
                SET is_active = TRUE
                RETURNING *
            """, telegram_id, username, full_name,
                added_by, json.dumps(permissions))

    async def remove_admin(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE admins SET is_active = FALSE
                WHERE telegram_id = $1
            """, telegram_id)

    async def get_all_admins(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM admins "
                "WHERE is_active = TRUE"
            )

    async def is_admin(self, telegram_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM admins
                WHERE telegram_id = $1
                AND is_active = TRUE
            """, telegram_id)
            return result > 0

    # ==================== الجلسات ====================

    async def save_session(
            self,
            telegram_id: int,
            phone: str,
            session_string: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_sessions
                (telegram_id, phone, session_string)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
            """, telegram_id, phone, session_string)

    async def get_session(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT * FROM user_sessions
                WHERE telegram_id = $1
                AND is_active = TRUE
                ORDER BY created_at DESC LIMIT 1
            """, telegram_id)

    async def delete_session(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE user_sessions
                SET is_active = FALSE
                WHERE telegram_id = $1
            """, telegram_id)

    # ==================== القنوات ====================

    async def save_chat(
            self,
            owner_id: int,
            chat_id: int,
            chat_title: str,
            chat_type: str,
            chat_username: str = None,
            members_count: int = 0):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                INSERT INTO chats
                (owner_id, chat_id, chat_title,
                 chat_type, chat_username, members_count)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (owner_id, chat_id) DO UPDATE
                SET chat_title = $3,
                    members_count = $6,
                    last_fetched = NOW()
                RETURNING *
            """, owner_id, chat_id, chat_title,
                chat_type, chat_username, members_count)

    async def get_user_chats(
            self,
            owner_id: int,
            chat_type: str = None):
        async with self.pool.acquire() as conn:
            if chat_type:
                return await conn.fetch("""
                    SELECT * FROM chats
                    WHERE owner_id = $1
                    AND chat_type = $2
                    ORDER BY chat_title
                """, owner_id, chat_type)
            return await conn.fetch("""
                SELECT * FROM chats
                WHERE owner_id = $1
                ORDER BY chat_title
            """, owner_id)

    # ==================== الأرشيف ====================

    async def create_archive(
            self,
            owner_id: int,
            chat_id: int,
            chat_title: str,
            content_type: str,
            settings: dict = None):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                INSERT INTO archives
                (owner_id, chat_id, chat_title,
                 content_type, settings)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
            """, owner_id, chat_id, chat_title,
                content_type,
                json.dumps(settings or {}))

    async def update_archive(
            self, archive_id: int, **kwargs):
        fields = ", ".join(
            [f"{k} = ${i+2}"
             for i, k in enumerate(kwargs.keys())]
        )
        values = list(kwargs.values())
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE archives SET {fields} "
                f"WHERE id = $1",
                archive_id, *values
            )

    async def get_archive(self, archive_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM archives WHERE id = $1",
                archive_id
            )

    async def get_user_archives(
            self,
            owner_id: int,
            limit: int = 20,
            offset: int = 0):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT * FROM archives
                WHERE owner_id = $1
                ORDER BY started_at DESC
                LIMIT $2 OFFSET $3
            """, owner_id, limit, offset)

    async def count_archives(
            self, owner_id: int = None):
        async with self.pool.acquire() as conn:
            if owner_id:
                return await conn.fetchval(
                    "SELECT COUNT(*) FROM archives "
                    "WHERE owner_id = $1",
                    owner_id
                )
            return await conn.fetchval(
                "SELECT COUNT(*) FROM archives"
            )

    # ==================== الرسائل ====================

    async def save_message(
            self,
            archive_id: int,
            owner_id: int,
            chat_id: int,
            message_id: int,
            message_type: str,
            text: str = None,
            file_path: str = None,
            file_size: int = 0,
            file_name: str = None,
            mime_type: str = None,
            date: datetime = None,
            sender_id: int = None,
            sender_name: str = None,
            views: int = 0,
            forwards: int = 0,
            ai_summary: str = None,
            ai_category: str = None,
            metadata: dict = None):

        # ===== تنظيف التاريخ =====
        date = clean_datetime(date)

        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                INSERT INTO messages (
                    archive_id, owner_id, chat_id,
                    message_id, message_type, text,
                    file_path, file_size, file_name,
                    mime_type, date, sender_id,
                    sender_name, views, forwards,
                    ai_summary, ai_category, metadata
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,
                    $10,$11,$12,$13,$14,$15,$16,$17,$18
                )
                ON CONFLICT (archive_id, message_id)
                DO NOTHING
                RETURNING *
            """, archive_id, owner_id, chat_id,
                message_id, message_type, text,
                file_path, file_size, file_name,
                mime_type, date, sender_id,
                sender_name, views, forwards,
                ai_summary, ai_category,
                json.dumps(metadata or {}))

    async def get_archive_messages(
            self,
            archive_id: int,
            message_type: str = None,
            limit: int = 50,
            offset: int = 0):
        async with self.pool.acquire() as conn:
            if message_type:
                return await conn.fetch("""
                    SELECT * FROM messages
                    WHERE archive_id = $1
                    AND message_type = $2
                    ORDER BY date DESC
                    LIMIT $3 OFFSET $4
                """, archive_id, message_type,
                    limit, offset)
            return await conn.fetch("""
                SELECT * FROM messages
                WHERE archive_id = $1
                ORDER BY date DESC
                LIMIT $2 OFFSET $3
            """, archive_id, limit, offset)

    async def search_messages(
            self,
            owner_id: int,
            query: str,
            limit: int = 50):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT * FROM messages
                WHERE owner_id = $1
                AND text ILIKE $2
                ORDER BY date DESC
                LIMIT $3
            """, owner_id, f"%{query}%", limit)

    async def count_messages(
            self,
            archive_id: int = None,
            owner_id: int = None):
        async with self.pool.acquire() as conn:
            if archive_id:
                return await conn.fetchval(
                    "SELECT COUNT(*) FROM messages "
                    "WHERE archive_id = $1",
                    archive_id
                )
            if owner_id:
                return await conn.fetchval(
                    "SELECT COUNT(*) FROM messages "
                    "WHERE owner_id = $1",
                    owner_id
                )
            return await conn.fetchval(
                "SELECT COUNT(*) FROM messages"
            )

    # ==================== المهام ====================

    async def create_task(
            self,
            owner_id: int,
            task_type: str,
            data: dict = None,
            priority: int = 0):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                INSERT INTO tasks
                (owner_id, task_type, data, priority)
                VALUES ($1, $2, $3, $4)
                RETURNING *
            """, owner_id, task_type,
                json.dumps(data or {}), priority)

    async def update_task(
            self, task_id: int, **kwargs):
        fields = ", ".join(
            [f"{k} = ${i+2}"
             for i, k in enumerate(kwargs.keys())]
        )
        values = list(kwargs.values())
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE tasks SET {fields} "
                f"WHERE id = $1",
                task_id, *values
            )

    async def get_pending_tasks(
            self, limit: int = 10):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT * FROM tasks
                WHERE status = 'pending'
                ORDER BY priority DESC,
                created_at ASC
                LIMIT $1
            """, limit)

    # ==================== الإحصائيات ====================

    async def get_stats(
            self, owner_id: int = None):
        async with self.pool.acquire() as conn:
            if owner_id:
                return await conn.fetchrow("""
                    SELECT
                        COUNT(DISTINCT a.id)
                            as total_archives,
                        COUNT(m.id)
                            as total_messages,
                        COALESCE(SUM(m.file_size), 0)
                            as total_size,
                        COUNT(CASE WHEN m.file_path
                              IS NOT NULL THEN 1 END)
                            as total_files
                    FROM archives a
                    LEFT JOIN messages m
                        ON a.id = m.archive_id
                    WHERE a.owner_id = $1
                """, owner_id)
            return await conn.fetchrow("""
                SELECT
                    COUNT(DISTINCT u.id)
                        as total_users,
                    COUNT(DISTINCT a.id)
                        as total_archives,
                    COUNT(m.id)
                        as total_messages,
                    COALESCE(SUM(m.file_size), 0)
                        as total_size
                FROM users u
                LEFT JOIN archives a
                    ON u.telegram_id = a.owner_id
                LEFT JOIN messages m
                    ON a.id = m.archive_id
            """)

    async def log_activity(
            self,
            user_id: int,
            action: str,
            details: dict = None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO activity_log
                (user_id, action, details)
                VALUES ($1, $2, $3)
            """, user_id, action,
                json.dumps(details or {}))

    async def get_activity_log(
            self,
            user_id: int = None,
            limit: int = 50):
        async with self.pool.acquire() as conn:
            if user_id:
                return await conn.fetch("""
                    SELECT * FROM activity_log
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, user_id, limit)
            return await conn.fetch("""
                SELECT * FROM activity_log
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)


# ==================== Instance ====================

db = Database()
