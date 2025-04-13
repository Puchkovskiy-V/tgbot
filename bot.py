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
    """Инициализация базы данных"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                used_options TEXT DEFAULT '[]',
                all_used INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats (
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
        """, (user_id, username or str(user_id), json.dumps(used_options), all_used))

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
    """Показать полную статистику"""
    try:
        user = update.effective_user
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT option, count FROM stats 
                WHERE user_id = ?
                ORDER BY count DESC
            """, (user.id,))
            stats_data = cursor.fetchall()
            
            cursor.execute("SELECT SUM(count) FROM stats WHERE user_id = ?", (user.id,))
            total = cursor.fetchone()[0] or 0
        
        if not stats_data:
            await update.message.reply_text("У вас еще нет статистики.")
            return
        
        response = f"📊 <b>Статистика для {user.mention_html()} (всего: {total}):</b>\n\n"
        for idx, (option, count) in enumerate(stats_data, 1):
            emoji = OPTIONS.get(option, "")
            percentage = (count / total) * 100 if total > 0 else 0
            response += f"{idx}. {emoji} <b>{option}</b>: {count} раз ({percentage:.1f}%)\n"
        
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
    """Обработчик инлайн-запросов с уникальными ID"""
    try:
        user = update.inline_query.from_user
        unique_prefix = f"{user.id}_"
        
        results = [
            InlineQueryResultArticle(
                id=f"{unique_prefix}char",
                title="🎲 Получить характеристику",
                description="Нажмите, чтобы получить случайную характеристику",
                input_message_content=InputTextMessageContent(
                    f"❓ {user.first_name} хочет узнать свою характеристику",
                    parse_mode='HTML'
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Показать", callback_data=f"char:{user.id}")
                ]])
            ),
            InlineQueryResultArticle(
                id=f"{unique_prefix}stats",
                title="📊 Моя статистика",
                description="Показать вашу персональную статистику",
                input_message_content=InputTextMessageContent(
                    f"📊 {user.first_name} запрашивает статистику",
                    parse_mode='HTML'
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Показать", callback_data=f"stats:{user.id}")
                ]])
            )
        ]
        await update.inline_query.answer(results)
    except Exception as e:
        logger.error(f"Error in inline_query: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок с проверкой прав"""
    query = update.callback_query
    await query.answer()
    
    try:
        action, requested_user_id = query.data.split(":")
        current_user = query.from_user
        
        # Проверка прав доступа
        if current_user.id != int(requested_user_id):
            await query.edit_message_text(
                "⛔ Доступ запрещен: это не ваш запрос",
                reply_markup=None
            )
            return
            
        if action == "char":
            response = get_random_option(current_user.id, current_user.username)
            await query.edit_message_text(
                text=f"🎯 {current_user.mention_html()}, ты - {response}",
                parse_mode='HTML'
            )
            
        elif action == "stats":
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT option, count FROM stats 
                    WHERE user_id = ?
                    ORDER BY count DESC
                """, (current_user.id,))
                stats_data = cursor.fetchall()
                
                cursor.execute("SELECT SUM(count) FROM stats WHERE user_id = ?", (current_user.id,))
                total = cursor.fetchone()[0] or 0
            
            if not stats_data:
                await query.edit_message_text("У вас еще нет статистики.")
                return
            
            response = f"📊 <b>Статистика для {current_user.mention_html()} (всего: {total}):</b>\n\n"
            for idx, (option, count) in enumerate(stats_data, 1):
                emoji = OPTIONS.get(option, "")
                percentage = (count / total) * 100 if total > 0 else 0
                response += f"{idx}. {emoji} <b>{option}</b>: {count} раз ({percentage:.1f}%)\n"
            
            await query.edit_message_text(response, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"Error in button callback: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка")

def main():
    """Запуск бота"""
    init_db()
    
    application = Application.builder() \
        .token("7031109248:AAEi_Eohl5yECvepbv0Ym60mdl_4M2q2IAA") \
        .build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("reset_stats", reset_stats))
    
    # Инлайн-режим
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчик команд в группах
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.Regex(r'^/(whoami|stats|reset_stats)'),
        lambda update, context: {
            'whoami': whoami,
            'stats': stats,
            'reset_stats': reset_stats
        }[update.message.text[1:]](update, context)
    ))
    
    logger.info("Бот запущен и готов к работе!")
    application.run_polling()

if __name__ == "__main__":
    main()
