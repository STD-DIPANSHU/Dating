from pymongo import MongoClient
import random
import os

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://<username>:<password>@<cluster-url>/")  # replace with your real URI
client = MongoClient(MONGO_URI)
db = client["dating_bot"]

users = db["users"]
likes = db["likes"]

# Save or update user profile
def save_user(user_id, name, gender, age, bio, photo):
    users.update_one(
        {"_id": user_id},
        {"$set": {
            "name": name,
            "gender": gender,
            "age": age,
            "bio": bio,
            "photo": photo
        }},
        upsert=True
    )

# Get user by ID
def get_user(user_id):
    user = users.find_one({"_id": user_id})
    if not user:
        return None
    return {
        "id": user["_id"],
        "name": user.get("name"),
        "gender": user.get("gender"),
        "age": user.get("age"),
        "bio": user.get("bio"),
        "photo": user.get("photo")
    }

# Get random user (not same, not already liked)
def get_random_user(current_user_id):
    liked_ids = [l["liked_id"] for l in likes.find({"liker_id": current_user_id})]
    pipeline = [
        {"$match": {"_id": {"$ne": current_user_id, "$nin": liked_ids}}},
        {"$sample": {"size": 1}}
    ]
    result = list(users.aggregate(pipeline))
    if not result:
        return None
    user = result[0]
    return {
        "id": user["_id"],
        "name": user.get("name"),
        "gender": user.get("gender"),
        "age": user.get("age"),
        "bio": user.get("bio"),
        "photo": user.get("photo")
    }

# Like another user
def like_user(liker_id, liked_id):
    likes.insert_one({"liker_id": liker_id, "liked_id": liked_id})

# Check if match exists
def is_match(user1, user2):
    return likes.find_one({"liker_id": user2, "liked_id": user1}) is not None
