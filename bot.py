import os
import asyncio
from typing import Dict, Any, List

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# MongoDB helper functions (you should have db.py as provided earlier)
from db import save_user, get_user, get_random_user, like_user, is_match

# ----------------------
# Config (from env)
# ----------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise RuntimeError("Set API_ID, API_HASH and BOT_TOKEN environment variables")

app = Client("std_dating_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ----------------------
# In-memory session state (temporary)
# ----------------------
sessions: Dict[int, Dict[str, Any]] = {}
# active anonymous chats mapping: user_id -> partner_id
active_chats: Dict[int, int] = {}

# ----------------------
# Helper keyboards
# ----------------------
def main_menu_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔍 Search Profiles", callback_data="search")],
            [InlineKeyboardButton("✏️ Edit Profile", callback_data="edit_profile")]
        ]
    )

def search_kb(target_id: int):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("❤️ Like", callback_data=f"like:{target_id}"),
                InlineKeyboardButton("💔 Dislike", callback_data=f"dislike:{target_id}"),
                InlineKeyboardButton("🔁 Next", callback_data="search")
            ]
        ]
    )

def edit_menu_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Name", callback_data="edit_field:name"),
             InlineKeyboardButton("Gender", callback_data="edit_field:gender")],
            [InlineKeyboardButton("Age", callback_data="edit_field:age"),
             InlineKeyboardButton("Photos", callback_data="edit_field:photos")],
            [InlineKeyboardButton("Hobbies", callback_data="edit_field:hobbies"),
             InlineKeyboardButton("Bio", callback_data="edit_field:bio")],
            [InlineKeyboardButton("Back", callback_data="back_to_menu")]
        ]
    )

# ----------------------
# Utility helpers
# ----------------------
def init_session(user_id: int):
    sessions[user_id] = {
        "stage": "name",
        "profile": {"photos": [], "hobbies": []}
    }

def clear_session(user_id: int):
    if user_id in sessions:
        del sessions[user_id]

# ----------------------
# /start handler - kick off profile creation if not present
# ----------------------
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    uid = message.from_user.id
    existing = get_user(uid)
    if existing and existing.get("name"):
        await message.reply_text(
            f"👋 Welcome back {existing.get('name')}!\nUse the menu below:",
            reply_markup=main_menu_kb()
        )
        return

    # start session
    init_session(uid)
    await message.reply_text("Hey! Let's create your profile. What's your *name*?")

# ----------------------
# Message handler for profile creation & anonymous chat
# ----------------------
@app.on_message(filters.private & ~filters.command(["start", "search", "find", "end"]))
async def message_router(client: Client, message: Message):
    uid = message.from_user.id

    # 1) If user in anonymous chat, relay messages to partner
    if uid in active_chats:
        partner = active_chats.get(uid)
        if partner:
            # send text or photo or other allowed types (here: text & photos)
            if message.text:
                await client.send_message(partner, f"💬 Stranger: {message.text}")
            elif message.photo:
                # forward photo by file_id
                file_id = message.photo.file_id
                await client.send_photo(partner, file_id, caption="📷 Stranger sent a photo")
            else:
                await message.reply_text("Only text and photos supported in anonymous chat.")
        else:
            await message.reply_text("Your chat partner is not available.")
        return

    # 2) Handle edit flows or profile creation sessions
    if uid in sessions:
        session = sessions[uid]
        stage = session.get("stage")

        # NAME
        if stage == "name":
            session["profile"]["name"] = message.text.strip()
            session["stage"] = "gender"
            await message.reply_text("Got it. What's your gender? (Male/Female/Other)")

        # GENDER
        elif stage == "gender":
            g = message.text.strip().title()
            if g not in ["Male", "Female", "Other"]:
                await message.reply_text("Please type Male, Female, or Other.")
                return
            session["profile"]["gender"] = g
            session["stage"] = "age"
            await message.reply_text("Great. How old are you? (number)")

        # AGE
        elif stage == "age":
            if not message.text.isdigit():
                await message.reply_text("Please send a valid number for age.")
                return
            age = int(message.text)
            if age < 16:
                await message.reply_text("You must be 16+ to use this bot.")
                clear_session(uid)
                return
            session["profile"]["age"] = age
            session["stage"] = "photos"
            await message.reply_text("Now send 3 profile photos, one by one. Send first photo.")

        # PHOTOS (text not expected)
        elif stage == "photos":
            await message.reply_text("Please send a photo (3 required).")

        # HOBBIES (expecting comma separated or one per message until 3)
        elif stage == "hobbies":
            # accept comma separated or single
            parts = [p.strip() for p in message.text.split(",") if p.strip()]
            current = session["profile"].get("hobbies", [])
            for p in parts:
                if len(current) < 3:
                    current.append(p)
            session["profile"]["hobbies"] = current
            if len(current) >= 3:
                session["stage"] = "bio"
                await message.reply_text("Nice. Now write a short bio about yourself (one line).")
            else:
                await message.reply_text(f"Added. Send more hobbies. {len(current)}/3 collected.")

        # BIO
        elif stage == "bio":
            session["profile"]["bio"] = message.text.strip()
            # finalize: save to DB
            prof = session["profile"]
            # ensure we have at least 3 photos and 3 hobbies
            photos = prof.get("photos", [])
            hobbies = prof.get("hobbies", [])
            if len(photos) < 3 or len(hobbies) < 3:
                await message.reply_text("Profile incomplete: need 3 photos and 3 hobbies. Please complete them.")
                return
            # Save user (db.save_user should upsert)
            save_user(uid, prof["name"], prof["gender"], prof["age"], prof["bio"], photos)
            clear_session(uid)
            await message.reply_text("✅ Profile saved! Use the menu below:", reply_markup=main_menu_kb())

        else:
            await message.reply_text("Unexpected stage. Please /start to begin.")

        return

    # 3) If not in session and not in chat -> help text
    await message.reply_text("Use /start to create profile or use the menu. /end to stop chat if any.")

# ----------------------
# Photo handler (collect photos during profile creation or editing)
# ----------------------
@app.on_message(filters.photo & filters.private)
async def photo_handler(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in sessions:
        await message.reply_text("Not expecting a photo now. Use /start to create a profile or Edit Profile.")
        return

    session = sessions[uid]
    if session.get("stage") != "photos":
        await message.reply_text("Not expecting a photo at this stage.")
        return

    # collect file_id (store up to 3)
    photos: List[str] = session["profile"].get("photos", [])
    file_id = message.photo.file_id
    if file_id not in photos:
        photos.append(file_id)
    session["profile"]["photos"] = photos

    if len(photos) < 3:
        await message.reply_text(f"Photo received ({len(photos)}/3). Send next photo.")
    else:
        session["stage"] = "hobbies"
        await message.reply_text("All photos received ✅\nNow send 3 hobbies (comma separated or one per message).")

# ----------------------
# Callback: main menu / search / edit
# ----------------------
@app.on_callback_query(filters.regex("^(search|edit_profile|create_profile)$"))
async def menu_buttons(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    action = query.data

    if action == "create_profile":
        init_session(uid)
        await query.message.reply_text("What's your name?")
        await query.answer()
        return

    if action == "edit_profile":
        # confirm user exists
        user = get_user(uid)
        if not user:
            await query.message.reply_text("You don't have a profile yet. Click Create Profile.")
            await query.answer()
            return
        await query.message.reply_text("Choose field to edit:", reply_markup=edit_menu_kb())
        await query.answer()
        return

    if action == "search":
        user = get_user(uid)
        if not user:
            await query.message.reply_text("Please create a profile first using /start")
            await query.answer()
            return
        candidate = get_random_user(uid)
        if not candidate:
            await query.message.reply_text("No profiles available right now, try later.")
            await query.answer()
            return

        caption = (
            f"👤 {candidate['name']}, {candidate.get('age','?')} yrs\n"
            f"🚻 {candidate.get('gender','?')}\n\n"
            f"📝 {candidate.get('bio','')}\n\n"
            "Choose an action:"
        )
        # candidate['photo'] might be list or single — handle both
        photo = candidate.get("photo")
        # If your db stored photos as list, show first; else direct
        if isinstance(photo, list):
            photo_to_send = photo[0] if photo else None
        else:
            photo_to_send = photo

        if photo_to_send:
            await client.send_photo(uid, photo_to_send, caption=caption, reply_markup=search_kb(candidate["_id"] if "_id" in candidate else candidate["id"]))
        else:
            await client.send_message(uid, caption, reply_markup=search_kb(candidate["_id"] if "_id" in candidate else candidate["id"]))

        await query.answer()
        return

# ----------------------
# Callback: like/dislike/next and edit subflows
# ----------------------
@app.on_callback_query(filters.regex("^(like:|dislike:|search|next:|edit_field:|back_to_menu)$"))
async def action_handler(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    data = query.data

    # Edit profile fields
    if data.startswith("edit_field:"):
        field = data.split(":", 1)[1]
        # start an edit session
        sessions[uid] = {"stage": f"edit_{field}", "profile": {}}
        await query.message.reply_text(f"Send new value for *{field}* now.")
        await query.answer()
        return

    if data == "back_to_menu":
        await query.message.reply_text("Back to menu:", reply_markup=main_menu_kb())
        await query.answer()
        return

    # Like
    if data.startswith("like:"):
        target_id = int(data.split(":", 1)[1])

        # record like
        like_user(uid, target_id)

        # check mutual
        if is_match(uid, target_id):
            # create anonymous chat
            active_chats[uid] = target_id
            active_chats[target_id] = uid

            await client.send_message(uid, "💞 It's a MATCH! Anonymous chat started. Type messages here — use /end to stop.")
            try:
                await client.send_message(target_id, "💞 It's a MATCH! Anonymous chat started. Type messages here — use /end to stop.")
            except Exception:
                # target may not be reachable
                pass
        else:
            await query.message.reply_text("You liked them — waiting for their response.")
        await query.answer()
        return

    # Dislike
    if data.startswith("dislike:"):
        # treat as skip; user asked search again
        await query.message.reply_text("Disliked. Searching next...")
        await query.answer()
        # trigger a search for next candidate
        # reuse search flow
        await menu_buttons(client, CallbackQuery._factory(client, query.message, "search", query.from_user))
        return

    # Next or general search trigger
    if data == "search" or data.startswith("next:"):
        await query.answer()
        # reuse search
        await menu_buttons(client, query._replace(data="search"))
        return

# ----------------------
# Command to end anonymous chat
# ----------------------
@app.on_message(filters.command("end") & filters.private)
async def end_chat(client: Client, message: Message):
    uid = message.from_user.id
    partner = active_chats.get(uid)
    if not partner:
        await message.reply_text("You don't have an active anonymous chat.")
        return

    # remove both sides
    active_chats.pop(uid, None)
    active_chats.pop(partner, None)

    await message.reply_text("You ended the anonymous chat.")
    try:
        await client.send_message(partner, "The other user ended the anonymous chat.")
    except Exception:
        pass

# ----------------------
# Edit session message handler (accept new data for edits)
# ----------------------
@app.on_message(filters.private & ~filters.command(["start", "end", "search"]))
async def edit_session_handler(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in sessions:
        return  # no edit session

    session = sessions[uid]
    stage = session.get("stage", "")

    # Editing a simple field
    if stage.startswith("edit_"):
        field = stage.replace("edit_", "")
        new_value = message.text.strip()

        # fetch current user, update and save
        user = get_user(uid) or {}
        # photos and hobbies are special
        if field == "photos":
            await message.reply_text("To update photos, send 3 photos one by one now.")
            sessions[uid] = {"stage": "edit_photos", "profile": {"photos": []}}
            return

        if field == "hobbies":
            # accept comma separated list or single lines
            parts = [p.strip() for p in new_value.split(",") if p.strip()]
            user["hobbies"] = parts[:3]
        else:
            user[field] = int(new_value) if field == "age" and new_value.isdigit() else new_value

        # Save merged fields (db.save_user upserts all fields)
        # Ensure you map db.save_user signature: save_user(user_id, name, gender, age, bio, photo)
        save_user(uid,
                  user.get("name"),
                  user.get("gender"),
                  user.get("age"),
                  user.get("bio"),
                  user.get("photo"))
        sessions.pop(uid, None)
        await message.reply_text(f"{field.capitalize()} updated successfully.", reply_markup=main_menu_kb())
        return

    # Editing photos flow
    if stage == "edit_photos":
        photos: List[str] = session["profile"].get("photos", [])
        if message.photo:
            fid = message.photo.file_id
            photos.append(fid)
            session["profile"]["photos"] = photos
            if len(photos) < 3:
                await message.reply_text(f"Photo received ({len(photos)}/3). Send next.")
            else:
                # update DB
                user = get_user(uid) or {}
                # store list of photos (db.save_user expects 'photo' param — we pass list)
                save_user(uid,
                          user.get("name"),
                          user.get("gender"),
                          user.get("age"),
                          user.get("bio"),
                          photos)
                sessions.pop(uid, None)
                await message.reply_text("Photos updated successfully.", reply_markup=main_menu_kb())
        else:
            await message.reply_text("Please send a photo.")
        return

# ----------------------
# Start the bot
# ----------------------
if __name__ == "__main__":
    print("🚀 STD Dating Bot (Pyrogram + MongoDB) starting...")
    app.run()
