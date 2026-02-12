"""
СТОМАТОЛОГИЧЕСКИЙ БОТ - ФИНАЛЬНАЯ ВЕРСИЯ
Версия: 8.0.0 (ИСПРАВЛЕНА ОБРАБОТКА ФИО)
"""

import logging
import re
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# ============================================================================
# СОСТОЯНИЯ РАЗГОВОРА - ВАЖНО!
# ============================================================================

(
    SELECTING_DOCTOR,
    SELECTING_DATE,
    SELECTING_TIME,
    CONFIRMING,
    GETTING_NAME,
    GETTING_PHONE
) = range(6)

# ============================================================================
# ЭМОДЗИ
# ============================================================================

class Emoji:
    CHECK = "✅"
    CANCEL = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    SUCCESS = "🎉"
    ERROR = "‼️"
    WAITING = "⏳"
    BACK = "◀️"
    MENU = "📋"
    DOCTOR = "👨‍⚕️"
    DOCTOR_WOMAN = "👩‍⚕️"
    HOSPITAL = "🏥"
    TOOTH = "🦷"
    CALENDAR = "📅"
    CLOCK = "🕐"
    BELL = "🔔"
    PHONE = "📞"
    LOCATION = "📍"
    EDIT = "✏️"
    ACTIVE = "🟢"
    STAR = "⭐"
    HEART = "❤️"
    SPARKLES = "✨"
    MONEY = "💰"
    QUESTION = "❓"
    USER = "👤"
    CROWN = "👑"

# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================

@dataclass
class Doctor:
    id: str
    name: str
    specialty: str
    experience: int
    description: str
    rating: float

@dataclass
class AppointmentData:
    doctor_id: str = ""
    doctor_name: str = ""
    date: str = ""
    time: str = ""
    patient_name: str = ""
    patient_phone: str = ""

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
    
    DOCTORS = {
        '1': Doctor('1', 'Иванова Мария Петровна', 'Терапевт', 15, 'Лечение кариеса, пульпита', 4.9),
        '2': Doctor('2', 'Петров Сергей Иванович', 'Хирург', 12, 'Удаление зубов, имплантация', 4.8),
        '3': Doctor('3', 'Сидорова Анна Викторовна', 'Ортодонт', 10, 'Исправление прикуса', 4.9),
        '4': Doctor('4', 'Козлов Алексей Николаевич', 'Ортопед', 20, 'Протезирование', 5.0),
        '5': Doctor('5', 'Соколова Елена Дмитриевна', 'Детский', 8, 'Лечение детей с 3 лет', 4.9)
    }
    
    WORK_HOURS = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00']

# ============================================================================
# GOOGLE SHEETS
# ============================================================================

class GoogleSheetsManager:
    def __init__(self):
        self.sheet = None
        self.authenticate()
    
    def authenticate(self):
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            if os.path.exists('credentials.json'):
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
                client = gspread.authorize(creds)
                if Config.GOOGLE_SHEETS_ID:
                    self.sheet = client.open_by_key(Config.GOOGLE_SHEETS_ID).sheet1
                    print(f"{Emoji.CHECK} Google Sheets подключен")
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка: {e}")
    
    def add_appointment(self, date, time, doctor, patient_name, phone, telegram_id):
        try:
            if self.sheet:
                row = [date, time, doctor, patient_name, phone, str(telegram_id), 'Подтверждена', 
                       datetime.now().strftime('%d.%m.%Y %H:%M'), 'Нет']
                self.sheet.append_row(row)
                return True
        except:
            return False
        return False
    
    def get_available_slots(self, date):
        try:
            if not self.sheet:
                return Config.WORK_HOURS
            records = self.sheet.get_all_records()
            busy = [r['Время'] for r in records if r.get('Дата') == date and r.get('Статус') == 'Подтверждена']
            return [t for t in Config.WORK_HOURS if t not in busy]
        except:
            return Config.WORK_HOURS

# ============================================================================
# КЛАВИАТУРЫ
# ============================================================================

class Keyboards:
    @staticmethod
    def main_menu():
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CALENDAR} Записаться", callback_data='appointment')],
            [InlineKeyboardButton(f"{Emoji.DOCTOR} Врачи", callback_data='doctors')],
            [InlineKeyboardButton(f"{Emoji.HOSPITAL} О клинике", callback_data='about')],
            [InlineKeyboardButton(f"{Emoji.PHONE} Контакты", callback_data='contacts')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def doctors_keyboard():
        keyboard = []
        for doc_id, doctor in Config.DOCTORS.items():
            icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
            keyboard.append([InlineKeyboardButton(
                f"{icon} {doctor.name.split()[1]} - {doctor.specialty}",
                callback_data=f"doctor_{doc_id}"
            )])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def date_keyboard():
        keyboard = []
        today = datetime.now()
        for i in range(7):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            if i == 0:
                label = f"{Emoji.CALENDAR} Сегодня"
            elif i == 1:
                label = f"{Emoji.CALENDAR} Завтра"
            else:
                label = f"{Emoji.CALENDAR} {date.day}.{date.month}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"date_{date_str}")])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_doctors')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def time_keyboard(date, times):
        keyboard = []
        for time in times[:6]:
            keyboard.append([InlineKeyboardButton(time, callback_data=f"time_{date}_{time}")])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_dates')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_keyboard(date, time, doctor_id):
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CHECK} Подтвердить", callback_data=f"confirm_{date}_{time}_{doctor_id}")],
            [InlineKeyboardButton(f"{Emoji.CANCEL} Отмена", callback_data='cancel_appointment')]
        ]
        return InlineKeyboardMarkup(keyboard)

# ============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# ============================================================================

class DentalClinicBot:
    def __init__(self):
        self.config = Config()
        self.keyboards = Keyboards()
        self.google_sheets = GoogleSheetsManager()
        self.user_data = defaultdict(AppointmentData)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await update.message.reply_text(
            f"{Emoji.TOOTH} Здравствуйте, {user.first_name}!\n\n"
            f"Я помогу записаться к врачу.",
            reply_markup=self.keyboards.main_menu()
        )
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.user_data:
            del self.user_data[user_id]
        await update.message.reply_text(
            f"{Emoji.CANCEL} Действие отменено",
            reply_markup=self.keyboards.main_menu()
        )
        return ConversationHandler.END
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        # Главное меню
        if data == 'back_to_menu':
            await query.edit_message_text(
                "Главное меню:",
                reply_markup=self.keyboards.main_menu()
            )
            return ConversationHandler.END
        
        # Запись на прием
        elif data == 'appointment':
            self.user_data[user_id] = AppointmentData()
            await query.edit_message_text(
                f"{Emoji.DOCTOR} Выберите врача:",
                reply_markup=self.keyboards.doctors_keyboard()
            )
            return SELECTING_DOCTOR
        
        # Информация о врачах
        elif data == 'doctors':
            text = f"{Emoji.DOCTOR} **Наши врачи**\n\n"
            for doctor in self.config.DOCTORS.values():
                icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
                stars = Emoji.STAR * int(doctor.rating)
                text += f"{icon} **{doctor.name}**\n"
                text += f"• {doctor.specialty}\n"
                text += f"• Стаж: {doctor.experience} лет {stars}\n"
                text += f"• {doctor.description}\n\n"
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.doctors_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DOCTOR
        
        # Выбор врача
        elif data.startswith('doctor_'):
            doctor_id = data.split('_')[1]
            doctor = self.config.DOCTORS[doctor_id]
            
            self.user_data[user_id].doctor_id = doctor_id
            self.user_data[user_id].doctor_name = f"{doctor.name} ({doctor.specialty})"
            
            await query.edit_message_text(
                f"{Emoji.DOCTOR} **{doctor.name}**\n"
                f"{doctor.specialty}\n\n"
                f"{Emoji.CALENDAR} Выберите дату:",
                reply_markup=self.keyboards.date_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DATE
        
        # Выбор даты
        elif data.startswith('date_'):
            date = data.split('_')[1]
            self.user_data[user_id].date = date
            
            available_times = self.google_sheets.get_available_slots(date)
            
            if not available_times:
                await query.edit_message_text(
                    f"{Emoji.CANCEL} Нет свободного времени.\nВыберите другую дату:",
                    reply_markup=self.keyboards.date_keyboard()
                )
                return SELECTING_DATE
            
            await query.edit_message_text(
                f"{Emoji.CALENDAR} Дата: {date}\n"
                f"{Emoji.CLOCK} Выберите время:",
                reply_markup=self.keyboards.time_keyboard(date, available_times)
            )
            return SELECTING_TIME
        
        # Выбор времени
        elif data.startswith('time_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            
            self.user_data[user_id].date = date
            self.user_data[user_id].time = time
            
            await query.edit_message_text(
                f"{Emoji.CHECK} **Проверьте данные:**\n\n"
                f"📅 Дата: {date}\n"
                f"🕐 Время: {time}\n"
                f"👨‍⚕️ Врач: {self.user_data[user_id].doctor_name}\n\n"
                f"Всё верно?",
                reply_markup=self.keyboards.confirm_keyboard(
                    date, time, self.user_data[user_id].doctor_id
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONFIRMING
        
        # ========== ПОДТВЕРЖДЕНИЕ - КРИТИЧЕСКИ ВАЖНО ==========
        elif data.startswith('confirm_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            doctor_id = parts[3]
            
            # СОХРАНЯЕМ ВСЕ ДАННЫЕ
            self.user_data[user_id].date = date
            self.user_data[user_id].time = time
            self.user_data[user_id].doctor_id = doctor_id
            
            if doctor_id in self.config.DOCTORS:
                doctor = self.config.DOCTORS[doctor_id]
                self.user_data[user_id].doctor_name = f"{doctor.name} ({doctor.specialty})"
            
            # Удаляем сообщение с подтверждением
            await query.message.delete()
            
            # ОТПРАВЛЯЕМ ЗАПРОС ФИО - НОВОЕ СООБЩЕНИЕ
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"{Emoji.EDIT} **Введите ваше ФИО**\n\n"
                    f"Пример: Иванов Иван Иванович"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            
            print(f"✅ ПОДТВЕРЖДЕНИЕ: данные сохранены для {user_id}")
            print(f"📋 ДАННЫЕ: {self.user_data[user_id]}")
            
            return GETTING_NAME  # ВАЖНО: возвращаем состояние
        
        # Отмена записи
        elif data == 'cancel_appointment':
            if user_id in self.user_data:
                del self.user_data[user_id]
            await query.edit_message_text(
                f"{Emoji.CANCEL} Запись отменена",
                reply_markup=self.keyboards.main_menu()
            )
            return ConversationHandler.END
        
        # О клинике
        elif data == 'about':
            await query.edit_message_text(
                f"{Emoji.HOSPITAL} **О клинике**\n\n"
                f"• Современная стоматология\n"
                f"• Опытные врачи\n"
                f"• Безболезненное лечение\n"
                f"• Работаем 9:00-20:00 ежедневно",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Контакты
        elif data == 'contacts':
            await query.edit_message_text(
                f"{Emoji.PHONE} **Контакты**\n\n"
                f"📞 +7 (999) 123-45-67\n"
                f"{Emoji.LOCATION} Москва, ул. Ленина, д. 10\n"
                f"🚇 Метро: Парк Культуры",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Навигация
        elif data == 'back_to_doctors':
            await query.edit_message_text(
                f"{Emoji.DOCTOR} Выберите врача:",
                reply_markup=self.keyboards.doctors_keyboard()
            )
            return SELECTING_DOCTOR
        
        elif data == 'back_to_dates':
            await query.edit_message_text(
                f"{Emoji.CALENDAR} Выберите дату:",
                reply_markup=self.keyboards.date_keyboard()
            )
            return SELECTING_DATE
        
        return ConversationHandler.END
    
    # ========== ОБРАБОТЧИК ФИО - ИСПРАВЛЕН ==========
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение ФИО"""
        user_id = update.effective_user.id
        name = update.message.text.strip()
        
        print(f"📝 ПОЛУЧЕНО ФИО: '{name}' от {user_id}")
        print(f"📋 ТЕКУЩИЕ ДАННЫЕ: {self.user_data.get(user_id, 'НЕТ ДАННЫХ')}")
        
        # Проверяем наличие данных
        if user_id not in self.user_data:
            self.user_data[user_id] = AppointmentData()
            print(f"⚠️ СОЗДАНЫ НОВЫЕ ДАННЫЕ ДЛЯ {user_id}")
        
        # Валидация
        if len(name) < 5:
            await update.message.reply_text(
                f"{Emoji.CANCEL} Слишком короткое ФИО.\n"
                f"Введите полное ФИО (минимум 5 символов):"
            )
            return GETTING_NAME
        
        if any(c.isdigit() for c in name):
            await update.message.reply_text(
                f"{Emoji.CANCEL} ФИО не должно содержать цифры.\n"
                f"Введите только буквы:"
            )
            return GETTING_NAME
        
        # СОХРАНЯЕМ ФИО
        self.user_data[user_id].patient_name = name
        print(f"✅ ФИО СОХРАНЕНО: {name}")
        print(f"📋 ОБНОВЛЕННЫЕ ДАННЫЕ: {self.user_data[user_id]}")
        
        # Отправляем подтверждение и запрос телефона
        await update.message.reply_text(
            f"{Emoji.CHECK} Спасибо, {name.split()[0]}!\n\n"
            f"{Emoji.PHONE} Введите номер телефона:\n"
            f"Формат: +79991234567 или 89991234567"
        )
        
        return GETTING_PHONE  # ВАЖНО: возвращаем следующее состояние
    
    # ========== ОБРАБОТЧИК ТЕЛЕФОНА - ИСПРАВЛЕН ==========
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение телефона и сохранение записи"""
        user_id = update.effective_user.id
        phone_raw = update.message.text.strip()
        
        print(f"📞 ПОЛУЧЕН ТЕЛЕФОН: '{phone_raw}' от {user_id}")
        
        # Проверяем наличие данных
        if user_id not in self.user_data:
            await update.message.reply_text(
                f"{Emoji.ERROR} Ошибка: данные не найдены.\n"
                f"Начните запись заново.",
                reply_markup=self.keyboards.main_menu()
            )
            return ConversationHandler.END
        
        # Очищаем телефон
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone_raw)
        
        # Валидация
        if not re.match(r'^(\+7|8|7)?\d{10}$', phone_clean):
            await update.message.reply_text(
                f"{Emoji.CANCEL} Неверный формат.\n"
                f"Используйте: +79991234567 или 89991234567"
            )
            return GETTING_PHONE
        
        # Форматируем телефон
        if len(phone_clean) == 10:
            phone = f"+7{phone_clean}"
        elif phone_clean.startswith('8'):
            phone = f"+7{phone_clean[1:]}"
        elif phone_clean.startswith('7'):
            phone = f"+7{phone_clean[1:]}"
        else:
            phone = phone_clean
        
        # Получаем данные записи
        appointment = self.user_data[user_id]
        appointment.patient_phone = phone
        
        print(f"💾 СОХРАНЕНИЕ ЗАПИСИ:")
        print(f"   Дата: {appointment.date}")
        print(f"   Время: {appointment.time}")
        print(f"   Врач: {appointment.doctor_name}")
        print(f"   Пациент: {appointment.patient_name}")
        print(f"   Телефон: {phone}")
        print(f"   ID: {user_id}")
        
        # Проверяем все ли поля заполнены
        if not appointment.date or not appointment.time or not appointment.doctor_name or not appointment.patient_name:
            missing = []
            if not appointment.date: missing.append("дата")
            if not appointment.time: missing.append("время")
            if not appointment.doctor_name: missing.append("врач")
            if not appointment.patient_name: missing.append("ФИО")
            
            await update.message.reply_text(
                f"{Emoji.ERROR} Ошибка: не хватает данных ({', '.join(missing)}).\n"
                f"Начните запись заново.",
                reply_markup=self.keyboards.main_menu()
            )
            return ConversationHandler.END
        
        # Сохраняем в Google Sheets
        success = self.google_sheets.add_appointment(
            date=appointment.date,
            time=appointment.time,
            doctor=appointment.doctor_name,
            patient_name=appointment.patient_name,
            phone=phone,
            telegram_id=user_id
        )
        
        if success:
            # Сообщение об успехе
            text = (
                f"{Emoji.SUCCESS} **ЗАПИСЬ ПОДТВЕРЖДЕНА!**\n\n"
                f"{Emoji.CALENDAR} **Дата:** {appointment.date}\n"
                f"{Emoji.CLOCK} **Время:** {appointment.time}\n"
                f"{Emoji.DOCTOR} **Врач:** {appointment.doctor_name}\n"
                f"{Emoji.USER} **Пациент:** {appointment.patient_name}\n"
                f"{Emoji.PHONE} **Телефон:** {phone}\n\n"
                f"{Emoji.BELL} Напоминание придет за 2 часа до приема.\n"
                f"{Emoji.HEART} Спасибо! Ждем вас."
            )
            
            await update.message.reply_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Уведомление админам
            for admin_id in self.config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"{Emoji.BELL} **НОВАЯ ЗАПИСЬ**\n\n"
                            f"📅 {appointment.date}\n"
                            f"⏰ {appointment.time}\n"
                            f"👨‍⚕️ {appointment.doctor_name}\n"
                            f"👤 {appointment.patient_name}\n"
                            f"📞 {phone}\n"
                            f"🆔 {user_id}"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            
            print(f"{Emoji.SUCCESS} ЗАПИСЬ УСПЕШНО СОХРАНЕНА!")
        else:
            await update.message.reply_text(
                f"{Emoji.ERROR} Ошибка сохранения.\n"
                f"Позвоните нам: +7 (999) 123-45-67",
                reply_markup=self.keyboards.main_menu()
            )
            print(f"{Emoji.ERROR} ОШИБКА СОХРАНЕНИЯ В GOOGLE SHEETS")
        
        # Очищаем данные
        if user_id in self.user_data:
            del self.user_data[user_id]
            print(f"🧹 ДАННЫЕ ПОЛЬЗОВАТЕЛЯ {user_id} ОЧИЩЕНЫ")
        
        return ConversationHandler.END
    
    # ========== ЗАПУСК БОТА ==========
    def run(self):
        """Запуск бота"""
        try:
            app = Application.builder().token(self.config.BOT_TOKEN).build()
            
            # Команды
            app.add_handler(CommandHandler('start', self.start))
            app.add_handler(CommandHandler('cancel', self.cancel))
            
            # ConversationHandler - ВАЖНО: правильная структура
            conv_handler = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(self.button_handler, pattern='^appointment$')
                ],
                states={
                    SELECTING_DOCTOR: [
                        CallbackQueryHandler(self.button_handler, pattern='^(doctor_|back_to_menu|back_to_doctors|doctors)$')
                    ],
                    SELECTING_DATE: [
                        CallbackQueryHandler(self.button_handler, pattern='^(date_|back_to_doctors|back_to_menu)$')
                    ],
                    SELECTING_TIME: [
                        CallbackQueryHandler(self.button_handler, pattern='^(time_|back_to_dates|back_to_menu)$')
                    ],
                    CONFIRMING: [
                        CallbackQueryHandler(self.button_handler, pattern='^(confirm_|cancel_appointment|back_to_menu)$')
                    ],
                    GETTING_NAME: [  # ВАЖНО: состояние для ФИО
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_name)
                    ],
                    GETTING_PHONE: [  # ВАЖНО: состояние для телефона
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_phone)
                    ],
                },
                fallbacks=[
                    CommandHandler('cancel', self.cancel),
                    CallbackQueryHandler(self.button_handler, pattern='^back_to_menu$')
                ],
            )
            
            app.add_handler(conv_handler)
            
            # Обработчик всех остальных callback
            app.add_handler(CallbackQueryHandler(self.button_handler))
            
            print("\n" + "="*50)
            print("🚀 СТОМАТОЛОГИЧЕСКИЙ БОТ ЗАПУЩЕН")
            print("="*50)
            print(f"✅ Токен: {self.config.BOT_TOKEN[:10]}...")
            print(f"👨‍⚕️ Врачей: {len(self.config.DOCTORS)}")
            print(f"👑 Админов: {len(self.config.ADMIN_IDS)}")
            print(f"📊 Google Sheets: {'✅' if self.google_sheets.sheet else '❌'}")
            print("="*50 + "\n")
            
            app.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            raise

# ============================================================================
# ЗАПУСК
# ============================================================================

if __name__ == '__main__':
    try:
        bot = DentalClinicBot()
        bot.run()
    except KeyboardInterrupt:
        print(f"\n👋 Бот остановлен")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка запуска: {e}")
        sys.exit(1)
