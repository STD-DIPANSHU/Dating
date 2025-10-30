import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ConversationHandler
)
# MongoDB ke liye
from pymongo import MongoClient

# === CONFIGURATION (Apna data yahan change karein) ===
BOT_TOKEN = "BOT_TOKEN" 
MONGO_URI = "YOUR_MONGO_CONNECTION_STRING" 
# Database aur Collection ka naam
DATABASE_NAME = 'datingbot_db'
COLLECTION_NAME = 'users'

# MongoDB Client setup
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[DATABASE_NAME][COLLECTION_NAME]
    logging.info("MongoDB se successful connection ho gaya.")
except Exception as e:
    logging.error(f"MongoDB connection mein error aaya: {e}")
    db = None

# === LOGGING SETUP ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# === CONVERSATION KE STAGES (States) ===
# Har state ek sawal ko represent karta hai
NAME, GENDER, LOOKING_FOR, CITY, AGE, PHOTO, BIO, MENU = range(8)

# === 1. /start command: Profile banana shuru karein ===
async def start(update: Update, context) -> int:
    user_id = update.effective_user.id
    
    # Check karein ki user ki profile already bani hui hai ya nahi
    user_data = db.find_one({'user_id': user_id})

    if user_data and user_data.get('profile_complete'):
        # Agar profile complete hai, to Menu dikhayein
        await update.message.reply_text(
            "Welcome back! Aapka profile ready hai. Kya karna chahte hain?",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END # Ya aap MENU state par bhi bhej sakte hain

    keyboard = [["Create a profile"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Hi! 👋\nWelcome to our Michi dating bot! 💕\nTo get started, create your profile - it's quick and easy!",
        reply_markup=reply_markup
    )
    # Agla step: Jab user 'Create a profile' click karega
    return NAME 

# === 2. Naam poochhna (Jab 'Create a profile' button click ho) ===
async def ask_name(update: Update, context) -> int:
    if update.message.text == "Create a profile":
        await update.message.reply_text(
            "What's your name? 📝",
            reply_markup=ReplyKeyboardRemove() # Keyboard hata diya
        )
        return GENDER # Agla step: GENDER

# === 3. Gender poochhna aur Naam save karna ===
async def ask_gender(update: Update, context) -> int:
    # Pichle step ka data (Naam) context mein save karein
    context.user_data['name'] = update.message.text
    
    keyboard = [["Boy", "Girl"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"Great, {context.user_data['name']}! State your gender 👤",
        reply_markup=reply_markup
    )
    return LOOKING_FOR # Agla step: LOOKING_FOR

# === 4. Kiske liye search kar rahe hain, poochhna aur Gender save karna ===
async def ask_looking_for(update: Update, context) -> int:
    gender = update.message.text
    if gender not in ["Boy", "Girl"]:
        await update.message.reply_text("Please use the buttons provided.")
        return LOOKING_FOR # Isi step mein rahenge
        
    context.user_data['gender'] = gender # Gender save kiya
    
    keyboard = [["Boys", "Girls", "Everyone"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Pick who you're looking for 💕",
        reply_markup=reply_markup
    )
    return CITY # Agla step: CITY

# === 5. City poochhna aur Looking For save karna ===
async def ask_city(update: Update, context) -> int:
    looking_for = update.message.text
    if looking_for not in ["Boys", "Girls", "Everyone"]:
        await update.message.reply_text("Please use the buttons provided.")
        return CITY
        
    context.user_data['looking_for'] = looking_for
    
    await update.message.reply_text(
        "Enter your city: 🏙️",
        reply_markup=ReplyKeyboardRemove()
    )
    return AGE # Agla step: AGE

# === 6. Age poochhna aur City save karna ===
async def ask_age(update: Update, context) -> int:
    context.user_data['city'] = update.message.text
    
    await update.message.reply_text(
        "How old are you? 🎂",
        reply_markup=ReplyKeyboardRemove()
    )
    return PHOTO # Agla step: PHOTO

# === 7. Photo upload karna aur Age save karna ===
async def ask_photo(update: Update, context) -> int:
    age_text = update.message.text
    # Age validation
    if not age_text.isdigit() or int(age_text) < 18 or int(age_text) > 99:
        await update.message.reply_text("Please enter a valid age between 18 and 99.")
        return PHOTO # Isi step mein rahenge

    context.user_data['age'] = int(age_text)
    context.user_data['photos'] = [] # Photos ki list
    
    await update.message.reply_text(
        "Upload your photo! You can send up to 3 photos at the same time! 📸"
    )
    return BIO # Agla step: BIO (Jahan Photo aur uske baad Bio aayega)

# === 8. Photos ko handle karna (Multiple Photos ke liye) ===
# Note: Hum BIO step mein hi hain, yahan photo/text dono handle honge
async def handle_photo_or_finish(update: Update, context) -> int:
    photos_list = context.user_data.get('photos', [])
    
    if update.message.photo:
        # Photo mili, uski sabse badi file_id save karein
        file_id = update.message.photo[-1].file_id
        
        if len(photos_list) < 3:
            photos_list.append(file_id)
            context.user_data['photos'] = photos_list
            
            remaining = 3 - len(photos_list)
            
            keyboard = [["That's it, keep the photo"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

            if remaining > 0:
                await update.message.reply_text(
                    f"Photo {len(photos_list)}/3 uploaded! You can upload {remaining} more photo(s) or press 'That's it, keep the photo'",
                    reply_markup=reply_markup
                )
            else:
                 # 3 photo ho chuki hain, ab seedhe bio par bhejein
                await ask_bio(update, context)
                return BIO # Bio step complete, ab bio input ka wait

        return BIO # Isi step mein rahenge

    # Agar 'That's it' button click hua ya user ne text message bhej diya
    if update.message.text == "That's it, keep the photo" or update.message.text and len(photos_list) > 0:
        await ask_bio(update, context)
        return BIO # Agla step: BIO
    
    await update.message.reply_text("Please upload at least one photo or use the 'That's it' button.")
    return BIO # Isi step mein rahenge

# === 9. Bio poochhna ===
async def ask_bio(update: Update, context) -> int:
    # Photo handle hone ke baad yeh chalta hai
    await update.message.reply_text(
        "Tell us a little about yourself - it will help others get to know you better! 📝",
        reply_markup=ReplyKeyboardRemove()
    )
    return MENU # Agla step: MENU (Final Save)

# === 10. Profile ko Final Save karna aur Menu dikhana ===
async def final_save(update: Update, context) -> int:
    bio_text = update.message.text
    context.user_data['bio'] = bio_text
    
    user_data = {
        'user_id': update.effective_user.id,
        'username': update.effective_user.username,
        'profile_complete': True,
        'name': context.user_data['name'],
        'gender': context.user_data['gender'],
        'looking_for': context.user_data['looking_for'],
        'city': context.user_data['city'],
        'age': context.user_data['age'],
        'photos': context.user_data['photos'],
        'bio': context.user_data['bio'],
        'is_in_chat': False, # Anonymous chat ke liye
        'matching_with_user_id': None # Anonymous chat ke liye
    }

    # Data ko MongoDB mein insert ya update karein
    if db:
        db.update_one({'user_id': user_data['user_id']}, {'$set': user_data}, upsert=True)
    
    # User data context se clear karein
    context.user_data.clear()
    
    await update.message.reply_text(
        "Great! Your profile is ready - now you can search for interesting people 💬",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END # Conversation ko end karein

# === Main Menu Keyboard Function ===
def get_main_menu_keyboard():
    keyboard = [
        ["View profiles"],
        ["My profile", "Who liked me"],
        ["Invite friends"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === Conversation ko rokna (/cancel) ===
async def cancel(update: Update, context) -> int:
    await update.message.reply_text(
        'Profile creation cancelled. You can /start again.',
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

# === Main Function ===
def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        
        states={
            NAME: [MessageHandler(filters.Regex('^Create a profile$'), ask_name)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
            LOOKING_FOR: [MessageHandler(filters.Regex('^(Boy|Girl)$'), ask_looking_for)],
            CITY: [MessageHandler(filters.Regex('^(Boys|Girls|Everyone)$'), ask_city)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_age)],
            # Photo aur "That's it" button ko isi step mein handle kar rahe hain
            PHOTO: [MessageHandler(filters.TEXT | filters.PHOTO & ~filters.COMMAND, handle_photo_or_finish)],
            # Bio input ke baad final save hoga
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, final_save)]
        },
        
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    
    # Yahan hum menu ke buttons ko handle karne ke liye naye handlers jod sakte hain
    # application.add_handler(MessageHandler(filters.Regex('^View profiles$'), view_profiles_command))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
