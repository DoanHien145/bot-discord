"""Lớp truy cập SQLite bất đồng bộ: Users, Pets, Played_History."""
import os
import time
import aiosqlite

DB_PATH = os.getenv("DB_PATH", "bot.db")
START_MONEY = 1000
QUEUE_SIZE = 1500

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    money   INTEGER NOT NULL DEFAULT 1000 CHECK(money >= 0),
    points  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pets(
    user_id INTEGER PRIMARY KEY,
    pet_name TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    last_fed_time REAL
);
CREATE TABLE IF NOT EXISTS played_history(
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    content_id INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hist ON played_history(guild_id, kind, seq DESC);
"""


async def init():
    async with aiosqlite.connect(DB_PATH) as con:
        await con.executescript(SCHEMA)
        await con.commit()


async def ensure_user(uid: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as con:
        await con.execute(
            "INSERT OR IGNORE INTO users(user_id, money) VALUES(?, ?)", (uid, START_MONEY))
        await con.commit()
        cur = await con.execute("SELECT money, points FROM users WHERE user_id=?", (uid,))
        m, p = await cur.fetchone()
        return {"money": m, "points": p}


async def try_debit(uid: int, amount: int) -> bool:
    """Trừ tiền nguyên tử: chỉ thành công nếu đủ số dư."""
    await ensure_user(uid)
    async with aiosqlite.connect(DB_PATH) as con:
        cur = await con.execute(
            "UPDATE users SET money = money - ? WHERE user_id=? AND money >= ?",
            (amount, uid, amount))
        await con.commit()
        return cur.rowcount == 1


async def add_money(uid: int, amount: int, points: int = 0):
    await ensure_user(uid)
    async with aiosqlite.connect(DB_PATH) as con:
        await con.execute(
            "UPDATE users SET money = money + ?, points = points + ? WHERE user_id=?",
            (amount, points, uid))
        await con.commit()


# ---------- Pets ----------
async def get_pet(uid: int):
    async with aiosqlite.connect(DB_PATH) as con:
        con.row_factory = aiosqlite.Row
        cur = await con.execute("SELECT * FROM pets WHERE user_id=?", (uid,))
        return await cur.fetchone()


async def create_pet(uid: int, name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as con:
        cur = await con.execute(
            "INSERT OR IGNORE INTO pets(user_id, pet_name) VALUES(?, ?)", (uid, name))
        await con.commit()
        return cur.rowcount == 1


async def update_pet(uid: int, level: int, exp: int):
    async with aiosqlite.connect(DB_PATH) as con:
        await con.execute(
            "UPDATE pets SET level=?, exp=?, last_fed_time=? WHERE user_id=?",
            (level, exp, time.time(), uid))
        await con.commit()


# ---------- Leaderboard ----------
async def top_money(ids: list[int], limit=10):
    if not ids:
        return []
    q = ",".join("?" * len(ids))
    async with aiosqlite.connect(DB_PATH) as con:
        cur = await con.execute(
            f"SELECT user_id, money FROM users WHERE user_id IN ({q}) "
            "ORDER BY money DESC LIMIT ?", (*ids, limit))
        return await cur.fetchall()


async def top_pets(ids: list[int], limit=10):
    if not ids:
        return []
    q = ",".join("?" * len(ids))
    async with aiosqlite.connect(DB_PATH) as con:
        cur = await con.execute(
            f"SELECT user_id, pet_name, level, exp FROM pets WHERE user_id IN ({q}) "
            "ORDER BY level DESC, exp DESC LIMIT ?", (*ids, limit))
        return await cur.fetchall()


# ---------- Anti-repeat queue ----------
async def recent_ids(guild_id: int, kind: str) -> list[int]:
    """Danh sách ID gần nhất (mới -> cũ), tối đa QUEUE_SIZE."""
    async with aiosqlite.connect(DB_PATH) as con:
        cur = await con.execute(
            "SELECT content_id FROM played_history WHERE guild_id=? AND kind=? "
            "ORDER BY seq DESC LIMIT ?", (guild_id, kind, QUEUE_SIZE))
        return [r[0] for r in await cur.fetchall()]


async def push_history(guild_id: int, kind: str, content_id: int):
    async with aiosqlite.connect(DB_PATH) as con:
        await con.execute(
            "INSERT INTO played_history(guild_id, kind, content_id) VALUES(?,?,?)",
            (guild_id, kind, content_id))
        # Xóa ID cũ nhất (thứ 1501 trở đi) khỏi danh sách loại trừ
        await con.execute(
            "DELETE FROM played_history WHERE guild_id=? AND kind=? AND seq NOT IN ("
            "SELECT seq FROM played_history WHERE guild_id=? AND kind=? "
            "ORDER BY seq DESC LIMIT ?)",
            (guild_id, kind, guild_id, kind, QUEUE_SIZE))
        await con.commit()
