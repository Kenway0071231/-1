"""
СТОМАТОЛОГИЧЕСКИЙ БОТ - ФИНАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ
Версия: 7.0.0 (ВСЕ ОШИБКИ ИСПРАВЛЕНЫ)
"""

import logging
import re
import sys
import os
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
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
# ЭМОДЗИ - ТОЛЬКО НЕОБХОДИМЫЕ, ВСЕ ОПРЕДЕЛЕНЫ
# ============================================================================

class Emoji:
    """Единая система эмодзи - ВСЕ НЕОБХОДИМЫЕ ОПРЕДЕЛЕНЫ"""
    
    # Основные
    CHECK = "✅"
    CANCEL = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    SUCCESS = "🎉"
    ERROR = "‼️"
    WAITING = "⏳"
    
    # Навигация
    BACK = "◀️"
    HOME = "🏠"
    MENU = "📋"
    
    # Медицина
    DOCTOR = "👨‍⚕️"
    DOCTOR_WOMAN = "👩‍⚕️"
    HOSPITAL = "🏥"
    TOOTH = "🦷"
    SYRINGE = "💉"
    STETHOSCOPE = "🩺"
    
    # Время
    CALENDAR = "📅"
    CLOCK = "🕐"
    BELL = "🔔"
    
    # Контакты
    PHONE = "📞"
    LOCATION = "📍"
    MAP = "🗺️"
    CAR = "🚗"
    SEARCH = "🔍"
    
    # Действия
    EDIT = "✏️"
    
    # Статусы
    ACTIVE = "🟢"
    
    # Другое - ВСЕ НЕОБХОДИМЫЕ ОПРЕДЕЛЕНЫ
    STAR = "⭐"
    HEART = "❤️"
    SPARKLES = "✨"  # БЫЛО ОТСУТСТВУЕТ - ДОБАВЛЕНО
    MONEY = "💰"
    QUESTION = "❓"
    DOTS = "..."
    CROWN = "👑"
    USER = "👤"
    STATS = "📊"    # ДОБАВЛЕНО
    BULLET = "•"    # ДОБАВЛЕНО


# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================

@dataclass
class Doctor:
    """Модель врача"""
    id: str
    name: str
    specialty: str
    experience: int
    description: str
    education: str
    rating: float
    
    def full_info(self) -> str:
        """Полная информация о враче"""
        icon = Emoji.DOCTOR_WOMAN if 'ва' in self.name else Emoji.DOCTOR
        stars = Emoji.STAR * int(self.rating)
        return (
            f"{icon} **{self.name}**\n"
            f"{Emoji.BULLET} {self.specialty}\n"
            f"{Emoji.BULLET} Стаж: {self.experience} лет\n"
            f"{Emoji.BULLET} Рейтинг: {self.rating} {stars}\n"
            f"{Emoji.BULLET} {self.description}\n"
            f"{Emoji.BULLET} {self.education}"
        )


@dataclass
class AppointmentData:
    """Данные для записи на прием"""
    doctor_id: str = ""
    doctor_name: str = ""
    date: str = ""
    time: str = ""
    patient_name: str = ""
    patient_phone: str = ""
    telegram_id: int = 0
    username: str = ""
    created_at: str = ""


# ============================================================================
# КОНФИГУРАЦИЯ - ВСЕ ЭМОДЗИ ИСПРАВЛЕНЫ
# ============================================================================

class Config:
    """Конфигурация бота"""
    
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
    
    DOCTORS = {
        '1': Doctor(
            id='1',
            name='Иванова Мария Петровна',
            specialty='Стоматолог-терапевт',
            experience=15,
            description='Лечение кариеса, пульпита, эндодонтия',
            education='МГМСУ им. Сеченова, 2009',
            rating=4.9
        ),
        '2': Doctor(
            id='2',
            name='Петров Сергей Иванович',
            specialty='Стоматолог-хирург',
            experience=12,
            description='Удаление зубов, имплантация',
            education='РУДН, 2012',
            rating=4.8
        ),
        '3': Doctor(
            id='3',
            name='Сидорова Анна Викторовна',
            specialty='Стоматолог-ортодонт',
            experience=10,
            description='Исправление прикуса, брекеты',
            education='МГМСУ, 2014',
            rating=4.9
        ),
        '4': Doctor(
            id='4',
            name='Козлов Алексей Николаевич',
            specialty='Стоматолог-ортопед',
            experience=20,
            description='Протезирование, коронки, виниры',
            education='СПбГМУ, 2004',
            rating=5.0
        ),
        '5': Doctor(
            id='5',
            name='Соколова Елена Дмитриевна',
            specialty='Детский стоматолог',
            experience=8,
            description='Лечение детей с 3 лет',
            education='РНИМУ им. Пирогова, 2016',
            rating=4.9
        )
    }
    
    WORK_HOURS = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '14:00', '14:30', '15:00', '15:30',
        '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]
    
    FAQ = {
        'Режим работы': (
            f"{Emoji.CLOCK} **Режим работы**\n\n"
            f"Ежедневно: 9:00 – 20:00\n"
            f"Без выходных\n\n"
            f"{Emoji.PHONE} Запись: +7 (999) 123-45-67"
        ),
        'Как добраться': (
            f"{Emoji.MAP} **Как нас найти**\n\n"
            f"{Emoji.LOCATION} Адрес: г. Москва, ул. Ленина, д. 10\n"
            f"{Emoji.SEARCH} Метро: Парк Культуры, выход №3\n"
            f"{Emoji.CAR} Парковка: бесплатно"
        ),
        'Стоимость услуг': (
            f"{Emoji.MONEY} **Стоимость услуг**\n\n"
            f"• Консультация: 500 ₽\n"
            f"• Лечение кариеса: от 3 000 ₽\n"
            f"• Удаление зуба: от 2 000 ₽\n"
            f"• Чистка зубов: 2 500 ₽"
        ),
        'Акции': (
            f"{Emoji.SPARKLES} **Акции**\n\n"
            f"• Скидка 10% на первое посещение\n"
            f"• Семейная скидка 15%\n"
            f"• Чистка + осмотр: 2 500 ₽"
        ),
        'Больно ли лечить': (
            f"{Emoji.HEART} **Болезненные ощущения**\n\n"
            f"• Современные анестетики\n"
            f"• Безболезненное лечение\n"
            f"• Седация (лечение во сне)"
        ),
        'Детский прием': (
            f"{Emoji.DOCTOR_WOMAN} **Детский прием**\n\n"
            f"• Возраст: с 3 лет\n"
            f"• Первый осмотр: бесплатно\n"
            f"• Адаптация в игровой форме"
        ),
        'Отмена записи': (
            f"{Emoji.CANCEL} **Отмена записи**\n\n"
            f"Отменить запись можно:\n"
            f"1. В боте (Мои записи → Отменить)\n"
            f"2. По телефону: +7 (999) 123-45-67"
        )
    }
    
    MAX_DAYS_AHEAD = 14


# ============================================================================
# GOOGLE SHEETS МЕНЕДЖЕР
# ============================================================================

class GoogleSheetsManager:
    """Управление Google Sheets"""
    
    def __init__(self):
        self.client = None
        self.sheet = None
        self.authenticate()
    
    def authenticate(self):
        """Аутентификация в Google Sheets API"""
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            if os.path.exists('credentials.json'):
                scope = [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'
                ]
                creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
                self.client = gspread.authorize(creds)
                
                if Config.GOOGLE_SHEETS_ID:
                    self.sheet = self.client.open_by_key(Config.GOOGLE_SHEETS_ID).sheet1
                    self.setup_headers()
                    print(f"{Emoji.CHECK} Google Sheets подключен")
                else:
                    print(f"{Emoji.WARNING} GOOGLE_SHEETS_ID не указан")
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка аутентификации: {e}")
    
    def setup_headers(self):
        """Настройка заголовков таблицы"""
        try:
            if self.sheet and not self.sheet.get_all_values():
                headers = [
                    'Дата', 'Время', 'Врач', 'Пациент', 'Телефон',
                    'Telegram ID', 'Username', 'Статус', 'Создано', 'Напоминание'
                ]
                self.sheet.append_row(headers)
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка настройки заголовков: {e}")
    
    def add_appointment(self, date: str, time: str, doctor: str, patient_name: str,
                       phone: str, telegram_id: int, username: str = '') -> bool:
        """Добавление новой записи"""
        try:
            if not self.sheet:
                return False
            
            row = [
                date,
                time,
                doctor,
                patient_name,
                phone,
                str(telegram_id),
                username or '-',
                'Подтверждена',
                datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                'Нет'
            ]
            self.sheet.append_row(row)
            print(f"{Emoji.SUCCESS} Запись создана: {date} {time} - {patient_name}")
            return True
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка добавления записи: {e}")
            return False
    
    def get_available_slots(self, date: str) -> List[str]:
        """Получение свободных временных слотов"""
        try:
            if not self.sheet:
                return Config.WORK_HOURS
            
            records = self.sheet.get_all_records()
            busy_times = []
            
            for record in records:
                if (record.get('Дата') == date and 
                    record.get('Статус') == 'Подтверждена'):
                    busy_times.append(record.get('Время'))
            
            available = [t for t in Config.WORK_HOURS if t not in busy_times]
            return available
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения слотов: {e}")
            return Config.WORK_HOURS
    
    def get_user_appointments(self, telegram_id: int) -> List[Dict]:
        """Получение записей пользователя"""
        try:
            if not self.sheet:
                return []
            
            records = self.sheet.get_all_records()
            user_appointments = []
            
            for record in records:
                if str(record.get('Telegram ID', '')) == str(telegram_id):
                    user_appointments.append(record)
            
            return user_appointments
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения записей: {e}")
            return []
    
    def cancel_appointment(self, date: str, time: str, telegram_id: int) -> bool:
        """Отмена записи"""
        try:
            if not self.sheet:
                return False
            
            records = self.sheet.get_all_records()
            
            for i, record in enumerate(records, start=2):
                if (str(record.get('Telegram ID', '')) == str(telegram_id) and
                    record.get('Дата') == date and
                    record.get('Время') == time):
                    
                    self.sheet.update_cell(i, 8, 'Отменена')
                    print(f"{Emoji.CHECK} Запись отменена: {date} {time}")
                    return True
            
            return False
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка отмены записи: {e}")
            return False
    
    def get_today_appointments(self) -> List[Dict]:
        """Получение записей на сегодня"""
        try:
            if not self.sheet:
                return []
            
            today = datetime.now().strftime('%d.%m.%Y')
            records = self.sheet.get_all_records()
            today_appointments = []
            
            for record in records:
                if (record.get('Дата') == today and 
                    record.get('Статус') == 'Подтверждена'):
                    today_appointments.append(record)
            
            return today_appointments
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения записей на сегодня: {e}")
            return []
    
    def mark_reminder_sent(self, date: str, time: str, telegram_id: int) -> bool:
        """Отметить отправку напоминания"""
        try:
            if not self.sheet:
                return False
            
            records = self.sheet.get_all_records()
            
            for i, record in enumerate(records, start=2):
                if (str(record.get('Telegram ID', '')) == str(telegram_id) and
                    record.get('Дата') == date and
                    record.get('Время') == time):
                    
                    sent_time = datetime.now().strftime('%d.%m.%Y %H:%M')
                    self.sheet.update_cell(i, 10, f'Отправлено {sent_time}')
                    return True
            
            return False
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка отметки напоминания: {e}")
            return False


# ============================================================================
# ПЛАНИРОВЩИК НАПОМИНАНИЙ
# ============================================================================

class ReminderScheduler:
    """Планировщик напоминаний о приеме"""
    
    def __init__(self, bot, google_sheets):
        self.bot = bot
        self.google_sheets = google_sheets
        self.scheduler = None
        self.setup()
    
    def setup(self):
        """Настройка планировщика"""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
            
            self.scheduler = AsyncIOScheduler()
            
            for hour in range(8, 21):
                self.scheduler.add_job(
                    self.send_reminders,
                    CronTrigger(hour=hour, minute=0),
                    id=f'reminder_{hour}'
                )
            
            self.scheduler.start()
            print(f"{Emoji.CHECK} Планировщик напоминаний запущен")
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка настройки планировщика: {e}")
    
    async def send_reminders(self):
        """Отправка напоминаний"""
        try:
            appointments = self.google_sheets.get_today_appointments()
            
            for appointment in appointments:
                if 'Отправлено' in str(appointment.get('Напоминание', '')):
                    continue
                
                telegram_id = int(appointment.get('Telegram ID', 0))
                time_str = appointment.get('Время', '')
                patient_name = appointment.get('Пациент', '')
                doctor = appointment.get('Врач', '')
                
                try:
                    appointment_time = datetime.strptime(time_str, '%H:%M')
                    now = datetime.now()
                    appointment_datetime = now.replace(
                        hour=appointment_time.hour,
                        minute=appointment_time.minute,
                        second=0
                    )
                    
                    time_diff = (appointment_datetime - now).total_seconds() / 3600
                    
                    if 1.5 <= time_diff <= 2.5:
                        message = (
                            f"{Emoji.BELL} **Напоминание о приеме!**\n\n"
                            f"Здравствуйте, {patient_name}!\n\n"
                            f"{Emoji.CLOCK} **Время:** {time_str}\n"
                            f"{Emoji.DOCTOR} **Врач:** {doctor}\n"
                            f"{Emoji.LOCATION} **Адрес:** г. Москва, ул. Ленина, д. 10\n\n"
                            f"{Emoji.INFO} Ждем вас!"
                        )
                        
                        await self.bot.send_message(
                            chat_id=telegram_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        
                        self.google_sheets.mark_reminder_sent(
                            appointment.get('Дата'),
                            appointment.get('Время'),
                            telegram_id
                        )
                except Exception as e:
                    print(f"{Emoji.ERROR} Ошибка отправки: {e}")
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка в планировщике: {e}")


# ============================================================================
# КЛАВИАТУРЫ
# ============================================================================

class Keyboards:
    """Клавиатуры для бота"""
    
    @staticmethod
    def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
        """Главное меню"""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CALENDAR} Записаться", callback_data='appointment')],
            [InlineKeyboardButton(f"{Emoji.DOCTOR} Врачи", callback_data='doctors')],
            [InlineKeyboardButton(f"{Emoji.QUESTION} Вопросы", callback_data='faq')],
            [InlineKeyboardButton(f"{Emoji.CHECK} Мои записи", callback_data='my_appointments')],
            [InlineKeyboardButton(f"{Emoji.HOSPITAL} О клинике", callback_data='about')],
            [InlineKeyboardButton(f"{Emoji.PHONE} Контакты", callback_data='contacts')]
        ]
        if is_admin:
            keyboard.append([InlineKeyboardButton(f"{Emoji.CROWN} Админ", callback_data='admin')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def doctors_keyboard() -> InlineKeyboardMarkup:
        """Выбор врача"""
        keyboard = []
        for doc_id, doctor in Config.DOCTORS.items():
            icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} {doctor.name.split()[1]}",
                    callback_data=f"doctor_{doc_id}"
                )
            ])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def date_keyboard() -> InlineKeyboardMarkup:
        """Выбор даты"""
        keyboard = []
        today = datetime.now()
        
        for i in range(Config.MAX_DAYS_AHEAD):
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
    def time_keyboard(date: str, times: List[str]) -> InlineKeyboardMarkup:
        """Выбор времени"""
        keyboard = []
        row = []
        
        for i, time in enumerate(times[:8], 1):
            row.append(InlineKeyboardButton(time, callback_data=f"time_{date}_{time}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_dates')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_keyboard(date: str, time: str, doctor_id: str) -> InlineKeyboardMarkup:
        """Подтверждение записи"""
        keyboard = [
            [
                InlineKeyboardButton(f"{Emoji.CHECK} Подтвердить", 
                                    callback_data=f"confirm_{date}_{time}_{doctor_id}"),
                InlineKeyboardButton(f"{Emoji.CANCEL} Отмена", 
                                    callback_data='cancel_appointment')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def faq_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура FAQ"""
        keyboard = []
        for question in Config.FAQ.keys():
            keyboard.append([
                InlineKeyboardButton(f"{Emoji.QUESTION} {question}", 
                                    callback_data=f"faq_{question}")
            ])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def my_appointments_keyboard(appointments: List[Dict]) -> InlineKeyboardMarkup:
        """Список записей пользователя"""
        keyboard = []
        for app in appointments[:3]:
            keyboard.append([
                InlineKeyboardButton(
                    f"{Emoji.CALENDAR} {app['Дата']} {app['Время']}",
                    callback_data=f"view_{app['Дата']}_{app['Время']}"
                )
            ])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def cancel_appointment_keyboard(date: str, time: str) -> InlineKeyboardMarkup:
        """Отмена записи"""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CANCEL} Отменить запись", 
                                 callback_data=f"cancel_{date}_{time}")],
            [InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='my_appointments')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_keyboard() -> InlineKeyboardMarkup:
        """Админ-панель"""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CALENDAR} Записи на сегодня", callback_data='admin_today')],
            [InlineKeyboardButton(f"{Emoji.STATS} Статистика", callback_data='admin_stats')],
            [InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')]
        ]
        return InlineKeyboardMarkup(keyboard)


# ============================================================================
# СОСТОЯНИЯ РАЗГОВОРА
# ============================================================================

(
    SELECTING_DOCTOR,
    SELECTING_DATE,
    SELECTING_TIME,
    CONFIRMING,
    GETTING_NAME,
    GETTING_PHONE,
    VIEWING_APPOINTMENT
) = range(7)


# ============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# ============================================================================

class DentalClinicBot:
    """Бот стоматологической клиники"""
    
    def __init__(self):
        self.config = Config()
        self.keyboards = Keyboards()
        self.google_sheets = GoogleSheetsManager()
        self.reminder_scheduler = None
        self.application = None
        self.user_data = defaultdict(AppointmentData)
        
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        is_admin = user.id in self.config.ADMIN_IDS
        
        text = (
            f"{Emoji.TOOTH} **Здравствуйте, {user.first_name}!**\n\n"
            f"Я помогу вам записаться к врачу.\n\n"
            f"{Emoji.CLOCK} Работаем: 9:00-20:00 ежедневно\n"
            f"{Emoji.LOCATION} Москва, ул. Ленина, д. 10"
        )
        
        await update.message.reply_text(
            text,
            reply_markup=self.keyboards.main_menu(is_admin),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена действия"""
        user_id = update.effective_user.id
        if user_id in self.user_data:
            del self.user_data[user_id]
        
        is_admin = user_id in self.config.ADMIN_IDS
        await update.message.reply_text(
            f"{Emoji.CANCEL} Действие отменено",
            reply_markup=self.keyboards.main_menu(is_admin)
        )
        return ConversationHandler.END
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        is_admin = user_id in self.config.ADMIN_IDS
        
        # Главное меню
        if data == 'back_to_menu':
            await query.edit_message_text(
                "Главное меню:",
                reply_markup=self.keyboards.main_menu(is_admin)
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
                text += doctor.full_info() + "\n\n"
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
                f"{doctor.full_info()}\n\n{Emoji.CALENDAR} Выберите дату:",
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
                    f"{Emoji.CANCEL} Нет свободного времени. Выберите другую дату:",
                    reply_markup=self.keyboards.date_keyboard()
                )
                return SELECTING_DATE
            
            await query.edit_message_text(
                f"{Emoji.CALENDAR} Дата: {date}\n{Emoji.CLOCK} Выберите время:",
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
                f"{Emoji.CALENDAR} Дата: {date}\n"
                f"{Emoji.CLOCK} Время: {time}\n"
                f"{Emoji.DOCTOR} Врач: {self.user_data[user_id].doctor_name}\n\n"
                f"Всё верно?",
                reply_markup=self.keyboards.confirm_keyboard(
                    date, time, self.user_data[user_id].doctor_id
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONFIRMING
        
        # Подтверждение записи - ВАЖНО!
        elif data.startswith('confirm_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            doctor_id = parts[3]
            
            self.user_data[user_id].date = date
            self.user_data[user_id].time = time
            self.user_data[user_id].doctor_id = doctor_id
            
            if doctor_id in self.config.DOCTORS:
                doctor = self.config.DOCTORS[doctor_id]
                self.user_data[user_id].doctor_name = f"{doctor.name} ({doctor.specialty})"
            
            await query.message.delete()
            
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"{Emoji.EDIT} **Введите ваше ФИО**\n\n"
                    f"Пример: Иванов Иван Иванович"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_NAME
        
        # Отмена записи
        elif data == 'cancel_appointment':
            if user_id in self.user_data:
                del self.user_data[user_id]
            await query.edit_message_text(
                f"{Emoji.CANCEL} Запись отменена",
                reply_markup=self.keyboards.main_menu(is_admin)
            )
            return ConversationHandler.END
        
        elif data.startswith('cancel_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            
            success = self.google_sheets.cancel_appointment(date, time, user_id)
            
            if success:
                text = f"{Emoji.SUCCESS} Запись отменена\n{date} {time}"
            else:
                text = f"{Emoji.ERROR} Не удалось отменить запись"
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(is_admin)
            )
        
        # Мои записи
        elif data == 'my_appointments':
            appointments = self.google_sheets.get_user_appointments(user_id)
            
            if not appointments:
                await query.edit_message_text(
                    f"{Emoji.INFO} У вас нет записей",
                    reply_markup=self.keyboards.main_menu(is_admin)
                )
            else:
                active = [a for a in appointments if a.get('Статус') == 'Подтверждена']
                
                if not active:
                    await query.edit_message_text(
                        f"{Emoji.INFO} Нет активных записей",
                        reply_markup=self.keyboards.main_menu(is_admin)
                    )
                else:
                    text = f"{Emoji.CHECK} Ваши записи:\n\n"
                    for app in active[:3]:
                        text += f"{Emoji.CALENDAR} {app['Дата']} {app['Время']}\n"
                        text += f"{Emoji.DOCTOR} {app['Врач'][:30]}...\n\n"
                    
                    await query.edit_message_text(
                        text,
                        reply_markup=self.keyboards.my_appointments_keyboard(active)
                    )
        
        # Просмотр записи
        elif data.startswith('view_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            
            appointments = self.google_sheets.get_user_appointments(user_id)
            appointment = None
            
            for app in appointments:
                if app['Дата'] == date and app['Время'] == time:
                    appointment = app
                    break
            
            if appointment:
                text = (
                    f"{Emoji.CHECK} **Детали записи**\n\n"
                    f"{Emoji.CALENDAR} Дата: {appointment['Дата']}\n"
                    f"{Emoji.CLOCK} Время: {appointment['Время']}\n"
                    f"{Emoji.DOCTOR} Врач: {appointment['Врач'][:40]}...\n"
                    f"{Emoji.USER} Пациент: {appointment['Пациент']}\n"
                    f"{Emoji.PHONE} Телефон: {appointment['Телефон']}\n"
                    f"{Emoji.ACTIVE} Статус: {appointment['Статус']}"
                )
                
                await query.edit_message_text(
                    text,
                    reply_markup=self.keyboards.cancel_appointment_keyboard(date, time),
                    parse_mode=ParseMode.MARKDOWN
                )
                return VIEWING_APPOINTMENT
        
        # FAQ
        elif data == 'faq':
            await query.edit_message_text(
                f"{Emoji.QUESTION} Часто задаваемые вопросы:",
                reply_markup=self.keyboards.faq_keyboard()
            )
        
        elif data.startswith('faq_'):
            question = data[4:]
            answer = self.config.FAQ.get(question, "Информация недоступна")
            await query.edit_message_text(
                f"**{question}**\n\n{answer}",
                reply_markup=self.keyboards.faq_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # О клинике
        elif data == 'about':
            text = (
                f"{Emoji.HOSPITAL} **О клинике**\n\n"
                f"• Современная стоматология с 2010\n"
                f"• 5 опытных врачей\n"
                f"• Безболезненное лечение\n"
                f"• Бесплатная парковка\n\n"
                f"{Emoji.CLOCK} 9:00-20:00 без выходных"
            )
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(is_admin),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Контакты
        elif data == 'contacts':
            text = (
                f"{Emoji.PHONE} **Контакты**\n\n"
                f"📞 +7 (999) 123-45-67\n"
                f"{Emoji.LOCATION} Москва, ул. Ленина, д. 10\n"
                f"{Emoji.MAP} Метро: Парк Культуры\n"
                f"{Emoji.CAR} Парковка: бесплатно"
            )
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(is_admin),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Админ-панель
        elif data == 'admin':
            if not is_admin:
                await query.edit_message_text(f"{Emoji.ERROR} Доступ запрещен")
                return
            
            await query.edit_message_text(
                f"{Emoji.CROWN} Панель администратора:",
                reply_markup=self.keyboards.admin_keyboard()
            )
        
        elif data == 'admin_today':
            if not is_admin:
                return
            
            appointments = self.google_sheets.get_today_appointments()
            
            if not appointments:
                text = f"{Emoji.CALENDAR} На сегодня записей нет"
            else:
                text = f"{Emoji.CALENDAR} Записи на сегодня ({len(appointments)}):\n\n"
                for app in appointments:
                    text += f"{Emoji.CLOCK} {app['Время']} - {app['Пациент']}\n"
                    text += f"{Emoji.DOCTOR} {app['Врач'][:30]}...\n\n"
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.admin_keyboard()
            )
        
        elif data == 'admin_stats':
            if not is_admin:
                return
            
            all_records = self.google_sheets.sheet.get_all_records() if self.google_sheets.sheet else []
            today = datetime.now().strftime('%d.%m.%Y')
            
            total = len(all_records)
            confirmed = len([r for r in all_records if r.get('Статус') == 'Подтверждена'])
            today_count = len([r for r in all_records if r.get('Дата') == today])
            
            text = (
                f"{Emoji.STATS} **Статистика**\n\n"
                f"📊 Всего записей: {total}\n"
                f"{Emoji.CHECK} Активных: {confirmed}\n"
                f"{Emoji.CALENDAR} На сегодня: {today_count}\n"
                f"{Emoji.DOCTOR} Врачей: {len(self.config.DOCTORS)}\n\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.admin_keyboard(),
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
    
    # ========================================================================
    # ОБРАБОТЧИКИ ТЕКСТА - ИСПРАВЛЕНЫ
    # ========================================================================
    
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение ФИО пациента"""
        user_id = update.effective_user.id
        name = update.message.text.strip()
        
        print(f"📝 ПОЛУЧЕНО ФИО: {name}")
        
        if user_id not in self.user_data:
            self.user_data[user_id] = AppointmentData()
        
        if len(name) < 5:
            await update.message.reply_text(
                f"{Emoji.CANCEL} Слишком короткое ФИО.\n"
                f"Пример: Иванов Иван Иванович"
            )
            return GETTING_NAME
        
        if any(c.isdigit() for c in name):
            await update.message.reply_text(
                f"{Emoji.CANCEL} ФИО не должно содержать цифры.\n"
                f"Введите только буквы:"
            )
            return GETTING_NAME
        
        self.user_data[user_id].patient_name = name
        print(f"✅ ФИО СОХРАНЕНО: {name}")
        
        await update.message.reply_text(
            f"{Emoji.CHECK} Спасибо, {name.split()[0]}!\n\n"
            f"{Emoji.PHONE} Введите номер телефона:\n"
            f"+79991234567 или 89991234567"
        )
        
        return GETTING_PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение телефона и сохранение записи"""
        user_id = update.effective_user.id
        phone_raw = update.message.text.strip()
        
        print(f"📞 ПОЛУЧЕН ТЕЛЕФОН: {phone_raw}")
        
        if user_id not in self.user_data:
            await update.message.reply_text(
                f"{Emoji.ERROR} Ошибка. Начните запись заново.",
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS)
            )
            return ConversationHandler.END
        
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone_raw)
        
        if not re.match(r'^(\+7|8|7)?\d{10}$', phone_clean):
            await update.message.reply_text(
                f"{Emoji.CANCEL} Неверный формат.\n"
                f"Используйте: +79991234567 или 89991234567"
            )
            return GETTING_PHONE
        
        if len(phone_clean) == 10:
            phone = f"+7{phone_clean}"
        elif phone_clean.startswith('8'):
            phone = f"+7{phone_clean[1:]}"
        elif phone_clean.startswith('7'):
            phone = f"+7{phone_clean[1:]}"
        else:
            phone = phone_clean
        
        appointment = self.user_data[user_id]
        appointment.patient_phone = phone
        appointment.telegram_id = user_id
        appointment.username = update.effective_user.username or ''
        
        print(f"💾 СОХРАНЕНИЕ В GOOGLE SHEETS:")
        print(f"   {appointment.date} {appointment.time}")
        print(f"   {appointment.doctor_name}")
        print(f"   {appointment.patient_name} {phone}")
        
        success = self.google_sheets.add_appointment(
            date=appointment.date,
            time=appointment.time,
            doctor=appointment.doctor_name,
            patient_name=appointment.patient_name,
            phone=phone,
            telegram_id=user_id,
            username=appointment.username
        )
        
        if success:
            text = (
                f"{Emoji.SUCCESS} **ЗАПИСЬ ПОДТВЕРЖДЕНА!**\n\n"
                f"{Emoji.CALENDAR} Дата: {appointment.date}\n"
                f"{Emoji.CLOCK} Время: {appointment.time}\n"
                f"{Emoji.DOCTOR} Врач: {appointment.doctor_name}\n"
                f"{Emoji.USER} Пациент: {appointment.patient_name}\n\n"
                f"{Emoji.BELL} Напоминание придет за 2 часа\n"
                f"{Emoji.HEART} Спасибо! Ждем вас."
            )
            
            await update.message.reply_text(
                text,
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS),
                parse_mode=ParseMode.MARKDOWN
            )
            
            for admin_id in self.config.ADMIN_IDS:
                try:
                    admin_text = (
                        f"{Emoji.BELL} НОВАЯ ЗАПИСЬ\n\n"
                        f"📅 {appointment.date}\n"
                        f"⏰ {appointment.time}\n"
                        f"👨‍⚕️ {appointment.doctor_name}\n"
                        f"👤 {appointment.patient_name}\n"
                        f"📞 {phone}\n"
                        f"🆔 {user_id}"
                    )
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text
                    )
                except:
                    pass
            
            print(f"{Emoji.SUCCESS} ЗАПИСЬ СОХРАНЕНА")
        else:
            await update.message.reply_text(
                f"{Emoji.ERROR} Ошибка сохранения. Позвоните нам:\n"
                f"{Emoji.PHONE} +7 (999) 123-45-67",
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS)
            )
        
        if user_id in self.user_data:
            del self.user_data[user_id]
        
        return ConversationHandler.END
    
    # ========================================================================
    # ЗАПУСК БОТА
    # ========================================================================
    
    def run(self):
        """Запуск бота"""
        try:
            self.application = Application.builder().token(self.config.BOT_TOKEN).build()
            
            self.application.add_handler(CommandHandler('start', self.start))
            self.application.add_handler(CommandHandler('cancel', self.cancel))
            
            conv_handler = ConversationHandler(
                entry_points=[CallbackQueryHandler(self.button_handler, pattern='^appointment$')],
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
                    GETTING_NAME: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_name)
                    ],
                    GETTING_PHONE: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_phone)
                    ],
                    VIEWING_APPOINTMENT: [
                        CallbackQueryHandler(self.button_handler, pattern='^(cancel_|my_appointments|back_to_menu)$')
                    ]
                },
                fallbacks=[
                    CommandHandler('cancel', self.cancel),
                    CallbackQueryHandler(self.button_handler, pattern='^back_to_menu$')
                ]
            )
            
            self.application.add_handler(conv_handler)
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            if self.google_sheets.client:
                self.reminder_scheduler = ReminderScheduler(self.application.bot, self.google_sheets)
            
            print("\n" + "="*50)
            print("🚀 СТОМАТОЛОГИЧЕСКИЙ БОТ ЗАПУЩЕН")
            print("="*50)
            print(f"✅ Токен: {self.config.BOT_TOKEN[:10]}...")
            print(f"👨‍⚕️ Врачей: {len(self.config.DOCTORS)}")
            print(f"👑 Админов: {len(self.config.ADMIN_IDS)}")
            print(f"📊 Google Sheets: {'✅' if self.google_sheets.client else '❌'}")
            print("="*50 + "\n")
            
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
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
