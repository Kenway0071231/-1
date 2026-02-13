"""
СУПЕР-ПРОСТОЙ ТЕСТОВЫЙ БОТ
Никаких сложностей, только проверка ввода ФИО
"""

import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes

load_dotenv()

# Состояние
GETTING_NAME = 1

# Токен
TOKEN = os.getenv('BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт"""
    keyboard = [[InlineKeyboardButton("📝 Тест ФИО", callback_data='test')]]
    await update.message.reply_text(
        "Нажми кнопку для теста:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'test':
        await query.message.delete()
        await query.message.reply_text(
            "✏️ **Введите ваше ФИО**\n\n"
            "Например: Иванов Иван Иванович",
            parse_mode='Markdown'
        )
        return GETTING_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ФИО"""
    user_id = update.effective_user.id
    name = update.message.text
    
    print(f"✅ ПОЛУЧЕНО СООБЩЕНИЕ от {user_id}: {name}")
    
    await update.message.reply_text(
        f"✅ Спасибо! Вы ввели: {name}\n\n"
        f"Тест пройден успешно!"
    )
    
    return ConversationHandler.END

def main():
    print("🚀 Запуск тестового бота...")
    
    app = Application.builder().token(TOKEN).build()
    
    # ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button, pattern='^test$')],
        states={
            GETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        },
        fallbacks=[]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
