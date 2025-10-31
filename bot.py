import os
import asyncio
from typing import Dict, Any, List, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery
)

from db import (
    save_user, get_user, update_user_partial,
    find_random_profile, like_user, check_match,
    list_who_liked_me, record_who_liked
)

# -------------------------
# Config from env
# -------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise RuntimeError("Please set API_ID, API_HASH and BOT_TOKEN env vars")

app = Client("std_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory sessions (reset on restart)
sessions: Dict[int, Dict[str, Any]] = {}
# active anonymous chats: user_id -> partner_id
active_chats: Dict[int, int] = {}

# -------------------------
# Keyboards / UI helpers
# -------------------------
def kb_start():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Create a profile", callback_data="create_profile")]
    ])

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 View profiles", callback_data="search_profiles"),
         InlineKeyboardButton("👤 My profile", callback_data="my_profile")],
        [InlineKeyboardButton("💌 Who liked me", callback_data="who_liked"),
         InlineKeyboardButton("✏️ Edit profile", callback_data="edit_profile")],
        [InlineKeyboardButton("📨 Invite friends", switch_inline_query="")]
    ])

def search_buttons(user_oid):
    # user_oid can be Mongo stored id or int
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❤️", callback_data=f"like:{user_oid}"),
            InlineKeyboardButton("💌", callback_data=f"message:{user_oid}"),
            InlineKeyboardButton("👎", callback_data=f"dislike:{user_oid}")
        ],
        [
            InlineKeyboardButton("🔁 Next", callback_data="search_profiles")
        ]
    ])

def photos_actions_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("That's it, keep the photo", callback_data="photos:done")]
    ])

def edit_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Name", callback_data="edit:name"),
         InlineKeyboardButton("Gender", callback_data="edit:gender")],
        [InlineKeyboardButton("Preference", callback_data="edit:preference"),
         InlineKeyboardButton("City", callback_data="edit:city")],
        [InlineKeyboardButton("Age", callback_data="edit:age"),
         InlineKeyboardButton("Photos", callback_data="edit:photos")],
        [InlineKeyboardButton("Hobbies", callback_data="edit:hobbies"),
         InlineKeyboardButton("Bio", callback_data="edit:bio")],
        [InlineKeyboardButton("Back", callback_data="back_to_menu")]
    ])

# -------------------------
# Utilities for sessions
# -------------------------
def start_profile_session(user_id: int):
    sessions[user_id] = {
        "stage": "name",
        "profile": {
            "photos": [],
            "hobbies": []
        }
    }

def clear_session(user_id: int):
    sessions.pop(user_id, None)

def session_exists(user_id: int) -> bool:
    return user_id in sessions

# -------------------------
# /start
# -------------------------
@app.on_message(filters.private & filters.command("start"))
async def start_cmd(client: Client, message: Message):
    uid = message.from_user.id
    user = get_user(uid)
    if user and user.get("name"):
        await message.reply_text(
            f"Hi {user.get('name')} 👋\nWelcome back! Use the menu below.",
            reply_markup=main_menu_kb()
        )
    else:
        # First-time: show welcome and "Create a profile"
        await message.reply_photo(
            photo="https://i.ibb.co/QMHKxSk/default-profile.jpg",
            caption="Hi! 👋\nWelcome to our dating bot!\nTo get started, create your profile — it's quick and easy.",
            reply_markup=kb_start()
        )

# -------------------------
# Create profile button
# -------------------------
@app.on_callback_query(filters.regex("^create_profile$"))
async def cb_create_profile(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    start_profile_session(uid)
    await query.message.reply_text("What's your name? ✍️")
    await query.answer()

# -------------------------
# Message router: handles profile creation, edits and anonymous chat messages
# -------------------------
@app.on_message(filters.private & ~filters.command(["start", "end"]))
async def message_router(client: Client, message: Message):
    uid = message.from_user.id

    # 1) If in anonymous chat -> relay
    if uid in active_chats:
        partner = active_chats.get(uid)
        if not partner:
            await message.reply_text("Your partner is not available.")
            return
        # relay text/photo
        if message.text:
            await client.send_message(partner, f"💬 Stranger: {message.text}")
        elif message.photo:
            await client.send_photo(partner, message.photo.file_id, caption="📷 Stranger sent a photo")
        else:
            await message.reply_text("Only text and photos are supported during anonymous chat.")
        return

    # 2) If user in session (creating or editing)
    if session_exists(uid):
        session = sessions[uid]
        stage = session["stage"]

        # NAME
        if stage == "name":
            session["profile"]["name"] = message.text.strip()
            session["stage"] = "gender"
            await message.reply_text("State your gender 👥 (Boy / Girl / Other)")

        # GENDER
        elif stage == "gender":
            g = message.text.strip().title()
            if g not in ["Boy", "Girl", "Other"]:
                await message.reply_text("Please reply with Boy, Girl, or Other.")
                return
            session["profile"]["gender"] = g
            session["stage"] = "preference"
            await message.reply_text("Pick who you're looking for 💕 (Boys / Girls / Everyone)")

        # PREFERENCE
        elif stage == "preference":
            pref = message.text.strip().title()
            if pref not in ["Boys", "Girls", "Everyone"]:
                await message.reply_text("Please choose: Boys / Girls / Everyone")
                return
            session["profile"]["preference"] = pref
            session["stage"] = "city"
            await message.reply_text("Enter your city 🏙️")

        # CITY
        elif stage == "city":
            session["profile"]["city"] = message.text.strip()
            session["stage"] = "age"
            await message.reply_text("How old are you? 🎂 (number)")

        # AGE
        elif stage == "age":
            if not message.text.isdigit():
                await message.reply_text("Please enter a valid number for age.")
                return
            age = int(message.text)
            session["profile"]["age"] = age
            session["stage"] = "photos"
            await message.reply_text("Upload your photo(s). You can send up to 3 photos. Send first photo now.")
            await message.reply_text("You can also send multiple at once; after sending press 'That's it, keep the photo' button.", reply_markup=photos_actions_kb())

        # HOBBIES
        elif stage == "hobbies":
            # accept comma-separated or single
            parts = [p.strip() for p in message.text.split(",") if p.strip()]
            existing = session["profile"].get("hobbies", [])
            for p in parts:
                if len(existing) < 3:
                    existing.append(p)
            session["profile"]["hobbies"] = existing
            if len(existing) >= 3:
                session["stage"] = "bio"
                await message.reply_text("Tell us a little about yourself – one line bio 📝")
            else:
                await message.reply_text(f"Added. {len(existing)}/3 hobbies collected. Send more or comma-separated list.")

        # BIO
        elif stage == "bio":
            session["profile"]["bio"] = message.text.strip()
            # finalize: require photos & hobbies length
            prof = session["profile"]
            photos = prof.get("photos", [])
            hobbies = prof.get("hobbies", [])
            if len(photos) < 1:
                await message.reply_text("You must upload at least 1 photo. Please send photos now.")
                session["stage"] = "photos"
                return
            # Save to DB (db.save_user should accept photos list)
            save_user(uid,
                      prof.get("name"),
                      prof.get("gender"),
                      prof.get("age"),
                      prof.get("bio"),
                      prof.get("photos"),
                      prof.get("city"),
                      prof.get("preference"),
                      prof.get("hobbies"))
            clear_session(uid)
            await message.reply_text("Great! Your profile is ready — now you can search for interesting people.", reply_markup=main_menu_kb())
        else:
            await message.reply_text("Unexpected stage. Use /start to create profile.")
        return

    # 3) Not in session and not in chat -> regular message (help)
    await message.reply_text("Use /start to begin or use the menu. Use /end to stop an anonymous chat.")

# -------------------------
# Photo handler for session
# -------------------------
@app.on_message(filters.photo & filters.private)
async def photo_receiver(client: Client, message: Message):
    uid = message.from_user.id
    if not session_exists(uid):
        await message.reply_text("Not expecting photos now. Use Create a profile to start.")
        return
    session = sessions[uid]
    if session["stage"] != "photos":
        await message.reply_text("Not expecting photo at this moment.")
        return
    photos: List[str] = session["profile"].get("photos", [])
    fid = message.photo.file_id
    photos.append(fid)
    # keep max 3
    if len(photos) > 3:
        photos = photos[:3]
    session["profile"]["photos"] = photos
    session["profile"]["photos_count"] = len(photos)
    await message.reply_text(f"📸 Photo {len(photos)}/3 uploaded!\nYou can upload more or press 'That's it, keep the photo'.", reply_markup=photos_actions_kb())

# -------------------------
# Photos: done callback
# -------------------------
@app.on_callback_query(filters.regex("^photos:done$"))
async def photos_done_cb(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    if not session_exists(uid):
        await query.answer("No photo session found.")
        return
    session = sessions[uid]
    # move to hobbies
    session["stage"] = "hobbies"
    await query.message.reply_text("Tell us a little about yourself - it will help others get to know you better! 📝\n(You will be asked to add 3 hobbies)")
    await query.answer()

# -------------------------
# Main menu callbacks: search / my profile / edit / who liked
# -------------------------
@app.on_callback_query(filters.regex("^(search_profiles|my_profile|edit_profile|who_liked)$"))
async def menu_cb(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    action = query.data

    if action == "my_profile":
        user = get_user(uid)
        if not user:
            await query.message.reply_text("You don't have a profile yet. Create one.")
            await query.answer()
            return
        photos = user.get("photos", [])
        caption = (f"{user.get('name')}, {user.get('age')} — {user.get('city')}\n"
                   f"{user.get('bio')}\n\nHobbies: {', '.join(user.get('hobbies',[])[:3])}")
        if photos:
            await client.send_photo(uid, photos[0], caption=caption)
        else:
            await query.message.reply_text(caption)
        await query.answer()
        return

    if action == "who_liked":
        who = list_who_liked_me(uid)
        if not who:
            await query.message.reply_text("No one liked you yet.")
            await query.answer()
            return
        text = "People who liked you:\n" + "\n".join([f"- {w.get('name','user')} (id:{w.get('user_id')})" for w in who])
        await query.message.reply_text(text)
        await query.answer()
        return

    if action == "edit_profile":
        user = get_user(uid)
        if not user:
            await query.message.reply_text("You don't have a profile yet. Create one.")
            await query.answer()
            return
        await query.message.reply_text("Choose field to edit:", reply_markup=edit_menu_kb())
        await query.answer()
        return

    if action == "search_profiles":
        # show one random candidate
        candidate = find_random_profile(uid)
        if not candidate:
            await query.message.reply_text("No profiles found right now. Try again later.")
            await query.answer()
            return
        # Build caption
        name = candidate.get("name", "User")
        age = candidate.get("age", "")
        city = candidate.get("city", "")
        bio = candidate.get("bio", "")
        hobbies = candidate.get("hobbies", [])
        caption = f"{name}, {age}, {city}\n\n{bio}\n\n{ ' // '.join(hobbies[:3]) }"
        photos = candidate.get("photos", [])
        first = photos[0] if photos else None
        # candidate's id key in db is user_id
        candidate_id = candidate.get("user_id")
        if first:
            await client.send_photo(uid, first, caption=caption, reply_markup=search_buttons(candidate_id))
        else:
            await client.send_message(uid, caption, reply_markup=search_buttons(candidate_id))
        await query.answer()
        return

# -------------------------
# Action buttons (like/dislike/message/next)
# -------------------------
@app.on_callback_query(filters.regex("^(like:|dislike:|message:|search_profiles|next_profile)$"))
async def action_cb(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    data = query.data

    if data.startswith("like:"):
        target_id = int(data.split(":",1)[1])
        # record like
        like_user(uid, target_id)
        # keep reverse record for "who liked"
        record_who_liked(target_id, uid)
        # check match
        if check_match(uid, target_id):
            # create anonymous mapping both ways
            active_chats[uid] = target_id
            active_chats[target_id] = uid
            await client.send_message(uid, "💞 It's a MATCH! 🎉 Anonymous chat started. Type messages here. Use /end to stop.")
            try:
                await client.send_message(target_id, "💞 It's a MATCH! 🎉 Anonymous chat started. Type messages here. Use /end to stop.")
            except Exception:
                pass
        else:
            await query.message.reply_text("Liked! We'll notify if it's mutual.")
        await query.answer()
        # show next candidate
        await client.delete_messages(uid, query.message.message_id)
        await menu_cb(client, CallbackQuery._factory(client, query.message, "search_profiles", query.from_user))
        return

    if data.startswith("dislike:"):
        # just skip and show next
        await query.answer("Disliked.")
        await client.delete_messages(uid, query.message.message_id)
        await menu_cb(client, CallbackQuery._factory(client, query.message, "search_profiles", query.from_user))
        return

    if data.startswith("message:"):
        # user pressed the 'message' button — we will simulate "send interest" (optional)
        target_id = int(data.split(":",1)[1])
        try:
            await client.send_message(target_id, "💌 Someone showed interest in your profile!")
        except Exception:
            pass
        await query.answer("Message sent.")
        return

    if data in ("search_profiles", "next_profile"):
        # call search
        await menu_cb(client, query._replace(data="search_profiles"))
        await query.answer()
        return

# -------------------------
# Edit field flow: choose field and accept new value
# -------------------------
@app.on_callback_query(filters.regex("^edit:"))
async def edit_field_cb(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    field = query.data.split(":",1)[1]
    # start session for edit
    sessions[uid] = {"stage": f"edit_{field}", "profile": {}}
    await query.message.reply_text(f"Send new value for *{field}* now.", parse_mode="Markdown")
    await query.answer()

# accept edit values (text or photos)
@app.on_message(filters.private & ~filters.command(["start","end"]))
async def edit_value_handler(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in sessions:
        return
    session = sessions[uid]
    stage = session.get("stage","")
    if stage.startswith("edit_"):
        field = stage.replace("edit_","")
        # photos special
        if field == "photos":
            # accept photos
            if not message.photo:
                await message.reply_text("Send photos to update (3 recommended).")
                return
            # collect photos until 3 then save
            photos = session["profile"].get("photos", [])
            photos.append(message.photo.file_id)
            session["profile"]["photos"] = photos
            if len(photos) >= 3:
                # fetch existing user to preserve other fields
                user = get_user(uid) or {}
                save_user(uid,
                          user.get("name"),
                          user.get("gender"),
                          user.get("age"),
                          user.get("bio"),
                          photos,
                          user.get("city"),
                          user.get("preference"),
                          user.get("hobbies"))
                sessions.pop(uid, None)
                await message.reply_text("Photos updated.", reply_markup=main_menu_kb())
            else:
                await message.reply_text(f"Photo received ({len(photos)}/3). Send more or press 'That's it' button.")
            return
        # other fields: simply update
        value = message.text.strip()
        user = get_user(uid) or {}
        # map to db save
        if field == "name":
            save_user(uid, value, user.get("gender"), user.get("age"), user.get("bio"), user.get("photos"), user.get("city"), user.get("preference"), user.get("hobbies"))
        elif field == "gender":
            save_user(uid, user.get("name"), value, user.get("age"), user.get("bio"), user.get("photos"), user.get("city"), user.get("preference"), user.get("hobbies"))
        elif field == "age":
            try:
                age = int(value)
            except:
                await message.reply_text("Please send a valid number for age.")
                return
            save_user(uid, user.get("name"), user.get("gender"), age, user.get("bio"), user.get("photos"), user.get("city"), user.get("preference"), user.get("hobbies"))
        elif field == "hobbies":
            parts = [p.strip() for p in value.split(",") if p.strip()]
            save_user(uid, user.get("name"), user.get("gender"), user.get("age"), user.get("bio"), user.get("photos"), user.get("city"), user.get("preference"), parts[:3])
        elif field == "bio":
            save_user(uid, user.get("name"), user.get("gender"), user.get("age"), value, user.get("photos"), user.get("city"), user.get("preference"), user.get("hobbies"))
        elif field == "city":
            save_user(uid, user.get("name"), user.get("gender"), user.get("age"), user.get("bio"), user.get("photos"), value, user.get("preference"), user.get("hobbies"))
        sessions.pop(uid, None)
        await message.reply_text(f"{field.capitalize()} updated.", reply_markup=main_menu_kb())

# -------------------------
# /end command to stop anonymous chat
# -------------------------
@app.on_message(filters.private & filters.command("end"))
async def end_cmd(client: Client, message: Message):
    uid = message.from_user.id
    partner = active_chats.pop(uid, None)
    if partner:
        # remove reciprocal
        active_chats.pop(partner, None)
        await message.reply_text("You ended the anonymous chat.")
        try:
            await client.send_message(partner, "The other user ended the anonymous chat.")
        except:
            pass
    else:
        await message.reply_text("You don't have an active anonymous chat.")

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    print("🚀 STD Dating Bot starting (Pyrogram + MongoDB)")
    app.run()
