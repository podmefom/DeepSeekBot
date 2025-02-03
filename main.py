import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from openai import OpenAI

# Инициализация окружения
load_dotenv()

# Конфигурация клиента OpenAI
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ID канала (нужно указать с @ или ID, например, "@mychannel")
CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL_USERNAME")

async def check_subscription(user_id, context) -> bool:
    """Проверяет, подписан ли пользователь на канал"""
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

async def subscribe(update: Update, context) -> None:
    """Отправляет сообщение с кнопками подписки"""
    keyboard = [
        [InlineKeyboardButton("✅ Подписаться", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
        [InlineKeyboardButton("🔄 Проверить подписку", callback_data="check_subscription")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔔 Чтобы пользоваться ботом, подпишитесь на канал и нажмите 'Проверить подписку'.",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context) -> None:
    """Обработчик кнопки 'Проверить подписку'"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if await check_subscription(user_id, context):
        await query.message.edit_text("✅ Спасибо за подписку! Теперь вы можете пользоваться ботом.")
    else:
        await query.answer("❌ Вы не подписаны! Подпишитесь и попробуйте снова.", show_alert=True)

async def start(update: Update, context) -> None:
    """Обработчик команды /start"""
    user_id = update.effective_user.id

    if await check_subscription(user_id, context):
        await update.message.reply_text("🚀 Привет! Я бот с интеграцией DeepSeek-R1. Задайте ваш вопрос!")
    else:
        await subscribe(update, context)

async def handle_message(update: Update, context) -> None:
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id

    if not await check_subscription(user_id, context):
        await subscribe(update, context)
        return

    try:
        user_message = update.message.text
        logger.info(f"User {user_id} asked: {user_message}")
        
        # Запрос к DeepSeek-R1
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": os.getenv("SITE_URL", "https://default.url").encode('utf-8'),
                "X-Title": os.getenv("SITE_NAME", "DeepSeek Telegram Bot").encode('utf-8'),
            },
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": user_message}]
        )
        
        response = completion.choices[0].message.content
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error for user {user_id}: {str(e)}", exc_info=True)
        await update.message.reply_text("⚠️ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже.")

def main() -> None:
    """Основная функция запуска бота"""
    try:
        application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
        
        # Регистрация обработчиков
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(button_handler))
        
        logger.info("Бот запущен...")
        application.run_polling()
        
    except Exception as e:
        logger.critical(f"Critical error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
