import os, re, json, asyncio, random, logging
from pathlib import Path
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    CopyTextButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

import config

# ═══════════════════════════════════════════════
#               📋 LOGGING
# ═══════════════════════════════════════════════
logging.basicConfig(level=logging.INFO)
for lg in ["aiogram", "aiohttp"]:
    logging.getLogger(lg).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
#               🤖 BOT INIT
# ═══════════════════════════════════════════════
bot = Bot(token=config.BOT_TOKEN)
dp  = Dispatcher()

ADMINS = set(config.ADMIN_IDS)

# ═══════════════════════════════════════════════
#               💾 DATA STORAGE
# ═══════════════════════════════════════════════
DATA_FILE = "user_data.json"

def load_data():
    default = {
        "users": {},
        "banned": [],
        "vip": [],
        "admins": [str(a) for a in config.ADMIN_IDS],
        "locked_countries": [],
        "user_limits": {},
        "per_req": config.DEFAULT_NUMBERS_PER_REQ,
        "support_msgs": {},
        "upload_mode": {}
    }
    if not os.path.exists(DATA_FILE):
        return default
    try:
        d = json.load(open(DATA_FILE))
        for k, v in default.items():
            if k not in d:
                d[k] = v
        return d
    except:
        return default

def save_data(d):
    json.dump(d, open(DATA_FILE, "w"), indent=2, ensure_ascii=False)

def get_user(uid):
    d = load_data()
    uid_s = str(uid)
    if uid_s not in d["users"]:
        d["users"][uid_s] = {
            "name": "", "username": "",
            "joined": datetime.now().strftime("%Y-%m-%d"),
            "last_active": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_numbers": 0,
            "last_numbers": []
        }
        save_data(d)
    return d["users"][uid_s]

def update_user(uid, **kwargs):
    d = load_data()
    uid_s = str(uid)
    if uid_s not in d["users"]:
        get_user(uid)
        d = load_data()
    d["users"][uid_s].update(kwargs)
    d["users"][uid_s]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_data(d)

def is_admin(uid):
    d = load_data()
    return str(uid) in d["admins"] or uid in ADMINS

def is_banned(uid):
    d = load_data()
    return str(uid) in d["banned"]

def is_vip(uid):
    d = load_data()
    return str(uid) in d["vip"]

# ═══════════════════════════════════════════════
#               📁 NUMBER MANAGEMENT
# ═══════════════════════════════════════════════
def clean_country_name(stem):
    # Remove emoji unicode escape sequences like #L01f1ff#L01f1fc
    import re
    name = re.sub(r'#L[0-9a-fA-F]+', '', stem).strip()
    return name if name else stem

def get_countries():
    path = Path(config.NUMBER_DIR)
    if not path.exists():
        return []
    countries = []
    for f in path.glob("*.txt"):
        lines = [l.strip() for l in f.read_text(errors="ignore").splitlines() if l.strip()]
        if lines:
            name = clean_country_name(f.stem)
            countries.append((name, len(lines), f.stem))
    return sorted(countries, key=lambda x: -x[1])

def get_numbers(country):
    # Try exact match first
    path = Path(config.NUMBER_DIR) / f"{country}.txt"
    if not path.exists():
        # Try finding by clean name
        for f in Path(config.NUMBER_DIR).glob("*.txt"):
            if clean_country_name(f.stem).lower() == country.lower():
                path = f
                break
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text(errors="ignore").splitlines() if l.strip()]

def get_seen(country):
    path = Path(config.SEEN_DIR) / f"{country}.json"
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text()))
    except:
        return set()

def add_seen(country, numbers):
    Path(config.SEEN_DIR).mkdir(exist_ok=True)
    path = Path(config.SEEN_DIR) / f"{country}.json"
    seen = get_seen(country)
    seen.update(numbers)
    path.write_text(json.dumps(list(seen)))

def get_unseen(country):
    return list(set(get_numbers(country)) - get_seen(country))

# ═══════════════════════════════════════════════
#               🌍 FLAG HELPER
# ═══════════════════════════════════════════════
FLAG_MAP = {
    "Afghanistan":"🇦🇫","Albania":"🇦🇱","Algeria":"🇩🇿","Angola":"🇦🇴","Argentina":"🇦🇷",
    "Armenia":"🇦🇲","Australia":"🇦🇺","Austria":"🇦🇹","Azerbaijan":"🇦🇿","Bahrain":"🇧🇭",
    "Bangladesh":"🇧🇩","Belarus":"🇧🇾","Belgium":"🇧🇪","Bolivia":"🇧🇴","Bosnia":"🇧🇦",
    "Brazil":"🇧🇷","Bulgaria":"🇧🇬","Cambodia":"🇰🇭","Cameroon":"🇨🇲","Canada":"🇨🇦",
    "Chile":"🇨🇱","China":"🇨🇳","Colombia":"🇨🇴","Croatia":"🇭🇷","Czech":"🇨🇿",
    "Denmark":"🇩🇰","Ecuador":"🇪🇨","Egypt":"🇪🇬","Ethiopia":"🇪🇹","Finland":"🇫🇮",
    "France":"🇫🇷","Georgia":"🇬🇪","Germany":"🇩🇪","Ghana":"🇬🇭","Greece":"🇬🇷",
    "Guatemala":"🇬🇹","Honduras":"🇭🇳","Hungary":"🇭🇺","India":"🇮🇳","Indonesia":"🇮🇩",
    "Iran":"🇮🇷","Iraq":"🇮🇶","Ireland":"🇮🇪","Israel":"🇮🇱","Italy":"🇮🇹",
    "Jamaica":"🇯🇲","Japan":"🇯🇵","Jordan":"🇯🇴","Kazakhstan":"🇰🇿","Kenya":"🇰🇪",
    "Kuwait":"🇰🇼","Kyrgyzstan":"🇰🇬","Latvia":"🇱🇻","Lebanon":"🇱🇧","Libya":"🇱🇾",
    "Lithuania":"🇱🇹","Malaysia":"🇲🇾","Mexico":"🇲🇽","Moldova":"🇲🇩","Morocco":"🇲🇦",
    "Myanmar":"🇲🇲","Nepal":"🇳🇵","Netherlands":"🇳🇱","Nicaragua":"🇳🇮","Nigeria":"🇳🇬",
    "Norway":"🇳🇴","Oman":"🇴🇲","Pakistan":"🇵🇰","Palestine":"🇵🇸","Panama":"🇵🇦",
    "Paraguay":"🇵🇾","Peru":"🇵🇪","Philippines":"🇵🇭","Poland":"🇵🇱","Portugal":"🇵🇹",
    "Qatar":"🇶🇦","Romania":"🇷🇴","Russia":"🇷🇺","Saudi":"🇸🇦","Saudi Arabia":"🇸🇦",
    "Senegal":"🇸🇳","Serbia":"🇷🇸","Singapore":"🇸🇬","Somalia":"🇸🇴","South Africa":"🇿🇦",
    "South Korea":"🇰🇷","Spain":"🇪🇸","Sri Lanka":"🇱🇰","Sudan":"🇸🇩","Sweden":"🇸🇪",
    "Switzerland":"🇨🇭","Syria":"🇸🇾","Taiwan":"🇹🇼","Tajikistan":"🇹🇯","Tanzania":"🇹🇿",
    "Thailand":"🇹🇭","Tunisia":"🇹🇳","Turkey":"🇹🇷","Turkmenistan":"🇹🇲","UAE":"🇦🇪",
    "Uganda":"🇺🇬","Ukraine":"🇺🇦","United Kingdom":"🇬🇧","UK":"🇬🇧","USA":"🇺🇸",
    "Uzbekistan":"🇺🇿","Venezuela":"🇻🇪","Vietnam":"🇻🇳","Yemen":"🇾🇪","Zimbabwe":"🇿🇼",
}

def get_flag(country):
    for k, v in FLAG_MAP.items():
        if k.lower() in country.lower() or country.lower() in k.lower():
            return v
    return "🌍"

# ═══════════════════════════════════════════════
#               ⌨️ KEYBOARDS
# ═══════════════════════════════════════════════
def main_keyboard(uid):
    rows = [
        [KeyboardButton(text="📱 Get Number"), KeyboardButton(text="📦 Available Country")],
        [KeyboardButton(text="☎️ Support")],
    ]
    if is_admin(uid):
        rows.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def country_keyboard(uid=None):
    d = load_data()
    locked = d.get("locked_countries", [])
    countries = get_countries()
    if not countries:
        return None
    rows = []
    row = []
    for country, count, stem in countries:
        flag = get_flag(country)
        is_locked = country in locked or stem in locked
        vip_ok = uid and is_vip(uid)
        if is_locked and not vip_ok:
            label = f"💲 {flag} {country}"
        else:
            label = f"{flag} {country} ({count})"
        row.append(InlineKeyboardButton(text=label, callback_data=f"country_{country}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_countries")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def numbers_keyboard(country, numbers):
    flag = get_flag(country)
    rows = []
    for n in numbers:
        clean = re.sub(r"\D", "", n)
        rows.append([InlineKeyboardButton(
            text=f"{flag}  {clean}",
            copy_text=CopyTextButton(text=f"+{clean}")
        )])
    rows.append([
        InlineKeyboardButton(text="🔄 Change Numbers", callback_data=f"refresh_{country}"),
        InlineKeyboardButton(text="🌍 Change Country",  callback_data="back_countries"),
    ])
    rows.append([
        InlineKeyboardButton(text="📲 OTP Group", url=config.OTP_GROUP_LINK),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 User Details",    callback_data="adm_user_details"),
         InlineKeyboardButton(text="📢 Broadcast",       callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="🎯 Set User Limit",  callback_data="adm_set_limit"),
         InlineKeyboardButton(text="🔢 Num/Request",     callback_data="adm_set_per_req")],
        [InlineKeyboardButton(text="📥 Add Numbers",     callback_data="adm_bulk_add"),
         InlineKeyboardButton(text="📤 Remove Numbers",  callback_data="adm_bulk_remove")],
        [InlineKeyboardButton(text="🗑 Clean Dupes",     callback_data="adm_clean"),
         InlineKeyboardButton(text="🚫 Ban User",        callback_data="adm_ban")],
        [InlineKeyboardButton(text="✅ Unban User",      callback_data="adm_unban"),
         InlineKeyboardButton(text="➕ Add Admin",       callback_data="adm_add_admin")],
        [InlineKeyboardButton(text="➖ Remove Admin",    callback_data="adm_remove_admin"),
         InlineKeyboardButton(text="📩 Support Check",   callback_data="adm_support")],
        [InlineKeyboardButton(text="👤 All Users",       callback_data="adm_all_users")],
        [InlineKeyboardButton(text="🔒 Lock Country",    callback_data="adm_lock_country"),
         InlineKeyboardButton(text="🔓 Unlock Country",  callback_data="adm_unlock_country")],
        [InlineKeyboardButton(text="💎 Add VIP",         callback_data="adm_add_vip"),
         InlineKeyboardButton(text="❌ Remove VIP",      callback_data="adm_remove_vip")],
    ])

# ═══════════════════════════════════════════════
#               🏠 START
# ═══════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    if is_banned(uid):
        return await message.answer("🚫 You are banned.")
    update_user(uid,
        name=message.from_user.first_name or "",
        username=message.from_user.username or "")
    await message.answer(
        f"👋 Welcome to <b>CodeGate Number Bot</b>!\n\n"
        f"📱 <b>Get Number</b> — Get virtual numbers\n"
        f"📦 <b>Available Country</b> — View countries & counts\n"
        f"☎️ <b>Support</b> — Contact support\n\n"
        f"📲 Join: {config.OTP_GROUP_LINK}",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(uid)
    )

# ═══════════════════════════════════════════════
#               📱 GET NUMBER
# ═══════════════════════════════════════════════
@dp.message(F.text == "📱 Get Number")
async def handle_get_number(message: Message):
    uid = message.from_user.id
    if is_banned(uid):
        return await message.answer("🚫 You are banned.")
    kb = country_keyboard(uid)
    if not kb:
        return await message.answer("❌ No numbers available right now.")
    await message.answer("🌍 <b>Select a Country:</b>", parse_mode=ParseMode.HTML, reply_markup=kb)

# ═══════════════════════════════════════════════
#               📦 AVAILABLE COUNTRY
# ═══════════════════════════════════════════════
@dp.message(F.text == "📦 Available Country")
async def handle_available(message: Message):
    countries = get_countries()
    if not countries:
        return await message.answer("❌ No numbers available.")
    d = load_data()
    locked = d.get("locked_countries", [])
    lines = []
    for country, count in countries:
        flag = get_flag(country)
        lock = "💲" if country in locked else "✅"
        lines.append(f"{lock} {flag} <b>{country}</b> — <code>{count}</code> numbers")
    await message.answer(
        f"📦 <b>Available Countries</b>\n\n" + "\n".join(lines),
        parse_mode=ParseMode.HTML
    )

# ═══════════════════════════════════════════════
#               ☎️ SUPPORT
# ═══════════════════════════════════════════════
@dp.message(F.text == "☎️ Support")
async def handle_support(message: Message):
    uid = message.from_user.id
    d = load_data()
    d.setdefault("support_mode", [])
    if uid not in d["support_mode"]:
        d["support_mode"].append(uid)
    save_data(d)
    await message.answer(
        "☎️ <b>Support</b>\n\nWrite your message and we'll get back to you:",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("reply"))
async def cmd_reply(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer("Usage: /reply {uid} {message}")
    try:
        target_uid = int(args[1])
        reply_text = args[2]
        await bot.send_message(target_uid,
            f"📩 <b>Support Reply:</b>\n\n{reply_text}",
            parse_mode=ParseMode.HTML)
        await message.answer(f"✅ Reply sent to <code>{target_uid}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"❌ Error: {e}")

# ═══════════════════════════════════════════════
#               ⚙️ ADMIN PANEL
# ═══════════════════════════════════════════════
@dp.message(F.text == "⚙️ Admin Panel")
async def handle_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    d = load_data()
    countries = get_countries()
    total_nums = sum(c[1] for c in countries)
    await message.answer(
        f"⚙️ <b>Admin Panel</b>\n\n"
        f"👥 Users: <b>{len(d['users'])}</b>\n"
        f"🚫 Banned: <b>{len(d['banned'])}</b>\n"
        f"💎 VIP: <b>{len(d['vip'])}</b>\n"
        f"🌍 Countries: <b>{len(countries)}</b>\n"
        f"📱 Total Numbers: <b>{total_nums}</b>\n"
        f"🔢 Per Request: <b>{d.get('per_req', config.DEFAULT_NUMBERS_PER_REQ)}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard()
    )

# ═══════════════════════════════════════════════
#               💬 TEXT HANDLER
# ═══════════════════════════════════════════════
ADMIN_MODE = {}

@dp.message(F.text)
async def handle_text(message: Message):
    uid = message.from_user.id
    text = message.text or ""

    # Support mode
    d = load_data()
    if uid in d.get("support_mode", []):
        d["support_mode"] = [x for x in d["support_mode"] if x != uid]
        d.setdefault("support_msgs", {})[str(uid)] = {
            "msg": text,
            "name": message.from_user.first_name or "",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_data(d)
        for adm in d["admins"]:
            try:
                await bot.send_message(int(adm),
                    f"📩 <b>Support Message</b>\n"
                    f"👤 <a href='tg://user?id={uid}'>{message.from_user.first_name}</a> (<code>{uid}</code>)\n\n"
                    f"{text}\n\n"
                    f"Reply: /reply {uid} your_message",
                    parse_mode=ParseMode.HTML)
            except: pass
        return await message.answer("✅ Message sent! We'll reply soon.")

    # Admin mode
    if uid in ADMIN_MODE:
        mode = ADMIN_MODE.pop(uid)
        d = load_data()

        if mode == "adm_broadcast":
            users = list(d["users"].keys())
            sent = 0
            for u in users:
                try:
                    await bot.send_message(int(u), f"📢 <b>Broadcast</b>\n\n{text}", parse_mode=ParseMode.HTML)
                    sent += 1
                except: pass
            return await message.answer(f"✅ Sent to {sent} users.")

        elif mode == "adm_ban":
            uid2 = re.sub(r"\D", "", text)
            if uid2:
                if uid2 not in d["banned"]:
                    d["banned"].append(uid2)
                save_data(d)
                try: await bot.send_message(int(uid2), "🚫 You have been banned.")
                except: pass
                return await message.answer(f"🚫 Banned: <code>{uid2}</code>", parse_mode=ParseMode.HTML)

        elif mode == "adm_unban":
            uid2 = re.sub(r"\D", "", text)
            if uid2 in d["banned"]:
                d["banned"].remove(uid2)
            save_data(d)
            try: await bot.send_message(int(uid2), "✅ You have been unbanned.")
            except: pass
            return await message.answer(f"✅ Unbanned: <code>{uid2}</code>", parse_mode=ParseMode.HTML)

        elif mode == "adm_add_admin":
            uid2 = re.sub(r"\D", "", text)
            if uid2 and uid2 not in d["admins"]:
                d["admins"].append(uid2)
            save_data(d)
            return await message.answer(f"✅ Admin added: <code>{uid2}</code>", parse_mode=ParseMode.HTML)

        elif mode == "adm_remove_admin":
            uid2 = re.sub(r"\D", "", text)
            if uid2 in d["admins"] and uid2 != str(list(ADMINS)[0]):
                d["admins"].remove(uid2)
            save_data(d)
            return await message.answer(f"✅ Admin removed: <code>{uid2}</code>", parse_mode=ParseMode.HTML)

        elif mode == "adm_add_vip":
            uid2 = re.sub(r"\D", "", text)
            if uid2 and uid2 not in d["vip"]:
                d["vip"].append(uid2)
            save_data(d)
            try: await bot.send_message(int(uid2), "💎 You have been granted VIP access!")
            except: pass
            return await message.answer(f"💎 VIP added: <code>{uid2}</code>", parse_mode=ParseMode.HTML)

        elif mode == "adm_remove_vip":
            uid2 = re.sub(r"\D", "", text)
            if uid2 in d["vip"]:
                d["vip"].remove(uid2)
            save_data(d)
            return await message.answer(f"✅ VIP removed: <code>{uid2}</code>", parse_mode=ParseMode.HTML)

        elif mode == "adm_set_limit":
            parts = text.split()
            if len(parts) == 2 and parts[1].isdigit():
                d.setdefault("user_limits", {})[parts[0]] = int(parts[1])
                save_data(d)
                return await message.answer(f"✅ Limit set: <code>{parts[0]}</code> → {parts[1]}", parse_mode=ParseMode.HTML)
            return await message.answer("Format: uid limit (e.g. 123456789 5)")

        elif mode == "adm_set_per_req":
            if text.isdigit() and 1 <= int(text) <= 10:
                d["per_req"] = int(text)
                save_data(d)
                return await message.answer(f"✅ Numbers per request: <b>{text}</b>", parse_mode=ParseMode.HTML)
            return await message.answer("Enter a number 1-10")

        elif mode == "adm_bulk_remove":
            country = text.strip()
            path = Path(config.NUMBER_DIR) / f"{country}.txt"
            if path.exists():
                path.unlink()
                return await message.answer(f"✅ Removed: <b>{country}</b>", parse_mode=ParseMode.HTML)
            return await message.answer(f"❌ Country not found: {country}")

        elif mode == "adm_lock_country":
            country = text.strip()
            if country not in d.get("locked_countries", []):
                d.setdefault("locked_countries", []).append(country)
            save_data(d)
            return await message.answer(f"🔒 Locked: <b>{country}</b>", parse_mode=ParseMode.HTML)

        elif mode == "adm_unlock_country":
            country = text.strip()
            if country in d.get("locked_countries", []):
                d["locked_countries"].remove(country)
            save_data(d)
            return await message.answer(f"🔓 Unlocked: <b>{country}</b>", parse_mode=ParseMode.HTML)

        elif mode == "adm_user_details":
            uid2 = re.sub(r"\D", "", text)
            u = d["users"].get(uid2)
            if not u:
                return await message.answer(f"❌ User not found: {uid2}")
            status = "💎 VIP" if uid2 in d["vip"] else ("🚫 Banned" if uid2 in d["banned"] else "👤 Member")
            nums = "\n".join([f"  <code>{n}</code>" for n in u.get("last_numbers", [])[-5:]]) or "None"
            return await message.answer(
                f"👤 <b>User Details</b>\n\n"
                f"🆔 ID: <code>{uid2}</code>\n"
                f"👤 Name: {u.get('name','')}\n"
                f"🌐 Username: @{u.get('username','')}\n"
                f"📌 Status: {status}\n"
                f"📅 Joined: {u.get('joined','')}\n"
                f"🕐 Last Active: {u.get('last_active','')}\n"
                f"📱 Total Numbers: {u.get('total_numbers',0)}\n"
                f"📋 Last Numbers:\n{nums}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚫 Ban",    callback_data=f"quick_ban_{uid2}"),
                     InlineKeyboardButton(text="✅ Unban",  callback_data=f"quick_unban_{uid2}")],
                    [InlineKeyboardButton(text="💎 Add VIP", callback_data=f"quick_vip_{uid2}"),
                     InlineKeyboardButton(text="❌ Rem VIP", callback_data=f"quick_unvip_{uid2}")],
                ])
            )

# ═══════════════════════════════════════════════
#               📄 FILE UPLOAD
# ═══════════════════════════════════════════════
@dp.message(F.document)
async def handle_file(message: Message):
    uid = message.from_user.id
    if not is_admin(uid):
        return
    d = load_data()
    if d.get("upload_mode", {}).get(str(uid)) != "adm_bulk_add":
        return
    d["upload_mode"].pop(str(uid), None)
    save_data(d)
    doc = message.document
    if not doc.file_name.endswith(".txt"):
        return await message.answer("❌ Only .txt files allowed.")
    country = doc.file_name.replace(".txt", "")
    path = Path(config.NUMBER_DIR)
    path.mkdir(exist_ok=True)
    file = await bot.get_file(doc.file_id)
    content = await bot.download_file(file.file_path)
    numbers = [l.strip() for l in content.read().decode(errors="ignore").splitlines() if l.strip()]
    filepath = path / f"{country}.txt"
    existing = set(get_numbers(country))
    new_nums = [n for n in numbers if n not in existing]
    with open(filepath, "a") as f:
        for n in new_nums:
            f.write(n + "\n")
    await message.answer(
        f"✅ <b>{country}</b> updated!\n"
        f"➕ Added: <b>{len(new_nums)}</b>\n"
        f"📱 Total: <b>{len(existing) + len(new_nums)}</b>",
        parse_mode=ParseMode.HTML
    )

# ═══════════════════════════════════════════════
#               🔘 CALLBACK HANDLER
# ═══════════════════════════════════════════════
@dp.callback_query()
async def handle_callback(call: CallbackQuery):
    uid = call.from_user.id
    data = call.data

    # ── Country select ──
    if data.startswith("country_"):
        country = data.replace("country_", "")
        d = load_data()
        locked = d.get("locked_countries", [])

        if country in locked and not is_vip(uid):
            return await call.answer(
                "❌ No Active Subscription\n💳 Contact @codegatex",
                show_alert=True
            )

        unseen = get_unseen(country)
        per_req = d.get("per_req", config.DEFAULT_NUMBERS_PER_REQ)

        if not unseen:
            # reset seen and try again
            seen_path = Path(config.SEEN_DIR) / f"{country}.json"
            if seen_path.exists():
                seen_path.unlink()
            unseen = get_numbers(country)

        if not unseen:
            return await call.answer("❌ No numbers available!", show_alert=True)

        selected = random.sample(unseen, min(per_req, len(unseen)))
        add_seen(country, selected)

        # Track user numbers
        u = d["users"].get(str(uid), {})
        last = u.get("last_numbers", [])
        last = (selected + last)[:20]
        update_user(uid, last_numbers=last,
                    total_numbers=u.get("total_numbers", 0) + len(selected))

        flag = get_flag(country)
        await call.message.edit_text(
            f"📱 <b>{flag} {country}</b>\n\n"
            f"👆 Click to copy • {len(selected)} numbers",
            parse_mode=ParseMode.HTML,
            reply_markup=numbers_keyboard(country, selected)
        )
        await call.answer()

    # ── Refresh numbers ──
    elif data.startswith("refresh_"):
        country = data.replace("refresh_", "")
        d = load_data()
        unseen = get_unseen(country)
        per_req = d.get("per_req", config.DEFAULT_NUMBERS_PER_REQ)

        if not unseen:
            seen_path = Path(config.SEEN_DIR) / f"{country}.json"
            if seen_path.exists():
                seen_path.unlink()
            unseen = get_numbers(country)

        if not unseen:
            return await call.answer("❌ No more numbers!", show_alert=True)

        selected = random.sample(unseen, min(per_req, len(unseen)))
        add_seen(country, selected)

        flag = get_flag(country)
        await call.message.edit_text(
            f"📱 <b>{flag} {country}</b>\n\n"
            f"👆 Click to copy • {len(selected)} numbers",
            parse_mode=ParseMode.HTML,
            reply_markup=numbers_keyboard(country, selected)
        )
        await call.answer()

    # ── Back to countries ──
    elif data in ("back_countries", "refresh_countries"):
        kb = country_keyboard(uid)
        if not kb:
            return await call.answer("No countries!", show_alert=True)
        await call.message.edit_text(
            "🌍 <b>Select a Country:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        await call.answer()

    # ── Quick actions ──
    elif data.startswith("quick_"):
        if not is_admin(uid):
            return await call.answer("No permission!", show_alert=True)
        parts = data.split("_", 2)
        action = parts[1]
        target = parts[2]
        d = load_data()

        if action == "ban":
            if target not in d["banned"]:
                d["banned"].append(target)
            save_data(d)
            try: await bot.send_message(int(target), "🚫 You have been banned.")
            except: pass
            await call.answer(f"🚫 Banned {target}")

        elif action == "unban":
            if target in d["banned"]:
                d["banned"].remove(target)
            save_data(d)
            try: await bot.send_message(int(target), "✅ You have been unbanned.")
            except: pass
            await call.answer(f"✅ Unbanned {target}")

        elif action == "vip":
            if target not in d["vip"]:
                d["vip"].append(target)
            save_data(d)
            try: await bot.send_message(int(target), "💎 VIP access granted!")
            except: pass
            await call.answer(f"💎 VIP added {target}")

        elif action == "unvip":
            if target in d["vip"]:
                d["vip"].remove(target)
            save_data(d)
            await call.answer(f"✅ VIP removed {target}")

    # ── Admin callbacks ──
    elif is_admin(uid):
        d = load_data()

        if data == "adm_broadcast":
            ADMIN_MODE[uid] = "adm_broadcast"
            await call.message.answer("📢 Enter broadcast message:")
            await call.answer()

        elif data == "adm_ban":
            ADMIN_MODE[uid] = "adm_ban"
            await call.message.answer("🚫 Enter user ID to ban:")
            await call.answer()

        elif data == "adm_unban":
            ADMIN_MODE[uid] = "adm_unban"
            await call.message.answer("✅ Enter user ID to unban:")
            await call.answer()

        elif data == "adm_add_admin":
            ADMIN_MODE[uid] = "adm_add_admin"
            await call.message.answer("➕ Enter user ID to add as admin:")
            await call.answer()

        elif data == "adm_remove_admin":
            ADMIN_MODE[uid] = "adm_remove_admin"
            await call.message.answer("➖ Enter user ID to remove from admin:")
            await call.answer()

        elif data == "adm_add_vip":
            ADMIN_MODE[uid] = "adm_add_vip"
            await call.message.answer("💎 Enter user ID to add VIP:")
            await call.answer()

        elif data == "adm_remove_vip":
            ADMIN_MODE[uid] = "adm_remove_vip"
            await call.message.answer("❌ Enter user ID to remove VIP:")
            await call.answer()

        elif data == "adm_set_limit":
            ADMIN_MODE[uid] = "adm_set_limit"
            await call.message.answer("🎯 Enter: uid limit\nExample: 123456789 5")
            await call.answer()

        elif data == "adm_set_per_req":
            ADMIN_MODE[uid] = "adm_set_per_req"
            await call.message.answer(f"🔢 Enter numbers per request (1-10)\nCurrent: {d.get('per_req', config.DEFAULT_NUMBERS_PER_REQ)}")
            await call.answer()

        elif data == "adm_bulk_add":
            d.setdefault("upload_mode", {})[str(uid)] = "adm_bulk_add"
            save_data(d)
            await call.message.answer("📥 Send a .txt file\nFile name = country name")
            await call.answer()

        elif data == "adm_bulk_remove":
            countries = get_countries()
            if not countries:
                return await call.answer("No countries!", show_alert=True)
            rows = []
            for c in countries:
                rows.append([InlineKeyboardButton(
                    text=f"🗑 {get_flag(c[0])} {c[0]} ({c[1]})",
                    callback_data=f"do_remove_{c[0]}"
                )])
            rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cancel")])
            await call.message.answer("📤 Select country to remove:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
            await call.answer()

        elif data.startswith("do_remove_"):
            country = data.replace("do_remove_", "")
            path = Path(config.NUMBER_DIR)
            removed = False
            for f in path.glob("*.txt"):
                if clean_country_name(f.stem).lower() == country.lower() or f.stem == country:
                    f.unlink()
                    removed = True
                    break
            if removed:
                await call.message.edit_text(f"✅ Removed: <b>{country}</b>", parse_mode=ParseMode.HTML)
            else:
                await call.answer("❌ Not found!", show_alert=True)

        elif data == "adm_cancel":
            await call.message.edit_text("❌ Cancelled.")
            await call.answer()

        elif data == "adm_clean":
            total_removed = 0
            for country, _ in get_countries():
                path = Path(config.NUMBER_DIR) / f"{country}.txt"
                numbers = get_numbers(country)
                unique = list(dict.fromkeys(numbers))
                removed = len(numbers) - len(unique)
                total_removed += removed
                path.write_text("\n".join(unique))
            await call.message.answer(f"🗑 Cleaned! Removed <b>{total_removed}</b> duplicates.", parse_mode=ParseMode.HTML)
            await call.answer()

        elif data == "adm_lock_country":
            countries = get_countries()
            ADMIN_MODE[uid] = "adm_lock_country"
            clist = "\n".join([f"• {c[0]}" for c in countries])
            await call.message.answer(f"🔒 Enter country name to lock:\n\n{clist}")
            await call.answer()

        elif data == "adm_unlock_country":
            locked = d.get("locked_countries", [])
            ADMIN_MODE[uid] = "adm_unlock_country"
            clist = "\n".join([f"• {c}" for c in locked]) or "None"
            await call.message.answer(f"🔓 Enter country name to unlock:\n\n{clist}")
            await call.answer()

        elif data == "adm_support":
            msgs = d.get("support_msgs", {})
            if not msgs:
                await call.message.answer("📩 No support messages.")
                return await call.answer()
            for uid_s, info in list(msgs.items())[-10:]:
                await call.message.answer(
                    f"📩 <b>Support</b>\n"
                    f"👤 {info.get('name','')} (<code>{uid_s}</code>)\n"
                    f"🕐 {info.get('time','')}\n\n"
                    f"{info.get('msg','')}\n\n"
                    f"Reply: /reply {uid_s} your_message",
                    parse_mode=ParseMode.HTML
                )
            await call.answer()

        elif data == "adm_all_users":
            users = d.get("users", {})
            vip_list = d.get("vip", [])
            banned_list = d.get("banned", [])
            lines = []
            for uid_s, u in list(users.items())[-30:]:
                icon = "💎" if uid_s in vip_list else ("🚫" if uid_s in banned_list else "👤")
                name = u.get("name", "")
                lines.append(f"{icon} <code>{uid_s}</code> {name}")
            await call.message.answer(
                f"👤 <b>All Users</b> ({len(users)} total)\n\n" + "\n".join(lines),
                parse_mode=ParseMode.HTML
            )
            await call.answer()

        elif data == "adm_user_details":
            ADMIN_MODE[uid] = "adm_user_details"
            await call.message.answer("👥 Enter user ID:")
            await call.answer()

        else:
            await call.answer()
    else:
        await call.answer()

# ═══════════════════════════════════════════════
#               🚀 MAIN
# ═══════════════════════════════════════════════
async def main():
    logger.info("🤖 CodeGate Number Bot starting...")
    Path(config.NUMBER_DIR).mkdir(exist_ok=True)
    Path(config.SEEN_DIR).mkdir(exist_ok=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
