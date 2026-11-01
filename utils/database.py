import aiosqlite
import logging
import asyncio
from typing import Optional, List, Dict, Set
from config import DB_PATH

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self):
        """Establish connection if not already open."""
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
            # Enable WAL mode for file-based databases to enhance concurrency
            if self.db_path != ":memory:":
                await self._conn.execute("PRAGMA journal_mode=WAL;")
            await self._conn.execute("PRAGMA foreign_keys=ON;")

    async def close(self):
        """Close database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def initialize(self):
        """Initialize database schema with required tables and indexes."""
        await self.connect()
        async with self._lock:
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS generators (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS temp_channels (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS control_panels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL
                );
            """)
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS trusted_users (
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    PRIMARY KEY (channel_id, user_id),
                    FOREIGN KEY (channel_id) REFERENCES temp_channels (channel_id) ON DELETE CASCADE
                );
            """)
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    PRIMARY KEY (channel_id, user_id),
                    FOREIGN KEY (channel_id) REFERENCES temp_channels (channel_id) ON DELETE CASCADE
                );
            """)
            await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_generators_guild ON generators(guild_id);")
            await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_channels_guild ON temp_channels(guild_id);")
            await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_channels_owner ON temp_channels(owner_id);")
            await self._conn.commit()
            logger.info("Database initialized successfully.")

    # ------------------ Generators ------------------

    async def add_generator(self, channel_id: int, guild_id: int, category_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute(
                "INSERT OR REPLACE INTO generators (channel_id, guild_id, category_id) VALUES (?, ?, ?);",
                (channel_id, guild_id, category_id)
            )
            await self._conn.commit()

    async def is_generator(self, channel_id: int) -> bool:
        await self.connect()
        async with self._lock:
            async with self._conn.execute(
                "SELECT 1 FROM generators WHERE channel_id = ? LIMIT 1;", (channel_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def get_generator(self, channel_id: int) -> Optional[Dict]:
        await self.connect()
        async with self._lock:
            async with self._conn.execute(
                "SELECT * FROM generators WHERE channel_id = ?;", (channel_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_generators(self) -> List[Dict]:
        await self.connect()
        async with self._lock:
            async with self._conn.execute("SELECT * FROM generators;") as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def remove_generator(self, channel_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute("DELETE FROM generators WHERE channel_id = ?;", (channel_id,))
            await self._conn.commit()

    # ------------------ Temp Channels ------------------

    async def add_temp_channel(self, channel_id: int, guild_id: int, owner_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute(
                "INSERT OR REPLACE INTO temp_channels (channel_id, guild_id, owner_id) VALUES (?, ?, ?);",
                (channel_id, guild_id, owner_id)
            )
            await self._conn.commit()

    async def get_temp_channel(self, channel_id: int) -> Optional[Dict]:
        await self.connect()
        async with self._lock:
            async with self._conn.execute(
                "SELECT * FROM temp_channels WHERE channel_id = ?;", (channel_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_user_temp_channel(self, guild_id: int, user_id: int) -> Optional[Dict]:
        await self.connect()
        async with self._lock:
            async with self._conn.execute(
                "SELECT * FROM temp_channels WHERE guild_id = ? AND owner_id = ? LIMIT 1;",
                (guild_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_temp_channels(self) -> List[Dict]:
        await self.connect()
        async with self._lock:
            async with self._conn.execute("SELECT * FROM temp_channels;") as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def update_temp_channel_owner(self, channel_id: int, new_owner_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute(
                "UPDATE temp_channels SET owner_id = ? WHERE channel_id = ?;",
                (new_owner_id, channel_id)
            )
            await self._conn.commit()

    async def remove_temp_channel(self, channel_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute("DELETE FROM trusted_users WHERE channel_id = ?;", (channel_id,))
            await self._conn.execute("DELETE FROM blocked_users WHERE channel_id = ?;", (channel_id,))
            await self._conn.execute("DELETE FROM temp_channels WHERE channel_id = ?;", (channel_id,))
            await self._conn.commit()

    # ------------------ Control Panels ------------------

    async def set_control_panel(self, guild_id: int, channel_id: int, message_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute(
                "INSERT OR REPLACE INTO control_panels (guild_id, channel_id, message_id) VALUES (?, ?, ?);",
                (guild_id, channel_id, message_id)
            )
            await self._conn.commit()

    async def get_control_panel(self, guild_id: int) -> Optional[Dict]:
        await self.connect()
        async with self._lock:
            async with self._conn.execute(
                "SELECT * FROM control_panels WHERE guild_id = ?;", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    # ------------------ Trusted Users ------------------

    async def add_trusted_user(self, channel_id: int, user_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute(
                "INSERT OR IGNORE INTO trusted_users (channel_id, user_id) VALUES (?, ?);",
                (channel_id, user_id)
            )
            await self._conn.commit()

    async def remove_trusted_user(self, channel_id: int, user_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute(
                "DELETE FROM trusted_users WHERE channel_id = ? AND user_id = ?;",
                (channel_id, user_id)
            )
            await self._conn.commit()

    async def get_trusted_users(self, channel_id: int) -> Set[int]:
        await self.connect()
        async with self._lock:
            async with self._conn.execute(
                "SELECT user_id FROM trusted_users WHERE channel_id = ?;", (channel_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return {r[0] for r in rows}

    # ------------------ Blocked Users ------------------

    async def add_blocked_user(self, channel_id: int, user_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute(
                "INSERT OR IGNORE INTO blocked_users (channel_id, user_id) VALUES (?, ?);",
                (channel_id, user_id)
            )
            await self._conn.commit()

    async def remove_blocked_user(self, channel_id: int, user_id: int):
        await self.connect()
        async with self._lock:
            await self._conn.execute(
                "DELETE FROM blocked_users WHERE channel_id = ? AND user_id = ?;",
                (channel_id, user_id)
            )
            await self._conn.commit()

    async def get_blocked_users(self, channel_id: int) -> Set[int]:
        await self.connect()
        async with self._lock:
            async with self._conn.execute(
                "SELECT user_id FROM blocked_users WHERE channel_id = ?;", (channel_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return {r[0] for r in rows}
