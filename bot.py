import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import asyncio
import os

from db import (
    save_user,
    get_user,
    update_user,
)

# -------------------
# Bot Setup
# -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)
users = {}

# -------------------
# Start Command
# -------------------
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    users[user_id] = {"step": "ask_gender"}

    gender_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("Male", callback_data="gender:Male"),
         InlineKeyboardButton("Female", callback_data="gender:Female")]
    ])

    await message.answer("Welcome to STD Dating Bot ❤️\nSelect your gender:", reply_markup=gender_markup)

# -------------------
# Handle Gender Selection
# -------------------
@dp.callback_query_handler(lambda c: c.data.startswith('gender:'))
async def process_gender(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    gender = callback_query.data.split(':')[1]

    # ✅ Prevent KeyError if user presses gender without /start
    if user_id not in users:
        users[user_id] = {}

    users[user_id]["gender"] = gender
    users[user_id]["step"] = "ask_name"

    await callback_query.message.edit_text("What's your name?")
    await callback_query.answer()

# -------------------
# Handle Messages (Name, Age, Bio)
# -------------------
@dp.message_handler(lambda message: True)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    if user_id not in users:
        await message.answer("Please start with /start 😊")
        return

    step = users[user_id].get("step")

    if step == "ask_name":
        users[user_id]["name"] = message.text
        users[user_id]["step"] = "ask_age"
        await message.answer("Nice! Now tell me your age 👀")

    elif step == "ask_age":
        if not message.text.isdigit():
            await message.answer("Please enter a valid number 🔢")
            return
        users[user_id]["age"] = int(message.text)
        users[user_id]["step"] = "ask_bio"
        await message.answer("Cool! Now write a short bio ✍️")

    elif step == "ask_bio":
        users[user_id]["bio"] = message.text
        users[user_id]["step"] = "complete"

        # Save user to database
        save_user(user_id, users[user_id])

        await message.answer(
            f"Profile created successfully ✅\n\n"
            f"👤 Name: {users[user_id]['name']}\n"
            f"⚧ Gender: {users[user_id]['gender']}\n"
            f"🎂 Age: {users[user_id]['age']}\n"
            f"💬 Bio: {users[user_id]['bio']}\n\n"
            f"Type /match to find new people 💕"
        )

    else:
        await message.answer("You're all set! Type /match to find a date 💘")

# -------------------
# Match Command
# -------------------
@dp.message_handler(commands=['match'])
async def match_command(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        await message.answer("Please complete your profile first using /start 😊")
        return

    # Get a random match (for now, a placeholder)
    other_user = get_user("random")

    if not other_user:
        await message.answer("No matches found yet 😢 Try again later.")
        return

    await message.answer(
        f"💞 You matched with {other_user['name']}!\n"
        f"Age: {other_user['age']}\n"
        f"Bio: {other_user['bio']}"
    )

# -------------------
# Run Bot
# -------------------
if __name__ == "__main__":
    logging.info("STD Dating Bot started successfully 🚀")

    try:
        # ✅ Polling wrapped in safe retry loop to avoid conflict errors
        while True:
            try:
                executor.start_polling(dp, skip_updates=True)
            except Exception as e:
                logging.error(f"Polling error: {e}")
                asyncio.sleep(2)
    except KeyboardInterrupt:
        logging.info("Bot stopped manually.")
