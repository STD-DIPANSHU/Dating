from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import json
from db import load_users, save_users, load_chats, save_chats

API_ID = int("22705233")
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"

app = Client("dating_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

users = load_users()
chats = load_chats()  # stores mutual chat pairs


def save_all():
    save_users(users)
    save_chats(chats)


# ----- START -----
@app.on_message(filters.command("start"))
def start(client, message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {"step": "name"}
        message.reply_text("👋 Hey! Let's set up your profile.\n\nWhat's your name?")
    else:
        message.reply_text("Welcome back! Use /search to find matches 🔍")

    save_all()


# ----- PROFILE SETUP -----
@app.on_message(filters.text & ~filters.command(["start", "search", "end"]))
def handle_profile(client, message):
    user_id = message.from_user.id

    # Check if user is in a chat
    if user_id in chats:
        partner_id = chats[user_id]
        try:
            app.send_message(partner_id, f"🗣️ Stranger: {message.text}")
        except Exception as e:
            message.reply_text("⚠️ Message delivery failed.")
        return

    if user_id not in users:
        message.reply_text("Please start first using /start.")
        return

    user = users[user_id]
    step = user.get("step")

    if step == "name":
        user["name"] = message.text
        user["step"] = "gender"
        message.reply_text("What's your gender? (Male/Female/Other)")
    elif step == "gender":
        user["gender"] = message.text
        user["step"] = "age"
        message.reply_text("How old are you?")
    elif step == "age":
        user["age"] = message.text
        user["step"] = "bio"
        message.reply_text("Tell something about yourself 📝")
    elif step == "bio":
        user["bio"] = message.text
        user["step"] = "photo"
        message.reply_text("Send your profile photo 📸")
    else:
        message.reply_text("Profile already complete! Use /search to find matches 🔍")

    save_all()


# ----- PHOTO -----
@app.on_message(filters.photo)
def handle_photo(client, message):
    user_id = message.from_user.id
    if user_id not in users:
        message.reply_text("Please start first using /start.")
        return

    user = users[user_id]
    if user.get("step") == "photo":
        user["photo"] = message.photo.file_id
        user["likes"] = []
        user["step"] = "done"
        message.reply_text("✅ Profile created successfully!\nUse /search to find matches 🔍")
        save_all()
    else:
        message.reply_text("Photo not expected right now.")


# ----- SEARCH -----
@app.on_message(filters.command("search"))
def search_profiles(client, message):
    user_id = message.from_user.id
    if user_id not in users or users[user_id].get("step") != "done":
        message.reply_text("Please complete your profile first using /start.")
        return

    for uid, data in users.items():
        if uid != user_id and data.get("step") == "done":
            caption = f"💫 Name: {data['name']}\n👫 Gender: {data['gender']}\n🎂 Age: {data['age']}\n📝 Bio: {data['bio']}"
            buttons = [
                [
                    InlineKeyboardButton("💖 Like", callback_data=f"like_{uid}"),
                    InlineKeyboardButton("💔 Dislike", callback_data="dislike"),
                    InlineKeyboardButton("➡️ Next", callback_data="next")
                ]
            ]
            message.reply_photo(data["photo"], caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
            return
    message.reply_text("No profiles found 😢")


# ----- CALLBACKS -----
@app.on_callback_query()
def handle_callback(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data.startswith("like_"):
        liked_id = int(data.split("_")[1])

        # add to user's like list
        users[user_id]["likes"].append(liked_id)

        # check for mutual like
        if liked_id in users and user_id in users[liked_id].get("likes", []):
            chats[user_id] = liked_id
            chats[liked_id] = user_id

            app.send_message(user_id, "💘 It's a match! You can now chat anonymously.\nSend messages freely!\nType /end to stop.")
            app.send_message(liked_id, "💘 It's a match! You can now chat anonymously.\nSend messages freely!\nType /end to stop.")

            save_all()
        else:
            callback_query.message.reply_text("You liked this profile 💖")

    elif data == "dislike":
        callback_query.message.reply_text("You disliked this profile 💔")

    elif data == "next":
        callback_query.message.reply_text("Searching next profile... 🔍")

    callback_query.answer()


# ----- END CHAT -----
@app.on_message(filters.command("end"))
def end_chat(client, message):
    user_id = message.from_user.id
    if user_id not in chats:
        message.reply_text("You are not in a chat.")
        return

    partner_id = chats[user_id]
    del chats[user_id]
    del chats[partner_id]

    app.send_message(partner_id, "❌ Stranger ended the chat.")
    message.reply_text("You ended the chat. Use /search to find new matches 🔍")

    save_all()


app.run()
