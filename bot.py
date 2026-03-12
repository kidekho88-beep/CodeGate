import os, random, time, json, asyncio, unicodedata, re
from aiohttp import web
from datetime import datetime, date
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
import config

# ═══════════════════════════════════════════════
#               GLOBALS
# ═══════════════════════════════════════════════
USERS       = set()
ADMINS      = set(config.ADMIN_IDS)
BANNED      = set()
USER_STATS  = {}
USER_LAST_NUMBERS  = {}   # uid → [numbers]
USER_LAST_ACTIVE   = {}
USER_DAILY_COUNT   = {}   # uid → {"date": "2026-03-12", "count": 3}
USER_DAILY_LIMIT   = {}   # uid → int (custom limit)
SUPPORT_TICKETS    = {}   # uid → [{"msg": ..., "time": ...}]
ADMIN_MODE         = {}
UPLOAD_MODE        = {}
SUPPORT_REPLY_MODE = {}
WEBHOOK_SECRET     = "codegate_bridge_2026"
LOCKED_COUNTRIES   = set()   # countries requiring subscription
VIP_USERS          = set()   # users with subscription access
MUTED_USERS        = set()   # muted users
USER_WARNS         = {}       # uid → warn count
USER_INFO          = {}       # uid → {name, username, joined}

DATA_FILE      = "user_data.json"
DATABASE_FILE  = "database.json"

bot = Bot(token=config.BOT_TOKEN)
dp  = Dispatcher()

os.makedirs(config.NUMBER_DIR, exist_ok=True)
os.makedirs(config.SEEN_DIR,   exist_ok=True)

# ═══════════════════════════════════════════════
#               DATA
# ═══════════════════════════════════════════════
def save_user_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "USER_STATS": USER_STATS,
            "USER_LAST_NUMBERS": USER_LAST_NUMBERS,
            "USER_LAST_ACTIVE": USER_LAST_ACTIVE,
            "USER_DAILY_COUNT": USER_DAILY_COUNT,
            "USER_DAILY_LIMIT": USER_DAILY_LIMIT,
            "BANNED": list(BANNED),
            "ADMINS": list(ADMINS),
            "SUPPORT_TICKETS": SUPPORT_TICKETS,
        }, f, indent=2)

def load_user_data():
    global USER_STATS, USER_LAST_NUMBERS, USER_LAST_ACTIVE
    global USER_DAILY_COUNT, USER_DAILY_LIMIT, SUPPORT_TICKETS
    if not os.path.exists(DATA_FILE):
        return
    with open(DATA_FILE) as f:
        data = json.load(f)
    USER_STATS         = data.get("USER_STATS", {})
    USER_LAST_NUMBERS  = data.get("USER_LAST_NUMBERS", {})
    USER_LAST_ACTIVE   = data.get("USER_LAST_ACTIVE", {})
    USER_DAILY_COUNT   = data.get("USER_DAILY_COUNT", {})
    USER_DAILY_LIMIT   = data.get("USER_DAILY_LIMIT", {})
    SUPPORT_TICKETS    = data.get("SUPPORT_TICKETS", {})
    for uid in data.get("BANNED", []): BANNED.add(uid)
    for uid in data.get("ADMINS", []): ADMINS.add(uid)
    for c in data.get("LOCKED_COUNTRIES", []): LOCKED_COUNTRIES.add(c)
    for u in data.get("VIP_USERS", []): VIP_USERS.add(u)
    for u in data.get("MUTED_USERS", []): MUTED_USERS.add(u)
    global USER_WARNS, USER_INFO
    USER_WARNS = data.get("USER_WARNS", {})
    USER_INFO  = data.get("USER_INFO", {})

# ═══════════════════════════════════════════════
#               NUMBER UTILS
# ═══════════════════════════════════════════════
def decode_country(fname):
    """#L01f1ff#L01f1fc → proper emoji display"""
    import re
    def replace_code(m):
        try: return chr(int(m.group(1), 16))
        except: return m.group(0)
    return re.sub(r'#L0(1[0-9a-fA-F]{4})', replace_code, fname)

def get_countries():
    return [f.replace(".txt","") for f in os.listdir(config.NUMBER_DIR)
            if f.endswith(".txt") and not f.endswith("_Backup.txt")]

def display_country(c):
    """Show proper emoji name for country"""
    return decode_country(c)

def get_numbers(country):
    path = f"{config.NUMBER_DIR}/{country}.txt"
    if not os.path.exists(path): return []
    with open(path) as f:
        return [x.strip() for x in f if x.strip()]

def get_global_seen(country):
    path = f"{config.SEEN_DIR}/global_{country}.txt"
    if not os.path.exists(path): return set()
    with open(path) as f:
        return set(x.strip() for x in f)

def add_global_seen(country, numbers):
    path = f"{config.SEEN_DIR}/global_{country}.txt"
    with open(path,"a") as f:
        for n in numbers: f.write(n+"\n")

def remove_from_seen(country, numbers):
    path = f"{config.SEEN_DIR}/global_{country}.txt"
    if not os.path.exists(path): return
    seen = get_global_seen(country)
    seen -= set(numbers)
    with open(path,"w") as f:
        for n in seen: f.write(n+"\n")

def remove_duplicates(country):
    nums = list(dict.fromkeys(get_numbers(country)))
    with open(f"{config.NUMBER_DIR}/{country}.txt","w") as f:
        f.write("\n".join(nums))
    return len(nums)

def cleanup_seen():
    now = time.time()
    for fname in os.listdir(config.SEEN_DIR):
        path = os.path.join(config.SEEN_DIR, fname)
        if os.path.isfile(path) and now - os.path.getmtime(path) > config.CLEANUP_DAYS * 86400:
            os.remove(path)

PREFIX_FLAGS = {
    "880":"🇧🇩","84":"🇻🇳","1":"🇺🇸","44":"🇬🇧","91":"🇮🇳",
    "263":"🇿🇼","234":"🇳🇬","254":"🇰🇪","27":"🇿🇦","62":"🇮🇩",
    "60":"🇲🇾","66":"🇹🇭","63":"🇵🇭","92":"🇵🇰","98":"🇮🇷",
    "7":"🇷🇺","86":"🇨🇳","81":"🇯🇵","82":"🇰🇷","55":"🇧🇷",
    "52":"🇲🇽","33":"🇫🇷","49":"🇩🇪","39":"🇮🇹","34":"🇪🇸",
    "20":"🇪🇬","212":"🇲🇦","213":"🇩🇿","216":"🇹🇳","237":"🇨🇲",
    "233":"🇬🇭","256":"🇺🇬","255":"🇹🇿","251":"🇪🇹","243":"🇨🇩",
    "966":"🇸🇦","971":"🇦🇪","965":"🇰🇼","964":"🇮🇶","962":"🇯🇴",
    "90":"🇹🇷","48":"🇵🇱","380":"🇺🇦","994":"🇦🇿","995":"🇬🇪",
    "996":"🇰🇬","998":"🇺🇿","977":"🇳🇵","94":"🇱🇰","95":"🇲🇲",
    "855":"🇰🇭","856":"🇱🇦","673":"🇧🇳","65":"🇸🇬","886":"🇹🇼",
    "852":"🇭🇰","853":"🇲🇴","976":"🇲🇳","961":"🇱🇧","972":"🇮🇱",
}

def number_to_flag(number: str) -> str:
    clean = re.sub(r"\D", "", number)
    for prefix, flag in sorted(PREFIX_FLAGS.items(), key=lambda x: -len(x[0])):
        if clean.startswith(prefix):
            return flag
    return "📱"

def get_flag(country_name):
    flag = ""
    for ch in country_name:
        if unicodedata.category(ch) in ("So","Sm") or ord(ch) > 127:
            flag += ch
    return flag.strip()

def get_user_limit(uid):
    return USER_DAILY_LIMIT.get(str(uid), config.DEFAULT_DAILY_LIMIT)

def check_daily_limit(uid):
    uid = str(uid)
    today = str(date.today())
    info = USER_DAILY_COUNT.get(uid, {"date": today, "count": 0})
    if info["date"] != today:
        info = {"date": today, "count": 0}
    return info["count"], get_user_limit(uid)

def increment_daily(uid, count):
    uid = str(uid)
    today = str(date.today())
    info = USER_DAILY_COUNT.get(uid, {"date": today, "count": 0})
    if info["date"] != today:
        info = {"date": today, "count": 0}
    info["count"] += count
    USER_DAILY_COUNT[uid] = info
    save_user_data()

def track_activity(uid, country, count, numbers=None):
    uid = str(uid)
    if uid not in USER_STATS:
        USER_STATS[uid] = {"total": 0, "countries": {}, "joined": str(datetime.now())[:19]}
    USER_STATS[uid]["total"] += count
    USER_STATS[uid]["countries"][country] = USER_STATS[uid]["countries"].get(country, 0) + count
    if numbers:
        USER_LAST_NUMBERS[uid] = numbers
    USER_LAST_ACTIVE[uid] = str(datetime.now())[:19]
    save_user_data()

# ═══════════════════════════════════════════════
#               KEYBOARDS
# ═══════════════════════════════════════════════
def user_keyboard(uid):
    is_adm = uid in ADMINS
    rows = [
        [KeyboardButton(text="📱 Get Number"),    KeyboardButton(text="📦 Available Country")],
        [KeyboardButton(text="☎️ Support")],
    ]
    if is_adm:
        rows.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def country_keyboard(uid=None, show_empty=False):
    countries = get_countries()
    buttons = []
    for c in countries:
        remaining = len(set(get_numbers(c)) - get_global_seen(c))
        if remaining == 0 and not show_empty:
            continue
        is_locked = c in LOCKED_COUNTRIES
        is_vip = uid and (int(uid) in VIP_USERS or int(uid) in ADMINS)
        if is_locked and not is_vip:
            label = f"{display_country(c)} 💲"
            cb = f"locked_{c}"
        else:
            label = f"{display_country(c)} ({remaining})"
            cb = f"country_{c}"
        buttons.append(InlineKeyboardButton(text=label, callback_data=cb))
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    if not buttons:
        rows = [[InlineKeyboardButton(text="❌ No numbers available", callback_data="back_to_start")]]
    rows.append([InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_countries")])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def numbers_keyboard(country, selected):
    flag = get_flag(country)
    rows = []
    for n in selected:
        clean = n.strip().replace("+","")
        rows.append([InlineKeyboardButton(
            text=f"{flag}  {clean}",
            copy_text=CopyTextButton(text="+"+clean)
        )])
    rows.append([
        InlineKeyboardButton(text="🔄 Change Numbers", callback_data=f"refresh_{country}"),
        InlineKeyboardButton(text="🌍 Change Country",  callback_data="back_to_countries"),
    ])
    rows.append([
        InlineKeyboardButton(text="📲 OTP Group", url=config.OTP_GROUP_LINK),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 User Details",    callback_data="adm_user_details"),
         InlineKeyboardButton(text="🔍 Check OTP",       callback_data="adm_check_otp")],
        [InlineKeyboardButton(text="📊 Live Traffic",    callback_data="adm_traffic"),
         InlineKeyboardButton(text="📢 Broadcast",       callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="🎯 Set User Limit",  callback_data="adm_set_limit"),
         InlineKeyboardButton(text="🔢 Num/Request",     callback_data="adm_set_per_req")],
        [InlineKeyboardButton(text="📥 Add Numbers",     callback_data="adm_bulk_add"),
         InlineKeyboardButton(text="📤 Remove Numbers",  callback_data="adm_bulk_remove")],
        [InlineKeyboardButton(text="🗑 Clean Dupes",     callback_data="adm_clean"),
         InlineKeyboardButton(text="🚫 Ban User",        callback_data="adm_ban")],
        [InlineKeyboardButton(text="✅ Unban",           callback_data="adm_unban"),
         InlineKeyboardButton(text="➕ Add Admin",       callback_data="adm_add_admin")],
        [InlineKeyboardButton(text="➖ Remove Admin",    callback_data="adm_remove_admin"),
         InlineKeyboardButton(text="📩 Support Check",   callback_data="adm_support")],
        [InlineKeyboardButton(text="👤 All Users",       callback_data="adm_all_users")],
        [InlineKeyboardButton(text="🔒 Lock Country",    callback_data="adm_lock_country"),
         InlineKeyboardButton(text="🔓 Unlock Country",  callback_data="adm_unlock_country")],
        [InlineKeyboardButton(text="💎 Add VIP User",    callback_data="adm_add_vip"),
         InlineKeyboardButton(text="❌ Remove VIP",      callback_data="adm_remove_vip")],
    ])

# ═══════════════════════════════════════════════
#               HANDLERS — USER
# ═══════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    if uid in BANNED: return
    if uid in MUTED_USERS:
        return await message.answer("🔇 You are muted. Contact support.")
    USERS.add(uid)
    uid_str = str(uid)
    fname = message.from_user.first_name or ""
    lname = message.from_user.last_name or ""
    uname = message.from_user.username or ""
    if uid_str not in USER_STATS:
        USER_STATS[uid_str] = {"total":0,"countries":{},"joined":str(datetime.now())[:19]}
    # Always update user info
    USER_INFO[uid_str] = {
        "name": fname,
        "surname": lname,
        "username": uname,
        "joined": USER_INFO.get(uid_str, {}).get("joined", str(datetime.now())[:19])
    }
    save_user_data()
    line = "━"*22
    fname = message.from_user.first_name or "User"
    await message.answer(
        f"👋 <b>Welcome, {fname}!</b>\n{line}\n\n"
        f"⭐ This bot provides virtual phone numbers for verification.\n\n"
        f"📚 <b>Available Features:</b>\n"
        f"📱 Get Number — Get a virtual number\n"
        f"📦 Available Country — See available countries\n"
        f"🔍 OTP Check — Check if OTP arrived\n"
        f"📅 Today OTP — View your numbers & OTPs\n"
        f"🌍 Live Traffic — Real-time OTP stats\n"
        f"☎️ Support — Contact for help\n\n"
        f"📲 <b>Join our OTP Group for better service!</b>\n"
        f"👉 {config.OTP_GROUP_LINK}\n{line}",
        parse_mode="HTML",
        reply_markup=user_keyboard(uid)
    )

@dp.message(F.text == "📱 Get Number")
async def handle_get_number(message: Message):
    uid = message.from_user.id
    if uid in BANNED: return
    if uid in MUTED_USERS: return await message.answer("🔇 You are muted. Contact support.")
    await message.answer("🌍 <b>Select a Country:</b>", parse_mode="HTML", reply_markup=country_keyboard(uid=message.from_user.id))

@dp.message(F.text == "📦 Available Country")
async def handle_available(message: Message):
    if message.from_user.id in BANNED: return
    await message.answer("🌍 <b>Select a Country:</b>", parse_mode="HTML", reply_markup=country_keyboard(uid=message.from_user.id))


@dp.message(F.text == "☎️ Support")
async def handle_support(message: Message):
    uid = message.from_user.id
    if uid in BANNED: return
    ADMIN_MODE[uid] = "support_msg"
    await message.answer(
        "☎️ <b>Support</b>\n\nWrite your message and we'll get back to you:",
        parse_mode="HTML"
    )

@dp.message(F.text == "⚙️ Admin Panel")
async def handle_admin_panel(message: Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔ No permission.")
    await message.answer("⚙️ <b>Admin Panel</b>", parse_mode="HTML", reply_markup=admin_keyboard())

@dp.message(Command("support"))
async def cmd_support(message: Message):
    if message.from_user.id not in ADMINS: return
    if not SUPPORT_TICKETS:
        return await message.answer("📭 No support messages.")
    lines = []
    for uid, tickets in SUPPORT_TICKETS.items():
        for t in tickets[-2:]:
            lines.append(f"👤 UID: <code>{uid}</code>\n🕐 {t['time']}\n💬 {t['msg']}")
    await message.answer(
        f"📩 <b>Support Messages ({len(SUPPORT_TICKETS)} users):</b>\n\n" + "\n\n".join(lines[-10:]),
        parse_mode="HTML"
    )
    await message.answer("To reply: /reply {uid} {message}")

@dp.message(Command("reply"))
async def cmd_reply(message: Message):
    if message.from_user.id not in ADMINS: return
    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        return await message.answer("Usage: /reply {uid} {message}")
    target_uid, reply_text = parts[1], parts[2]
    try:
        await bot.send_message(int(target_uid),
            f"📩 <b>Support Reply</b>\n"
            f"{'─'*28}\n\n"
            f"{reply_text}\n\n"
            f"{'─'*28}\n"
            f"<i>— CodeGate Support Team</i>",
            parse_mode="HTML")
        await message.answer(
            f"✅ Reply sent to <code>{target_uid}</code>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Failed: {e}")

# ═══════════════════════════════════════════════
#               TEXT HANDLER
# ═══════════════════════════════════════════════
@dp.message(F.text)
async def handle_text(message: Message):
    uid  = message.from_user.id
    text = message.text.strip()

    # Admin mode
    if uid in ADMINS:
        mode = ADMIN_MODE.get(uid)
        if mode == "broadcast":
            sent = 0
            failed = 0
            all_users = set(int(u) for u in USER_STATS.keys()) | USERS
            total = len(all_users)
            await message.answer(f"📤 Sending to <b>{total}</b> users...", parse_mode="HTML")
            for u in all_users:
                try:
                    await bot.send_message(int(u), text, parse_mode="HTML")
                    sent += 1
                except Exception as ex:
                    failed += 1
                await asyncio.sleep(0.05)
            await message.answer(
                f"✅ <b>Broadcast Complete</b>\n\n"
                f"📤 Sent: <b>{sent}</b>\n"
                f"❌ Failed: <b>{failed}</b>",
                parse_mode="HTML")
            ADMIN_MODE.pop(uid, None)
            return

        elif mode == "adm_user_details":
            target = re.sub(r"\D","", text)
            if not target:
                await message.answer("❌ Invalid ID")
                ADMIN_MODE.pop(uid, None)
                return
            uid_s = str(target)
            stats   = USER_STATS.get(uid_s, {})
            info    = USER_INFO.get(uid_s, {})
            numbers = USER_LAST_NUMBERS.get(uid_s, [])
            countries = stats.get("countries", {})
            top_c   = max(countries, key=countries.get) if countries else "None"
            warns   = USER_WARNS.get(uid_s, 0)
            is_vip  = int(target) in VIP_USERS
            is_muted= int(target) in MUTED_USERS
            is_banned= int(target) in BANNED
            status  = "🚫 Banned" if is_banned else ("🔇 Muted" if is_muted else ("💎 VIP" if is_vip else "👤 Member"))
            name    = info.get("name","?")
            surname = info.get("surname","")
            uname   = info.get("username","")
            joined  = info.get("joined", stats.get("joined","?"))
            last_act= USER_LAST_ACTIVE.get(uid_s,"?")
            total   = stats.get("total", 0)

            await message.answer(
                f"👤 <b>User Details</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 ID: <code>{target}</code>\n"
                f"👤 Name: {name} {surname}\n"
                f"🌐 Username: @{uname}\n"
                f"👁 Status: {status}\n"
                f"⚠️ Warns: {warns}/3\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 Joined: {joined}\n"
                f"🕐 Last Active: {last_act}\n"
                f"📱 Total Numbers: {total}\n"
                f"🌍 Top Country: {display_country(top_c) if top_c != 'None' else 'None'}\n"
                f"📋 Last Numbers: {chr(10).join(numbers[-3:]) or 'None'}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⚠️ Warn", callback_data=f"warn_{target}"),
                     InlineKeyboardButton(text="🔇 Mute", callback_data=f"mute_{target}")],
                    [InlineKeyboardButton(text="🚫 Ban",  callback_data=f"ban_{target}"),
                     InlineKeyboardButton(text="📋 Permissions", callback_data=f"perms_{target}")],
                ])
            )
            ADMIN_MODE.pop(uid, None)
            return

        elif mode == "adm_set_limit":
            parts = text.split()
            if len(parts) == 2 and parts[1].isdigit():
                USER_DAILY_LIMIT[parts[0]] = int(parts[1])
                save_user_data()
                await message.answer(f"✅ Limit set: UID {parts[0]} → {parts[1]}/day")
            else:
                await message.answer("Usage: {uid} {limit}\nExample: 6260167422 20")
            ADMIN_MODE.pop(uid, None)
            return

        elif mode == "adm_set_per_req":
            if text.isdigit() and 1 <= int(text) <= 10:
                config.DEFAULT_NUMBERS_PER_REQ = int(text)
                await message.answer(f"✅ Numbers per request set to <b>{text}</b>", parse_mode="HTML")
            else:
                await message.answer("❌ Enter a number between 1-10")
            ADMIN_MODE.pop(uid, None)
            return



        elif mode == "adm_add_vip":
            VIP_USERS.add(int(text)); save_user_data()
            await message.answer(f"💎 VIP access granted to: <code>{text}</code>", parse_mode="HTML")
            ADMIN_MODE.pop(uid, None)
            return

        elif mode == "adm_remove_vip":
            VIP_USERS.discard(int(text)); save_user_data()
            await message.answer(f"❌ VIP access removed from: <code>{text}</code>", parse_mode="HTML")
            ADMIN_MODE.pop(uid, None)
            return

        elif mode == "adm_ban":
            BANNED.add(int(text)); save_user_data()
            await message.answer(f"🚫 Banned: <code>{text}</code>", parse_mode="HTML")
            ADMIN_MODE.pop(uid, None)
            return

        elif mode == "adm_unban":
            BANNED.discard(int(text)); save_user_data()
            await message.answer(f"✅ Unbanned: <code>{text}</code>", parse_mode="HTML")
            ADMIN_MODE.pop(uid, None)
            return

        elif mode == "adm_add_admin":
            ADMINS.add(int(text)); save_user_data()
            await message.answer(f"✅ Admin added: <code>{text}</code>", parse_mode="HTML")
            ADMIN_MODE.pop(uid, None)
            return

        elif mode == "adm_remove_admin":
            ADMINS.discard(int(text)); save_user_data()
            await message.answer(f"🗑 Admin removed: <code>{text}</code>", parse_mode="HTML")
            ADMIN_MODE.pop(uid, None)
            return

    # Support message from user
    mode = ADMIN_MODE.get(uid)
    if mode == "support_msg":
        uid_str = str(uid)
        if uid_str not in SUPPORT_TICKETS:
            SUPPORT_TICKETS[uid_str] = []
        SUPPORT_TICKETS[uid_str].append({"msg": text, "time": str(datetime.now())[:19]})
        save_user_data()
        # Forward to all admins
        uname = message.from_user.username or "no username"
        fname_u = message.from_user.first_name or ""
        for adm in config.ADMIN_IDS:
            try:
                await bot.send_message(int(adm),
                    f"📩 <b>New Support Ticket</b>\n"
                    f"{'─'*28}\n"
                    f"👤 User: <a href='tg://user?id={uid}'>{fname_u}</a> (@{uname})\n"
                    f"🆔 UID: <code>{uid}</code>\n"
                    f"🕐 Time: {str(datetime.now())[:19]}\n"
                    f"{'─'*28}\n"
                    f"💬 <b>Message:</b>\n{text}\n"
                    f"{'─'*28}\n"
                    f"✏️ /reply {uid} your_message",
                    parse_mode="HTML")
            except Exception as e:
                print(f"Support forward error: {e}")
        await message.answer(
            f"✅ <b>Message Received!</b>\n"
            f"{'─'*28}\n"
            f"Thank you for contacting support.\n"
            f"Our team will get back to you shortly. 🙏\n"
            f"{'─'*28}\n"
            f"<i>CodeGate Support Team</i>",
            parse_mode="HTML")
        ADMIN_MODE.pop(uid, None)
        return

# ═══════════════════════════════════════════════
#               WEBHOOK — OTP NOTIFY FROM OTP BOTS
# ═══════════════════════════════════════════════
async def handle_callback(call: CallbackQuery):
    uid  = call.from_user.id
    data = call.data
    cleanup_seen()

    if data == "back_to_start":
        USERS.add(uid)
        line = "━"*22
        await call.message.edit_text(
            f"✨ <b>Welcome to CodeGate Number Bot!</b>\n{line}\n\n💡 Get virtual numbers instantly.",
            parse_mode="HTML"
        )

    elif data == "refresh_countries":
        await call.message.edit_text("🌍 <b>Select a Country:</b>", parse_mode="HTML", reply_markup=country_keyboard(uid=call.from_user.id))

    elif data in ("back_to_countries",):
        await call.message.edit_text("🌍 <b>Select a Country:</b>", parse_mode="HTML", reply_markup=country_keyboard(uid=call.from_user.id))

    elif data == "refresh_traffic":
        await send_live_traffic(uid, call=call)
        await call.answer("🔄 Refreshed!")
        return



    elif data.startswith("locked_"):
        country = data.replace("locked_","")
        await call.answer("🔒 Subscription Required", show_alert=False)
        await call.message.answer(
            f"❌ <b>No Active Subscription.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Get Subscription", url="https://t.me/codegatex")],
            ])
        )
        return

    elif data.startswith("country_"):
        await show_numbers(call, data.replace("country_",""))

    elif data.startswith("refresh_"):
        await show_numbers(call, data.replace("refresh_",""))

    elif data == "today_otp":
        uid_str = str(uid)
        numbers = USER_LAST_NUMBERS.get(uid_str, [])
        if not numbers:
            await call.answer("No numbers taken yet!", show_alert=True)
            return
        lines = []
        for n in numbers:
            status = "✅ Done"
            lines.append(f"📱 <code>{n}</code> — {status}")
        await call.message.answer("\n".join(lines), parse_mode="HTML")
        await call.answer()

    # ── Admin callbacks ──
    elif uid in ADMINS:
        if data == "adm_user_details":
            ADMIN_MODE[uid] = "adm_user_details"
            await call.message.answer("👤 Enter User ID:")

        elif data == "adm_check_otp":
            ADMIN_MODE[uid] = "adm_check_otp"
            await call.message.answer("🔍 Paste the number to check OTP status:")

        elif data == "adm_traffic":
            lines = []
            for c in get_countries():
                total  = len(get_numbers(c))
                seen   = len(get_global_seen(c))
                avail  = max(0, total - seen)
                lines.append(
                    f"🌐 <b>{display_country(c)}</b>\n"
                    f"   📦 Total: {total} | 🔓 Available: <b>{avail}</b> | 📤 Used: {min(seen,total)}"
                )
            await call.message.answer("\n\n".join(lines) or "No data.", parse_mode="HTML")

        elif data == "adm_broadcast":
            ADMIN_MODE[uid] = "broadcast"
            await call.message.answer("📢 Send broadcast text:")

        elif data == "adm_set_limit":
            ADMIN_MODE[uid] = "adm_set_limit"
            await call.message.answer("🎯 Enter: {uid} {daily_limit}\nExample: 6260167422 20")

        elif data == "adm_bulk_add":
            UPLOAD_MODE[uid] = "add"
            await call.message.answer("📥 Send a .txt file (filename = country name):")

        elif data == "adm_bulk_remove":
            kb = [[InlineKeyboardButton(text=f"❌ {display_country(c)}", callback_data=f"rm_country_{c}")] for c in get_countries()]
            kb.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")])
            await call.message.answer("📤 Select country to remove:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

        elif data.startswith("rm_country_"):
            country = data.replace("rm_country_","")
            nums = get_numbers(country)
            remove_from_seen(country, nums)
            open(f"{config.NUMBER_DIR}/{country}.txt","w").close()
            await call.message.answer(
                "✅ <b>Numbers Removed</b>\n\n🌍 Country: <b>" + display_country(country) + "</b>\n🗑 Removed: <b>" + str(len(nums)) + "</b> numbers",
                parse_mode="HTML")

        elif data == "adm_clean":
            cleaned = sum(remove_duplicates(c) for c in get_countries())
            await call.message.answer(f"✅ Cleaned. Total remaining: {cleaned}")

        elif data == "adm_ban":
            ADMIN_MODE[uid] = "adm_ban"
            await call.message.answer("🚫 Enter User ID to ban:")

        elif data == "adm_unban":
            ADMIN_MODE[uid] = "adm_unban"
            await call.message.answer("✅ Enter User ID to unban:")

        elif data == "adm_add_admin":
            ADMIN_MODE[uid] = "adm_add_admin"
            await call.message.answer("➕ Enter User ID to make admin:")

        elif data == "adm_remove_admin":
            ADMIN_MODE[uid] = "adm_remove_admin"
            await call.message.answer("➖ Enter User ID to remove admin:")

        elif data == "adm_support":
            if not SUPPORT_TICKETS:
                await call.message.answer("📭 No support messages.")
            else:
                lines = []
                for u, tickets in list(SUPPORT_TICKETS.items())[-10:]:
                    for t in tickets[-1:]:
                        lines.append(f"👤 <code>{u}</code> | {t['time']}\n💬 {t['msg']}")
                await call.message.answer(
                    "📩 <b>Support Panel:</b>\n\n" + "\n\n".join(lines) +
                    "\n\n✏️ Reply: /reply {uid} {message}",
                    parse_mode="HTML"
                )

        elif data == "adm_set_per_req":
            ADMIN_MODE[uid] = "adm_set_per_req"
            await call.message.answer(
                f"🔢 <b>Numbers per Request</b>\n\n"
                f"Current: <b>{config.DEFAULT_NUMBERS_PER_REQ}</b>\n\n"
                f"Enter new number (1-10):",
                parse_mode="HTML"
            )

        elif data == "adm_all_users":
            total = len(USERS)
            banned = len(BANNED)
            lines = []
            for u, stats in list(USER_STATS.items())[-15:]:
                last = USER_LAST_ACTIVE.get(u, "?")
                total_nums = stats.get("total", 0)
                vip = "💎" if int(u) in VIP_USERS else ""
                lines.append(f"{vip}👤 <code>{u}</code> | Nums: {total_nums} | Last: {last}")
            await call.message.answer(
                f"👥 <b>All Users</b>\nTotal: {total} | Banned: {banned}\n\n" +
                ("\n".join(lines) or "No users yet."),
                parse_mode="HTML"
            )

        elif data == "adm_lock_country":
            countries = get_countries()
            kb = [[InlineKeyboardButton(
                text=f"{'🔒' if c in LOCKED_COUNTRIES else '🌍'} {display_country(c)}",
                callback_data=f"toggle_lock_{c}"
            )] for c in countries]
            kb.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")])
            await call.message.answer(
                "🔒 <b>Lock/Unlock Countries</b>\n🔒 = Locked (💲) | 🌍 = Open\nClick to toggle:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
            )

        elif data == "adm_unlock_country":
            if not LOCKED_COUNTRIES:
                await call.message.answer("✅ No locked countries.")
            else:
                kb = [[InlineKeyboardButton(
                    text=f"🔓 {display_country(c)}",
                    callback_data=f"toggle_lock_{c}"
                )] for c in LOCKED_COUNTRIES]
                kb.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")])
                await call.message.answer(
                    "🔓 <b>Unlock a Country:</b>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                )

        elif data.startswith("toggle_lock_"):
            country = data.replace("toggle_lock_","")
            if country in LOCKED_COUNTRIES:
                LOCKED_COUNTRIES.discard(country)
                await call.message.answer(f"🔓 <b>{display_country(country)}</b> unlocked!", parse_mode="HTML")
            else:
                LOCKED_COUNTRIES.add(country)
                await call.message.answer(f"🔒 <b>{display_country(country)}</b> locked! Users need subscription.", parse_mode="HTML")
            save_user_data()

        elif data.startswith("warn_"):
            target = data.replace("warn_","")
            uid_s = str(target)
            USER_WARNS[uid_s] = USER_WARNS.get(uid_s, 0) + 1
            warns = USER_WARNS[uid_s]
            save_user_data()
            try:
                await bot.send_message(int(target),
                    f"⚠️ <b>Warning Issued</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"You have received a warning.\n"
                    f"Warns: <b>{warns}/3</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Reaching 3 warns will result in a ban.</i>",
                    parse_mode="HTML")
            except: pass
            if warns >= 3:
                BANNED.add(int(target))
                save_user_data()
                await call.message.answer(f"🚫 User <code>{target}</code> auto-banned after 3 warns!", parse_mode="HTML")
            else:
                await call.message.answer(f"⚠️ Warned <code>{target}</code> — Warns: {warns}/3", parse_mode="HTML")

        elif data.startswith("mute_"):
            target = data.replace("mute_","")
            if int(target) in MUTED_USERS:
                MUTED_USERS.discard(int(target))
                save_user_data()
                await call.message.answer(f"🔊 <code>{target}</code> unmuted!", parse_mode="HTML")
                try:
                    await bot.send_message(int(target), "🔊 <b>You have been unmuted.</b>", parse_mode="HTML")
                except: pass
            else:
                MUTED_USERS.add(int(target))
                save_user_data()
                await call.message.answer(f"🔇 <code>{target}</code> muted!", parse_mode="HTML")
                try:
                    await bot.send_message(int(target),
                        f"🔇 <b>You have been muted.</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"Contact support to appeal.",
                        parse_mode="HTML")
                except: pass

        elif data.startswith("ban_"):
            target = data.replace("ban_","")
            if int(target) in BANNED:
                BANNED.discard(int(target))
                save_user_data()
                await call.message.answer(f"✅ <code>{target}</code> unbanned!", parse_mode="HTML")
                try:
                    await bot.send_message(int(target), "✅ <b>You have been unbanned. Welcome back!</b>", parse_mode="HTML")
                except: pass
            else:
                BANNED.add(int(target))
                save_user_data()
                await call.message.answer(f"🚫 <code>{target}</code> banned!", parse_mode="HTML")
                try:
                    await bot.send_message(int(target),
                        f"🚫 <b>You have been banned.</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"Contact support to appeal.",
                        parse_mode="HTML")
                except: pass

        elif data.startswith("perms_"):
            target = data.replace("perms_","")
            uid_s = str(target)
            is_vip   = int(target) in VIP_USERS
            is_muted = int(target) in MUTED_USERS
            is_banned= int(target) in BANNED
            warns    = USER_WARNS.get(uid_s, 0)
            await call.message.answer(
                f"📋 <b>Permissions</b> — <code>{target}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 VIP: {'✅' if is_vip else '❌'}\n"
                f"🔇 Muted: {'✅' if is_muted else '❌'}\n"
                f"🚫 Banned: {'✅' if is_banned else '❌'}\n"
                f"⚠️ Warns: {warns}/3\n"
                f"━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"{'❌ Remove' if is_vip else '💎 Give'} VIP",
                                          callback_data=f"togglevip_{target}")],
                    [InlineKeyboardButton(text=f"{'🔊 Unmute' if is_muted else '🔇 Mute'}",
                                          callback_data=f"mute_{target}"),
                     InlineKeyboardButton(text=f"{'✅ Unban' if is_banned else '🚫 Ban'}",
                                          callback_data=f"ban_{target}")],
                    [InlineKeyboardButton(text="🗑 Reset Warns", callback_data=f"resetwarn_{target}")],
                ])
            )

        elif data.startswith("togglevip_"):
            target = data.replace("togglevip_","")
            if int(target) in VIP_USERS:
                VIP_USERS.discard(int(target))
                await call.message.answer(f"❌ VIP removed from <code>{target}</code>", parse_mode="HTML")
            else:
                VIP_USERS.add(int(target))
                await call.message.answer(f"💎 VIP granted to <code>{target}</code>", parse_mode="HTML")
            save_user_data()

        elif data.startswith("resetwarn_"):
            target = data.replace("resetwarn_","")
            USER_WARNS.pop(str(target), None)
            save_user_data()
            await call.message.answer(f"✅ Warns reset for <code>{target}</code>", parse_mode="HTML")

        elif data == "adm_add_vip":
            ADMIN_MODE[uid] = "adm_add_vip"
            await call.message.answer("💎 Enter User ID to give VIP/subscription access:")

        elif data == "adm_remove_vip":
            ADMIN_MODE[uid] = "adm_remove_vip"
            await call.message.answer("❌ Enter User ID to remove VIP access:")

        await call.answer()
    else:
        await call.answer()

# ═══════════════════════════════════════════════
#               SHOW NUMBERS
# ═══════════════════════════════════════════════
async def show_numbers(call: CallbackQuery, country: str):
    uid = call.from_user.id
    per_req = config.DEFAULT_NUMBERS_PER_REQ

    unseen = list(set(get_numbers(country)) - get_global_seen(country))
    if not unseen:
        await call.answer("❌ No numbers available for this country!", show_alert=True)
        return

    can_take = min(per_req, len(unseen))
    selected = random.sample(unseen, can_take)

    add_global_seen(country, selected)
    track_activity(uid, country, can_take, selected)

    save_user_data()

    await call.message.edit_text(
        f"⏳ <b>Waiting for OTP...</b>\n\n"
        f"👆 Click number to copy • You'll be notified on OTP arrival",
        parse_mode="HTML",
        reply_markup=numbers_keyboard(country, selected)
    )
    await call.answer()

# ═══════════════════════════════════════════════
#               FILE UPLOAD
# ═══════════════════════════════════════════════
@dp.message(F.document)
async def receive_file(message: Message):
    uid = message.from_user.id
    if uid not in ADMINS or uid not in UPLOAD_MODE: return
    mode = UPLOAD_MODE.get(uid)
    doc  = message.document
    try:
        file    = await bot.get_file(doc.file_id)
        content = await bot.download_file(file.file_path)
        numbers = [x.strip() for x in content.read().decode("utf-8","ignore").splitlines() if x.strip()]
        if not numbers:
            await message.answer("❌ File empty!")
            UPLOAD_MODE.pop(uid, None)
            return
        country = doc.file_name.replace(".txt","").strip()
        path    = f"{config.NUMBER_DIR}/{country}.txt"
        if mode == "add":
            with open(path,"a") as f: f.write("\n"+"\n".join(numbers))
            await message.answer(f"✅ Added <b>{len(numbers)}</b> numbers to <b>{country}</b>!", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Failed: {e}")
    UPLOAD_MODE.pop(uid, None)

# ═══════════════════════════════════════════════
#               MAIN
# ═══════════════════════════════════════════════
async def main():
    load_user_data()
    print("🤖 CodeGate Number Bot starting...")
    for adm in config.ADMIN_IDS:
        try:
            await bot.send_message(adm, "🤖 <b>CodeGate Number Bot Started ✅</b>", parse_mode="HTML")
        except: pass

    # Start webhook server
    app = web.Application()
    app.router.add_post("/otp", handle_otp_webhook)
    app.router.add_get("/health", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("🌐 Webhook server started on port 8080")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
v10
fix
