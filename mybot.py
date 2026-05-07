import logging
import sqlite3
import json
import requests
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
# --- НАСТРОЙКИ (ЗАПОЛНИ СВОИ ДАННЫЕ) ---
TOKEN = '7684953787:AAEcIMd1i9POTUPa7ZuIeejoYE70X3wAv7U'
PROXY_API_KEY = 'sk-zq9qY2WopXj3tsYpMLil7VV98RGlOm9M'
ADMIN_ID = 6760835730  # Ваш Telegram ID
CHANNEL_ID = "@NorkaGpt" # Замени на свой

BASE_URL = "https://api.proxyapi.ru/openai/v1/chat/completions"
IMG_URL = "https://api.proxyapi.ru/openai/v1/images/generations"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('/data/users.db')
    cursor = conn.cursor()
    # Добавляем колонки для рефералов и подписки
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY,
                       balance INTEGER, 
                       model TEXT,
                       history TEXT, 
                       is_premium INTEGER DEFAULT 0, 
                       referrer_id INTEGER, 
                       is_rewarded INTEGER DEFAULT 0, 
                       sub_rewarded INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('/data/users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (user_id, 10, "-4o-mini", "[]", 0, None, 0, 0))
        conn.commit()
        user = (user_id, 10, "-4o-mini", "[]", 0)
    conn.close()
    return user

def update_user(user_id, balance=None, model=None, history=None, is_premium=None):
    conn = sqlite3.connect('/data/users.db')
    cursor = conn.cursor()
    if balance is not None:
        cursor.execute("UPDATE users SET balance=? WHERE id=?", (balance, user_id))
    if model is not None:
        cursor.execute("UPDATE users SET model=? WHERE id=?", (model, user_id))
    if history is not None:
        cursor.execute("UPDATE users SET history=? WHERE id=?", (history, user_id))
    if is_premium is not None:
        cursor.execute("UPDATE users SET is_premium=? WHERE id=?", (is_premium, user_id))
    conn.commit()
    conn.close()

# --- КЛАВИАТУРЫ ---
def main_menu():
    # В aiogram 3.x кнопки передаются списком внутри аргумента keyboard
    kb = [
        [KeyboardButton(text="🧠  Задать вопрос"), KeyboardButton(text="🎨  Создать фото")],
        [KeyboardButton(text="⚙️  Настройки"), KeyboardButton(text="💰 Купить Premium")],
        [KeyboardButton(text="🎁  Бесплатные запросы")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def settings_menu(is_premium):
    status = "🌟  Premium" if is_premium else "Бесплатный"
    
    # В aiogram 3.x кнопки передаются списком внутри аргумента inline_keyboard
    buttons = [
        [InlineKeyboardButton(text=f"Ваш статус: {status}", callback_data="none")],
        [InlineKeyboardButton(text="Выбрать GPT-4o-mini", callback_data="set_model_-4o-mini")],
        [InlineKeyboardButton(text="Выбрать GPT-4o (Premium)", callback_data="set_model_-4o")],
        [InlineKeyboardButton(text="🗑 Очистить историю", callback_data="clear_history")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- КОМАНДЫ И ОБРАБОТЧИКИ ---
@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    # Если юзер зашел в бота ПЕРВЫЙ РАЗ
    if not user:
        referrer_id = None
        # Проверяем, есть ли в ссылке ID пригласившего
        if command.args and command.args.isdigit():
            ref_candidate = int(command.args)
            if ref_candidate != user_id: # Защита, чтобы не приглашал сам себя
                referrer_id = ref_candidate
        
        # Создаем нового юзера в базе (добавляем referrer_id)
        conn = sqlite3.connect('/data/users.db')
        cursor = conn.cursor()
        # ВАЖНО: Тут 8 знаков ?, так как мы добавили колонки в init_db
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                       (user_id, 10, "-4o-mini", "[]", 0, referrer_id, 0, 0))
        conn.commit()
        conn.close()
        
        # Пишем тому, кто пригласил, что у него новый реферал
        if referrer_id:
            try:
                await bot.send_message(referrer_id, "🤝  По вашей ссылке зашел новый друг! Вы получите +3 запроса, когда он напишет первое сообщение.")
            except:
                pass

    # Обычное приветствие (как и было у тебя)
    await message.answer(
        "Привет! Я ИИ бот. У тебя есть 10 бесплатных запросов. Можешь задавать вопросы или создавать фото.", 
        reply_markup=main_menu()
    )

@router.message(F.text(equals="💰 Купить Premium"))
async def buy_premium(message: Message):
    uid = message.from_user.id
    text = (
        f"🌟  **Преимущества Premium:**\n"
        f"1. Доступ к самой умной модели GPT-4o\n"
        f"2. Приоритетная скорость ответов\n"
        f"3. +100 запросов на баланс\n\n"
        f"**Цена:** 200 рублей.\n"
        f"Для покупки переведи деньги на карту: `2202 2082 6287 3053`\n"
        f"После оплаты скинь чек и свой ID: `{uid}` админу @zilowu"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text(equals="⚙️  Настройки"))
async def open_settings(message: Message):
    user = get_user(message.from_user.id)
    await message.answer(
        f"⚙️  **Настройки**\n\nБаланс: {user[1]} запросов\nМодель: {user[2]}",
        reply_markup=settings_menu(user[4]),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith('set_model_'))
async def change_model(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    requested_model = callback.data.split('_')[2]

    if requested_model == "-4o" and not user[4]:
        await callback.answer("❌ GPT-4.0 доступна только для Premium пользователей!", show_alert=True)
        return

    update_user(callback.from_user.id, model=requested_model)
    await callback.answer(f"✅ Модель {requested_model} установлена")
    await callback.message.edit_text(f"✅ Модель изменена на {requested_model}. Теперь пиши сообщение!")

@router.callback_query(F.data == 'clear_history')
async def clear_history(callback: CallbackQuery):
    update_user(callback.from_user.id, history="[]")
    await callback.answer("🗑 История очищена!")

@router.message(Command('set_premium'))
async def admin_set_premium(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.get_args()
    if not args:
        await message.answer("Ошибка! Пиши: /set_premium ID_ПОЛЬЗОВАТЕЛЯ")
        return

    try:
        target_id = int(args)
        update_user(target_id, is_premium=1, balance=100)
        await message.answer(f"✅ Премиум выдан пользователю {target_id}!")
        await bot.send_message(target_id, "🌟  Вам выдан Premium доступ! Теперь вы можете выбрать модель 4.0 в настройках.")
    except Exception as e:
        await message.answer(f"Ошибка! Проверь правильность ID. ({e})")
@router.message(F.text == "🎁  Бесплатные запросы")
async def free_bonus(message: Message):
    user_id = message.from_user.id
    bot_name = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_name}?start={user_id}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢  Подписаться", url=f"https://t.me/{CHANNEL_ID[1:]}")],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")]
    ])
    await message.answer(f"1. Подпишись на {CHANNEL_ID} (+1 запрос)\n2. Ссылка для друзей:\n`{ref_link}`", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "check_sub")
async def check_sub_handler(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user[7] == 1: # Колонка sub_rewarded
        await callback.answer("Вы уже получили бонус!", show_alert=True)
        return

    # Проверка статуса в канале
    chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=callback.from_user.id)
    if chat_member.status != 'left':
        update_user(callback.from_user.id, balance=user[1]+1, sub_rewarded=1)
        await callback.message.answer("✅ +1 запрос начислен!")
    else:
        await callback.answer("❌ Вы не подписаны!", show_alert=True)

# --- ГЛАВНАЯ ЛОГИКА ---
@router.message()
async def main_handler(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    # ЛОГИКА НАГРАДЫ ЗА ДРУГА
    # Если у юзера есть referrer_id и награда еще не была выдана (is_rewarded == 0)
    if user[5] and user[6] == 0:
        referrer_id = user[5]
        ref_data = get_user(referrer_id)
        if ref_data:
            # Начисляем +3 тому, кто пригласил
            update_user(referrer_id, balance=ref_data[1] + 3)
            # Помечаем, что награда за этого приглашенного выдана
            update_user(message.from_user.id, is_rewarded=1)
            try: await bot.send_message(referrer_id, "🎁  Бонус! Ваш приглашенный друг активен, вам начислено +3 запроса!")
            except: pass
    balance, current_model, history_json, is_premium = user[1], user[2], user[3], user[4]

    if balance <= 0:
        await message.answer("❌ Запросы закончились. Купите Premium или дождитесь пополнения.")
        return

    # Генерация изображения
    if any(word in message.text.lower() for word in ["нарисуй", "фото", "картинка"]):
        await message.answer("⏳ Генерирую изображение...")
        headers = {"Authorization": f"Bearer {PROXY_API_KEY}"}
        payload = {"model": "dall-e-3", "prompt": message.text, "n": 1, "size": "1024x1024"}

        try:
            r = requests.post(IMG_URL, json=payload, headers=headers).json()
            photo_url = r['data'][0]['url']
            await bot.send_photo(message.chat.id, photo_url, caption="Готово!")
            update_user(message.from_user.id, balance=balance - 5)
            return
        except Exception as e:
            await message.answer(f"Ошибка при создании фото: {e}")
            return

    # Текстовый запрос к ИИ
    try:
        history = json.loads(history_json)
        history.append({"role": "user", "content": message.text})

        payload = {
            "model": current_model,
            "messages": [{"role": "system", "content": "Ты полезный ассистент."}] + history[-10:],
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 1,
            "presence_penalty": 0,
            "frequency_penalty": 0
        }

        headers = {"Authorization": f"Bearer {PROXY_API_KEY}"}

        thinking_msg = await message.answer("🤔  Думаю...")

        res = requests.post(BASE_URL, json=payload, headers=headers).json()

        reply_text = res['choices'][0]['message']['content']

        history.append({"role": "assistant", "content": reply_text})

        update_user(
            message.from_user.id,
            balance=balance - 1,
            history=json.dumps(history)
        )

        await thinking_msg.edit_text(reply_text)

    except Exception as e:
        await thinking_msg.edit_text(f"❌ Ошибка API. Проверьте баланс ProxyAPI. ({e})")

# --- ЗАПУСК БОТА ---
def main():
    init_db()
    dp.include_router(router)
    dp.run_polling(bot)

if __name__ == '__main__':
    main()