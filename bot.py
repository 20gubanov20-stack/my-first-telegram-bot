import os
import logging
import random
import sqlite3  # 👈 Подключаем базу данных (она встроена в Python)
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ⚠️ ВСТАВЬ СЮДА СВОЙ НОВЫЙ ТОКЕН (после /revoke у BotFather)
TOKEN = os.environ.get("BOT_TOKEN")
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ---
def init_db():
    # Подключаемся к файлу базы данных (если его нет, он создастся)
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    # Создаем таблицу, если ее еще нет
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            attempts INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def save_score(user_id, username, attempts):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Проверяем, есть ли уже игрок в базе
    cursor.execute("SELECT attempts FROM leaderboard WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row is None:
        # Если игрока нет, добавляем его
        cursor.execute("INSERT INTO leaderboard (user_id, username, attempts) VALUES (?, ?, ?)", 
                       (user_id, username, attempts))
    elif attempts < row[0]:
        # Если игрок есть, но побил свой рекорд — обновляем
        cursor.execute("UPDATE leaderboard SET attempts = ?, username = ? WHERE user_id = ?", 
                       (attempts, username, user_id))
    
    conn.commit()
    conn.close()

def get_top_scores():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    # Берем топ-5 игроков, сортируем по возрастанию попыток
    cursor.execute("SELECT username, attempts FROM leaderboard ORDER BY attempts ASC LIMIT 5")
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- ФУНКЦИИ БОТА ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎮 Начать игру", callback_data='game')],
        [InlineKeyboardButton("🏆 Таблица рекордов", callback_data='top')], # Новая кнопка
        [InlineKeyboardButton("ℹ️ Помощь", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! 👋\nЯ теперь с базой данных. Смогу запомнить твой рекорд!",
        reply_markup=reply_markup
    )

async def show_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Для команды /top
    top = get_top_scores()
    text = "🏆 **Топ-5 лучших игроков:**\n\n"
    if not top:
        text += "Пока никто не играл. Будь первым!"
    else:
        for i, (username, attempts) in enumerate(top, 1):
            text += f"{i}. {username} — {attempts} попыток\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Доступные команды:\n/start — меню\n/game — игра\n/top — рекорды\n/cancel — отмена")

async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['secret_number'] = random.randint(1, 100)
    context.user_data['attempts'] = 0
    context.user_data['game_active'] = True
    await update.message.reply_text("🎮 Я загадал число от 1 до 100. Попробуй угадать! (Напиши число)")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['game_active'] = False
    await update.message.reply_text("Игра отменена. 👋")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('game_active'):
        text = update.message.text
        if not text.isdigit():
            await update.message.reply_text("Введи целое число от 1 до 100.")
            return
            
        guess = int(text)
        secret = context.user_data['secret_number']
        context.user_data['attempts'] += 1
        attempts = context.user_data['attempts']
        
        if guess < secret:
            await update.message.reply_text(f"📉 Мое число больше. (Попытка: {attempts})")
        elif guess > secret:
            await update.message.reply_text(f"📈 Мое число меньше. (Попытка: {attempts})")
        else:
            # ПОБЕДА! Сохраняем результат в базу данных
            user_id = update.effective_user.id
            username = update.effective_user.first_name
            save_score(user_id, username, attempts)
            
            await update.message.reply_text(
                f"🎉 Ура! Ты угадал число {secret} за {attempts} попыток!\n"
                "Твой результат сохранен в базе. Проверь рекорды: /top"
            )
            context.user_data['game_active'] = False
    else:
        await update.message.reply_text(f"Ты написал: {update.message.text}\n(Чтобы поиграть, напиши /game)")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'help':
        await query.edit_message_text("Это справка. Используй /help для списка команд.")
    elif query.data == 'game':
        await query.edit_message_text("Отлично! Начинаем игру. Напиши мне число от 1 до 100.")
        context.user_data['secret_number'] = random.randint(1, 100)
        context.user_data['attempts'] = 0
        context.user_data['game_active'] = True
    elif query.data == 'top':
        top = get_top_scores()
        text = "🏆 **Топ-5 лучших игроков:**\n\n"
        if not top:
            text += "Пока никто не играл. Будь первым!"
        else:
            for i, (username, attempts) in enumerate(top, 1):
                text += f"{i}. {username} — {attempts} попыток\n"
        await query.edit_message_text(text, parse_mode='Markdown')

if __name__ == '__main__':
    init_db()  # 👈 Инициализируем базу данных при запуске
    
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("top", show_top)) # Добавили команду /top
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Бот с базой данных запущен!")
    app.run_polling()