import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import save_user, get_user, get_random_user, like_user, is_match

# ========= BOT CONFIG =========
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client("dating-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ========= COMMAND HANDLERS =========

@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply_text(
        f"👋 Hey {msg.from_user.first_name}!\n\n"
        "Welcome to **STD Dating Bot ❤️**\n"
        "Create your profile using /setprofile\n"
        "Then start finding matches using /find",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❤️ Set Profile", callback_data="set_profile")],
            [InlineKeyboardButton("🔍 Find Match", callback_data="find_match")]
        ])
    )

# ========= PROFILE CREATION =========

@app.on_callback_query(filters.regex("set_profile"))
async def ask_name(_, query):
    await query.message.reply_text("👤 What's your name?")
    await query.answer()
    app.set_parse_mode("private")
    app.set_parse_mode("user_name")

@app.on_message(filters.text & filters.private)
async def profile_flow(client, message):
    user_id = message.from_user.id

    if "user_name" in app.parse_mode:
        name = message.text
        app.parse_mode = {"user_name_done": name}
        await message.reply_text("🚻 What's your gender? (Male/Female)")
        return

    if "user_name_done" in app.parse_mode:
        gender = message.text.lower()
        if gender not in ["male", "female"]:
            await message.reply_text("❌ Please type either Male or Female.")
            return
        app.parse_mode = {"user_gender_done": gender}
        await message.reply_text("🎂 How old are you?")
        return

    if "user_gender_done" in app.parse_mode:
        try:
            age = int(message.text)
            if not (16 <= age <= 80):
                raise ValueError
        except ValueError:
            await message.reply_text("⚠️ Please enter a valid age (16–80).")
            return
        app.parse_mode = {"user_age_done": age}
        await message.reply_text("📝 Write a short bio about yourself.")
        return

    if "user_age_done" in app.parse_mode:
        bio = message.text
        app.parse_mode = {"user_bio_done": bio}
        await message.reply_text("📸 Please send your photo.")
        return

    if "user_bio_done" in app.parse_mode and message.photo:
        photo = message.photo.file_id
        data = app.parse_mode
        save_user(user_id, data["user_name_done"], data["user_gender_done"], data["user_age_done"], data["user_bio_done"], photo)
        await message.reply_text("✅ Your profile has been saved successfully!")
        app.parse_mode = None
        return

# ========= MATCHING SYSTEM =========

@app.on_callback_query(filters.regex("find_match"))
async def find_match_cb(_, query):
    user_id = query.from_user.id
    current_user = get_user(user_id)

    if not current_user:
        await query.message.reply_text("❌ You don't have a profile yet. Use /setprofile first.")
        await query.answer()
        return

    user = get_random_user(user_id)
    if not user:
        await query.message.reply_text("😔 No more users found right now. Try again later!")
        await query.answer()
        return

    caption = (
        f"💫 **{user['name']}**, {user['age']}\n"
        f"🧬 Gender: {user['gender'].capitalize()}\n\n"
        f"🗒️ Bio: {user['bio']}"
    )

    await query.message.reply_photo(
        user["photo"],
        caption=caption,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❤️ Like", callback_data=f"like_{user['id']}"),
             InlineKeyboardButton("💔 Skip", callback_data="find_match")]
        ])
    )
    await query.answer()

@app.on_callback_query(filters.regex(r"like_(\d+)"))
async def like_user_cb(_, query):
    liker_id = query.from_user.id
    liked_id = int(query.data.split("_")[1])

    like_user(liker_id, liked_id)

    if is_match(liker_id, liked_id):
        await query.message.reply_text(
            f"🎉 It's a Match! ❤️\n"
            f"You and [{liked_id}](tg://user?id={liked_id}) liked each other!\n\n"
            "Start chatting anonymously!"
        )
    else:
        await query.message.reply_text("❤️ Liked! Let's see if they like you back 😉")

    await query.answer("Liked!")

# ========= ERROR HANDLER =========
@app.on_message(filters.command("help"))
async def help_cmd(_, msg):
    await msg.reply_text(
        "**Commands List**\n"
        "/start - Start bot\n"
        "/setprofile - Create or update your profile\n"
        "/find - Start finding matches"
    )

# ========= RUN =========
print("🚀 STD Dating Bot is running...")
app.run()
