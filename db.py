import aiosqlite
import random

DB_PATH = "database.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            gender TEXT,
            city TEXT,
            age INTEGER,
            hobbies TEXT,
            photo_file_id TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            liker INTEGER,
            liked INTEGER
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS dislikes (
            disliker INTEGER,
            disliked INTEGER
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS active_chats (
            user1 INTEGER,
            user2 INTEGER
        )
        """)
        await db.commit()


async def save_profile(uid, name, gender, city, age, hobbies, photo_file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT OR REPLACE INTO profiles (user_id, name, gender, city, age, hobbies, photo_file_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (uid, name, gender, city, age, hobbies, photo_file_id))
        await db.commit()


async def get_profile(uid):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)) as cursor:
            return await cursor.fetchone()


async def get_random_candidate(current_uid):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM profiles WHERE user_id != ?", (current_uid,)) as cursor:
            candidates = [r[0] async for r in cursor]
        if not candidates:
            return None
        return random.choice(candidates)


async def record_like(liker, liked):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO likes (liker, liked) VALUES (?, ?)", (liker, liked))
        await db.commit()


async def record_dislike(disliker, disliked):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO dislikes (disliker, disliked) VALUES (?, ?)", (disliker, disliked))
        await db.commit()


async def has_liked(uid1, uid2):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM likes WHERE liker = ? AND liked = ?", (uid1, uid2)) as cursor:
            return await cursor.fetchone() is not None


async def create_active_chat(u1, u2):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO active_chats (user1, user2) VALUES (?, ?)", (u1, u2))
        await db.commit()


async def find_chat_partner(uid):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user1, user2 FROM active_chats WHERE user1 = ? OR user2 = ?", (uid, uid)) as cursor:
            row = await cursor.fetchone()
        if row:
            return row[1] if row[0] == uid else row[0]
        return None


async def remove_active_chat(uid):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM active_chats WHERE user1 = ? OR user2 = ?", (uid, uid))
        await db.commit()
