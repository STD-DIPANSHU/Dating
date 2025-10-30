import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# In-memory database (for demo)
users = {}
likes = {}


# ----- Start Command -----
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    users[user_id] = {"step": "ask_gender"}

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='Male', callback_data='gender:Male'),
            InlineKeyboardButton(text='Female', callback_data='gender:Female'),
            InlineKeyboardButton(text='Other', callback_data='gender:Other')
        ]
    ])

    await message.answer(
        "👋 Welcome to STD Dating Bot!\n\nPlease select your gender:",
        reply_markup=kb
    )


# ----- Handle Gender -----
@dp.callback_query(lambda c: c.data.startswith('gender:'))
async def process_gender(callback_query: types.CallbackQuery):
    gender = callback_query.data.split(':')[1]
    user_id = callback_query.from_user.id
    users[user_id]["gender"] = gender
    users[user_id]["step"] = "ask_name"

    await callback_query.message.edit_text("What's your name?")
    await callback_query.answer()


# ----- Handle Name -----
@dp.message(lambda msg: users.get(msg.from_user.id, {}).get("step") == "ask_name")
async def process_name(message: types.Message):
    user_id = message.from_user.id
    users[user_id]["name"] = message.text
    users[user_id]["step"] = "ask_age"

    await message.answer("How old are you?")


# ----- Handle Age -----
@dp.message(lambda msg: users.get(msg.from_user.id, {}).get("step") == "ask_age")
async def process_age(message: types.Message):
    user_id = message.from_user.id

    try:
        age = int(message.text)
    except ValueError:
        await message.answer("Please enter a valid number for age.")
        return

    users[user_id]["age"] = age
    users[user_id]["step"] = "profile_done"

    await message.answer("Your profile has been created ✅", reply_markup=profile_keyboard())


# ----- Profile Menu -----
def profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔍 Search Profiles', callback_data='search')],
        [InlineKeyboardButton(text='ℹ️ My Profile', callback_data='myprofile')]
    ])


# ----- Show My Profile -----
@dp.callback_query(lambda c: c.data == 'myprofile')
async def my_profile(callback_query: types.CallbackQuery):
    user = users.get(callback_query.from_user.id)
    if not user:
        await callback_query.answer("No profile found! Use /start again.")
        return

    text = (
        f"<b>👤 Name:</b> {user['name']}\n"
        f"<b>🚻 Gender:</b> {user['gender']}\n"
        f"<b>🎂 Age:</b> {user['age']}"
    )
    await callback_query.message.edit_text(text, reply_markup=profile_keyboard())
    await callback_query.answer()


# ----- Search Profiles -----
@dp.callback_query(lambda c: c.data == 'search')
async def search_profiles(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    all_users = [uid for uid in users.keys() if uid != user_id]

    if not all_users:
        await callback_query.answer("No other profiles yet 😅")
        return

    target_id = all_users[0]
    target = users[target_id]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='❤️ Like', callback_data=f'like:{target_id}'),
            InlineKeyboardButton(text='👎 Dislike', callback_data=f'dislike:{target_id}'),
            InlineKeyboardButton(text='🔁 Next', callback_data=f'next:{target_id}')
        ]
    ])

    text = (
        f"<b>👤 Name:</b> {target['name']}\n"
        f"<b>🚻 Gender:</b> {target['gender']}\n"
        f"<b>🎂 Age:</b> {target['age']}"
    )
    await callback_query.message.edit_text(text, reply_markup=kb)
    await callback_query.answer()


# ----- Handle Likes -----
@dp.callback_query(lambda c: c.data.startswith('like:'))
async def handle_like(callback_query: types.CallbackQuery):
    liker = callback_query.from_user.id
    liked = int(callback_query.data.split(':')[1])

    if liked not in likes:
        likes[liked] = set()
    likes[liked].add(liker)

    await callback_query.answer("You liked this profile ❤️")


# ----- Handle Dislike -----
@dp.callback_query(lambda c: c.data.startswith('dislike:'))
async def handle_dislike(callback_query: types.CallbackQuery):
    await callback_query.answer("You disliked this profile 👎")


# ----- Handle Next -----
@dp.callback_query(lambda c: c.data.startswith('next:'))
async def handle_next(callback_query: types.CallbackQuery):
    await search_profiles(callback_query)


# ----- Run Bot -----
async def main():
    print("STD Dating Bot started successfully 🚀")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
