import aiosqlite
candidates = [r[0] for r in rows if r[0] not in disliked]
if not candidates:
return None
import random
return random.choice(candidates)


# Likes / Dislikes
async def record_like(liker, liked):
async with aiosqlite.connect(DB_PATH) as db:
await db.execute('INSERT INTO likes (liker, liked) VALUES (?, ?)', (liker, liked))
await db.commit()


async def has_liked(liker, liked):
async with aiosqlite.connect(DB_PATH) as db:
cur = await db.execute('SELECT 1 FROM likes WHERE liker=? AND liked=?', (liker, liked))
row = await cur.fetchone()
return bool(row)


async def record_dislike(disliker, disliked):
async with aiosqlite.connect(DB_PATH) as db:
await db.execute('INSERT INTO dislikes (disliker, disliked) VALUES (?, ?)', (disliker, disliked))
await db.commit()


async def is_disliked(disliker, candidate):
async with aiosqlite.connect(DB_PATH) as db:
cur = await db.execute('SELECT 1 FROM dislikes WHERE disliker=? AND disliked=?', (disliker, candidate))
row = await cur.fetchone()
return bool(row)


# Active chats
async def create_active_chat(a, b):
# store smaller id in user_a for consistency
a1, b1 = (a, b) if a <= b else (b, a)
async with aiosqlite.connect(DB_PATH) as db:
# avoid duplicate
cur = await db.execute('SELECT 1 FROM active_chats WHERE user_a=? AND user_b=?', (a1, b1))
if await cur.fetchone():
return
await db.execute('INSERT INTO active_chats (user_a, user_b) VALUES (?, ?)', (a1, b1))
await db.commit()


async def find_chat_partner(user_id):
async with aiosqlite.connect(DB_PATH) as db:
cur = await db.execute('SELECT user_a, user_b FROM active_chats')
rows = await cur.fetchall()
for a, b in rows:
if user_id == a:
return b
if user_id == b:
return a
return None


async def remove_active_chat(user_id):
async with aiosqlite.connect(DB_PATH) as db:
cur = await db.execute('SELECT user_a, user_b FROM active_chats')
rows = await cur.fetchall()
for a, b in rows:
if user_id == a or user_id == b:
await db.execute('DELETE FROM active_chats WHERE user_a=? AND user_b=?', (a, b))
await db.commit()
