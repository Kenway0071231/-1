"""
СТОМАТОЛОГИЧЕСКИЙ БОТ - МАКСИМАЛЬНО ПРОСТАЯ ВЕРСИЯ
Никаких баз данных, только запись в память
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes

load_dotenv()

# ============================================================================
# СОСТОЯНИЯ
# ============================================================================
GETTING_NAME, GETTING_PHONE, SELECTING_DOCTOR, SELECTING_DATE, SELECTING_TIME, CONFIRMING = range(6)

# ============================================================================
# ТОКЕН
# ============================================================================
TOKEN = os.getenv('BOT_TOKEN')

# ============================================================================
# ДАННЫЕ В ПАМЯТИ
# ============================================================================

# Врачи
DOCTORS = {
    1: {"name": "Иванова Мария Петровна", "specialty": "Терапевт"},
    2: {"name": "Петров Сергей Иванович", "specialty": "Хирург"},
    3: {"name": "Сидорова Анна Викторовна", "specialty": "Ортодонт"},
    4: {"name": "Козлов Алексей Николаевич", "specialty": "Ортопед"},
    5: {"name": "Соколова Елена Дмитриевна", "specialty": "Детский"}
}

# Рабочее время
WORK_HOURS = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00']

# Хранилище занятого времени {doctor_id}_{date}: [time1, time2]
busy_slots = {}

# Временные данные пользователей
user_temp = {}

# ============================================================================
# КЛАВИАТУРЫ
# ============================================================================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📝 Записаться", callback_data='appointment')],
        [InlineKeyboardButton("👨‍⚕️ Врачи", callback_data='doctors')],
        [InlineKeyboardButton("📋 Мои записи", callback_data='my_appointments')],
        [InlineKeyboardButton("🏥 О нас", callback_data='about')],
        [InlineKeyboardButton("📞 Контакты", callback_data='contacts')]
    ]
    return InlineKeyboardMarkup(keyboard)

def doctors_keyboard():
    keyboard = []
    for doc_id, doc in DOCTORS.items():
        name_part = doc["name"].split()[1] if len(doc["name"].split()) > 1 else doc["name"]
        keyboard.append([
            InlineKeyboardButton(f"👨‍⚕️ {name_part} - {doc['specialty']}", callback_data=f"doc_{doc_id}")
        ])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_menu')])
    return InlineKeyboardMarkup(keyboard)

def date_keyboard():
    keyboard = []
    today = datetime.now()
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime('%d.%m.%Y')
        if i == 0:
            label = f"📅 Сегодня ({date.day}.{date.month})"
        elif i == 1:
            label = f"📅 Завтра ({date.day}.{date.month})"
        else:
            label = f"📅 {date.day}.{date.month}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"date_{date_str}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_doctors')])
    return InlineKeyboardMarkup(keyboard)

def time_keyboard(doctor_id, date):
    keyboard = []
    key = f"{doctor_id}_{date}"
    busy = busy_slots.get(key, [])
    available = [t for t in WORK_HOURS if t not in busy]
    
    row = []
    for time in available[:6]:
        row.append(InlineKeyboardButton(time, callback_data=f"time_{doctor_id}_{date}_{time}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_dates')])
    return InlineKeyboardMarkup(keyboard)

def confirm_keyboard(date, time, doctor_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{date}_{time}_{doctor_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data='cancel')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ============================================================================
# ОБРАБОТЧИКИ
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт"""
    user = update.effective_user
    await update.message.reply_text(
        f"🦷 Здравствуйте, {user.first_name}!\n\n"
        f"Я помогу записаться к стоматологу.\n"
        f"Выберите действие:",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    print(f"Нажата кнопка: {data}")
    
    # ========== НАЗАД ==========
    if data == 'back_menu':
        await query.edit_message_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END
    
    # ========== ЗАПИСЬ ==========
    if data == 'appointment':
        user_temp[user_id] = {}
        await query.edit_message_text("👨‍⚕️ Выберите врача:", reply_markup=doctors_keyboard())
        return SELECTING_DOCTOR
    
    # ========== ВЫБОР ВРАЧА ==========
    if data.startswith('doc_'):
        doctor_id = int(data.split('_')[1])
        doctor = DOCTORS[doctor_id]
        
        user_temp[user_id]['doctor_id'] = doctor_id
        user_temp[user_id]['doctor_name'] = f"{doctor['name']} ({doctor['specialty']})"
        
        await query.edit_message_text(
            f"✅ Выбрано: {doctor['name']}\n"
            f"📌 {doctor['specialty']}\n\n"
            f"📅 Выберите дату:",
            reply_markup=date_keyboard()
        )
        return SELECTING_DATE
    
    # ========== ВЫБОР ДАТЫ ==========
    if data.startswith('date_'):
        date = data.split('_')[1]
        user_temp[user_id]['date'] = date
        
        doctor_id = user_temp[user_id]['doctor_id']
        
        await query.edit_message_text(
            f"📅 Дата: {date}\n\n"
            f"🕐 Выберите время:",
            reply_markup=time_keyboard(doctor_id, date)
        )
        return SELECTING_TIME
    
    # ========== ВЫБОР ВРЕМЕНИ ==========
    if data.startswith('time_'):
        parts = data.split('_')
        doctor_id = int(parts[1])
        date = parts[2]
        time = parts[3]
        
        user_temp[user_id]['date'] = date
        user_temp[user_id]['time'] = time
        
        await query.edit_message_text(
            f"✅ **Проверьте данные:**\n\n"
            f"📅 Дата: {date}\n"
            f"🕐 Время: {time}\n"
            f"👨‍⚕️ Врач: {user_temp[user_id]['doctor_name']}\n\n"
            f"Всё верно?",
            reply_markup=confirm_keyboard(date, time, doctor_id),
            parse_mode='Markdown'
        )
        return CONFIRMING
    
    # ========== ПОДТВЕРЖДЕНИЕ ==========
    if data.startswith('confirm_'):
        await query.message.delete()
        await context.bot.send_message(
            chat_id=user_id,
            text="✏️ **Введите ваше полное ФИО**\n\nНапример: Иванов Иван Иванович",
            parse_mode='Markdown'
        )
        return GETTING_NAME
    
    # ========== ОТМЕНА ==========
    if data == 'cancel':
        if user_id in user_temp:
            del user_temp[user_id]
        await query.edit_message_text("❌ Запись отменена", reply_markup=main_menu())
        return ConversationHandler.END
    
    # ========== НАВИГАЦИЯ ==========
    if data == 'back_doctors':
        await query.edit_message_text("👨‍⚕️ Выберите врача:", reply_markup=doctors_keyboard())
        return SELECTING_DOCTOR
    
    if data == 'back_dates':
        await query.edit_message_text("📅 Выберите дату:", reply_markup=date_keyboard())
        return SELECTING_DATE
    
    # ========== ИНФО ==========
    if data == 'doctors':
        text = "👨‍⚕️ **Наши врачи**\n\n"
        for doc in DOCTORS.values():
            text += f"**{doc['name']}**\n• {doc['specialty']}\n\n"
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode='Markdown')
    
    if data == 'about':
        text = "🏥 **О клинике**\n\nСовременная стоматология\nРаботаем с 9:00 до 20:00\nБез выходных"
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode='Markdown')
    
    if data == 'contacts':
        text = "📞 **Контакты**\n\n+7 (999) 123-45-67\nг. Москва, ул. Ленина, д. 10"
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode='Markdown')
    
    if data == 'my_appointments':
        await query.edit_message_text(
            "📋 У вас пока нет записей",
            reply_markup=main_menu()
        )
    
    return ConversationHandler.END

# ============================================================================
# ПОЛУЧЕНИЕ ФИО
# ============================================================================
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ФИО"""
    user_id = update.effective_user.id
    name = update.message.text.strip()
    
    print(f"📝 ФИО: {name} от {user_id}")
    
    if user_id not in user_temp:
        user_temp[user_id] = {}
    
    user_temp[user_id]['patient_name'] = name
    
    await update.message.reply_text(
        f"✅ Спасибо, {name.split()[0] if name.split() else ''}!\n\n"
        f"📞 **Введите номер телефона**\n"
        f"Формат: +79991234567",
        parse_mode='Markdown'
    )
    
    return GETTING_PHONE

# ============================================================================
# ПОЛУЧЕНИЕ ТЕЛЕФОНА И СОХРАНЕНИЕ
# ============================================================================
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение телефона и сохранение"""
    user_id = update.effective_user.id
    phone = update.message.text.strip()
    
    print(f"📞 Телефон: {phone} от {user_id}")
    
    # Простейшая проверка
    if not phone.startswith('+7') and not phone.startswith('8') and not phone.startswith('7'):
        await update.message.reply_text("❌ Неверный формат. Используйте +79991234567")
        return GETTING_PHONE
    
    data = user_temp.get(user_id, {})
    
    # Проверяем, что все данные есть
    if 'doctor_id' in data and 'date' in data and 'time' in data and 'patient_name' in data:
        # Сохраняем в "базу данных" (память)
        key = f"{data['doctor_id']}_{data['date']}"
        if key not in busy_slots:
            busy_slots[key] = []
        busy_slots[key].append(data['time'])
        
        # Отправляем подтверждение
        await update.message.reply_text(
            f"✅ **ЗАПИСЬ ПОДТВЕРЖДЕНА!**\n\n"
            f"📅 Дата: {data['date']}\n"
            f"🕐 Время: {data['time']}\n"
            f"👨‍⚕️ Врач: {data['doctor_name']}\n"
            f"👤 Пациент: {data['patient_name']}\n"
            f"📞 Телефон: {phone}\n\n"
            f"🔔 Напоминание придет за 2 часа",
            reply_markup=main_menu(),
            parse_mode='Markdown'
        )
        
        print(f"✅ Запись сохранена: {data['date']} {data['time']} - {data['patient_name']}")
    else:
        await update.message.reply_text(
            "❌ Ошибка данных. Начните запись заново.",
            reply_markup=main_menu()
        )
    
    # Очищаем временные данные
    if user_id in user_temp:
        del user_temp[user_id]
    
    return ConversationHandler.END

# ============================================================================
# ЗАПУСК
# ============================================================================
def main():
    print("🚀 Запуск бота...")
    
    if not TOKEN:
        print("❌ ОШИБКА: Токен не найден!")
        return
    
    app = Application.builder().token(TOKEN).build()
    
    # ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^appointment$')],
        states={
            SELECTING_DOCTOR: [
                CallbackQueryHandler(button_handler, pattern='^(doc_|back_doctors|back_menu)$')
            ],
            SELECTING_DATE: [
                CallbackQueryHandler(button_handler, pattern='^(date_|back_doctors|back_dates|back_menu)$')
            ],
            SELECTING_TIME: [
                CallbackQueryHandler(button_handler, pattern='^(time_|back_dates|back_menu)$')
            ],
            CONFIRMING: [
                CallbackQueryHandler(button_handler, pattern='^(confirm_|cancel|back_menu)$')
            ],
            GETTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)
            ],
            GETTING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
            ],
        },
        fallbacks=[],
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Бот запущен! Нажмите Ctrl+C для остановки.")
    print("="*50)
    
    app.run_polling()

if __name__ == '__main__':
    main()
