import os
import random
import time
import json
import asyncio
import unicodedata
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
import config

# ================= GLOBALS =================
USERS = set()
ADMINS = set(config.ADMIN_IDS)
BANNED = set()
USER_STATS = {}
USER_LAST_NUMBERS = {}
USER_LAST_ACTIVE = {}
UPLOAD_MODE = {}
ADMIN_MODE = {}
DATA_FILE = "user_data.json"

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

os.makedirs(config.NUMBER_DIR, exist_ok=True)
os.makedirs(config.SEEN_DIR, exist_ok=True)

# ================= DATA =================
def save_user_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "USER_STATS": USER_STATS,
            "USER_LAST_NUMBERS": USER_LAST_NUMBERS,
            "USER_LAST_ACTIVE": USER_LAST_ACTIVE
        }, f)

def load_user_data():
    global USER_STATS, USER_LAST_NUMBERS, USER_LAST_ACTIVE
    if not os.path.exists(DATA_FILE):
        return
    with open(DATA_FILE) as f:
        data = json.load(f)
    USER_STATS = data.get("USER_STATS", {})
    USER_LAST_NUMBERS = data.get("USER_LAST_NUMBERS", {})
    USER_LAST_ACTIVE = data.get("USER_LAST_ACTIVE", {})

# ================= UTILS =================
def get_countries():
    return [f.replace(".txt", "") for f in os.listdir(config.NUMBER_DIR)
            if f.endswith(".txt") and not f.endswith("_Backup.txt")]

def get_numbers(country):
    path = f"{config.NUMBER_DIR}/{country}.txt"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [x.strip() for x in f if x.strip()]

def get_global_seen(country):
    path = f"{config.SEEN_DIR}/global_{country}.txt"
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return set(x.strip() for x in f)

def add_global_seen(country, numbers):
    path = f"{config.SEEN_DIR}/global_{country}.txt"
    with open(path, "a") as f:
        for n in numbers:
            f.write(n + "\n")

def cleanup_seen():
    now = time.time()
    for fname in os.listdir(config.SEEN_DIR):
        path = os.path.join(config.SEEN_DIR, fname)
        if os.path.isfile(path) and now - os.path.getmtime(path) > config.CLEANUP_DAYS * 86400:
            os.remove(path)

def remove_duplicates(country):
    nums = list(dict.fromkeys(get_numbers(country)))
    with open(f"{config.NUMBER_DIR}/{country}.txt", "w") as f:
        f.write("\n".join(nums))
    return len(nums)

def track_activity(uid, country, count, numbers=None):
    uid = str(uid)
    if uid not in USER_STATS:
        USER_STATS[uid] = {"total": 0, "countries": {}}
    USER_STATS[uid]["total"] += count
    USER_STATS[uid]["countries"][country] = USER_STATS[uid]["countries"].get(country, 0) + count
    if numbers:
        USER_LAST_NUMBERS[uid] = numbers
    USER_LAST_ACTIVE[uid] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_user_data()

def get_flag(country_name):
    flag = ""
    for ch in country_name:
        if unicodedata.category(ch) in ("So", "Sm") or ord(ch) > 127:
            flag += ch
    return flag.strip()

# ================= KEYBOARDS =================
def dashboard_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Get Number"), KeyboardButton(text="📦 Available Country")],
        [KeyboardButton(text="🌍 Active Traffic"), KeyboardButton(text="☎️ Support")]
    ], resize_keyboard=True)

def country_keyboard():
    countries = get_countries()
    rows = []
    temp = []
    for c in countries:
        remaining = len(set(get_numbers(c)) - get_global_seen(c))
        temp.append(InlineKeyboardButton(
            text=f"{c} ({remaining})",
            callback_data=f"country_{c}"
        ))
        if len(temp) == 3:
            rows.append(temp)
            temp = []
    if temp:
        rows.append(temp)

    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def numbers_keyboard(country, selected):
    flag = get_flag(country)
    rows = []

    for n in selected:
        display = n.lstrip("+")
        copy_val = n if n.startswith("+") else f"+{n}"
        rows.append([
            InlineKeyboardButton(
                text=f"{flag} {display}",
                copy_text=CopyTextButton(text=copy_val)
            )
        ])

    rows.append([InlineKeyboardButton(text="🔄 Refresh", callback_data=f"refresh_{country}")])
    rows.append([InlineKeyboardButton(text="🌍 Change Country", callback_data="back_to_countries")])
    rows.append([InlineKeyboardButton(text="👥 OTP Group", url=config.OTP_GROUP_LINK)])

    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Admin", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Remove Admin", callback_data="remove_admin")],
        [InlineKeyboardButton(text="👥 Online Users", callback_data="online_users")],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton(text="🚫 Ban User", callback_data="ban")],
        [InlineKeyboardButton(text="✅ Unban User", callback_data="unban")],
        [InlineKeyboardButton(text="🗑 Clean Duplicates", callback_data="clean")],
        [InlineKeyboardButton(text="📥 Bulk Add Numbers", callback_data="bulk_add")],
        [InlineKeyboardButton(text="📤 Bulk Remove Numbers", callback_data="bulk_remove")],
    ])

# ================= HANDLERS =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    if uid in BANNED:
        return
    USERS.add(uid)
    await message.answer(
        "✨ Premium Number Bot ✨\n\nSelect an option below:",
        reply_markup=dashboard_keyboard()
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Not admin.")
        return
    await message.answer("⚙ Admin Panel", reply_markup=admin_keyboard())

@dp.callback_query()
async def handle_callback(call: CallbackQuery):
    uid = call.from_user.id
    data = call.data
    cleanup_seen()

    try:
        if data == "back_to_start":
            await call.message.edit_text(
                "✨ Premium Number Bot ✨\n\nSelect an option below:"
            )

        elif data == "back_to_countries":
            await call.message.edit_text(
                "🌍 Select a Country",
                reply_markup=country_keyboard()
            )

        elif data.startswith("country_"):
            await show_numbers(call, data.replace("country_", ""))

        elif data.startswith("refresh_"):
            await show_numbers(call, data.replace("refresh_", ""))

        await call.answer()

    except:
        await call.answer()

async def show_numbers(call: CallbackQuery, country: str):
    unseen = list(set(get_numbers(country)) - get_global_seen(country))

    if not unseen:
        await call.message.edit_text("❌ No numbers available right now.")
        return

    selected = random.sample(unseen, min(3, len(unseen)))
    add_global_seen(country, selected)
    track_activity(call.from_user.id, country, len(selected), selected)

    await call.message.edit_text(
        f"📱 {country} Numbers",
        reply_markup=numbers_keyboard(country, selected)
    )

# ================= MAIN =================
async def main():
    load_user_data()
    print("Bot running (FULL ORIGINAL SAFE)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
