import os
from pymongo import MongoClient
from bson import ObjectId
import random

# ----------------------
# MongoDB Connection
# ----------------------
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("Set MONGO_URI environment variable for MongoDB connection.")

client = MongoClient(MONGO_URI)
db = client["std_dating_bot"]
users = db["users"]
likes = db["likes"]

# ----------------------
# Save or update a user profile
# ----------------------
def save_user(user_id: int, name: str, gender: str, age: int, bio: str, photos):
    """Insert or update a user's profile"""
    if not isinstance(photos, list):
        photos = [photos] if photos else []

    users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "name": name,
                "gender": gender,
                "age": age,
                "bio": bio,
                "photos": photos,
            }
        },
        upsert=True
    )

# ----------------------
# Get user by ID
# ----------------------
def get_user(user_id: int):
    return users.find_one({"user_id": user_id})

# ----------------------
# Find random user (exclude self)
# ----------------------
def get_random_user(current_user_id: int):
    pipeline = [
        {"$match": {"user_id": {"$ne": current_user_id}}},
        {"$sample": {"size": 1}}
    ]
    result = list(users.aggregate(pipeline))
    if not result:
        return None
    return result[0]

# ----------------------
# Record a like
# ----------------------
def like_user(liker_id: int, liked_id: int):
    likes.update_one(
        {"liker_id": liker_id, "liked_id": liked_id},
        {"$set": {"liker_id": liker_id, "liked_id": liked_id}},
        upsert=True
    )

# ----------------------
# Check if two users liked each other (match)
# ----------------------
def is_match(user1: int, user2: int) -> bool:
    """Returns True if both liked each other"""
    return (
        likes.find_one({"liker_id": user1, "liked_id": user2}) is not None and
        likes.find_one({"liker_id": user2, "liked_id": user1}) is not None
    )

# ----------------------
# Debug utility (optional)
# ----------------------
def all_users():
    return list(users.find({}))

def clear_all():
    users.delete_many({})
    likes.delete_many({})
