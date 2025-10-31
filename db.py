import sqlite3
import random

# Initialize database
def init_db():
    conn = sqlite3.connect("dating.db")
    c = conn.cursor()

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            gender TEXT,
            age INTEGER,
            bio TEXT,
            photo TEXT
        )
    """)

    # Likes table
    c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            liker_id INTEGER,
            liked_id INTEGER
        )
    """)

    conn.commit()
    conn.close()

# Save new user
def save_user(user_id, name, gender, age, bio, photo):
    conn = sqlite3.connect("dating.db")
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if c.fetchone():
        c.execute("""
            UPDATE users SET name=?, gender=?, age=?, bio=?, photo=? WHERE id=?
        """, (name, gender, age, bio, photo, user_id))
    else:
        c.execute("""
            INSERT INTO users (id, name, gender, age, bio, photo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, name, gender, age, bio, photo))

    conn.commit()
    conn.close()

# Get user by ID
def get_user(user_id):
    conn = sqlite3.connect("dating.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "gender": row[2],
        "age": row[3],
        "bio": row[4],
        "photo": row[5]
    }

# Get random user (not same, not already liked)
def get_random_user(current_user_id):
    conn = sqlite3.connect("dating.db")
    c = conn.cursor()
    c.execute("""
        SELECT * FROM users 
        WHERE id != ? AND id NOT IN (SELECT liked_id FROM likes WHERE liker_id = ?)
        ORDER BY RANDOM() LIMIT 1
    """, (current_user_id, current_user_id))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "gender": row[2],
        "age": row[3],
        "bio": row[4],
        "photo": row[5]
    }

# Save like
def like_user(liker_id, liked_id):
    conn = sqlite3.connect("dating.db")
    c = conn.cursor()
    c.execute("INSERT INTO likes (liker_id, liked_id) VALUES (?, ?)", (liker_id, liked_id))
    conn.commit()
    conn.close()

# Check mutual like (match)
def is_match(user1, user2):
    conn = sqlite3.connect("dating.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM likes WHERE liker_id=? AND liked_id=?", (user2, user1))
    match = c.fetchone()
    conn.close()
    return bool(match)

# Initialize database when file runs
init_db()
