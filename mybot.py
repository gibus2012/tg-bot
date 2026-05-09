import asyncio
import sqlite3
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from openai import AsyncOpenAI

# --- НАСТРОЙКИ ---
TOKEN = "7684953787:AAEcIMd1i9POTUPa7ZuIeejoYE70X3wAv7U"
OPENAI_KEY = "sk-zq9qY2WopXj3tsYpMLil7VV98RGlOm9M"
ADMIN_ID = 6760835730  # Ваш ID
CHANNEL_ID = -1003921488947 # ID канала для проверки подписки
CHANNEL_URL = "https://t.me/NorkaGpt"
CARD_NUMBER = "2202 2082 6287 3053"

# Если используете прокси, добавьте base_url
client = AsyncOpenAI(
    api_key=OPENAI_KEY, 
    base_url="https://api.proxy-provider.com/v1" # Ссылка от вашего прокси-сервиса
) 
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("bot_final.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 10,
        is_premium INTEGER DEFAULT 0,
        last_reset TEXT,
        history TEXT DEFAULT '[]',
        referrer_id INTEGER,
        ref_reward_given INTEGER DEFAULT 0,
        sub_reward_given INTEGER DEFAULT 0,
        img_today INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

def get_user(user_id, referrer_id=None):
    conn = sqlite3.connect("bot_final.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    today = datetime.now().strftime("%Y-%m-%d")

    if not user:
        cursor.execute("INSERT INTO users (user_id, last_reset, referrer_id) VALUES (?, ?, ?)", 
                       (user_id, today, referrer_id))
        conn.commit()
        return get_user(user_id)
    
    # СБРОС ЛИМИТОВ КАЖДЫЙ ДЕНЬ
    if user[3] != today:
        daily_balance = 50 if user[2] == 1 else 10
        cursor.execute("UPDATE users SET balance = ?, img_today = 0, last_reset = ? WHERE user_id = ?", 
                       (daily_balance, today, user_id))
        conn.commit()
        return get_user(user_id)

    conn.close()
    return user

def update_db(user_id, column, value):
    conn = sqlite3.connect("bot_final.db")
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

# --- ПРОВЕРКА ПОДПИСКИ ---
async def is_subscribed(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ["member", "administrator", "creator"]
    except: return False

# --- КЛАВИАТУРА ---
def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Баланс")
    kb.button(text="Очистить историю")
    kb.button(text="Купить Premium")
    kb.button(text="Помощь")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def start(message: types.Message, command: CommandObject):
    ref_id = int(command.args) if command.args and command.args.isdigit() else None
    get_user(message.from_user.id, ref_id)
    await message.answer(f"Привет! Твой ID: `{message.from_user.id}`. Напиши 'нарисуй или сгенерируй' или просто задай вопрос.", 
                         reply_markup=main_kb(), parse_mode="Markdown")

@dp.message(F.text == "Баланс")
async def balance(message: types.Message):
    user = get_user(message.from_user.id)
    status = "Premium 👑" if user[2] else "Бесплатный"
    await message.answer(f"📊 Статус: {status}\n💰 Запросы: {user[1]}\n🖼 Фото сегодня: {user[8]}/5")

@dp.message(F.text == "Купить Premium")
async def buy(message: types.Message):
    await message.answer(f"💳 Цена: 300 руб/мес\nЛимит: 50 зап/день + 5 фото.\nКарта: `{CARD_NUMBER}`\nПосле оплаты скинь скрин и ID администратору: @zilowu.")

@dp.message(Command("give_premium"))
async def adm(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    tid = int(message.text.split()[1])
    update_db(tid, "is_premium", 1)
    update_db(tid, "balance", 50)
    await message.answer("Готово")

@dp.message()
async def handle_all(message: types.Message):
    if not message.text: return
    user = get_user(message.from_user.id)
    text = message.text.lower()

    # Начисление за реферала (при первом сообщении)
    if user[6] == 0 and user[5]:
        inviter = get_user(user[5])
        update_db(inviter[0], "balance", inviter[1] + 3)
        update_db(user[0], "ref_reward_given", 1)
        try: await bot.send_message(inviter[0], "🎁 +3 запроса за друга!")
        except: pass

    # --- ЛОГИКА ГЕНЕРАЦИИ ФОТО ---
    if text.startswith("нарисуй") or text.startswith("сгенерируй"):
        if user[8] >= 5:
            return await message.answer("❌ Лимит 5 фото в день исчерпан.")
        if user[1] < 5:
            return await message.answer("❌ Нужно 5 запросов для фото.")
        
        prompt = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        if not prompt: return await message.answer("Что нарисовать?")
        
        m = await message.answer("🎨 Рисую...")
        try:
            res = await client.images.generate(model="dall-e-3", prompt=prompt)
            await message.answer_photo(res.data[0].url)
            update_db(user[0], "balance", user[1] - 5)
            update_db(user[0], "img_today", user[8] + 1)
        except Exception as e: await message.answer(f"Ошибка: {e}")
        finally: await m.delete()
        return

    # --- ЛОГИКА ЧАТА ---
    if user[1] < 1:
        return await message.answer("Запросы кончились.")

    model = "-4o" if user[2] else "-4o-mini"
    history = json.loads(user[4])
    history.append({"role": "user", "content": message.text})
    history = history[-10:]

    try:
        res = await client.chat.completions.create(model=model, messages=history)
        ans = res.choices[0].message.content
        history.append({"role": "assistant", "content": ans})
        update_db(user[0], "history", json.dumps(history))
        if not user[2]: update_db(user[0], "balance", user[1] - 1)
        await message.answer(ans)
    except Exception as e: await message.answer(f"Ошибка: {e}")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
