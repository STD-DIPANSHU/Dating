import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from db import (
    init_db, save_profile, get_profile, get_random_candidate,
    record_like, has_liked, record_dislike,
    create_active_chat, find_chat_partner, remove_active_chat
)

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
MODE = os.getenv('MODE', 'polling')
PORT = int(os.getenv('PORT', 8000))

if not TOKEN:
    raise RuntimeError('Set TELEGRAM_BOT_TOKEN in env')

bot = Bot(TOKEN)
dp = Dispatcher()

CREATING = {}
TEMP = {}

# --- Helpers ---
def profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton('🔍 Search Profiles', callback_data='search')],
        [InlineKeyboardButton('ℹ️ My Profile', callback_data='myprofile')]
    ])

async def send_profile_preview(chat_id, target_id):
    row = await get_profile(target_id)
    if not row:
        await bot.send_message(chat_id, 'Profile not available.')
        return

    _, name, gender, city, age, hobbies, photo_file_id = row
    text = f"Meet {name} — {hobbies}\\nAge: {age} | City: {city} | Gender: {gender}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton('❤️ Like', callback_data=f'like:{target_id}'),
        InlineKeyboardButton('👎 Dislike', callback_data=f'dislike:{target_id}'),
        InlineKeyboardButton('🔁 Next', callback_data=f'next:{target_id}')
    ]])

    if photo_file_id:
        try:
            await bot.send_photo(chat_id, photo_file_id, caption=text, reply_markup=kb)
            return
        except Exception:
            pass

    await bot.send_message(chat_id, text, reply_markup=kb)

# --- Commands ---
@dp.message(Command('start'))
async def cmd_start(msg: types.Message):
    await init_db()
    await msg.reply(
        "Hey, main *STD* — tumhara AI matchmaker 💌\\n"
        "Pehle apna profile bana lein. /createprofile",
        parse_mode='Markdown'
    )

@dp.message(Command('createprofile'))
async def cmd_create(msg: types.Message):
    uid = msg.from_user.id
    CREATING[uid] = 'name'
    TEMP[uid] = {}
    await msg.reply('Tumhara naam kya hai?')

@dp.message(Command('search'))
async def cmd_search(msg: types.Message):
    uid = msg.from_user.id
    candidate = await get_random_candidate(uid)
    if not candidate:
        await msg.reply('Koi aur profiles nahi mile abhi. Wait karo ya friends ko bulao!')
        return
    await send_profile_preview(msg.chat.id, candidate)

@dp.message(Command('stopchat'))
async def cmd_stopchat(msg: types.Message):
    uid = msg.from_user.id
    partner = await find_chat_partner(uid)
    if not partner:
        await msg.reply('Koi active chat nahi chal rahi.')
        return
    await remove_active_chat(uid)
    await msg.reply('Anonymous chat band kar di gayi. /search se fir shuru karo.')
    try:
        await bot.send_message(partner, 'Partner ne chat end kar diya.')
    except Exception:
        pass

# --- Message Handler ---
@dp.message()
async def handle_messages(msg: types.Message):
    uid = msg.from_user.id

    # 1️⃣ relay messages if in anonymous chat
    partner = await find_chat_partner(uid)
    if partner:
        if msg.text:
            await bot.send_message(partner, f"Someone: {msg.text}")
        elif msg.photo:
            file_id = msg.photo[-1].file_id
            await bot.send_photo(partner, file_id)
        else:
            await msg.reply('Unsupported message type in anonymous chat.')
        return

    # 2️⃣ profile creation flow
    if uid in CREATING:
        step = CREATING[uid]
        text = (msg.text or '').strip()

        if step == 'name':
            TEMP[uid]['name'] = text or msg.from_user.full_name
            CREATING[uid] = 'gender'
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton('Male', callback_data='gender:Male'),
                InlineKeyboardButton('Female', callback_data='gender:Female'),
                InlineKeyboardButton('Other', callback_data='gender:Other')
            ]])
            await msg.reply('Gender choose karo:', reply_markup=kb)
            return

        if step == 'city':
            TEMP[uid]['city'] = text
            CREATING[uid] = 'age'
            await msg.reply('Kitne saal ke ho? (Number)')
            return

        if step == 'age':
            try:
                age = int(text)
            except:
                await msg.reply('Please ek valid number bhejo.')
                return
            if age < 18:
                await msg.reply('Sorry, 18+ required hai. Profile nahi banega.')
                CREATING.pop(uid, None)
                TEMP.pop(uid, None)
                return
            TEMP[uid]['age'] = age
            CREATING[uid] = 'hobbies'
            await msg.reply('Apne hobbies/ek-line batado (example: Music, Travel)')
            return

        if step == 'hobbies':
            TEMP[uid]['hobbies'] = text
            CREATING[uid] = 'photo'
            await msg.reply('Agar photo bhejna chahte ho to ab bhejo, ya "skip" likh do.')
            return

        if step == 'photo':
            if msg.text and msg.text.lower() == 'skip':
                d = TEMP[uid]
                await save_profile(uid, d.get('name'), d.get('gender'),
                                   d.get('city'), d.get('age'), d.get('hobbies'), None)
                CREATING.pop(uid, None)
                TEMP.pop(uid, None)
                await msg.reply('Profile saved without photo!', reply_markup=profile_keyboard())
                return

            if msg.photo:
                file_id = msg.photo[-1].file_id
                d = TEMP[uid]
                await save_profile(uid, d.get('name'), d.get('gender'),
                                   d.get('city'), d.get('age'), d.get('hobbies'), file_id)
                CREATING.pop(uid, None)
                TEMP.pop(uid, None)
                await msg.reply('Profile saved with photo!', reply_markup=profile_keyboard())
                return

            await msg.reply('Photo bhejo ya "skip" likh do.')
            return

    await msg.reply('Agar profile banana hai to /createprofile ya profiles dekhne ke liye /search')

# --- Callback Handlers ---
@dp.callback_query()
async def cb_handler(call: types.CallbackQuery):
    data = call.data or ''
    uid = call.from_user.id

    if data.startswith('gender:'):
        g = data.split(':', 1)[1]
        TEMP.setdefault(uid, {})['gender'] = g
        CREATING[uid] = 'city'
        await call.message.reply('Kahan se ho? (city name)')
        return

    if data == 'search':
        candidate = await get_random_candidate(uid)
        if not candidate:
            await call.message.answer('Abhi koi suitable profile nahi mila.')
            return
        await send_profile_preview(call.message.chat.id, candidate)
        return

    if data == 'myprofile':
        row = await get_profile(uid)
        if not row:
            await call.message.answer('Tumhara profile nahi mila. /createprofile karlo.')
            return
        _, name, gender, city, age, hobbies, photo_file_id = row
        txt = f"Your profile:\\nName: {name}\\nAge: {age}\\nGender: {gender}\\nCity: {city}\\nHobbies: {hobbies}"
        if photo_file_id:
            await bot.send_photo(uid, photo_file_id, caption=txt)
        else:
            await call.message.answer(txt)
        return

    if data.startswith('like:'):
        target = int(data.split(':', 1)[1])
        await record_like(uid, target)
        if await has_liked(target, uid):
            await create_active_chat(uid, target)
            await call.message.answer("It's a MATCH! 🎉 Anonymous chat started. Use /stopchat to end.")
            try:
                await bot.send_message(target, "It's a MATCH! 🎉 Anonymous chat started. Use /stopchat to end.")
            except Exception:
                pass
        else:
            await call.message.answer('Like noted. Agar mutual hua to bata dunga 😏')
        return

    if data.startswith('dislike:'):
        target = int(data.split(':', 1)[1])
        await record_dislike(uid, target)
        await call.message.answer('Noted. I won’t show similar profiles.')
        return

    if data.startswith('next:'):
        candidate = await get_random_candidate(uid)
        if not candidate:
            await call.message.answer('No more profiles abhi.')
            return
        await send_profile_preview(call.message.chat.id, candidate)
        return

# --- Run Bot ---
if MODE == 'polling':
    async def start_polling():
        await init_db()
        print("STD Dating Bot started successfully 🚀")
        await dp.start_polling(bot)

    if __name__ == '__main__':
        asyncio.run(start_polling())
