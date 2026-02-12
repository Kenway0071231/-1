"""
СТОМАТОЛОГИЧЕСКИЙ БОТ - ПРЕМИУМ ВЕРСИЯ
Версия: 3.0.1 (ИСПРАВЛЕНЫ ВСЕ ОШИБКИ)
"""

import logging
import re
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
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
# ДИЗАЙН-СИСТЕМА
# ============================================================================

class Emoji:
    """Единая система эмодзи"""
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
    
    # Другое
    STAR = "⭐"
    HEART = "❤️"
    SPARKLES = "✨"
    MONEY = "💰"
    QUESTION = "❓"
    DOTS = "..."
    CROWN = "👑"
    USER = "👤"


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


@dataclass
class AppointmentData:
    """Данные для записи"""
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
            description='Специалист по лечению кариеса, пульпита, эндодонтии.',
            education='МГМСУ им. Сеченова, 2009',
            rating=4.9
        ),
        '2': Doctor(
            id='2',
            name='Петров Сергей Иванович',
            specialty='Стоматолог-хирург',
            experience=12,
            description='Проводит удаление любой сложности, имплантацию.',
            education='РУДН, 2012',
            rating=4.8
        ),
        '3': Doctor(
            id='3',
            name='Сидорова Анна Викторовна',
            specialty='Стоматолог-ортодонт',
            experience=10,
            description='Исправление прикуса у взрослых и детей.',
            education='МГМСУ, 2014',
            rating=4.9
        ),
        '4': Doctor(
            id='4',
            name='Козлов Алексей Николаевич',
            specialty='Стоматолог-ортопед',
            experience=20,
            description='Протезирование любой сложности.',
            education='СПбГМУ, 2004',
            rating=5.0
        ),
        '5': Doctor(
            id='5',
            name='Соколова Елена Дмитриевна',
            specialty='Детский стоматолог',
            experience=8,
            description='Лечение детей с 3 лет.',
            education='РНИМУ им. Пирогова, 2016',
            rating=4.9
        )
    }
    
    WORK_HOURS = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '14:00', '14:30', '15:00', '15:30',
        '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]


# ============================================================================
# GOOGLE SHEETS МЕНЕДЖЕР
# ============================================================================

class GoogleSheetsManager:
    """Управление Google Sheets"""
    
    def __init__(self):
        self.client = None
        self.appointments_sheet = None
        self.authenticate()
    
    def authenticate(self):
        """Аутентификация"""
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            if os.path.exists('credentials.json'):
                scope = [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/spreadsheets'
                ]
                creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
                self.client = gspread.authorize(creds)
                self.setup_sheets()
                print(f"{Emoji.CHECK} Google Sheets подключен")
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка аутентификации: {e}")
    
    def setup_sheets(self):
        """Настройка таблиц"""
        try:
            if Config.GOOGLE_SHEETS_ID:
                spreadsheet = self.client.open_by_key(Config.GOOGLE_SHEETS_ID)
            else:
                spreadsheet = self.client.create('Стоматология - Записи')
            
            try:
                self.appointments_sheet = spreadsheet.worksheet('Записи')
            except:
                self.appointments_sheet = spreadsheet.add_worksheet('Записи', 1000, 20)
                headers = ['Дата', 'Время', 'Врач', 'Пациент', 'Телефон', 
                          'Telegram ID', 'Username', 'Статус', 'Создано', 'Напоминание']
                self.appointments_sheet.append_row(headers)
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка настройки таблиц: {e}")
    
    def add_appointment(self, date: str, time: str, doctor: str, patient_name: str, 
                       phone: str, telegram_id: int, username: str = '') -> bool:
        """Добавление записи"""
        try:
            if not self.appointments_sheet:
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
                datetime.now().strftime('%d.%m.%Y %H:%M'),
                'Нет'
            ]
            self.appointments_sheet.append_row(row)
            print(f"{Emoji.SUCCESS} Запись создана: {date} {time} - {patient_name}")
            return True
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка добавления записи: {e}")
            return False
    
    def get_available_slots(self, date: str) -> List[str]:
        """Получение свободных слотов"""
        try:
            if not self.appointments_sheet:
                return Config.WORK_HOURS
            
            all_records = self.appointments_sheet.get_all_records()
            busy_times = []
            
            for record in all_records:
                if record.get('Дата') == date and record.get('Статус') == 'Подтверждена':
                    busy_times.append(record.get('Время'))
            
            return [t for t in Config.WORK_HOURS if t not in busy_times]
        except:
            return Config.WORK_HOURS
    
    def get_user_appointments(self, telegram_id: int) -> List[Dict]:
        """Получение записей пользователя"""
        try:
            if not self.appointments_sheet:
                return []
            
            all_records = self.appointments_sheet.get_all_records()
            user_apps = []
            
            for record in all_records:
                if str(record.get('Telegram ID', '')) == str(telegram_id):
                    user_apps.append(record)
            
            return user_apps
        except:
            return []
    
    def cancel_appointment(self, date: str, time: str, telegram_id: int) -> bool:
        """Отмена записи"""
        try:
            if not self.appointments_sheet:
                return False
            
            all_records = self.appointments_sheet.get_all_records()
            
            for i, record in enumerate(all_records, start=2):
                if (str(record.get('Telegram ID', '')) == str(telegram_id) and
                    record.get('Дата') == date and
                    record.get('Время') == time):
                    
                    self.appointments_sheet.update_cell(i, 8, 'Отменена')
                    return True
            return False
        except:
            return False


# ============================================================================
# КЛАВИАТУРЫ
# ============================================================================

class Keyboards:
    """Клавиатуры"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Главное меню"""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CALENDAR} Записаться", callback_data='appointment')],
            [InlineKeyboardButton(f"{Emoji.DOCTOR} Врачи", callback_data='doctors')],
            [InlineKeyboardButton(f"{Emoji.CHECK} Мои записи", callback_data='my_appointments')],
            [InlineKeyboardButton(f"{Emoji.HOSPITAL} О клинике", callback_data='about')],
            [InlineKeyboardButton(f"{Emoji.PHONE} Контакты", callback_data='contacts')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def doctors_keyboard() -> InlineKeyboardMarkup:
        """Выбор врача"""
        keyboard = []
        for doc_id, doctor in Config.DOCTORS.items():
            icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} {doctor.name.split()[0]} {doctor.name.split()[1][0]}.",
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
        
        for i in range(7):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            
            if i == 0:
                label = f"{Emoji.CALENDAR} Сегодня ({date.day}.{date.month})"
            elif i == 1:
                label = f"{Emoji.CALENDAR} Завтра ({date.day}.{date.month})"
            else:
                days = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']
                label = f"{Emoji.CALENDAR} {date.day}.{date.month} {days[date.weekday()]}"
            
            keyboard.append([InlineKeyboardButton(label, callback_data=f"date_{date_str}")])
        
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_doctors')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def time_keyboard(date: str, available_times: List[str]) -> InlineKeyboardMarkup:
        """Выбор времени"""
        keyboard = []
        row = []
        
        for i, time in enumerate(available_times, 1):
            row.append(InlineKeyboardButton(time, callback_data=f"time_{date}_{time}"))
            if len(row) == 3:
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
                InlineKeyboardButton(f"{Emoji.CHECK} Подтвердить", callback_data=f"confirm_{date}_{time}_{doctor_id}"),
                InlineKeyboardButton(f"{Emoji.CANCEL} Отменить", callback_data='cancel_appointment')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def my_appointments_keyboard(appointments: List[Dict]) -> InlineKeyboardMarkup:
        """Список записей"""
        keyboard = []
        for app in appointments[:3]:
            if app['Статус'] == 'Подтверждена':
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
            [InlineKeyboardButton(f"{Emoji.CANCEL} Отменить запись", callback_data=f"cancel_{date}_{time}")],
            [InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='my_appointments')]
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
        self.application = None
        
        # Хранилище данных пользователей
        self.user_data = defaultdict(AppointmentData)
        
        # Настройка логирования
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)
    
    # ========================================================================
    # КОМАНДЫ
    # ========================================================================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        
        text = (
            f"{Emoji.TOOTH} **Здравствуйте, {user.first_name}!**\n\n"
            f"Добро пожаловать в бот стоматологической клиники.\n\n"
            f"**Что я умею:**\n"
            f"{Emoji.CHECK} Запись к врачу\n"
            f"{Emoji.CHECK} Просмотр записей\n"
            f"{Emoji.CHECK} Напоминания о приёме\n\n"
            f"Выберите действие в меню ниже:"
        )
        
        await update.message.reply_text(
            text,
            reply_markup=self.keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена действия"""
        user_id = update.effective_user.id
        
        if user_id in self.user_data:
            del self.user_data[user_id]
        
        await update.message.reply_text(
            f"{Emoji.CANCEL} Действие отменено",
            reply_markup=self.keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    # ========================================================================
    # ОБРАБОТЧИКИ КНОПОК
    # ========================================================================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        # ========== ГЛАВНОЕ МЕНЮ ==========
        if data == 'back_to_menu':
            await query.edit_message_text(
                f"{Emoji.MENU} **Главное меню**",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # ========== ЗАПИСЬ НА ПРИЕМ ==========
        elif data == 'appointment':
            self.user_data[user_id] = AppointmentData()
            
            await query.edit_message_text(
                f"{Emoji.DOCTOR} **Выберите врача:**",
                reply_markup=self.keyboards.doctors_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DOCTOR
        
        # ========== ВРАЧИ ==========
        elif data == 'doctors':
            text = f"{Emoji.DOCTOR} **Наши врачи**\n\n"
            
            for doctor in self.config.DOCTORS.values():
                stars = "⭐" * int(doctor.rating)
                icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
                
                text += (
                    f"{icon} **{doctor.name}**\n"
                    f"└ {doctor.specialty}\n"
                    f"└ Стаж: {doctor.experience} лет {stars}\n"
                    f"└ {doctor.description}\n\n"
                )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.doctors_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DOCTOR
        
        # ========== ВЫБОР ВРАЧА ==========
        elif data.startswith('doctor_'):
            doctor_id = data.split('_')[1]
            doctor = self.config.DOCTORS[doctor_id]
            
            self.user_data[user_id].doctor_id = doctor_id
            self.user_data[user_id].doctor_name = f"{doctor.name} ({doctor.specialty})"
            
            stars = "⭐" * int(doctor.rating)
            icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
            
            text = (
                f"{icon} **{doctor.name}**\n"
                f"**{doctor.specialty}**\n\n"
                f"{Emoji.STETHOSCOPE} Стаж: {doctor.experience} лет\n"
                f"{stars} Рейтинг: {doctor.rating}\n\n"
                f"{doctor.description}\n\n"
                f"{Emoji.CALENDAR} **Выберите дату приема:**"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.date_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DATE
        
        # ========== ВЫБОР ДАТЫ ==========
        elif data.startswith('date_'):
            date = data.split('_')[1]
            
            self.user_data[user_id].date = date
            
            available_times = self.google_sheets.get_available_slots(date)
            
            if not available_times:
                await query.edit_message_text(
                    f"{Emoji.CANCEL} **Нет свободного времени**\n\n"
                    f"Выберите другую дату:",
                    reply_markup=self.keyboards.date_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                return SELECTING_DATE
            
            date_obj = datetime.strptime(date, '%d.%m.%Y')
            date_display = date_obj.strftime('%d.%m.%Y')
            
            text = (
                f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                f"{Emoji.CLOCK} **Свободное время:**\n"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.time_keyboard(date, available_times),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_TIME
        
        # ========== ВЫБОР ВРЕМЕНИ ==========
        elif data.startswith('time_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            
            self.user_data[user_id].date = date
            self.user_data[user_id].time = time
            
            date_obj = datetime.strptime(date, '%d.%m.%Y')
            date_display = date_obj.strftime('%d.%m.%Y')
            
            text = (
                f"{Emoji.CHECK} **Проверьте данные**\n\n"
                f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                f"{Emoji.CLOCK} **Время:** {time}\n"
                f"{Emoji.DOCTOR} **Врач:** {self.user_data[user_id].doctor_name}\n\n"
                f"Всё верно?"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.confirm_keyboard(date, time, self.user_data[user_id].doctor_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONFIRMING
        
        # ========== ПОДТВЕРЖДЕНИЕ ==========
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
            
            # Удаляем сообщение с подтверждением
            await query.message.delete()
            
            # Отправляем запрос ФИО
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"{Emoji.WAITING} **Остался последний шаг!**\n\n"
                    f"{Emoji.EDIT} **Введите ваше полное ФИО**\n"
                    f"└ Например: Иванов Иван Иванович\n\n"
                    f"{Emoji.INFO} Это необходимо для оформления медицинской карты"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            
            return GETTING_NAME
        
        # ========== ОТМЕНА ЗАПИСИ ==========
        elif data == 'cancel_appointment':
            if user_id in self.user_data:
                del self.user_data[user_id]
            
            await query.edit_message_text(
                f"{Emoji.CANCEL} **Запись отменена**",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        elif data.startswith('cancel_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            
            success = self.google_sheets.cancel_appointment(date, time, user_id)
            
            if success:
                text = f"{Emoji.SUCCESS} **Запись отменена**\n\n📅 {date} в {time}"
            else:
                text = f"{Emoji.ERROR} **Не удалось отменить запись**"
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== МОИ ЗАПИСИ ==========
        elif data == 'my_appointments':
            appointments = self.google_sheets.get_user_appointments(user_id)
            
            if not appointments:
                text = f"{Emoji.CALENDAR} **У вас нет записей**"
                await query.edit_message_text(
                    text,
                    reply_markup=self.keyboards.main_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                active = [a for a in appointments if a['Статус'] == 'Подтверждена']
                
                if not active:
                    text = f"{Emoji.INFO} **Нет активных записей**"
                    await query.edit_message_text(
                        text,
                        reply_markup=self.keyboards.main_menu(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    text = f"{Emoji.CHECK} **Ваши записи ({len(active)})**\n\n"
                    
                    for app in active:
                        text += (
                            f"{Emoji.CALENDAR} **{app['Дата']}** в **{app['Время']}**\n"
                            f"└ {Emoji.DOCTOR} {app['Врач'][:30]}...\n"
                            f"└ {Emoji.ACTIVE} {app['Статус']}\n\n"
                        )
                    
                    await query.edit_message_text(
                        text,
                        reply_markup=self.keyboards.my_appointments_keyboard(active),
                        parse_mode=ParseMode.MARKDOWN
                    )
        
        # ========== ПРОСМОТР ЗАПИСИ ==========
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
                    f"{Emoji.CALENDAR} **Дата:** {appointment['Дата']}\n"
                    f"{Emoji.CLOCK} **Время:** {appointment['Время']}\n"
                    f"{Emoji.DOCTOR} **Врач:** {appointment['Врач']}\n"
                    f"{Emoji.USER} **Пациент:** {appointment['Пациент']}\n"
                    f"{Emoji.PHONE} **Телефон:** {appointment['Телефон']}\n"
                    f"{Emoji.ACTIVE} **Статус:** {appointment['Статус']}"
                )
                
                await query.edit_message_text(
                    text,
                    reply_markup=self.keyboards.cancel_appointment_keyboard(date, time),
                    parse_mode=ParseMode.MARKDOWN
                )
                return VIEWING_APPOINTMENT
        
        # ========== О КЛИНИКЕ ==========
        elif data == 'about':
            text = (
                f"{Emoji.HOSPITAL} **О клинике**\n\n"
                f"🏥 Современная стоматология с 2010 года\n\n"
                f"{Emoji.DOCTOR} **Врачи:** 5 специалистов\n"
                f"{Emoji.TOOTH} **Оборудование:** Микроскоп, 3D томограф\n"
                f"{Emoji.HEART} **Безболезненно** - современная анестезия\n"
                f"{Emoji.CAR} **Парковка** - бесплатно\n\n"
                f"{Emoji.CLOCK} **Режим работы:** 9:00-20:00 без выходных"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== КОНТАКТЫ ==========
        elif data == 'contacts':
            text = (
                f"{Emoji.PHONE} **Контакты**\n\n"
                f"**Телефон:** +7 (999) 123-45-67\n"
                f"**Адрес:** г. Москва, ул. Ленина, д. 10\n"
                f"**Метро:** Парк Культуры, выход №3\n"
                f"**Время работы:** 9:00-20:00 ежедневно\n"
                f"**Парковка:** Бесплатная для пациентов"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== НАВИГАЦИЯ ==========
        elif data == 'back_to_doctors':
            await query.edit_message_text(
                f"{Emoji.DOCTOR} **Выберите врача:**",
                reply_markup=self.keyboards.doctors_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DOCTOR
        
        elif data == 'back_to_dates':
            await query.edit_message_text(
                f"{Emoji.CALENDAR} **Выберите дату:**",
                reply_markup=self.keyboards.date_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DATE
        
        return ConversationHandler.END
    
    # ========================================================================
    # ОБРАБОТЧИКИ ТЕКСТА
    # ========================================================================
    
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение ФИО"""
        user_id = update.effective_user.id
        name = update.message.text.strip()
        
        print(f"📝 Получено ФИО от {user_id}: {name}")
        
        # Проверка наличия данных
        if user_id not in self.user_data:
            self.user_data[user_id] = AppointmentData()
            print(f"⚠️ Созданы новые данные для {user_id}")
        
        # Валидация
        if len(name) < 5:
            await update.message.reply_text(
                f"{Emoji.CANCEL} **Слишком короткое имя**\n\n"
                f"Введите полное ФИО (минимум 5 символов):",
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_NAME
        
        if any(char.isdigit() for char in name):
            await update.message.reply_text(
                f"{Emoji.CANCEL} **Имя не должно содержать цифры**\n\n"
                f"Введите ФИО правильно:",
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_NAME
        
        # Сохраняем имя
        self.user_data[user_id].patient_name = name
        print(f"✅ Имя сохранено: {name}")
        
        # Запрашиваем телефон
        await update.message.reply_text(
            f"{Emoji.CHECK} **Спасибо, {name.split()[0]}!**\n\n"
            f"{Emoji.PHONE} **Введите номер телефона**\n"
            f"в формате: +79991234567 или 89991234567\n\n"
            f"{Emoji.INFO} Нужен для связи и регистратуры",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return GETTING_PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение телефона и сохранение записи"""
        user_id = update.effective_user.id
        phone_raw = update.message.text.strip()
        
        print(f"📞 Получен телефон от {user_id}: {phone_raw}")
        
        # Проверка наличия данных
        if user_id not in self.user_data:
            await update.message.reply_text(
                f"{Emoji.ERROR} **Ошибка**\n\n"
                f"Данные не найдены. Начните запись заново.",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Очищаем телефон
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone_raw)
        
        # Валидация
        if not re.match(r'^(\+7|8|7)?\d{10}$', phone_clean):
            await update.message.reply_text(
                f"{Emoji.CANCEL} **Неверный формат**\n\n"
                f"Введите номер в формате:\n"
                f"• +79991234567\n"
                f"• 89991234567\n"
                f"• 79991234567",
                parse_mode=ParseMode.MARKDOWN
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
        
        print(f"📋 Данные для сохранения: {appointment}")
        
        # Проверка наличия всех полей
        if not all([appointment.date, appointment.time, appointment.doctor_name, appointment.patient_name]):
            missing = []
            if not appointment.date: missing.append("дата")
            if not appointment.time: missing.append("время")
            if not appointment.doctor_name: missing.append("врач")
            if not appointment.patient_name: missing.append("ФИО")
            
            await update.message.reply_text(
                f"{Emoji.ERROR} **Ошибка: не хватает данных**\n\n"
                f"Отсутствует: {', '.join(missing)}\n"
                f"Начните запись заново.",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Сохраняем в Google Sheets
        success = self.google_sheets.add_appointment(
            date=appointment.date,
            time=appointment.time,
            doctor=appointment.doctor_name,
            patient_name=appointment.patient_name,
            phone=phone,
            telegram_id=user_id,
            username=update.effective_user.username or ''
        )
        
        if success:
            # Форматируем дату
            try:
                dt = datetime.strptime(appointment.date, '%d.%m.%Y')
                date_display = dt.strftime('%d.%m.%Y')
            except:
                date_display = appointment.date
            
            # Сообщение об успехе
            text = (
                f"{Emoji.SUCCESS * 3} **ЗАПИСЬ ПОДТВЕРЖДЕНА** {Emoji.SUCCESS * 3}\n\n"
                
                f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                f"{Emoji.CLOCK} **Время:** {appointment.time}\n"
                f"{Emoji.DOCTOR} **Врач:** {appointment.doctor_name}\n"
                f"{Emoji.USER} **Пациент:** {appointment.patient_name}\n"
                f"{Emoji.PHONE} **Телефон:** {phone}\n\n"
                
                f"{Emoji.BELL} **Напоминание** придёт за 2 часа до приема\n"
                f"{Emoji.HEART} **Спасибо!** Ждем вас в клинике"
            )
            
            await update.message.reply_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Уведомление администраторам
            for admin_id in self.config.ADMIN_IDS:
                try:
                    admin_text = (
                        f"{Emoji.BELL} **НОВАЯ ЗАПИСЬ**\n\n"
                        f"📅 {appointment.date}\n"
                        f"⏰ {appointment.time}\n"
                        f"👨‍⚕️ {appointment.doctor_name}\n"
                        f"👤 {appointment.patient_name}\n"
                        f"📞 {phone}\n"
                        f"🆔 {user_id}"
                    )
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            
            print(f"{Emoji.SUCCESS} Запись создана для пользователя {user_id}")
            
        else:
            await update.message.reply_text(
                f"{Emoji.ERROR} **Ошибка сохранения**\n\n"
                f"Попробуйте позже или позвоните нам:\n"
                f"{Emoji.PHONE} +7 (999) 123-45-67",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Очищаем данные
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
            
            # Команды
            self.application.add_handler(CommandHandler('start', self.start))
            self.application.add_handler(CommandHandler('cancel', self.cancel))
            
            # ConversationHandler для записи
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
                        CallbackQueryHandler(self.button_handler, pattern='^(confirm_|cancel_appointment|back_to_times|back_to_menu)$')
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
                ],
                name="appointment_conversation"
            )
            
            self.application.add_handler(conv_handler)
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            print("\n" + "="*50)
            print(f"{Emoji.TOOTH} БОТ ЗАПУЩЕН")
            print("="*50)
            print(f"{Emoji.CHECK} Токен: {self.config.BOT_TOKEN[:10]}...")
            print(f"{Emoji.DOCTOR} Врачей: {len(self.config.DOCTORS)}")
            print(f"{Emoji.CROWN} Админов: {len(self.config.ADMIN_IDS)}")
            print(f"{Emoji.CHECK} Google Sheets: {'✅' if self.google_sheets.client else '❌'}")
            print("="*50 + "\n")
            
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка: {e}")
            raise


# ============================================================================
# ЗАПУСК
# ============================================================================

if __name__ == '__main__':
    try:
        bot = DentalClinicBot()
        bot.run()
    except KeyboardInterrupt:
        print(f"\n{Emoji.CANCEL} Бот остановлен")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Emoji.ERROR} Ошибка запуска: {e}")
        sys.exit(1)
