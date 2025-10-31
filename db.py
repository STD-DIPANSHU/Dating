import pymongo
import random
from typing import List, Dict, Any

# MongoDB setup
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "std_dating"

client = pymongo.MongoClient(MONGO_URI)
db = client[DB_NAME]

users_col = db["users"]
likes_col = db["likes"]
blocks_col = db["blocks"]
reports_col = db["reports"]
ratings_col = db["ratings"]


# -------------------- USER FUNCTIONS --------------------
def save_user(user_id: int, name: str, gender: str, age: int, bio: str,
              photos: List[str], city: str, preference: str, hobbies: List[str]):
    """Create or update a user profile"""
    users_col.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "name": name,
            "gender": gender,
            "age": age,
            "bio": bio,
            "photos": photos,
            "city": city,
            "preference": preference,
            "hobbies": hobbies
        }},
        upsert=True
    )


def get_user(user_id: int) -> Dict[str, Any]:
    """Return user profile dict"""
    return users_col.find_one({"user_id": user_id})


def update_user_partial(user_id: int, data: Dict[str, Any]):
    """Update partial fields"""
    users_col.update_one({"user_id": user_id}, {"$set": data})


# -------------------- MATCHING --------------------
def find_random_profile(user_id: int) -> Dict[str, Any]:
    """Find random profile based on gender preference"""
    me = get_user(user_id)
    if not me:
        return None

    pref = me.get("preference", "Everyone")
    gender_filter = {}
    if pref == "Boys":
        gender_filter = {"gender": "Boy"}
    elif pref == "Girls":
        gender_filter = {"gender": "Girl"}

    # blocked users (skip)
    blocked_ids = [b["blocked_id"] for b in blocks_col.find({"blocker_id": user_id})]
    blocked_ids += [b["blocker_id"] for b in blocks_col.find({"blocked_id": user_id})]

    candidates = list(users_col.find({
        "user_id": {"$ne": user_id, "$nin": blocked_ids},
        **gender_filter
    }))

    if not candidates:
        return None
    return random.choice(candidates)


# -------------------- LIKES & MATCH --------------------
def like_user(user_id: int, target_id: int):
    """Record a like"""
    if not likes_col.find_one({"user_id": user_id, "target_id": target_id}):
        likes_col.insert_one({"user_id": user_id, "target_id": target_id})


def check_match(user_id: int, target_id: int) -> bool:
    """Check if both liked each other"""
    return (
        likes_col.find_one({"user_id": user_id, "target_id": target_id}) and
        likes_col.find_one({"user_id": target_id, "target_id": user_id})
    )


def list_who_liked_me(user_id: int) -> List[Dict[str, Any]]:
    """Return list of users who liked current user"""
    liked = likes_col.find({"target_id": user_id})
    result = []
    for l in liked:
        u = get_user(l["user_id"])
        if u:
            result.append(u)
    return result


def record_who_liked(target_id: int, user_id: int):
    """Extra function to log likes (if needed for analytics)"""
    pass  # already handled in like_user()


# -------------------- REPORTS --------------------
def record_report(reporter_id: int, target_id: int, reason: str):
    """Record a report"""
    reports_col.insert_one({
        "reporter_id": reporter_id,
        "target_id": target_id,
        "reason": reason
    })


# -------------------- BLOCKS --------------------
def block_user(blocker_id: int, blocked_id: int):
    """Block a user"""
    if not blocks_col.find_one({"blocker_id": blocker_id, "blocked_id": blocked_id}):
        blocks_col.insert_one({"blocker_id": blocker_id, "blocked_id": blocked_id})


def is_blocked(user_id: int, target_id: int) -> bool:
    """Check if user or target has blocked each other"""
    return bool(blocks_col.find_one({
        "$or": [
            {"blocker_id": user_id, "blocked_id": target_id},
            {"blocker_id": target_id, "blocked_id": user_id}
        ]
    }))


# -------------------- RATINGS --------------------
def record_rating(rater_id: int, partner_id: int, stars: int):
    """Store rating for partner"""
    if not (1 <= stars <= 5):
        return
    ratings_col.insert_one({
        "rater_id": rater_id,
        "partner_id": partner_id,
        "stars": stars
    })


def get_average_rating(user_id: int) -> float:
    """Return average rating of a user"""
    ratings = list(ratings_col.find({"partner_id": user_id}))
    if not ratings:
        return 0.0
    total = sum(r["stars"] for r in ratings)
    return total / len(ratings)
