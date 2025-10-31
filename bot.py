import os
import asyncio
from typing import Dict, Any, List, Optional

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

from db import (
    save_user, get_user, update_user_partial,
    find_random_profile, like_user, check_match,
    list_who_liked_me, record_who_liked,
    record_report, block_user, is_blocked,
    record_rating, get_average_rating
)

# ---------------- ENV ----------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise RuntimeError("Set API_ID, API_HASH, BOT_TOKEN environment variables.")

app = Client("std_dating_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------------- STATE ----------------
sessions: Dict[int, Dict[str, Any]] = {}
active_chats: Dict[int, int] = {}
pending_ratings: Dict[int, int] = {}

WELCOME_IMAGE = "start.jpg" if os.path.exists("start.jpg") else None

# ---------------- KEYBOARDS ----------------
def start_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Create Profile 👤", callback_data="create_profile")]])

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Search Profiles", callback_data="search")],
        [InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
        [InlineKeyboardButton("💌 Who Liked Me", callback_data="who_liked"),
         InlineKeyboardButton("✏️ Edit Profile", callback_data="edit_profile")]
    ])

def search_kb(target_user_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❤️ Like", callback_data=f"like:{target_user_id}"),
            InlineKeyboardButton("💔 Dislike", callback_data=f"dislike:{target_user_id}"),
            InlineKeyboardButton("🚫 Report", callback_data=f"report_menu:{target_user_id}")
        ],
        [InlineKeyboardButton("🔁 Next", callback_data="search")]
    ])

def report_reasons_kb(target_user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Fake Profile", callback_data=f"report:{target_user_id}:fake")],
        [InlineKeyboardButton("Spam", callback_data=f"report:{target_user_id}:spam")],
        [InlineKeyboardButton("Abuse / Harassment", callback_data=f"report:{target_user_id}:abuse")]
    ])

def rate_kb(partner_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐", callback_data=f"rate:{partner_id}:1"),
         InlineKeyboardButton("⭐⭐", callback_data=f"rate:{partner_id}:2"),
         InlineKeyboardButton("⭐⭐⭐", callback_data=f"rate:{partner_id}:3")],
        [InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rate:{partner_id}:4"),
         InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate:{partner_id}:5")]
    ])

# ---------------- HELPERS ----------------
def start_session(uid: int):
    sessions[uid] = {"stage": "name", "profile": {"photos": [], "hobbies": []}}

def clear_session(uid: int):
    sessions.pop(uid, None)

def session_get(uid: int) -> Optional[Dict[str, Any]]:
    return sessions.get(uid)

# ---------------- /start ----------------
@app.on_message(filters.private & filters.command("start"))
async def start_cmd(_, message: Message):
    uid = message.from_user.id
    user = get_user(uid)
    caption = "🌟 Welcome to STD Dating Bot — Create your profile to start meeting amazing people!"

    if user and user.get("name"):
        await message.reply_text(f"Welcome back, {user.get('name')}!", reply_markup=main_kb())
        return

    if WELCOME_IMAGE:
        try:
            await message.reply_photo(WELCOME_IMAGE, caption=caption, reply_markup=start_kb())
            return
        except:
            pass

    await message.reply_text(caption, reply_markup=start_kb())

# ---------------- PROFILE CREATION ----------------
@app.on_callback_query(filters.regex("^create_profile$"))
async def cb_create_profile(_, query: CallbackQuery):
    uid = query.from_user.id
    start_session(uid)
    await query.message.reply_text("Let's start! What's your *name*?", parse_mode="markdown")
    await query.answer()

# ---------------- MESSAGE ROUTER ----------------
@app.on_message(filters.private & ~filters.command(["start", "end"]))
async def message_router(client: Client, message: Message):
    uid = message.from_user.id

    # Chat mode
    if uid in active_chats:
        partner = active_chats.get(uid)
        if not partner:
            await message.reply_text("Your chat partner is unavailable.")
            return
        if is_blocked(uid, partner) or is_blocked(partner, uid):
            active_chats.pop(uid, None)
            active_chats.pop(partner, None)
            await message.reply_text("Chat ended due to block.")
            try:
                await client.send_message(partner, "Chat ended due to block.")
            except:
                pass
            return

        if message.text:
            await client.send_message(partner, f"💬 Stranger: {message.text}")
        elif message.photo:
            await client.send_photo(partner, message.photo.file_id, caption="📷 Stranger sent a photo")
        else:
            await message.reply_text("Only text and photos can be sent here.")
        return

    # Profile creation session
    sess = session_get(uid)
    if not sess:
        await message.reply_text("Use /start to begin or tap a menu button.", reply_markup=main_kb())
        return

    stage = sess["stage"]
    prof = sess["profile"]

    if stage == "name":
        prof["name"] = message.text.strip()
        sess["stage"] = "gender"
        await message.reply_text("What's your gender? (Boy/Girl/Other)")

    elif stage == "gender":
        g = message.text.title().strip()
        if g not in ["Boy", "Girl", "Other"]:
            await message.reply_text("Please reply with Boy / Girl / Other.")
            return
        prof["gender"] = g
        sess["stage"] = "preference"
        await message.reply_text("Who are you looking for? (Boys/Girls/Everyone)")

    elif stage == "preference":
        p = message.text.title().strip()
        if p not in ["Boys", "Girls", "Everyone"]:
            await message.reply_text("Please reply with Boys / Girls / Everyone.")
            return
        prof["preference"] = p
        sess["stage"] = "city"
        await message.reply_text("Which city are you from?")

    elif stage == "city":
        prof["city"] = message.text.strip()
        sess["stage"] = "age"
        await message.reply_text("How old are you?")

    elif stage == "age":
        if not message.text.isdigit():
            await message.reply_text("Please enter a valid age.")
            return
        prof["age"] = int(message.text)
        sess["stage"] = "photos"
        await message.reply_text("Send up to 3 photos (send one now). When done, press 'That's it'.",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("That's it", callback_data="photos:done")]]))

    elif stage == "hobbies":
        parts = [p.strip() for p in message.text.split(",") if p.strip()]
        prof["hobbies"].extend(parts[:3 - len(prof['hobbies'])])
        if len(prof["hobbies"]) >= 3:
            sess["stage"] = "bio"
            await message.reply_text("Now write a short bio about yourself.")
        else:
            await message.reply_text(f"Got {len(prof['hobbies'])}/3 hobbies. Send more or comma-separated list.")

    elif stage == "bio":
        prof["bio"] = message.text.strip()
        if not prof.get("photos"):
            sess["stage"] = "photos"
            await message.reply_text("You must upload at least one photo. Send now.")
            return

        save_user(uid, prof.get("name"), prof.get("gender"), prof.get("age"),
                  prof.get("bio"), prof.get("photos"), prof.get("city"),
                  prof.get("preference"), prof.get("hobbies"))
        clear_session(uid)
        await message.reply_text("✅ Profile saved successfully!", reply_markup=main_kb())

# ---------------- PHOTO HANDLER ----------------
@app.on_message(filters.photo & filters.private)
async def photo_handler(_, message: Message):
    uid = message.from_user.id
    sess = session_get(uid)
    if not sess or sess["stage"] != "photos":
        await message.reply_text("Not expecting a photo now.")
        return
    prof = sess["profile"]
    if len(prof["photos"]) < 3:
        prof["photos"].append(message.photo.file_id)
        await message.reply_text(f"Photo saved ({len(prof['photos'])}/3). Send more or press 'That's it'.",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("That's it", callback_data="photos:done")]]))
    else:
        await message.reply_text("You can only upload up to 3 photos.")

# ---------------- /end ----------------
@app.on_message(filters.private & filters.command("end"))
async def end_chat_cmd(client: Client, message: Message):
    uid = message.from_user.id
    partner = active_chats.pop(uid, None)
    if not partner:
        await message.reply_text("You’re not in a chat right now.")
        return
    active_chats.pop(partner, None)
    await message.reply_text("Chat ended. Please rate your partner:", reply_markup=rate_kb(partner))
    try:
        await client.send_message(partner, "The other user ended the chat. Please rate them:", reply_markup=rate_kb(uid))
    except:
        pass
    pending_ratings[uid] = partner
    pending_ratings[partner] = uid

# ---------------- START BOT ----------------
if __name__ == "__main__":
    print("🚀 STD Dating Bot (MongoDB + Pyrogram) started successfully...")
    app.run()
