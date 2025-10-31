import os
from pymongo import MongoClient
from typing import Optional, List, Dict, Any

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("Set MONGO_URI env var")

client = MongoClient(MONGO_URI)
db = client["std_dating_bot"]
users = db["users"]          # documents keyed by user_id
likes = db["likes"]          # documents: { user_id: X, target_id: Y }
who_likes = db["who_likes"]  # optional: quick lookup

# Save or update full user profile
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
            "hobbies": hobbies
        }},
        upsert=True
    )

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    doc = users.find_one({"user_id": user_id})
    return doc

# update partial (convenience)
def update_user_partial(user_id: int, patch: Dict[str, Any]):
    users.update_one({"user_id": user_id}, {"$set": patch}, upsert=True)

# Find random profile according to preference & excluding already liked ones
def find_random_profile(current_user_id: int) -> Optional[Dict[str, Any]]:
    cur = get_user(current_user_id)
    if not cur:
        return None
    pref = cur.get("preference", "Everyone")
    # build filter
    flt = {"user_id": {"$ne": current_user_id}}
    if pref == "Boys":
        flt["gender"] = "Boy"
    elif pref == "Girls":
        flt["gender"] = "Girl"
    # Exclude users already liked by current_user
    liked = [d["target_id"] for d in likes.find({"user_id": current_user_id})]
    if liked:
        flt["user_id"] = {"$ne": current_user_id, "$nin": liked}
    # sample one
    res = list(users.aggregate([{"$match": flt}, {"$sample": {"size": 1}}]))
    if not res:
        return None
    return res[0]

# record a like
def like_user(user_id: int, target_id: int):
    likes.update_one({"user_id": user_id, "target_id": target_id},
                     {"$set": {"user_id": user_id, "target_id": target_id}}, upsert=True)

# who liked me list (reads likes collection)
def list_who_liked_me(user_id: int) -> List[Dict[str, Any]]:
    docs = likes.find({"target_id": user_id})
    out = []
    for d in docs:
        u = get_user(d["user_id"])
        if u:
            out.append({"user_id": d["user_id"], "name": u.get("name")})
    return out

# optional helper to record reverse quick lookup
def record_who_liked(user_id: int, liker_id: int):
    # also keep a separate small collection for faster "who liked me" queries if needed
    who_likes.update_one({"user_id": user_id, "liker_id": liker_id},
                         {"$set": {"user_id": user_id, "liker_id": liker_id}}, upsert=True)

# check mutual like
def check_match(user1: int, user2: int) -> bool:
    return likes.find_one({"user_id": user2, "target_id": user1}) is not None
