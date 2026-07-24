"""
Very small persistence layer on top of SQLite (via aiosqlite).

Table `subscriptions`:
    chat_id       -- Telegram chat id (primary key, one tracked case per chat)
    tracking_id   -- the UUID from the AIMA tracking link
    last_tipo     -- the `tipo` field of the last known "estadoAtual" step
    last_label    -- the human readable label, kept for nicer messages
    lang          -- 'pt' or 'en', which description language to send
    created_at    -- ISO timestamp
    updated_at    -- ISO timestamp of the last successful check
"""

import datetime
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    chat_id     INTEGER PRIMARY KEY,
    tracking_id TEXT NOT NULL,
    last_tipo   TEXT,
    last_label  TEXT,
    lang        TEXT NOT NULL DEFAULT 'pt',
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT
);
"""


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(SCHEMA)
        await db.commit()


async def upsert_subscription(db_path: str, chat_id: int, tracking_id: str, lang: str = "pt") -> None:
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO subscriptions (chat_id, tracking_id, lang, active, created_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                tracking_id = excluded.tracking_id,
                lang = excluded.lang,
                active = 1
            """,
            (chat_id, tracking_id, lang, now),
        )
        await db.commit()


async def remove_subscription(db_path: str, chat_id: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM subscriptions WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def get_subscription(db_path: str, chat_id: int):
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM subscriptions WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_all_subscriptions(db_path: str, only_active: bool = True):
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM subscriptions"
        if only_active:
            query += " WHERE active = 1"
        cur = await db.execute(query)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def set_active(db_path: str, chat_id: int, active: bool) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE subscriptions SET active = ? WHERE chat_id = ?",
            (1 if active else 0, chat_id),
        )
        await db.commit()


async def update_status(db_path: str, chat_id: int, tipo: str, label: str) -> None:
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE subscriptions SET last_tipo = ?, last_label = ?, updated_at = ? WHERE chat_id = ?",
            (tipo, label, now, chat_id),
        )
        await db.commit()
