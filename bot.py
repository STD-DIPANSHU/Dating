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

# env
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise RuntimeError("Set API_ID, API_HASH, BOT_TOKEN env vars")

app = Client("std_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# sessions in-memory
sessions: Dict[int, Dict[str, Any]] = {}
# active anonymous chats
active_chats: Dict[int, int] = {}
# pending rating prompts: user_id -> partner_id (after chat ended)
pending_ratings: Dict[int, int] = {}

# local fallback welcome image (put start.jpg in repo root) - optional
WELCOME_IMAGE = "start.jpg" if os.path.exists("start.jpg") else None

# ---------------- Keyboards ----------------
def start_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Create profile 👤", callback_data="create_profile")]])

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Search profiles", callback_data="search")],
        [InlineKeyboardButton("👤 My profile", callback_data="my_profile")],
        [InlineKeyboardButton("💌 Who liked me", callback_data="who_liked"),
         InlineKeyboardButton("✏️ Edit profile", callback_data="edit_profile")]
    ])

def search_kb(target_user_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❤️ Like", callback_data=f"like:{target_user_id}"),
            InlineKeyboardButton("💔 Dislike", callback_data=f"dislike:{target_user_id}"),
            InlineKeyboardButton("🚫 Report", callback_data=f"report_menu:{target_user_id}")
        ],
        [
            InlineKeyboardButton("🔁 Next", callback_data="search")
        ]
    ])

def report_reasons_kb(target_user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Fake profile", callback_data=f"report:{target_user_id}:fake")],
        [InlineKeyboardButton("Spam", callback_data=f"report:{target_user_id}:spam")],
        [InlineKeyboardButton("Abuse / Harassment", callback_data=f"report:{target_user_id}:abuse")]
    ])

def post_match_kb(target_user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Chat now 💬", callback_data=f"chat:{target_user_id}")],
        [InlineKeyboardButton("Block 🚫", callback_data=f"block:{target_user_id}")]
    ])

def rate_kb(partner_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐", callback_data=f"rate:{partner_id}:1"),
         InlineKeyboardButton("⭐⭐", callback_data=f"rate:{partner_id}:2"),
         InlineKeyboardButton("⭐⭐⭐", callback_data=f"rate:{partner_id}:3")],
        [InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rate:{partner_id}:4"),
         InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate:{partner_id}:5")]
    ])

# ---------------- Helpers ----------------
def start_session(uid: int):
    sessions[uid] = {
        "stage": "name",
        "profile": {"photos": [], "hobbies": []}
    }

def clear_session(uid: int):
    sessions.pop(uid, None)

def session_get(uid: int) -> Optional[Dict[str, Any]]:
    return sessions.get(uid)

# ---------------- /start ----------------
@app.on_message(filters.private & filters.command("start"))
async def start_cmd(client: Client, message: Message):
    uid = message.from_user.id
    user = get_user(uid)
    caption = "Welcome to STD Dating Bot — create a profile to start meeting people!"
    if user and user.get("name"):
        await message.reply_text(f"Welcome back {user.get('name')}!", reply_markup=main_kb())
        return
    # show welcome photo if available
    if WELCOME_IMAGE:
        try:
            await message.reply_photo(WELCOME_IMAGE, caption=caption, reply_markup=start_kb())
            return
        except Exception:
            pass
    await message.reply_text(caption, reply_markup=start_kb())

# ---------------- Create profile button ----------------
@app.on_callback_query(filters.regex("^create_profile$"))
async def cb_create_profile(_, query: CallbackQuery):
    uid = query.from_user.id
    start_session(uid)
    await query.message.reply_text("What's your *name*?", parse_mode="markdown")
    await query.answer()

# ---------------- Message router (profile creation, edits & chat) ----------------
@app.on_message(filters.private & ~filters.command(["start","end"]))
async def message_router(client: Client, message: Message):
    uid = message.from_user.id

    # 1) If user in anonymous chat -> relay
    if uid in active_chats:
        partner = active_chats.get(uid)
        if not partner:
            await message.reply_text("Your partner is unavailable.")
            return
        # blocked check (if partner blocked)
        if is_blocked(uid, partner) or is_blocked(partner, uid):
            # end chat
            active_chats.pop(uid, None)
            active_chats.pop(partner, None)
            await message.reply_text("Chat ended because of block.")
            try:
                await client.send_message(partner, "Chat ended because of block.")
            except:
                pass
            return
        # relay text or photo
        if message.text:
            await client.send_message(partner, f"💬 Stranger: {message.text}")
        elif message.photo:
            await client.send_photo(partner, message.photo.file_id, caption="📷 Stranger sent a photo")
        else:
            await message.reply_text("Only text and photos are relayed in anonymous chat.")
        return

    # 2) If in session (profile creation or editing)
    sess = session_get(uid)
    if sess:
        stage = sess["stage"]
        prof = sess["profile"]

        # name
        if stage == "name":
            prof["name"] = (message.text or "").strip()
            sess["stage"] = "gender"
            await message.reply_text("What's your gender? (Boy/Girl/Other)")

        # gender
        elif stage == "gender":
            g = (message.text or "").strip().title()
            if g not in ["Boy", "Girl", "Other"]:
                await message.reply_text("Reply with Boy / Girl / Other.")
                return
            prof["gender"] = g
            sess["stage"] = "preference"
            await message.reply_text("Who are you looking for? (Boys/Girls/Everyone)")

        # preference
        elif stage == "preference":
            p = (message.text or "").strip().title()
            if p not in ["Boys", "Girls", "Everyone"]:
                await message.reply_text("Choose Boys / Girls / Everyone")
                return
            prof["preference"] = p
            sess["stage"] = "city"
            await message.reply_text("Which city are you from?")

        # city
        elif stage == "city":
            prof["city"] = (message.text or "").strip()
            sess["stage"] = "age"
            await message.reply_text("How old are you? (number)")

        # age
        elif stage == "age":
            if not (message.text and message.text.isdigit()):
                await message.reply_text("Send a valid number for age.")
                return
            prof["age"] = int(message.text)
            sess["stage"] = "photos"
            await message.reply_text("Send up to 3 photos. Send first photo now. When done press \"That's it\".")
            # show the photos done button
            await message.reply_text("When finished press:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("That's it, keep the photo", callback_data="photos:done")]]))

        # hobbies
        elif stage == "hobbies":
            if not message.text:
                await message.reply_text("Send 1-3 hobbies (comma separated or one per message).")
                return
            parts = [p.strip() for p in message.text.split(",") if p.strip()]
            existing = prof.get("hobbies", [])
            for p in parts:
                if len(existing) < 3:
                    existing.append(p)
            prof["hobbies"] = existing
            if len(existing) >= 3:
                sess["stage"] = "bio"
                await message.reply_text("Write a short one-line bio about yourself.")
            else:
                await message.reply_text(f"Saved {len(existing)}/3 hobbies. Send more or comma-separated list.")

        # bio
        elif stage == "bio":
            prof["bio"] = (message.text or "").strip()
            # finalize - ensure we have at least 1 photo and up to 3 hobbies
            photos = prof.get("photos", [])
            if len(photos) < 1:
                sess["stage"] = "photos"
                await message.reply_text("You need to upload at least one photo. Send photos now.")
                return
            # persist to DB
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
            await message.reply_text("✅ Profile saved!", reply_markup=main_kb())
        return

    # 3) Not in session and not in chat: ignore or direct to menu
    await message.reply_text("Use /start to create profile or use the menu buttons.", reply_markup=main_kb())

# ---------------- Photo handler (session) ----------------
@app.on_message(filters.photo & filters.private)
async def photo_handler(client: Client, message: Message):
    uid = message.from_user.id
    sess = session_get(uid)
    if not sess or sess["stage"] != "photos":
        await message.reply_text("Not expecting a photo now. Use Create profile first.")
        return
    prof = sess["profile"]
    photos: List[str] = prof.get("photos", [])
    fid = message.photo.file_id
    if fid not in photos:
        photos.append(fid)
    prof["photos"] = photos[:3]
    await message.reply_text(f"Photo received ({len(photos)}/3). Send more or press \"That's it\".", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("That's it, keep the photo", callback_data="photos:done")]]))

# ---------------- photos done callback ----------------
@app.on_callback_query(filters.regex("^photos:done$"))
async def photos_done_cb(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    if not session_get(uid):
        await query.answer("No active photo session.")
        return
    session = session_get(uid)
    session["stage"] = "hobbies"
    await query.message.reply_text("Now send your 3 hobbies (comma separated or one per message).")
    await query.answer()

# ---------------- main menu callbacks ----------------
@app.on_callback_query(filters.regex("^(search|my_profile|who_liked|edit_profile)$"))
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
        caption = f"{user.get('name','')}, {user.get('age','')} — {user.get('city','')}\n\n{user.get('bio','')}\n\nHobbies: {', '.join(user.get('hobbies',[])[:3])}\n\nRating: {get_average_rating(uid):.2f}/5"
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
            await query.message.reply_text("Create profile first.")
            await query.answer()
            return
        await query.message.reply_text("Choose field to edit:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Name", callback_data="edit:name"),
             InlineKeyboardButton("Gender", callback_data="edit:gender")],
            [InlineKeyboardButton("Age", callback_data="edit:age"),
             InlineKeyboardButton("Photos", callback_data="edit:photos")],
            [InlineKeyboardButton("Hobbies", callback_data="edit:hobbies"),
             InlineKeyboardButton("Bio", callback_data="edit:bio")]
        ]))
        await query.answer()
        return

    if action == "search":
        # show a candidate
        candidate = find_random_profile(uid)
        if not candidate:
            await query.message.reply_text("No profiles available right now.")
            await query.answer()
            return
        # check blocks: find_random_profile already filters blocks, but double-check
        if is_blocked(uid, candidate.get("user_id")) or is_blocked(candidate.get("user_id"), uid):
            await query.answer()
            return
        caption = f"💫 {candidate.get('name','')}, {candidate.get('age','')} — {candidate.get('city','')}\n\n{candidate.get('bio','')}\n\nHobbies: {', '.join(candidate.get('hobbies',[])[:3])}\n\nRating: {get_average_rating(candidate.get('user_id')):.2f}/5"
        photos = candidate.get("photos", [])
        first = photos[0] if photos else None
        tid = candidate.get("user_id")
        if first:
            await client.send_photo(uid, first, caption=caption, reply_markup=search_kb(tid))
        else:
            await client.send_message(uid, caption, reply_markup=search_kb(tid))
        await query.answer()
        return

# ---------------- action callbacks (like/dislike/report/block/rate) ----------------
@app.on_callback_query(filters.regex("^(like:|dislike:|report_menu:|report:|block:|chat:|rate:)"))
async def action_cb(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    data = query.data

    # report menu
    if data.startswith("report_menu:"):
        target = int(data.split(":",1)[1])
        await query.message.reply_text("Choose reason:", reply_markup=report_reasons_kb(target))
        await query.answer()
        return

    # report submission
    if data.startswith("report:"):
        parts = data.split(":")
        target = int(parts[1])
        reason = parts[2]
        record_report(uid, target, reason)
        await query.message.reply_text("Thanks — report submitted. We'll review this profile.")
        await query.answer()
        return

    # like
    if data.startswith("like:"):
        target = int(data.split(":",1)[1])
        # check blocks
        if is_blocked(uid, target) or is_blocked(target, uid):
            await query.message.reply_text("Cannot like user (blocked).")
            await query.answer()
            return
        like_user(uid, target)
        record_who_liked(target, uid)
        if check_match(uid, target):
            # create anonymous chat
            active_chats[uid] = target
            active_chats[target] = uid
            # notify both
            await client.send_message(uid, "💞 It's a MATCH! Anonymous chat started. Chat here. Use /end to stop.")
            try:
                await client.send_message(target, "💞 It's a MATCH! Anonymous chat started. Chat here. Use /end to stop.")
            except:
                pass
            await query.answer("Match!")
            return
        else:
            await query.message.reply_text("Liked! We'll notify if it's mutual.")
            await query.answer()
            # show next
            await client.delete_messages(uid, query.message.message_id)
            await menu_cb(client, query._replace(data="search"))
            return

    # dislike -> skip
    if data.startswith("dislike:"):
        await query.answer("Skipped.")
        await client.delete_messages(uid, query.message.message_id)
        await menu_cb(client, query._replace(data="search"))
        return

    # block
    if data.startswith("block:"):
        target = int(data.split(":",1)[1])
        block_user(uid, target)
        # end active chat if any
        if active_chats.get(uid) == target:
            active_chats.pop(uid, None)
            active_chats.pop(target, None)
            # prompt rating for partner
            pending_ratings[target] = None  # partner won't rate because they were blocked
        await query.message.reply_text("User blocked. They won't appear for you anymore.")
        await query.answer()
        return

    # chat (optional direct invite)
    if data.startswith("chat:"):
        target = int(data.split(":",1)[1])
        # we don't reveal identities: just send a ping
        try:
            await client.send_message(target, "💌 Someone is interested in your profile!")
        except:
            pass
        await query.answer("Notification sent.")

    # rating
    if data.startswith("rate:"):
        parts = data.split(":")
        target = int(parts[1])
        rating = int(parts[2])
        record_rating(uid, target, rating)
        await query.message.reply_text(f"Thanks! You rated the chat partner {rating}⭐")
        await query.answer()
        # remove pending if present
        pending_ratings.pop(uid, None)
        return

# ---------------- /end - stop anonymous chat & prompt rating ----------------
@app.on_message(filters.private & filters.command("end"))
async def end_chat_cmd(client: Client, message: Message):
    uid = message.from_user.id
    partner = active_chats.pop(uid, None)
    if not partner:
        await message.reply_text("You don't have an active anonymous chat.")
        return
    # remove partner's mapping if present
    active_chats.pop(partner, None)
    await message.reply_text("You ended the anonymous chat. Please rate your partner:", reply_markup=rate_kb(partner))
    try:
        await client.send_message(partner, "The other user ended the chat. Please rate them:", reply_markup=rate_kb(uid))
    except:
        pass
    # store pending in case they don't press rate but we still want to show later
    pending_ratings[uid] = partner
    pending_ratings[partner] = uid

# ---------------- utility command: /whoami (debug) ----------------
@app.on_message(filters.private & filters.command("whoami"))
async def whoami_cmd(_, message: Message):
    uid = message.from_user.id
    user = get_user(uid)
    await message.reply_text(str(user))

# ---------------- start the bot ----------------
if __name__ == "__main__":
    print("🚀 STD Dating Bot (full features) starting...")
    app.run()
