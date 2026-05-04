import asyncio
import json
import os
import time
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

# 🔑 Токен
TOKEN = "8730730499:AAHD8XSd7DeFidMP1ogi5rJoUOY0erI0psg"

bot = Bot(token=TOKEN)
dp = Dispatcher()

DATA_FILE = "users.json"
COOLDOWN = 10

API_URL = "https://earnball.onrender.com"
SITE_URL = "https://tumrik.github.io/serverrr/"

CHANNELS = [
    {"id": -1003877994893, "link": "https://t.me/+Hs8CEusLEvc1YjYx"},
    {"id": -1003981236439, "link": "https://t.me/+-gBUqAHwj7I4Y2My"},
]

# 📁 Данные
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_user(user_id):
    data = load_data()
    user_id = str(user_id)

    if user_id not in data:
        data[user_id] = {"balance": 0, "last_claim": 0}
        save_data(data)

    return data[user_id]

def add_balance(user_id, amount):
    data = load_data()
    user_id = str(user_id)

    if user_id not in data:
        data[user_id] = {"balance": 0, "last_claim": 0}

    data[user_id]["balance"] += amount
    save_data(data)

def get_balance(user_id):
    return get_user(user_id)["balance"]

def set_last_claim(user_id):
    data = load_data()
    data[str(user_id)]["last_claim"] = time.time()
    save_data(data)

# 🔐 Подписка
async def check_sub(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel["id"], user_id)
            if member.status in ["left", "kicked"]:
                return False
        except:
            return False
    return True

def get_sub_keyboard():
    buttons = []

    for channel in CHANNELS:
        buttons.append([
            InlineKeyboardButton(text="📢 Подписаться", url=channel["link"])
        ])

    buttons.append([
        InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(callback):
    if await check_sub(callback.from_user.id):
        await callback.message.answer("✅ Подписка подтверждена!")
    else:
        await callback.message.answer("❌ Подпишись на все каналы!")

# 🧠 Клава
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Заработать балл")],
        [KeyboardButton(text="💳 Мой баланс")],
        [KeyboardButton(text="🛒 Магазин")]
    ],
    resize_keyboard=True
)

# 🚀 СТАРТ (с проверкой click_id)
@dp.message(Command("start"))
async def start(message: Message):
    args = message.text.split()

    # если пришёл с сайта
    if len(args) > 1:
        click_id = args[1]

        try:
            res = requests.get(f"{API_URL}/check/{click_id}").json()

            if res.get("valid"):
                requests.post(f"{API_URL}/use/{click_id}")

                add_balance(message.from_user.id, 1)
                set_last_claim(message.from_user.id)

                await message.answer("⭐ Балл начислен!")
            else:
                await message.answer("❌ Задание не засчитано")

        except:
            await message.answer("⚠️ Ошибка проверки")

    # обычный старт
    if not await check_sub(message.from_user.id):
        await message.answer("❗ Подпишись:", reply_markup=get_sub_keyboard())
        return

    get_user(message.from_user.id)

    await message.answer(
        "Привет! Зарабатывай баллы 👇",
        reply_markup=main_keyboard
    )

# 💰 Заработать
@dp.message(F.text == "💰 Заработать балл")
async def earn(message: Message):
    user = get_user(message.from_user.id)

    if not await check_sub(message.from_user.id):
        await message.answer("❗ Сначала подпишись!", reply_markup=get_sub_keyboard())
        return

    now = time.time()
    last = user.get("last_claim", 0)

    if now - last < COOLDOWN:
        wait = int(COOLDOWN - (now - last))
        await message.answer(f"⏳ Подожди {wait} сек")
        return

    click_id = f"{message.from_user.id}_{int(time.time())}"

    # создаём задание на сервере
    try:
        requests.post(f"{API_URL}/create_click", json={
            "click_id": click_id,
            "user_id": message.from_user.id
        })
    except:
        await message.answer("⚠️ Ошибка сервера")
        return

    task_link = f"{SITE_URL}?click_id={click_id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Перейти", url=task_link)]
    ])

    await message.answer("📋 Выполни задание:", reply_markup=kb)

# 💳 Баланс
@dp.message(F.text == "💳 Мой баланс")
async def balance(message: Message):
    if not await check_sub(message.from_user.id):
        await message.answer("❗ Сначала подпишись!", reply_markup=get_sub_keyboard())
        return

    bal = get_balance(message.from_user.id)
    await message.answer(f"💰 Баланс: {bal}")

# ▶️ Запуск
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())