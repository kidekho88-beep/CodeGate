import os
import asyncio
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    CopyTextButton
)
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

NUMBER_DIR = "numbers"

# ================= START =================

@dp.message(Command("start"))
async def start(message: Message):

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Get Number")],
            [KeyboardButton(text="🌍 Country")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Welcome",
        reply_markup=kb
    )

# ================= COUNTRY =================

def country_keyboard():

    buttons = []

    for f in os.listdir(NUMBER_DIR):

        if not f.endswith(".txt"):
            continue

        country = f.replace(".txt","")

        buttons.append(
            InlineKeyboardButton(
                text=country,
                callback_data=f"country_{country}"
            )
        )

    rows = [buttons[i:i+3] for i in range(0,len(buttons),3)]

    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(F.text == "📱 Get Number")
async def get_country(message: Message):

    await message.answer(
        "Select Country",
        reply_markup=country_keyboard()
    )

# ================= COUNTRY SELECT =================

@dp.callback_query(F.data.startswith("country_"))
async def country_select(call: CallbackQuery):

    country = call.data.replace("country_","")

    path = f"{NUMBER_DIR}/{country}.txt"

    if not os.path.exists(path):

        await call.answer("No numbers")
        return

    with open(path) as f:
        numbers = [x.strip() for x in f if x.strip()]

    if not numbers:

        await call.answer("Empty")
        return

    selected = random.sample(numbers,min(3,len(numbers)))

    rows = []

    for n in selected:

        rows.append([
            InlineKeyboardButton(
                text=n,
                copy_text=CopyTextButton(text=n)
            )
        ])

    rows.append([InlineKeyboardButton(text="Refresh",callback_data=f"country_{country}")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await call.message.edit_text(
        f"{country} numbers",
        reply_markup=kb
    )

# ================= ADMIN =================

ADMINS = [6260167422]

@dp.message(Command("admin"))
async def admin(message: Message):

    if message.from_user.id not in ADMINS:
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Status",callback_data="status")]
        ]
    )

    await message.answer("Admin panel",reply_markup=kb)

@dp.callback_query(F.data=="status")
async def status(call: CallbackQuery):

    await call.message.edit_text("Bot running")

# ================= RUN =================

async def main():

    print("Bot started")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())