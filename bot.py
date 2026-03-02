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

# ================= UTILS =================
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
    buttons = []
    for c in countries:
        remaining = len(set(get_numbers(c)) - get_global_seen(c))
        buttons.append(InlineKeyboardButton(text=f"{c} ({remaining})", callback_data=f"country_{c}"))
    rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def numbers_keyboard(country, selected):
    flag = get_flag(country)
    rows = []
    for n in selected:
        rows.append([InlineKeyboardButton(
            text=n,
            copy_text=CopyTextButton(text=n)
        )])
    rows.append([InlineKeyboardButton(text="Change Country", callback_data="back_to_countries")])
    rows.append([InlineKeyboardButton(text="Refresh", callback_data=f"refresh_{country}")])
    rows.append([InlineKeyboardButton(text="OTP Group", url=config.OTP_GROUP_LINK)])
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
        "✨ *Premium Number Bot* ✨\n\n💡 Access multiple countries' numbers instantly.",
        parse_mode="Markdown",
        reply_markup=dashboard_keyboard()
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    uid = message.from_user.id
    if uid not in ADMINS:
        await message.answer("❌ You are not an admin.")
        return
    await message.answer("⚙ *Admin Panel*", parse_mode="Markdown", reply_markup=admin_keyboard())

@dp.message(F.text.in_({"📱 Get Number", "📦 Available Country"}))
async def handle_get_number(message: Message):
    await message.answer("🌍 *Select a Country*", parse_mode="Markdown", reply_markup=country_keyboard())

@dp.message(F.text == "🌍 Active Traffic")
async def handle_traffic(message: Message):
    info = ""
    for c in get_countries():
        total = len(get_numbers(c))
        used = len(get_global_seen(c))
        info += f"🌐 {c} → Total: {total} | Used: {used} | Unused: {total - used}\n"
    await message.answer(info or "No data.")

@dp.message(F.text == "☎️ Support")
async def handle_support(message: Message):
    await message.answer("📞 Support: " + config.SUPPORT_LINK)

@dp.message(F.document)
async def receive_file(message: Message):
    uid = message.from_user.id
    if uid not in ADMINS or uid not in UPLOAD_MODE:
        return
    mode = UPLOAD_MODE.get(uid)
    doc = message.document
    try:
        file = await bot.get_file(doc.file_id)
        content_bytes = await bot.download_file(file.file_path)
        content_str = content_bytes.read().decode("utf-8", errors="ignore")
        numbers = [x.strip() for x in content_str.splitlines() if x.strip()]
        if not numbers:
            await message.answer("❌ File is empty or invalid!")
            UPLOAD_MODE.pop(uid, None)
            return
        country = doc.file_name.replace(".txt", "").strip()
        path = f"{config.NUMBER_DIR}/{country}.txt"
        if mode == "add":
            with open(path, "a") as f:
                f.write("\n" + "\n".join(numbers))
            await message.answer(f"✅ Numbers added to {country}!")
    except Exception as e:
        await message.answer(f"❌ Failed: {e}")
    UPLOAD_MODE.pop(uid, None)

@dp.message(F.text)
async def admin_text(message: Message):
    uid = message.from_user.id
    if uid not in ADMINS:
        return
    mode = ADMIN_MODE.get(uid)
    if not mode:
        return
    text = message.text.strip()
    try:
        if mode == "add_admin":
            ADMINS.add(int(text))
            await message.answer(f"✅ Admin added: {text}")
        elif mode == "remove_admin":
            ADMINS.discard(int(text))
            await message.answer(f"❌ Admin removed: {text}")
        elif mode == "broadcast":
            sent = 0
            for u in USERS:
                try:
                    await bot.send_message(u, f"📢 {text}")
                    sent += 1
                except:
                    pass
            await message.answer(f"✅ Sent to {sent} users")
        elif mode == "ban":
            BANNED.add(int(text))
            await message.answer(f"🚫 Banned: {text}")
        elif mode == "unban":
            BANNED.discard(int(text))
            await message.answer(f"✅ Unbanned: {text}")
    except Exception as e:
        await message.answer(f"❌ Invalid: {e}")
    ADMIN_MODE.pop(uid, None)

# ================= CALLBACKS =================
@dp.callback_query()
async def handle_callback(call: CallbackQuery):
    uid = call.from_user.id
    data = call.data
    cleanup_seen()

    if data == "back_to_start":
        USERS.add(uid)
        await call.message.edit_text(
            "✨ *Premium Number Bot* ✨\n\n💡 Access multiple countries' numbers instantly.",
            parse_mode="Markdown"
        )
        await call.answer()

    elif data == "back_to_countries":
        await call.message.edit_text(
            "🌍 *Select a Country*",
            parse_mode="Markdown",
            reply_markup=country_keyboard()
        )
        await call.answer()

    elif data.startswith("country_"):
        await show_numbers(call, data.replace("country_", ""))

    elif data.startswith("refresh_"):
        await show_numbers(call, data.replace("refresh_", ""))

    elif uid in ADMINS:
        if data == "bulk_add":
            UPLOAD_MODE[uid] = "add"
            await call.message.answer("📥 Send a .txt file to add numbers (filename = country).")
        elif data == "bulk_remove":
            kb_rows = [[InlineKeyboardButton(text=f"❌ Remove {c}", callback_data=f"bulk_remove_country_{c}")] for c in get_countries()]
            kb_rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")])
            await call.message.answer("📤 Select country to remove:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
        elif data.startswith("bulk_remove_country_"):
            country = data.replace("bulk_remove_country_", "")
            removed = len(get_numbers(country))
            open(f"{config.NUMBER_DIR}/{country}.txt", "w").close()
            await call.message.answer(f"✅ Removed {removed} numbers from {country}.")
        elif data == "clean":
            cleaned = sum(remove_duplicates(c) for c in get_countries())
            await call.message.answer(f"✅ Cleaned. Total: {cleaned}")
        elif data == "broadcast":
            ADMIN_MODE[uid] = "broadcast"
            await call.message.answer("📢 Send broadcast text:")
        elif data in ["add_admin", "remove_admin", "ban", "unban"]:
            ADMIN_MODE[uid] = data
            await call.message.answer("✏️ Send the ID now.")
        elif data == "online_users":
            await call.message.answer(f"👥 Total Users: {len(USERS)}")
        await call.answer()
    else:
        await call.answer()

async def show_numbers(call: CallbackQuery, country: str):
    uid = call.from_user.id
    unseen = list(set(get_numbers(country)) - get_global_seen(country))
    if not unseen:
        await call.message.edit_text("❌ No numbers available right now.")
        await call.answer()
        return
    selected = random.sample(unseen, min(3, len(unseen)))
    add_global_seen(country, selected)
    track_activity(uid, country, len(selected), selected)
    # + sign সরাও
    clean = [n.lstrip("+") for n in selected]
    await call.message.edit_text(".", reply_markup=numbers_keyboard(country, clean))
    await call.answer()

# ================= MAIN =================
async def main():
    load_user_data()
    print(">>> Bot starting (aiogram)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
