import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from db import (
    init_db, save_profile, get_profile, get_random_candidate,
    record_like, has_liked, record_dislike, is_disliked,
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

# temporaries for multi-step profile creation
CREATING = {}  # uid -> step
TEMP = {}      # uid -> partial data

# --- Helpers ---
def profile_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton('🔍 Search Profiles', callback_data='search')],
        [InlineKeyboardButton('ℹ️ My Profile', callback_data='myprofile')]
    ])
    return kb

async def send_profile_preview(chat_id, target_id):
    row = await get_profile(target_id)
    if not row:
        await bot.send_message(chat_id, 'Profile not available.')
        return
    _, name, gender, city, age, hobbies, photo_file_id = row
    text = f"Meet {name} — {hobbies}
Age: {age} | City: {city} | Gender: {gender}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton('❤️ Like', callback_data=f'like:{target_id}'), InlineKeyboardButton('👎 Dislike', callback_data=f'dislike:{target_id}'), InlineKeyboardButton('🔁 Next', callback_data=f'next:{target_id}')]
    ])
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
    await msg.reply('Hey, main *STD* — tumhara AI matchmaker 💌
Pehle apna profile bana lein. /createprofile', parse_mode='Markdown')

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

# --- Message handler for profile creation and chat relay ---
@dp.message()
async def handle_messages(msg: types.Message):
    uid = msg.from_user.id
    # 1) if in active anonymous chat, relay
    partner = await find_chat_partner(uid)
    if partner:
        # relay message text or photo
        if msg.text:
            await bot.send_message(partner, f"Someone: {msg.text}")
        elif msg.photo:
            # forward photo as file_id
            file_id = msg.photo[-1].file_id
            await bot.send_photo(partner, file_id)
        else:
            await msg.reply('Unsupported message type in anonymous chat.')
        return

    # 2) handle multi-step profile creation
    if uid in CREATING:
        step = CREATING[uid]
        text = (msg.text or '').strip()
        if step == 'name':
            TEMP[uid]['name'] = text or msg.from_user.full_name
            CREATING[uid] = 'gender'
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton('Male', callback_data='gender:Male'), InlineKeyboardButton('Female', callback_data='gender:Female'), InlineKeyboardButton('Other', callback_data='gender:Other')]
            ])
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
  
