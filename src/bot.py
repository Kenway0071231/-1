"""
СТОМАТОЛОГИЧЕСКИЙ БОТ - РАБОЧАЯ ВЕРСИЯ НА ОСНОВЕ ТЕСТА
Основан на проверенном рабочем коде
"""

import os
import sqlite3
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes

load_dotenv()

# ============================================================================
# СОСТОЯНИЯ - ТАК ЖЕ КАК В ТЕСТЕ
# ============================================================================
GETTING_NAME = 1
GETTING_PHONE = 2
SELECTING_DOCTOR = 3
SELECTING_DATE = 4
SELECTING_TIME = 5
CONFIRMING = 6

# ============================================================================
# ТОКЕН
# ============================================================================
TOKEN = os.getenv('BOT_TOKEN')

# ============================================================================
# БАЗА ДАННЫХ
# ============================================================================
def init_db():
    conn = sqlite3.connect('clinic.db')
    c = conn.cursor()
    
    # Таблица врачей
    c.execute('''CREATE TABLE IF NOT EXISTS doctors
                 (id INTEGER PRIMARY KEY, name TEXT, specialty TEXT, experience INTEGER, description TEXT, rating REAL)''')
    
    # Таблица записей
    c.execute('''CREATE TABLE IF NOT EXISTS appointments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  doctor_id INTEGER,
                  doctor_name TEXT,
                  date TEXT,
                  time TEXT,
                  patient_name TEXT,
                  patient_phone TEXT,
                  telegram_id INTEGER,
                  status TEXT,
                  created_at TEXT)''')
    
    # Добавляем врачей если их нет
    c.execute("SELECT COUNT(*) FROM doctors")
    if c.fetchone()[0] == 0:
        doctors = [
            (1, 'Иванова Мария Петровна', 'Стоматолог-терапевт', 15, 'Лечение кариеса, пульпита', 4.9),
            (2, 'Петров Сергей Иванович', 'Стоматолог-хирург', 12, 'Удаление зубов, имплантация', 4.8),
            (3, 'Сидорова Анна Викторовна', 'Стоматолог-ортодонт', 10, 'Исправление прикуса', 4.9),
            (4, 'Козлов Алексей Николаевич', 'Стоматолог-ортопед', 20, 'Протезирование', 5.0),
            (5, 'Соколова Елена Дмитриевна', 'Детский стоматолог', 8, 'Лечение детей', 4.9)
        ]
        c.executemany("INSERT INTO doctors VALUES (?,?,?,?,?,?)", doctors)
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

# ============================================================================
# РАБОЧЕЕ ВРЕМЯ
# ============================================================================
WORK_HOURS = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00']

# ============================================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ (как в тесте)
# ============================================================================
user_data = {}

# ============================================================================
# КЛАВИАТУРЫ
# ============================================================================
def get_doctors_keyboard():
    keyboard = []
    conn = sqlite3.connect('clinic.db')
    c = conn.cursor()
    c.execute("SELECT id, name, specialty FROM doctors")
    doctors = c.fetchall()
    conn.close()
    
    for doc in doctors:
        doc_id, name, specialty = doc
        short_name = name.split()[1] if len(name.split()) > 1 else name
        keyboard.append([InlineKeyboardButton(f"👨‍⚕️ {short_name} - {specialty}", callback_data=f"doc_{doc_id}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def get_date_keyboard():
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
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_doctors")])
    return InlineKeyboardMarkup(keyboard)

def get_time_keyboard(doctor_id, date):
    keyboard = []
    
    # Получаем занятое время
    conn = sqlite3.connect('clinic.db')
    c = conn.cursor()
    c.execute("SELECT time FROM appointments WHERE doctor_id = ? AND date = ? AND status = 'confirmed'", 
              (doctor_id, date))
    busy_times = [row[0] for row in c.fetchall()]
    conn.close()
    
    # Доступное время
    available = [t for t in WORK_HOURS if t not in busy_times]
    
    row = []
    for time in available[:8]:
        row.append(InlineKeyboardButton(time, callback_data=f"time_{doctor_id}_{date}_{time}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_dates")])
    return InlineKeyboardMarkup(keyboard)

def get_confirm_keyboard(date, time, doctor_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{date}_{time}_{doctor_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_appointment")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📝 Записаться на прием", callback_data="appointment")],
        [InlineKeyboardButton("👨‍⚕️ Наши врачи", callback_data="doctors_list")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_appointments")],
        [InlineKeyboardButton("🏥 О клинике", callback_data="about")],
        [InlineKeyboardButton("📞 Контакты", callback_data="contacts")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ============================================================================
# ОБРАБОТЧИКИ
# ============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"🦷 Здравствуйте, {user.first_name}!\n\n"
        f"Я бот стоматологической клиники. Помогу записаться к врачу, "
        f"посмотреть свободное время и получить напоминание о приеме.\n\n"
        f"Выберите действие:",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок - как в тесте"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    print(f"🔘 Нажата кнопка: {data}")
    
    # ========== НАЗАД В ГЛАВНОЕ МЕНЮ ==========
    if data == 'back_main':
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=main_menu()
        )
        return ConversationHandler.END
    
    # ========== ЗАПИСЬ НА ПРИЕМ ==========
    if data == 'appointment':
        user_data[user_id] = {}
        await query.edit_message_text(
            "👨‍⚕️ Выберите врача:",
            reply_markup=get_doctors_keyboard()
        )
        return SELECTING_DOCTOR
    
    # ========== ВЫБОР ВРАЧА ==========
    if data.startswith('doc_'):
        doctor_id = int(data.split('_')[1])
        
        conn = sqlite3.connect('clinic.db')
        c = conn.cursor()
        c.execute("SELECT name, specialty FROM doctors WHERE id = ?", (doctor_id,))
        doctor = c.fetchone()
        conn.close()
        
        if doctor:
            user_data[user_id]['doctor_id'] = doctor_id
            user_data[user_id]['doctor_name'] = f"{doctor[0]} ({doctor[1]})"
            
            await query.edit_message_text(
                f"👨‍⚕️ Выбрано: {doctor[0]}\n"
                f"📌 {doctor[1]}\n\n"
                f"📅 Выберите дату:",
                reply_markup=get_date_keyboard()
            )
            return SELECTING_DATE
    
    # ========== ВЫБОР ДАТЫ ==========
    if data.startswith('date_'):
        date = data.split('_')[1]
        user_data[user_id]['date'] = date
        
        doctor_id = user_data[user_id]['doctor_id']
        
        await query.edit_message_text(
            f"📅 Дата: {date}\n\n"
            f"🕐 Выберите время:",
            reply_markup=get_time_keyboard(doctor_id, date)
        )
        return SELECTING_TIME
    
    # ========== ВЫБОР ВРЕМЕНИ ==========
    if data.startswith('time_'):
        parts = data.split('_')
        doctor_id = int(parts[1])
        date = parts[2]
        time = parts[3]
        
        user_data[user_id]['date'] = date
        user_data[user_id]['time'] = time
        
        await query.edit_message_text(
            f"✅ Проверьте данные:\n\n"
            f"📅 Дата: {date}\n"
            f"🕐 Время: {time}\n"
            f"👨‍⚕️ Врач: {user_data[user_id]['doctor_name']}\n\n"
            f"Всё верно?",
            reply_markup=get_confirm_keyboard(date, time, doctor_id)
        )
        return CONFIRMING
    
    # ========== ПОДТВЕРЖДЕНИЕ - ТАК ЖЕ КАК В ТЕСТЕ ==========
    if data.startswith('confirm_'):
        # Удаляем сообщение с кнопками
        await query.message.delete()
        
        # Запрашиваем ФИО - как в тесте
        await context.bot.send_message(
            chat_id=user_id,
            text="✏️ **Введите ваше полное ФИО**\n\nНапример: Иванов Иван Иванович",
            parse_mode='Markdown'
        )
        return GETTING_NAME
    
    # ========== ОТМЕНА ==========
    if data == 'cancel_appointment':
        if user_id in user_data:
            del user_data[user_id]
        await query.edit_message_text(
            "❌ Запись отменена",
            reply_markup=main_menu()
        )
        return ConversationHandler.END
    
    # ========== НАВИГАЦИЯ ==========
    if data == 'back_doctors':
        await query.edit_message_text(
            "👨‍⚕️ Выберите врача:",
            reply_markup=get_doctors_keyboard()
        )
        return SELECTING_DOCTOR
    
    if data == 'back_dates':
        await query.edit_message_text(
            "📅 Выберите дату:",
            reply_markup=get_date_keyboard()
        )
        return SELECTING_DATE
    
    # ========== СПИСОК ВРАЧЕЙ ==========
    if data == 'doctors_list':
        conn = sqlite3.connect('clinic.db')
        c = conn.cursor()
        c.execute("SELECT name, specialty, experience, description, rating FROM doctors")
        doctors = c.fetchall()
        conn.close()
        
        text = "👨‍⚕️ **Наши врачи**\n\n"
        for doc in doctors:
            stars = "⭐" * int(doc[4])
            text += f"**{doc[0]}**\n"
            text += f"• {doc[1]}\n"
            text += f"• Стаж: {doc[2]} лет {stars}\n"
            text += f"• {doc[3]}\n\n"
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_main")
            ]]),
            parse_mode='Markdown'
        )
    
    # ========== МОИ ЗАПИСИ ==========
    if data == 'my_appointments':
        conn = sqlite3.connect('clinic.db')
        c = conn.cursor()
        c.execute("""SELECT date, time, doctor_name, status 
                     FROM appointments 
                     WHERE telegram_id = ? AND status = 'confirmed'
                     ORDER BY date, time""", (user_id,))
        apps = c.fetchall()
        conn.close()
        
        if not apps:
            text = "📋 У вас нет активных записей"
        else:
            text = "📋 **Ваши записи**\n\n"
            for app in apps:
                text += f"📅 {app[0]} в {app[1]}\n"
                text += f"👨‍⚕️ {app[2]}\n"
                text += f"✅ {app[3]}\n\n"
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_main")
            ]]),
            parse_mode='Markdown'
        )
    
    # ========== О КЛИНИКЕ ==========
    if data == 'about':
        text = (
            "🏥 **О клинике**\n\n"
            "🦷 Современная стоматология\n"
            "📅 Работаем с 2010 года\n"
            "👨‍⚕️ Опытные врачи\n"
            "💉 Безболезненное лечение\n"
            "🚗 Бесплатная парковка\n\n"
            "🕐 Режим работы: 9:00 - 20:00 (без выходных)"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_main")
            ]]),
            parse_mode='Markdown'
        )
    
    # ========== КОНТАКТЫ ==========
    if data == 'contacts':
        text = (
            "📞 **Контакты**\n\n"
            "📱 Телефон: +7 (999) 123-45-67\n"
            "📧 Email: info@dentclinic.ru\n\n"
            "📍 Адрес: г. Москва, ул. Ленина, д. 10\n"
            "🚇 Метро: Парк Культуры, выход №3\n\n"
            "🕐 Режим работы: 9:00-20:00"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_main")
            ]]),
            parse_mode='Markdown'
        )
    
    return ConversationHandler.END

# ============================================================================
# ПОЛУЧЕНИЕ ФИО - ТОЧНО ТАК ЖЕ КАК В РАБОЧЕМ ТЕСТЕ
# ============================================================================
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ФИО - как в рабочем тесте"""
    user_id = update.effective_user.id
    name = update.message.text.strip()
    
    print(f"📝 ПОЛУЧЕНО ФИО: {name} от {user_id}")
    
    # Сохраняем ФИО
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['patient_name'] = name
    
    # Запрашиваем телефон
    await update.message.reply_text(
        f"✅ Спасибо, {name.split()[0] if name.split() else ''}!\n\n"
        f"📞 **Введите номер телефона**\n"
        f"Формат: +79991234567 или 89991234567",
        parse_mode='Markdown'
    )
    
    return GETTING_PHONE

# ============================================================================
# ПОЛУЧЕНИЕ ТЕЛЕФОНА И СОХРАНЕНИЕ
# ============================================================================
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение телефона и сохранение записи"""
    user_id = update.effective_user.id
    phone_raw = update.message.text.strip()
    
    print(f"📞 ПОЛУЧЕН ТЕЛЕФОН: {phone_raw} от {user_id}")
    
    # Очищаем телефон
    phone_clean = re.sub(r'[\s\-\(\)]', '', phone_raw)
    
    # Проверка формата
    if not re.match(r'^(\+7|8|7)?\d{10}$', phone_clean):
        await update.message.reply_text(
            "❌ Неверный формат телефона\n\n"
            "Используйте: +79991234567 или 89991234567"
        )
        return GETTING_PHONE
    
    # Форматируем
    if len(phone_clean) == 10:
        phone = f"+7{phone_clean}"
    elif phone_clean.startswith('8'):
        phone = f"+7{phone_clean[1:]}"
    elif phone_clean.startswith('7'):
        phone = f"+7{phone_clean[1:]}"
    else:
        phone = phone_clean
    
    # Получаем данные
    data = user_data.get(user_id, {})
    
    # Сохраняем в базу
    try:
        conn = sqlite3.connect('clinic.db')
        c = conn.cursor()
        c.execute("""INSERT INTO appointments 
                    (doctor_id, doctor_name, date, time, patient_name, patient_phone, telegram_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (data['doctor_id'], data['doctor_name'], data['date'], data['time'],
                   data['patient_name'], phone, user_id, 'confirmed',
                   datetime.now().strftime('%d.%m.%Y %H:%M:%S')))
        conn.commit()
        conn.close()
        
        # Сообщение об успехе
        await update.message.reply_text(
            f"✅ **ЗАПИСЬ ПОДТВЕРЖДЕНА!**\n\n"
            f"📅 Дата: {data['date']}\n"
            f"🕐 Время: {data['time']}\n"
            f"👨‍⚕️ Врач: {data['doctor_name']}\n"
            f"👤 Пациент: {data['patient_name']}\n"
            f"📞 Телефон: {phone}\n\n"
            f"🔔 Напоминание придет за 2 часа до приема",
            reply_markup=main_menu(),
            parse_mode='Markdown'
        )
        
        print(f"✅ ЗАПИСЬ СОХРАНЕНА ДЛЯ {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        await update.message.reply_text(
            "❌ Ошибка при сохранении записи\n"
            "Попробуйте позже",
            reply_markup=main_menu()
        )
    
    # Очищаем временные данные
    if user_id in user_data:
        del user_data[user_id]
    
    return ConversationHandler.END

# ============================================================================
# ЗАПУСК
# ============================================================================
def main():
    """Запуск бота"""
    print("🚀 Запуск стоматологического бота...")
    
    # Инициализируем базу данных
    init_db()
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # ConversationHandler - КАК В РАБОЧЕМ ТЕСТЕ
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern='^appointment$')
        ],
        states={
            SELECTING_DOCTOR: [
                CallbackQueryHandler(button_handler, pattern='^(doc_|back_main|back_doctors|doctors_list)$')
            ],
            SELECTING_DATE: [
                CallbackQueryHandler(button_handler, pattern='^(date_|back_doctors|back_dates|back_main)$')
            ],
            SELECTING_TIME: [
                CallbackQueryHandler(button_handler, pattern='^(time_|back_dates|back_main)$')
            ],
            CONFIRMING: [
                CallbackQueryHandler(button_handler, pattern='^(confirm_|cancel_appointment|back_main)$')
            ],
            GETTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)
            ],
            GETTING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
            ],
        },
        fallbacks=[]
    )
    
    # Добавляем обработчики
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Бот запущен и готов к работе!")
    print("="*50)
    
    # Запускаем
    app.run_polling()

if __name__ == '__main__':
    main()
