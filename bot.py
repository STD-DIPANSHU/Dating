import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import get_user, save_user, like_user, find_match

API_ID = int(os.getenv("API_ID"))  # ensure integer
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client("dating_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Start command
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "👋 Welcome to *STD Dating Bot!*\n\n"
        "Use /register to create your profile 💞",
        quote=True
    )

# Register command
@app.on_message(filters.command("register"))
async def register(client, message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if user:
        await message.reply_text("✅ You are already registered!")
        return

    await message.reply_text(
        "Let's create your profile! Send me your name."
    )
    save_user(user_id, step="name")

# Handle text messages
@app.on_message(filters.text & ~filters.command(["start", "register"]))
async def handle_text(client, message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        await message.reply_text("Please register first using /register")
        return

    if user["step"] == "name":
        user["name"] = message.text
        user["step"] = "hobbies"
        save_user(user_id, user)
        await message.reply_text("Great! Now tell me your hobbies or interests.")
    elif user["step"] == "hobbies":
        user["hobbies"] = message.text
        user["step"] = "gender"
        save_user(user_id, user)

        buttons = [
            [InlineKeyboardButton("👨 Male", callback_data="gender:Male"),
             InlineKeyboardButton("👩 Female", callback_data="gender:Female")]
        ]
        await message.reply_text("Select your gender:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply_text("Use /register to update your info.")

# Handle gender selection
@app.on_callback_query(filters.regex("gender:"))
async def handle_gender(client, callback_query):
    user_id = callback_query.from_user.id
    gender = callback_query.data.split(":")[1]
    user = get_user(user_id)
    user["gender"] = gender
    user["step"] = "done"
    save_user(user_id, user)

    await callback_query.message.edit_text(
        "✅ Profile created successfully!\nUse /find to match with others."
    )

# Find match
@app.on_message(filters.command("find"))
async def find_partner(client, message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user or user["step"] != "done":
        await message.reply_text("Please complete your registration first.")
        return

    match = find_match(user_id)
    if match:
        match_user = get_user(match)
        text = (
            f"💞 *Match Found!*\n\n"
            f"Name: {match_user['name']}\n"
            f"Hobbies: {match_user['hobbies']}\n"
            f"Gender: {match_user['gender']}"
        )
        buttons = [
            [InlineKeyboardButton("❤️ Like", callback_data=f"like:{match_user['id']}")]
        ]
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply_text("No users found yet. Please try again later 💔")

# Handle like button
@app.on_callback_query(filters.regex("like:"))
async def handle_like(client, callback_query):
    from_id = callback_query.from_user.id
    to_id = int(callback_query.data.split(":")[1])

    if like_user(from_id, to_id):
        partner = get_user(to_id)
        await callback_query.message.reply_text(
            f"❤️ You liked {partner['name']}!"
        )

        # If mutual like
        if like_user(to_id, from_id, check_only=True):
            await callback_query.message.reply_text(
                f"💌 It's a match! You can now chat anonymously.\n"
                f"Type /chat to start."
            )
            save_user(from_id, {"partner": to_id})
            save_user(to_id, {"partner": from_id})
    else:
        await callback_query.message.reply_text("You already liked this user.")

# Anonymous chat command
@app.on_message(filters.command("chat"))
async def start_chat(client, message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user or "partner" not in user:
        await message.reply_text("You don't have a match yet 💔")
        return

    partner_id = user["partner"]
    await message.reply_text("💬 You can start chatting anonymously now!")
    save_user(user_id, {"chatting": True})
    save_user(partner_id, {"chatting": True})

# Forward messages anonymously
@app.on_message(filters.text & ~filters.command(["start", "register", "find", "chat"]))
async def anonymous_chat(client, message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user or not user.get("chatting"):
        return

    partner_id = user.get("partner")
    if partner_id:
        await client.send_message(partner_id, f"💌 {message.text}")

print("🚀 STD Dating Bot is running...")
app.run()
