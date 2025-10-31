import os
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING
from datetime import datetime

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("Set MONGO_URI env var")

client = MongoClient(MONGO_URI)
db = client["std_dating_bot"]
users = db["users"]         # user documents keyed by user_id
likes = db["likes"]         # { user_id, target_id }
blocks = db["blocks"]       # { blocker_id, blocked_id }
reports = db["reports"]     # { reporter_id, reported_id, reason, ts }
ratings = db["ratings"]     # { rater_id, target_id, rating, ts }

# indexes (optional, improves queries)
users.create_index([("user_id", ASCENDING)], unique=True)
likes.create_index([("user_id", ASCENDING), ("target_id", ASCENDING)], unique=True)
blocks.create_index([("blocker_id", ASCENDING), ("blocked_id", ASCENDING)], unique=True)
reports.create_index([("reported_id", ASCENDING)])
ratings.create_index([("target_id", ASCENDING)])

# Save / update full profile
def save_user(user_id: int,
              name: Optional[str],
              gender: Optional[str],
              age: Optional[int],
              bio: Optional[str],
              photos: Optional[List[str]],
              city: Optional[str] = None,
              preference: Optional[str] = None,
              hobbies: Optional[List[str]] = None):
    if photos is None:
        photos = []
    if hobbies is None:
        hobbies = []
    users.update_one(
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
            "hobbies": hobbies,
            "updated_at": datetime.utcnow()
        }},
        upsert=True
    )

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    return users.find_one({"user_id": user_id})

def update_user_partial(user_id: int, patch: Dict[str, Any]):
    users.update_one({"user_id": user_id}, {"$set": patch}, upsert=True)

# block utilities
def block_user(blocker_id: int, blocked_id: int):
    blocks.update_one({"blocker_id": blocker_id, "blocked_id": blocked_id},
                      {"$set": {"blocker_id": blocker_id, "blocked_id": blocked_id, "ts": datetime.utcnow()}},
                      upsert=True)

def is_blocked(a: int, b: int) -> bool:
    # return True if a blocked b OR b blocked a? We use directional checks in bot; here check if a blocked b
    return blocks.find_one({"blocker_id": a, "blocked_id": b}) is not None

# find random profile, exclude blocks and those already liked
def find_random_profile(current_user_id: int) -> Optional[Dict[str, Any]]:
    cur = get_user(current_user_id)
    if not cur:
        return None
    pref = cur.get("preference", "Everyone")
    flt = {"user_id": {"$ne": current_user_id}}
    if pref == "Boys":
        flt["gender"] = "Boy"
    elif pref == "Girls":
        flt["gender"] = "Girl"
    # exclude users blocked by current_user or who blocked current_user
    blocked_by_me = [d["blocked_id"] for d in blocks.find({"blocker_id": current_user_id})]
    blocked_me = [d["blocker_id"] for d in blocks.find({"blocked_id": current_user_id})]
    exclude = set(blocked_by_me + blocked_me + [current_user_id])
    if exclude:
        flt["user_id"] = {"$nin": list(exclude)}
    # exclude already liked targets
    liked = [d["target_id"] for d in likes.find({"user_id": current_user_id})]
    if liked:
        # we must intersect with other filters; easiest: do aggregate with match excluding liked
        if "user_id" in flt and isinstance(flt["user_id"], dict):
            # combine conditions: user_id not in exclude AND not in liked
            flt["user_id"]["$nin"] = list(set(flt["user_id"].get("$nin", []) + liked))
        else:
            flt["user_id"] = {"$nin": list(set(list(exclude) + liked))}
    # aggregate sample
    res = list(users.aggregate([{"$match": flt}, {"$sample": {"size": 1}}]))
    if not res:
        return None
    return res[0]

# likes
def like_user(user_id: int, target_id: int):
    likes.update_one({"user_id": user_id, "target_id": target_id},
                     {"$set": {"user_id": user_id, "target_id": target_id, "ts": datetime.utcnow()}},
                     upsert=True)

def check_match(user1: int, user2: int) -> bool:
    return likes.find_one({"user_id": user2, "target_id": user1}) is not None

def record_who_liked(target_id: int, liker_id: int):
    # this just duplicates likes collection — here for convenience / analytics
    # we already store likes; nothing extra required
    return

def list_who_liked_me(user_id: int) -> List[Dict[str, Any]]:
    docs = likes.find({"target_id": user_id})
    out = []
    for d in docs:
        u = get_user(d["user_id"])
        if u:
            out.append({"user_id": d["user_id"], "name": u.get("name")})
    return out

# reports
def record_report(reporter_id: int, reported_id: int, reason: str):
    reports.insert_one({"reporter_id": reporter_id, "reported_id": reported_id, "reason": reason, "ts": datetime.utcnow()})

# ratings
def record_rating(rater_id: int, target_id: int, rating: int):
    if rating < 1 or rating > 5:
        return
    ratings.update_one({"rater_id": rater_id, "target_id": target_id},
                       {"$set": {"rater_id": rater_id, "target_id": target_id, "rating": rating, "ts": datetime.utcnow()}},
                       upsert=True)

def get_average_rating(user_id: int) -> float:
    docs = list(ratings.find({"target_id": user_id}))
    if not docs:
        return 0.0
    total = sum([d.get("rating", 0) for d in docs])
    return total / len(docs)
