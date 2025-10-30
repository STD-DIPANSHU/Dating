import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import save_user, get_user, update_user

# -------------------
# Bot Setup
# -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)
users = {}

# -------------------
# Start Command
# -------------------
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    if message.text == "/start":
        users[user_id] = {"step": "ask_gender"}
        gender_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("Male", callback_data="gender:Male"),
             InlineKeyboardButton("Female", callback_data="gender:Female")]
        ])
        await message.answer("Welcome to STD Dating Bot ❤️\nSelect your gender:", reply_markup=gender_markup)
        return

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

        save_user(user_id, users[user_id])

        await message.answer(
            f"Profile created successfully ✅\n\n"
            f"👤 Name: {users[user_id]['name']}\n"
            f"⚧ Gender: {users[user_id]['gender']}\n"
            f"🎂 Age: {users[user_id]['age']}\n"
            f"💬 Bio: {users[user_id]['bio']}\n\n"
            f"Type /match to find new people 💕"
        )

    elif message.text == "/match":
        user = get_user(user_id)
        if not user:
            await message.answer("Please complete your profile first using /start 😊")
            return

        other_user = get_user("random")
        if not other_user:
            await message.answer("No matches found yet 😢 Try again later.")
            return

        await message.answer(
            f"💞 You matched with {other_user['name']}!\n"
            f"Age: {other_user['age']}\n"
            f"Bio: {other_user['bio']}"
        )

    else:
        await message.answer("You're all set! Type /match to find a date 💘")


# -------------------
# Handle Gender Callback
# -------------------
@dp.callback_query(lambda c: c.data.startswith('gender:'))
async def process_gender(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    gender = callback_query.data.split(':')[1]

    if user_id not in users:
        users[user_id] = {}

    users[user_id]["gender"] = gender
    users[user_id]["step"] = "ask_name"

    await callback_query.message.edit_text("What's your name?")
    await callback_query.answer()

# -------------------
# Main runner for Aiogram v3
# -------------------
async def main():
    logging.info("STD Dating Bot started successfully 🚀")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
