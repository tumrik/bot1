import asyncio
import os
from datetime import datetime

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart

TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = None


# ---------------- БД ----------------
async def init_db():
    global db
    db = await asyncpg.create_pool(DB_URL)

    async with db.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            points INT DEFAULT 0,
            clicks INT DEFAULT 0,
            refs INT DEFAULT 0,
            reg_date TEXT
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id SERIAL PRIMARY KEY,
            name TEXT,
            reward INT
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS conversions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            offer_id INT,
            txid TEXT UNIQUE,
            reward INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)


async def get_user(uid):
    async with db.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id=$1", uid
        )

        if not user:
            await conn.execute("""
                INSERT INTO users(user_id, reg_date)
                VALUES($1, $2)
            """, uid, datetime.now().strftime("%Y-%m-%d"))

            return await get_user(uid)

        return user


async def get_offers():
    async with db.acquire() as conn:
        return await conn.fetch("SELECT * FROM offers")


# ---------------- START ----------------
@dp.message(CommandStart())
async def start(msg: Message):
    uid = msg.from_user.id

    await get_user(uid)

    offers = await get_offers()

    if not offers:
        await msg.answer("⚠️ Пока нет доступных офферов")
        return

    text = "💰 Доступные задания:\n\n"

    for offer in offers:
        link = f"https://your-offer.com?subid={uid}&offer_id={offer['id']}"
        text += f"{offer['name']} (+{offer['reward']})\n{link}\n\n"

    await msg.answer(text)


# ---------------- ПРОФИЛЬ ----------------
@dp.message(F.text == "/profile")
async def profile(msg: Message):
    user = await get_user(msg.from_user.id)

    await msg.answer(
        f"👤 Профиль\n\n"
        f"Баллы: {user['points']}\n"
        f"Клики: {user['clicks']}\n"
        f"Рефералы: {user['refs']}\n"
        f"Дата: {user['reg_date']}"
    )


# ---------------- СТАТИСТИКА ----------------
@dp.message(F.text == "/stats")
async def stats(msg: Message):
    async with db.acquire() as conn:

        total = await conn.fetchval("""
            SELECT SUM(reward) FROM conversions
        """)

        today = await conn.fetchval("""
            SELECT SUM(reward)
            FROM conversions
            WHERE created_at >= CURRENT_DATE
        """)

        count = await conn.fetchval("""
            SELECT COUNT(*) FROM conversions
        """)

    await msg.answer(
        f"📊 Статистика:\n\n"
        f"💰 Всего заработано: {total or 0}\n"
        f"📅 Сегодня: {today or 0}\n"
        f"🔢 Конверсий: {count}"
    )


# ---------------- POSTBACK ----------------
from fastapi import FastAPI, Request

app = FastAPI()

SECRET = os.getenv("POSTBACK_SECRET", "secret123")


@app.get("/postback")
async def postback(request: Request):
    data = dict(request.query_params)

    if data.get("key") != SECRET:
        return {"error": "unauthorized"}

    subid = data.get("subid")
    status = data.get("status")
    txid = data.get("txid")
    offer_id = data.get("offer_id")

    if not subid or not txid or status != "approved":
        return {"status": "ignored"}

    user_id = int(subid)
    offer_id = int(offer_id)

    async with db.acquire() as conn:

        # анти-дубликат
        exists = await conn.fetchrow(
            "SELECT * FROM conversions WHERE txid=$1", txid
        )

        if exists:
            return {"status": "duplicate"}

        offer = await conn.fetchrow(
            "SELECT * FROM offers WHERE id=$1", offer_id
        )

        if not offer:
            return {"error": "no offer"}

        reward = offer["reward"]

        await conn.execute("""
            INSERT INTO conversions(user_id, offer_id, txid, reward)
            VALUES($1, $2, $3, $4)
        """, user_id, offer_id, txid, reward)

        await conn.execute("""
            UPDATE users
            SET points = points + $1,
                clicks = clicks + 1
            WHERE user_id=$2
        """, reward, user_id)

    try:
        await bot.send_message(
            user_id,
            f"✅ +{reward} баллов начислено!"
        )
    except:
        pass

    return {"status": "ok"}


# ---------------- RUN ----------------
async def run_bot():
    await dp.start_polling(bot)


@app.on_event("startup")
async def startup():
    await init_db()
    asyncio.create_task(run_bot())
