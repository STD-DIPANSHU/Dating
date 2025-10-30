import json
import os

DB_FILE = "users.json"


# Load database from file
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)


# Save database to file
def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


# Get user info
def get_user(user_id):
    data = load_db()
    user_id = str(user_id)
    return data.get(user_id)


# Save or update user
def save_user(user_id, info=None, step=None):
    data = load_db()
    user_id = str(user_id)

    if user_id not in data:
        data[user_id] = {"id": user_id}

    if step:
        data[user_id]["step"] = step
    if isinstance(info, dict):
        data[user_id].update(info)

    save_db(data)


# Like system
def like_user(from_id, to_id, check_only=False):
    data = load_db()
    from_id, to_id = str(from_id), str(to_id)

    if from_id not in data:
        return False

    if "likes" not in data[from_id]:
        data[from_id]["likes"] = []

    # Check mutual like
    if check_only:
        return "likes" in data[to_id] and from_id in data[to_id]["likes"]

    if to_id in data[from_id]["likes"]:
        return False

    data[from_id]["likes"].append(to_id)
    save_db(data)
    return True


# Find potential match
def find_match(user_id):
    data = load_db()
    user_id = str(user_id)

    if user_id not in data:
        return None

    user = data[user_id]

    for uid, info in data.items():
        if uid == user_id:
            continue
        if info.get("step") == "done":
            # Skip already matched
            if "likes" in info and user_id in info["likes"]:
                continue
            return uid
    return None
