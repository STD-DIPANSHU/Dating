import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import save_user, get_user, get_random_user, like_user, is_match

# Environment variables
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Pyrogram client
app = Client("dating_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Store chat matches (active anonymous chats)
active_chats = {}

# Start command
@app.on_message(filters.command("start"))
async def start(_, message):
    user = get_user(message.from_user.id)
    if user:
        await message.reply_text(
            f"👋 Welcome back, {user['name']}!\n\nUse /find to discover new people ❤️",
        )
    else:
        await message.reply_text(
            "👋 Welcome to *STD Dating Bot!*\nLet's create your profile first.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Create Profile 💘", callback_data="create_profile")]
            ])
        )

# Handle create profile button
@app.on_callback_query(filters.regex("create_profile"))
async def ask_name(_, query):
    await query.message.reply_text("What's your name?")
    app.set_parse_mode("private")
    app.set_parse_mode("creating_name", query.from_user.id)

# Store name
@app.on_message(filters.private & ~filters.command(["start", "find"]))
async def get_name(_, message):
    user_state = app.get_parse_mode("private")
    if user_state == "creating_name":
        app.set_parse_mode("creating_gender", message.from_user.id)
        app.set_parse_mode("name", message.text)
        await message.reply_text(
            "Select your gender:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Male ♂️", callback_data="gender_male")],
                [InlineKeyboardButton("Female ♀️", callback_data="gender_female")]
            ])
        )

# Handle gender selection
@app.on_callback_query(filters.regex("gender_"))
async def ask_age(_, query):
    gender = query.data.split("_")[1]
    app.set_parse_mode("gender", gender)
    app.set_parse_mode("creating_age", query.from_user.id)
    await query.message.reply_text("Enter your age:")

# Store age
@app.on_message(filters.private & filters.text & ~filters.command(["start", "find"]))
async def get_age(_, message):
    user_state = app.get_parse_mode("private")
    if user_state == "creating_age":
        try:
            age = int(message.text)
            app.set_parse_mode("age", age)
            app.set_parse_mode("creating_bio", message.from_user.id)
            await message.reply_text("Tell us something about yourself 💬:")
        except ValueError:
            await message.reply_text("❌ Please enter a valid number for age!")

# Store bio
@app.on_message(filters.private & filters.text & ~filters.command(["start", "find"]))
async def get_bio(_, message):
    user_state = app.get_parse_mode("private")
    if user_state == "creating_bio":
        app.set_parse_mode("bio", message.text)
        app.set_parse_mode("creating_photo", message.from_user.id)
        await message.reply_text("Now send me your profile photo 📸:")

# Store photo and complete registration
@app.on_message(filters.private & filters.photo)
async def get_photo(_, message):
    user_state = app.get_parse_mode("private")
    if user_state == "creating_photo":
        photo = message.photo.file_id
        name = app.get_parse_mode("name")
        gender = app.get_parse_mode("gender")
        age = app.get_parse_mode("age")
        bio = app.get_parse_mode("bio")

        save_user(message.from_user.id, name, gender, age, bio, photo)
        await message.reply_text("✅ Profile created successfully!\nUse /find to start matching 💞")

# Command: Find new people
@app.on_message(filters.command("find"))
async def find(_, message):
    user = get_user(message.from_user.id)
    if not user:
        await message.reply_text("⚠️ Please create a profile first using /start.")
        return

    random_user = get_random_user(message.from_user.id)
    if not random_user:
        await message.reply_text("😕 No users found. Try again later!")
        return

    await message.reply_photo(
        random_user["photo"],
        caption=f"✨ *{random_user['name']}*, {random_user['age']} yrs\n\n_{random_user['bio']}_",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❤️ Like", callback_data=f"like_{random_user['id']}")],
            [InlineKeyboardButton("➡️ Next", callback_data="next_user")]
        ])
    )

# Like handler
@app.on_callback_query(filters.regex("^like_"))
async def like_handler(_, query):
    liked_id = int(query.data.split("_")[1])
    liker_id = query.from_user.id

    like_user(liker_id, liked_id)

    if is_match(liker_id, liked_id):
        # If both liked each other — start anonymous chat
        active_chats[liker_id] = liked_id
        active_chats[liked_id] = liker_id
        await query.message.reply_text("💘 It's a Match! Starting anonymous chat...")

        user1 = await app.get_users(liker_id)
        user2 = await app.get_users(liked_id)

        await app.send_message(liked_id, "💞 You both liked each other! Start chatting here (anonymous mode).")
        await app.send_message(liker_id, "💞 You both liked each other! Start chatting here (anonymous mode).")
    else:
        await query.message.reply_text("❤️ Liked! Wait to see if they like you back!")

# Next button
@app.on_callback_query(filters.regex("next_user"))
async def next_user(_, query):
    await find(_, query.message)

# Anonymous chat forwarding
@app.on_message(filters.private & filters.text)
async def chat_forwarder(_, message):
    if message.from_user.id in active_chats:
        partner_id = active_chats[message.from_user.id]
        await app.send_message(partner_id, f"🗣 {message.text}")

# Bot running
print("🚀 STD Dating Bot is running...")
app.run()
