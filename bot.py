import logging
import random
import sqlite3
import threading
import sys
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.ERROR)
API_TOKEN = '7951043607:AAG_FZfAHGxaUEAfdsB_RYmg1ZKDvhkbhd0'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

last_messages = {}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('economy.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER, 
                       mult INTEGER, last_farm TEXT)''')
    conn.commit()
    conn.close()

def get_user(user_id, username="User"):
    conn = sqlite3.connect('economy.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, mult, last_farm FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (user_id, str(username), 0, 1, "2000-01-01 00:00:00"))
        conn.commit()
        result = (0, 1, "2000-01-01 00:00:00")
    conn.close()
    return {"balance": result[0], "mult": result[1], "last_farm": result[2]}

def update_user(user_id, balance, mult, last_farm=None):
    conn = sqlite3.connect('economy.db', check_same_thread=False)
    cursor = conn.cursor()
    if last_farm:
        cursor.execute("UPDATE users SET balance = ?, mult = ?, last_farm = ? WHERE user_id = ?", (int(balance), int(mult), last_farm, user_id))
    else:
        cursor.execute("UPDATE users SET balance = ?, mult = ? WHERE user_id = ?", (int(balance), int(mult), user_id))
    conn.commit()
    conn.close()

async def delete_old_message(chat_id, user_id):
    key = f"{chat_id}_{user_id}"
    if key in last_messages:
        try:
            await bot.delete_message(chat_id, last_messages[key])
        except:
            pass

# --- АДМИНКА ---
def console_admin():
    import time
    time.sleep(3)
    print("\n" + "!"*30 + "\nАДМИНКА ГОТОВА (give ID SUM)\n" + "!"*30)
    while True:
        try:
            line = sys.stdin.readline().strip()
            if not line: continue
            if line.startswith("give"):
                parts = line.split()
                tid, summa = int(parts[1]), int(parts[2])
                conn = sqlite3.connect('economy.db')
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (summa, tid))
                conn.commit()
                conn.close()
                print(f"✅ Выдано {summa} юзеру {tid}")
        except Exception as e: print(f"❌ Ошибка: {e}")

# --- ОБРАБОТКА КОМАНД (УНИВЕРСАЛЬНАЯ ДЛЯ ГРУПП) ---
@dp.message_handler(lambda message: message.text and message.text.startswith('/'))
async def global_handler(message: types.Message):
    # Извлекаем чистую команду без @бота
    full_command = message.text.split()[0].split('@')[0].lower()
    user_id = message.from_user.id
    chat_id = message.chat.id

    valid_commands = ['/start', '/money', '/shop', '/mystats', '/top']
    if full_command not in valid_commands:
        return

    # Удаляем сообщение пользователя
    try: await message.delete()
    except: pass

    # Удаляем предыдущее сообщение бота
    await delete_old_message(chat_id, user_id)

    u = get_user(user_id, message.from_user.username or f"user_{user_id}")
    res_msg = None

    if full_command == '/start':
        res_msg = await message.answer("🛠 Бот активен! Используйте меню команд.")

    elif full_command == '/mystats':
        now = datetime.now()
        last = datetime.strptime(u['last_farm'], "%Y-%m-%d %H:%M:%S")
        status = "✅ Готов!" if now >= last + timedelta(hours=2) else f"⏳ {int(((last + timedelta(hours=2)) - now).total_seconds() // 60)} мин."
        text = f"📊 **Статистика {message.from_user.first_name}:**\n💰 Баланс: {u['balance']}$\n⚡ Множитель: x{u['mult']}\n🕒 Фарм: {status}"
        res_msg = await message.answer(text, parse_mode="Markdown")

    elif full_command == '/money':
        now = datetime.now()
        last = datetime.strptime(u['last_farm'], "%Y-%m-%d %H:%M:%S")
        if now < last + timedelta(hours=2):
            wait = (last + timedelta(hours=2)) - now
            res_msg = await message.answer(f"⏳ {message.from_user.first_name}, жди {int(wait.total_seconds() // 60)} мин.")
        else:
            m = u['mult']
            if m > 1 and random.random() < (0.45 if m >= 30 else 0.25):
                update_user(user_id, u['balance'], 1, now.strftime("%Y-%m-%d %H:%M:%S"))
                res_msg = await message.answer(f"💥 {message.from_user.first_name}, инструмент сломан! Множитель x1.")
            else:
                prize = random.randint(50, 150) * m
                update_user(user_id, u['balance'] + prize, m, now.strftime("%Y-%m-%d %H:%M:%S"))
                res_msg = await message.answer(f"💵 {message.from_user.first_name}, фарм: +{prize}$!")

    elif full_command == '/shop':
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("⛏ Кирка x10 (500$)", callback_data="buy_1"),
            InlineKeyboardButton("⛏ Редк. x30 (1500$)", callback_data="buy_2"),
            InlineKeyboardButton("🧹 Лопата x20 (1000$)", callback_data="buy_3"),
            InlineKeyboardButton("🧹 Редк. x40 (2000$)", callback_data="buy_4")
        )
        res_msg = await message.answer(f"🛒 Магазин для {message.from_user.first_name}:", reply_markup=kb)

    elif full_command == '/top':
        conn = sqlite3.connect('economy.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
        res = cursor.fetchall()
        conn.close()
        text = "🏆 **ТОП 10 МАЖОРОВ:**\n" + "\n".join([f"{i+1}. {r[0]} — {r[1]}$" for i, r in enumerate(res)])
        res_msg = await message.answer(text, parse_mode="Markdown")

    if res_msg:
        last_messages[f"{chat_id}_{user_id}"] = res_msg.message_id

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def shop_logic(call: types.CallbackQuery):
    idx = call.data.split('_')[1]
    u = get_user(call.from_user.id)
    items = {"1": [500, 10, "кирку"], "2": [1500, 30, "редк. кирку"],
             "3": [1000, 20, "лопату"], "4": [2000, 40, "редк. лопату"]}
    
    cost, m, name = items[idx]
    if u['balance'] >= cost:
        update_user(call.from_user.id, u['balance'] - cost, m)
        try: await bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        await bot.send_message(call.message.chat.id, f"✅ {call.from_user.first_name} купил {name}! (x{m})")
    else:
        await bot.answer_callback_query(call.id, "❌ Не хватает денег!", show_alert=True)

if __name__ == '__main__':
    init_db()
    threading.Thread(target=console_admin, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
