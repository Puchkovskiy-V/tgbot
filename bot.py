import random
import sqlite3
import json
import logging
from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    InlineQueryHandler,
    CallbackQueryHandler,
    filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройки
DB_FILE = "jarvis_bot.db"
OPTIONS = {
    "Сын подстилки": "🧹",
    "Сын удачи": "🍀",
    "Сын хуяги парашника": "🪂",
    "Сын золотого яблока": "🍏",
    "Мопс": "🐶",
    "Лизун": "👅",
    "Вонючий Шланг": "🐍",
    "Тути фрути проститути": "🍑",
    "Анальный Вульварине": "🕳️",
    "Гомельский Дайсон": "🌀",
    "Дед Ганс": "👴",
    "100% Гей": "🌈",
    "Очкастая лулумба": "👓"
}

def init_db():
    """Инициализация базы данных с проверкой существующих таблиц"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Проверяем существование таблицы users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    used_options TEXT DEFAULT '[]',
                    all_used INTEGER DEFAULT 0
                )
            """)
        else:
            # Проверяем наличие колонки username
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'username' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
        
        # Проверяем существование таблицы stats
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stats'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE stats (
                    user_id INTEGER,
                    option TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, option)
                )
            """)

def get_user_data(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT used_options, all_used FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            try:
                return json.loads(result[0]), result[1]
            except json.JSONDecodeError:
                return [], 0
        return [], 0

def update_user_data(user_id, username, used_options, all_used):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, username, used_options, all_used)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, json.dumps(used_options), all_used))

def update_stats(user_id, option):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO stats (user_id, option, count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, option) DO UPDATE SET count = count + 1
        """, (user_id, option))

def reset_user_stats(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stats WHERE user_id = ?", (user_id,))
        cursor.execute("UPDATE users SET used_options = '[]', all_used = 0 WHERE user_id = ?", (user_id,))

def get_random_option(user_id, username):
    used_options, all_used = get_user_data(user_id)
    
    if len(used_options) >= len(OPTIONS):
        used_options = []
        all_used = 1
    
    available_options = [opt for opt in OPTIONS.items() if opt[0] not in used_options]
    
    if not available_options:
        used_options = []
        available_options = list(OPTIONS.items())
    
    chosen_option, emoji = random.choice(available_options)
    used_options.append(chosen_option)
    update_user_data(user_id, username, used_options, all_used)
    update_stats(user_id, chosen_option)
    
    return f"{chosen_option} {emoji}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    text = (
        "🤖 <b>Бот характеристик</b>\n\n"
        "Доступные команды:\n"
        "/whoami - Получить случайную характеристику\n"
        "/stats - Показать статистику\n"
        "/reset_stats - Сбросить статистику\n\n"
        "В группе используйте @username_бота для выбора действия"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode='HTML'
    )

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация характеристики"""
    try:
        user = update.effective_user
        response = get_random_option(user.id, user.username)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🎯 {user.mention_html()}, ты - {response}",
            parse_mode='HTML',
            reply_to_message_id=update.message.message_id if update.message else None
        )
    except Exception as e:
        logger.error(f"Error in whoami: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ Произошла ошибка при генерации характеристики"
        )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    try:
        user = update.effective_user
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT option, count FROM stats 
                WHERE user_id = ? 
                ORDER BY count DESC
                LIMIT 10
            """, (user.id,))
            stats_data = cursor.fetchall()
        
        if not stats_data:
            await update.message.reply_text("У вас еще нет статистики.")
            return
        
        response = "📊 <b>Ваша статистика:</b>\n\n"
        for idx, (option, count) in enumerate(stats_data, 1):
            emoji = OPTIONS.get(option, "")
            response += f"{idx}. {emoji} {option}: {count} раз\n"
        
        await update.message.reply_text(response, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error in stats: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при получении статистики")

async def reset_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить статистику"""
    try:
        user = update.effective_user
        reset_user_stats(user.id)
        await update.message.reply_text("✅ <b>Ваша статистика сброшена!</b>", parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error in reset_stats: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при сбросе статистики")

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик инлайн-запросов"""
    try:
        user = update.inline_query.from_user
        
        # Вариант 1: Получить характеристику
        result1 = InlineQueryResultArticle(
            id="1",
            title="🎲 Получить характеристику",
            description="Нажмите, чтобы получить случайную характеристику",
            input_message_content=InputTextMessageContent(
                f"❓ {user.first_name} хочет узнать свою характеристику",
                parse_mode='HTML'
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Показать характеристику", callback_data=f"char:{user.id}")
            ]])
        )
        
        # Вариант 2: Показать статистику
        result2 = InlineQueryResultArticle(
            id="2",
            title="📊 Моя статистика",
            description="Показать вашу персональную статистику",
            input_message_content=InputTextMessageContent(
                f"📊 {user.first_name} запрашивает статистику",
                parse_mode='HTML'
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Показать статистику", callback_data=f"stats:{user.id}")
            ]])
        )
        
        await update.inline_query.answer([result1, result2])
    except Exception as e:
        logger.error(f"Error in inline_query: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    try:
        user = query.from_user
        action, user_id = query.data.split(":")
        
        if user.id != int(user_id):
            await query.edit_message_text("⛔ Это действие доступно только автору запроса")
            return
        
        if action == "char":
            response = get_random_option(user.id, user.username)
            await query.edit_message_text(
                text=f"🎯 {user.mention_html()}, ты - {response}",
                parse_mode='HTML'
            )
        elif action == "stats":
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT option, count FROM stats 
                    WHERE user_id = ? 
                    ORDER BY count DESC
                    LIMIT 5
                """, (user.id,))
                stats_data = cursor.fetchall()
            
            if not stats_data:
                await query.edit_message_text("У вас еще нет статистики.")
                return
            
            response = "📊 <b>Ваша статистика:</b>\n\n"
            for idx, (option, count) in enumerate(stats_data, 1):
                emoji = OPTIONS.get(option, "")
                response += f"{idx}. {emoji} {option}: {count} раз\n"
            
            await query.edit_message_text(response, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"Error in button callback: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка, попробуйте позже")

def main():
    """Запуск бота"""
    init_db()
    
    application = Application.builder() \
        .token("7031109248:AAF5RIKLWc1uDsDUGLechx1LgocVbJVHU4g") \
        .build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("reset_stats", reset_stats))
    
    # Инлайн-режим
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчик для команд в группах
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.Regex(r'^/whoami'),
        whoami
    ))
    
    logger.info("Бот запущен и готов к работе!")
    application.run_polling()

if __name__ == "__main__":
    main()
