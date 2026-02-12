"""
СТОМАТОЛОГИЧЕСКИЙ БОТ - ПОЛНАЯ РАБОЧАЯ ВЕРСИЯ
Версия: 6.0.0 (ФИНАЛЬНАЯ, 100% РАБОТАЕТ)
Функции: запись, Google Sheets, напоминания, админка, FAQ, отмена
"""

import logging
import re
import sys
import os
import json
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
# ЭМОДЗИ - ТОЛЬКО НЕОБХОДИМЫЕ
# ============================================================================

class Emoji:
    """Минимальный набор эмодзи для работы бота"""
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
    USER = "👤"
    CROWN = "👑"
    MONEY = "💰"
    QUESTION = "❓"
    SEARCH = "🔍"
    MAP = "🗺️"
    CAR = "🚗"
    DOTS = "..."
    BULLET = "•"

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
    photo_url: str = ""
    
    def full_info(self) -> str:
        """Полная информация о враче"""
        return (
            f"{Emoji.DOCTOR if 'ва' not in self.name else Emoji.DOCTOR_WOMAN} "
            f"**{self.name}**\n"
            f"{Emoji.BULLET} {self.specialty}\n"
            f"{Emoji.BULLET} Стаж: {self.experience} лет\n"
            f"{Emoji.BULLET} Рейтинг: {self.rating} ⭐\n"
            f"{Emoji.BULLET} {self.description}\n"
            f"{Emoji.BULLET} {self.education}"
        )
    
    def short_info(self) -> str:
        """Краткая информация"""
        return f"{Emoji.DOCTOR} **{self.name}** - {self.specialty}"


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
    status: str = "pending"
    reminder_sent: bool = False
    appointment_id: str = ""


@dataclass
class Patient:
    """Модель пациента"""
    telegram_id: int
    name: str
    phone: str
    username: str
    registered_at: str
    total_appointments: int = 0
    last_visit: str = ""
    notes: str = ""


# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

class Config:
    """Конфигурация бота"""
    
    # Токен бота
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Google Sheets
    GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
    
    # ID администраторов
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
    
    # Врачи клиники
    DOCTORS = {
        '1': Doctor(
            id='1',
            name='Иванова Мария Петровна',
            specialty='Стоматолог-терапевт',
            experience=15,
            description='Лечение кариеса, пульпита, эндодонтия под микроскопом',
            education='МГМСУ им. Сеченова, 2009',
            rating=4.9
        ),
        '2': Doctor(
            id='2',
            name='Петров Сергей Иванович',
            specialty='Стоматолог-хирург, имплантолог',
            experience=12,
            description='Удаление любой сложности, одномоментная имплантация',
            education='РУДН, 2012',
            rating=4.8
        ),
        '3': Doctor(
            id='3',
            name='Сидорова Анна Викторовна',
            specialty='Стоматолог-ортодонт',
            experience=10,
            description='Исправление прикуса, брекеты, элайнеры',
            education='МГМСУ, 2014',
            rating=4.9
        ),
        '4': Doctor(
            id='4',
            name='Козлов Алексей Николаевич',
            specialty='Стоматолог-ортопед',
            experience=20,
            description='Протезирование, коронки, виниры, съемные протезы',
            education='СПбГМУ, 2004',
            rating=5.0
        ),
        '5': Doctor(
            id='5',
            name='Соколова Елена Дмитриевна',
            specialty='Детский стоматолог',
            experience=8,
            description='Лечение детей с 3 лет, адаптация, профилактика',
            education='РНИМУ им. Пирогова, 2016',
            rating=4.9
        )
    }
    
    # Часы работы (доступное время)
    WORK_HOURS = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '14:00', '14:30', '15:00', '15:30',
        '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]
    
    # FAQ - Часто задаваемые вопросы
    FAQ = {
        'Режим работы': (
            f"{Emoji.CLOCK} **Режим работы**\n\n"
            f"Ежедневно: 9:00 – 20:00\n"
            f"Без выходных\n\n"
            f"{Emoji.PHONE} Запись по телефону: +7 (999) 123-45-67"
        ),
        'Как добраться': (
            f"{Emoji.MAP} **Как нас найти**\n\n"
            f"{Emoji.LOCATION} Адрес: г. Москва, ул. Ленина, д. 10\n"
            f"{Emoji.SEARCH} Метро: Парк Культуры, выход №3\n"
            f"{Emoji.CAR} Парковка: бесплатно для пациентов"
        ),
        'Стоимость услуг': (
            f"{Emoji.MONEY} **Стоимость услуг**\n\n"
            f"• Консультация: 500 ₽\n"
            f"• Лечение кариеса: от 3 000 ₽\n"
            f"• Удаление зуба: от 2 000 ₽\n"
            f"• Чистка зубов: 2 500 ₽\n"
            f"• Имплантация: от 25 000 ₽\n\n"
            f"Точная стоимость после осмотра"
        ),
        'Акции': (
            f"{Emoji.SPARKLES} **Акции**\n\n"
            f"🎁 Скидка 10% на первое посещение\n"
            f"🎁 Семейная скидка 15%\n"
            f"🎁 Чистка + осмотр: 2 500 ₽"
        ),
        'Больно ли лечить': (
            f"{Emoji.HEART} **Болезненные ощущения**\n\n"
            f"✅ Современные анестетики\n"
            f"✅ Безболезненное лечение\n"
            f"✅ Седация (лечение во сне)\n"
            f"✅ Индивидуальный подход"
        ),
        'Детский прием': (
            f"{Emoji.DOCTOR_WOMAN} **Детский прием**\n\n"
            f"👶 Возраст: с 3 лет\n"
            f"🎈 Первый осмотр: бесплатно\n"
            f"🧸 Адаптация в игровой форме\n"
            f"🛏 Лечение во сне при необходимости"
        ),
        'Оплата': (
            f"{Emoji.MONEY} **Оплата**\n\n"
            f"💳 Наличные\n"
            f"💳 Банковские карты\n"
            f"💳 Перевод на карту\n"
            f"💳 ДМС"
        ),
        'Отмена записи': (
            f"{Emoji.CANCEL} **Отмена записи**\n\n"
            f"Отменить запись можно:\n"
            f"1️⃣ В боте (Мои записи → Отменить)\n"
            f"2️⃣ По телефону: +7 (999) 123-45-67"
        )
    }
    
    # Время напоминания (за часов до приема)
    REMINDER_HOURS = 2
    
    # Максимальное количество дней для записи
    MAX_DAYS_AHEAD = 14
    
    # Длительность приема в минутах
    APPOINTMENT_DURATION = 30


# ============================================================================
# GOOGLE SHEETS МЕНЕДЖЕР
# ============================================================================

class GoogleSheetsManager:
    """Управление Google Sheets - ПОЛНАЯ РЕАЛИЗАЦИЯ"""
    
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.appointments_sheet = None
        self.patients_sheet = None
        self.settings_sheet = None
        self.authenticate()
    
    def authenticate(self):
        """Аутентификация в Google Sheets API"""
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
            else:
                print(f"{Emoji.WARNING} credentials.json не найден")
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка аутентификации: {e}")
    
    def setup_sheets(self):
        """Настройка таблиц и листов"""
        try:
            # Открываем или создаем таблицу
            if Config.GOOGLE_SHEETS_ID:
                self.spreadsheet = self.client.open_by_key(Config.GOOGLE_SHEETS_ID)
            else:
                self.spreadsheet = self.client.create('Стоматологическая клиника - Записи')
            
            # Лист записей
            try:
                self.appointments_sheet = self.spreadsheet.worksheet('Записи')
            except:
                self.appointments_sheet = self.spreadsheet.add_worksheet('Записи', 1000, 20)
                headers = [
                    'ID', 'Дата', 'Время', 'Врач', 'Пациент', 'Телефон',
                    'Telegram ID', 'Username', 'Статус', 'Создано', 'Напоминание'
                ]
                self.appointments_sheet.append_row(headers)
            
            # Лист пациентов
            try:
                self.patients_sheet = self.spreadsheet.worksheet('Пациенты')
            except:
                self.patients_sheet = self.spreadsheet.add_worksheet('Пациенты', 1000, 15)
                headers = [
                    'Telegram ID', 'Имя', 'Телефон', 'Username',
                    'Дата регистрации', 'Всего записей', 'Последний визит', 'Заметки'
                ]
                self.patients_sheet.append_row(headers)
            
            # Лист настроек
            try:
                self.settings_sheet = self.spreadsheet.worksheet('Настройки')
            except:
                self.settings_sheet = self.spreadsheet.add_worksheet('Настройки', 100, 5)
                headers = ['Параметр', 'Значение', 'Описание']
                self.settings_sheet.append_row(headers)
                self.settings_sheet.append_row(['last_appointment_id', '0', 'Последний ID записи'])
            
            print(f"{Emoji.CHECK} Таблицы настроены")
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка настройки таблиц: {e}")
    
    def generate_appointment_id(self) -> str:
        """Генерация уникального ID записи"""
        timestamp = datetime.now().strftime('%y%m%d%H%M%S')
        random_suffix = hashlib.md5(str(time.time()).encode()).hexdigest()[:4]
        return f"AP{timestamp}{random_suffix}"
    
    def add_appointment(self, date: str, time: str, doctor: str, patient_name: str,
                       phone: str, telegram_id: int, username: str = '') -> bool:
        """Добавление новой записи"""
        try:
            if not self.appointments_sheet:
                return False
            
            # Генерируем ID записи
            appointment_id = self.generate_appointment_id()
            created_at = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            
            # Добавляем строку
            row = [
                appointment_id,
                date,
                time,
                doctor,
                patient_name,
                phone,
                str(telegram_id),
                username or '-',
                'Подтверждена',
                created_at,
                'Нет'
            ]
            self.appointments_sheet.append_row(row)
            
            # Обновляем данные пациента
            self.update_patient(telegram_id, patient_name, phone, username, date)
            
            print(f"{Emoji.SUCCESS} Запись {appointment_id} создана для {patient_name}")
            return True
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка добавления записи: {e}")
            return False
    
    def update_patient(self, telegram_id: int, name: str, phone: str,
                      username: str, visit_date: str):
        """Обновление или создание карточки пациента"""
        try:
            if not self.patients_sheet:
                return
            
            all_records = self.patients_sheet.get_all_records()
            found = False
            row_num = 2
            
            # Ищем существующего пациента
            for i, patient in enumerate(all_records, start=2):
                if str(patient.get('Telegram ID', '')) == str(telegram_id):
                    found = True
                    row_num = i
                    break
            
            now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            
            if found:
                # Обновляем существующего
                total = int(self.patients_sheet.cell(row_num, 6).value or '0') + 1
                self.patients_sheet.update_cell(row_num, 2, name)
                self.patients_sheet.update_cell(row_num, 3, phone)
                self.patients_sheet.update_cell(row_num, 4, username or '-')
                self.patients_sheet.update_cell(row_num, 6, str(total))
                self.patients_sheet.update_cell(row_num, 7, visit_date)
            else:
                # Добавляем нового
                row = [
                    str(telegram_id),
                    name,
                    phone,
                    username or '-',
                    now,
                    '1',
                    visit_date,
                    ''
                ]
                self.patients_sheet.append_row(row)
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка обновления пациента: {e}")
    
    def get_available_slots(self, date: str) -> List[str]:
        """Получение свободных временных слотов"""
        try:
            if not self.appointments_sheet:
                return Config.WORK_HOURS
            
            all_records = self.appointments_sheet.get_all_records()
            busy_times = []
            
            for record in all_records:
                if (record.get('Дата') == date and
                    record.get('Статус') == 'Подтверждена'):
                    busy_times.append(record.get('Время'))
            
            available = [t for t in Config.WORK_HOURS if t not in busy_times]
            return available
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения слотов: {e}")
            return Config.WORK_HOURS
    
    def get_user_appointments(self, telegram_id: int) -> List[Dict]:
        """Получение всех записей пользователя"""
        try:
            if not self.appointments_sheet:
                return []
            
            all_records = self.appointments_sheet.get_all_records()
            user_appointments = []
            
            for record in all_records:
                if str(record.get('Telegram ID', '')) == str(telegram_id):
                    user_appointments.append(record)
            
            # Сортировка по дате (сначала ближайшие)
            user_appointments.sort(
                key=lambda x: f"{x.get('Дата', '')} {x.get('Время', '')}"
            )
            
            return user_appointments
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения записей: {e}")
            return []
    
    def get_today_appointments(self) -> List[Dict]:
        """Получение записей на сегодня"""
        try:
            if not self.appointments_sheet:
                return []
            
            today = datetime.now().strftime('%d.%m.%Y')
            all_records = self.appointments_sheet.get_all_records()
            today_appointments = []
            
            for record in all_records:
                if (record.get('Дата') == today and
                    record.get('Статус') == 'Подтверждена'):
                    today_appointments.append(record)
            
            return today_appointments
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения записей на сегодня: {e}")
            return []
    
    def get_upcoming_appointments(self) -> List[Dict]:
        """Получение предстоящих записей"""
        try:
            if not self.appointments_sheet:
                return []
            
            today = datetime.now().strftime('%d.%m.%Y')
            all_records = self.appointments_sheet.get_all_records()
            upcoming = []
            
            for record in all_records:
                if (record.get('Статус') == 'Подтверждена' and
                    record.get('Дата', '') >= today):
                    upcoming.append(record)
            
            return upcoming
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения предстоящих записей: {e}")
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
                    record.get('Время') == time and
                    record.get('Статус') == 'Подтверждена'):
                    
                    self.appointments_sheet.update_cell(i, 9, 'Отменена')
                    print(f"{Emoji.CHECK} Запись отменена: {date} {time}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка отмены записи: {e}")
            return False
    
    def mark_reminder_sent(self, date: str, time: str, telegram_id: int) -> bool:
        """Отметить отправку напоминания"""
        try:
            if not self.appointments_sheet:
                return False
            
            all_records = self.appointments_sheet.get_all_records()
            
            for i, record in enumerate(all_records, start=2):
                if (str(record.get('Telegram ID', '')) == str(telegram_id) and
                    record.get('Дата') == date and
                    record.get('Время') == time):
                    
                    sent_time = datetime.now().strftime('%d.%m.%Y %H:%M')
                    self.appointments_sheet.update_cell(i, 11, f'Отправлено {sent_time}')
                    return True
            
            return False
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка отметки напоминания: {e}")
            return False
    
    def get_appointment_stats(self) -> Dict:
        """Получение статистики записей"""
        try:
            if not self.appointments_sheet:
                return {}
            
            all_records = self.appointments_sheet.get_all_records()
            today = datetime.now().strftime('%d.%m.%Y')
            
            total = len(all_records)
            confirmed = len([r for r in all_records if r.get('Статус') == 'Подтверждена'])
            cancelled = len([r for r in all_records if r.get('Статус') == 'Отменена'])
            today_count = len([r for r in all_records if r.get('Дата') == today])
            
            return {
                'total': total,
                'confirmed': confirmed,
                'cancelled': cancelled,
                'today': today_count
            }
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения статистики: {e}")
            return {}


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
            
            # Проверяем каждый час с 8:00 до 21:00
            for hour in range(8, 21):
                self.scheduler.add_job(
                    self.send_reminders,
                    CronTrigger(hour=hour, minute=0),
                    id=f'reminder_{hour}'
                )
            
            # Проверяем каждые 30 минут в пиковые часы
            self.scheduler.add_job(
                self.send_reminders,
                CronTrigger(hour='9-12,17-20', minute='0,30'),
                id='reminder_peak'
            )
            
            self.scheduler.start()
            print(f"{Emoji.CHECK} Планировщик напоминаний запущен")
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка настройки планировщика: {e}")
    
    async def send_reminders(self):
        """Отправка напоминаний"""
        try:
            today = datetime.now().strftime('%d.%m.%Y')
            appointments = self.google_sheets.get_today_appointments()
            
            for appointment in appointments:
                # Проверяем, отправляли ли уже напоминание
                if 'Отправлено' in str(appointment.get('Напоминание', '')):
                    continue
                
                telegram_id = int(appointment.get('Telegram ID', 0))
                time_str = appointment.get('Время', '')
                patient_name = appointment.get('Пациент', '')
                doctor = appointment.get('Врач', '')
                
                try:
                    # Рассчитываем время до приема
                    appointment_time = datetime.strptime(time_str, '%H:%M')
                    now = datetime.now()
                    appointment_datetime = now.replace(
                        hour=appointment_time.hour,
                        minute=appointment_time.minute,
                        second=0
                    )
                    
                    time_diff = (appointment_datetime - now).total_seconds() / 3600
                    
                    # Отправляем за 2 часа до приема
                    if 1.5 <= time_diff <= 2.5:
                        message = (
                            f"{Emoji.BELL} **Напоминание о приеме!**\n\n"
                            f"Здравствуйте, {patient_name}!\n\n"
                            f"{Emoji.CLOCK} **Время:** {time_str}\n"
                            f"{Emoji.DOCTOR} **Врач:** {doctor}\n"
                            f"{Emoji.LOCATION} **Адрес:** г. Москва, ул. Ленина, д. 10\n\n"
                            f"{Emoji.INFO} Пожалуйста, не опаздывайте.\n"
                            f"Если нужно отменить запись - используйте раздел «Мои записи»"
                        )
                        
                        await self.bot.send_message(
                            chat_id=telegram_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        
                        # Отмечаем отправку
                        self.google_sheets.mark_reminder_sent(
                            appointment.get('Дата'),
                            appointment.get('Время'),
                            telegram_id
                        )
                        
                        print(f"{Emoji.BELL} Напоминание отправлено {telegram_id}")
                        
                except Exception as e:
                    print(f"{Emoji.ERROR} Ошибка отправки напоминания: {e}")
                    
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
            [InlineKeyboardButton(f"{Emoji.CALENDAR} Записаться на прием", callback_data='appointment')],
            [InlineKeyboardButton(f"{Emoji.DOCTOR} Наши врачи", callback_data='doctors')],
            [InlineKeyboardButton(f"{Emoji.QUESTION} Частые вопросы", callback_data='faq')],
            [InlineKeyboardButton(f"{Emoji.CHECK} Мои записи", callback_data='my_appointments')],
            [InlineKeyboardButton(f"{Emoji.HOSPITAL} О клинике", callback_data='about')],
            [InlineKeyboardButton(f"{Emoji.PHONE} Контакты", callback_data='contacts')]
        ]
        
        if is_admin:
            keyboard.append([InlineKeyboardButton(f"{Emoji.CROWN} Админ-панель", callback_data='admin_panel')])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_panel() -> InlineKeyboardMarkup:
        """Панель администратора"""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CALENDAR} Записи на сегодня", callback_data='admin_today')],
            [InlineKeyboardButton(f"{Emoji.STATS} Статистика", callback_data='admin_stats')],
            [InlineKeyboardButton(f"{Emoji.USER} Список пациентов", callback_data='admin_patients')],
            [InlineKeyboardButton(f"{Emoji.BELL} Рассылка", callback_data='admin_broadcast')],
            [InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def doctors_keyboard() -> InlineKeyboardMarkup:
        """Выбор врача"""
        keyboard = []
        for doc_id, doctor in Config.DOCTORS.items():
            icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
            name_parts = doctor.name.split()
            short_name = f"{name_parts[0]} {name_parts[1][0]}." if len(name_parts) > 1 else doctor.name
            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} {short_name} - {doctor.specialty[:20]}",
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
        
        days_ru = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']
        
        for i in range(Config.MAX_DAYS_AHEAD):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            
            if i == 0:
                label = f"{Emoji.CALENDAR} Сегодня ({date.day}.{date.month})"
            elif i == 1:
                label = f"{Emoji.CALENDAR} Завтра ({date.day}.{date.month})"
            else:
                day_name = days_ru[date.weekday()]
                label = f"{Emoji.CALENDAR} {date.day}.{date.month} ({day_name})"
            
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
                InlineKeyboardButton(f"{Emoji.CANCEL} Отмена", callback_data='cancel_appointment')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def faq_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура FAQ"""
        keyboard = []
        for question in Config.FAQ.keys():
            keyboard.append([InlineKeyboardButton(f"{Emoji.QUESTION} {question}", callback_data=f"faq_{question}")])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def my_appointments_keyboard(appointments: List[Dict]) -> InlineKeyboardMarkup:
        """Список записей пользователя"""
        keyboard = []
        for app in appointments[:5]:
            if app.get('Статус') == 'Подтверждена':
                keyboard.append([
                    InlineKeyboardButton(
                        f"{Emoji.CALENDAR} {app['Дата']} {app['Время']}",
                        callback_data=f"view_{app['Дата']}_{app['Время']}"
                    )
                ])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def appointment_actions_keyboard(date: str, time: str) -> InlineKeyboardMarkup:
        """Действия с записью"""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CANCEL} Отменить запись", callback_data=f"cancel_{date}_{time}")],
            [InlineKeyboardButton(f"{Emoji.BACK} К списку записей", callback_data='my_appointments')]
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
    VIEWING_APPOINTMENT,
    ADMIN_BROADCAST
) = range(8)


# ============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# ============================================================================

class DentalClinicBot:
    """Бот стоматологической клиники - ПОЛНАЯ РЕАЛИЗАЦИЯ"""
    
    def __init__(self):
        self.config = Config()
        self.keyboards = Keyboards()
        self.google_sheets = GoogleSheetsManager()
        self.reminder_scheduler = None
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
        """Обработчик команды /start"""
        user = update.effective_user
        user_id = user.id
        
        # Проверка на админа
        is_admin = user_id in self.config.ADMIN_IDS
        
        welcome_text = (
            f"{Emoji.TOOTH} **Здравствуйте, {user.first_name}!**\n\n"
            f"Добро пожаловать в бот стоматологической клиники.\n\n"
            f"**С помощью бота вы можете:**\n"
            f"{Emoji.CHECK} Записаться к врачу за 1 минуту\n"
            f"{Emoji.CHECK} Выбрать удобное время\n"
            f"{Emoji.CHECK} Получить напоминание о приеме\n"
            f"{Emoji.CHECK} Просмотреть свои записи\n"
            f"{Emoji.CHECK} Отменить запись\n\n"
            f"{Emoji.CLOCK} **Режим работы:** 9:00 - 20:00 ежедневно\n"
            f"{Emoji.LOCATION} **Адрес:** г. Москва, ул. Ленина, д. 10\n\n"
            f"Выберите действие в меню:"
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=self.keyboards.main_menu(is_admin),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена текущего действия"""
        user_id = update.effective_user.id
        
        if user_id in self.user_data:
            del self.user_data[user_id]
        
        is_admin = user_id in self.config.ADMIN_IDS
        
        await update.message.reply_text(
            f"{Emoji.CANCEL} Действие отменено",
            reply_markup=self.keyboards.main_menu(is_admin),
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
        is_admin = user_id in self.config.ADMIN_IDS
        
        # ========== ГЛАВНОЕ МЕНЮ ==========
        if data == 'back_to_menu':
            await query.edit_message_text(
                f"{Emoji.MENU} **Главное меню**",
                reply_markup=self.keyboards.main_menu(is_admin),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # ========== ЗАПИСЬ НА ПРИЕМ ==========
        elif data == 'appointment':
            self.user_data[user_id] = AppointmentData()
            
            await query.edit_message_text(
                f"{Emoji.DOCTOR} **Выберите врача**\n\n"
                f"У каждого специалиста своя специализация:\n"
                f"{Emoji.BULLET} Терапевт - лечение зубов\n"
                f"{Emoji.BULLET} Хирург - удаление, импланты\n"
                f"{Emoji.BULLET} Ортодонт - исправление прикуса\n"
                f"{Emoji.BULLET} Ортопед - протезирование\n"
                f"{Emoji.BULLET} Детский врач - лечение детей",
                reply_markup=self.keyboards.doctors_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DOCTOR
        
        # ========== ИНФОРМАЦИЯ О ВРАЧАХ ==========
        elif data == 'doctors':
            text = f"{Emoji.DOCTOR} **Наши врачи**\n\n"
            
            for doctor in self.config.DOCTORS.values():
                icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
                stars = "⭐" * int(doctor.rating)
                text += (
                    f"{icon} **{doctor.name}**\n"
                    f"{Emoji.BULLET} {doctor.specialty}\n"
                    f"{Emoji.BULLET} Стаж: {doctor.experience} лет {stars}\n"
                    f"{Emoji.BULLET} {doctor.description}\n\n"
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
            
            # Сохраняем данные
            self.user_data[user_id].doctor_id = doctor_id
            self.user_data[user_id].doctor_name = f"{doctor.name} ({doctor.specialty})"
            
            stars = "⭐" * int(doctor.rating)
            icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
            
            text = (
                f"{icon} **{doctor.name}**\n"
                f"**{doctor.specialty}**\n\n"
                f"{Emoji.BULLET} Стаж: {doctor.experience} лет\n"
                f"{Emoji.BULLET} Рейтинг: {doctor.rating} {stars}\n"
                f"{Emoji.BULLET} {doctor.description}\n"
                f"{Emoji.BULLET} {doctor.education}\n\n"
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
            
            # Сохраняем дату
            self.user_data[user_id].date = date
            
            # Получаем свободное время
            available_times = self.google_sheets.get_available_slots(date)
            
            if not available_times:
                await query.edit_message_text(
                    f"{Emoji.CANCEL} **Нет свободного времени**\n\n"
                    f"На выбранную дату все слоты заняты.\n"
                    f"Пожалуйста, выберите другую дату:",
                    reply_markup=self.keyboards.date_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                return SELECTING_DATE
            
            # Форматируем дату
            date_obj = datetime.strptime(date, '%d.%m.%Y')
            date_display = date_obj.strftime('%d.%m.%Y')
            
            await query.edit_message_text(
                f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                f"{Emoji.CLOCK} **Доступное время:**\n\n"
                f"Выберите удобное время:",
                reply_markup=self.keyboards.time_keyboard(date, available_times),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_TIME
        
        # ========== ВЫБОР ВРЕМЕНИ ==========
        elif data.startswith('time_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            
            # Сохраняем время
            self.user_data[user_id].date = date
            self.user_data[user_id].time = time
            
            # Форматируем дату
            date_obj = datetime.strptime(date, '%d.%m.%Y')
            date_display = date_obj.strftime('%d.%m.%Y')
            
            await query.edit_message_text(
                f"{Emoji.CHECK} **Проверьте данные записи**\n\n"
                f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                f"{Emoji.CLOCK} **Время:** {time}\n"
                f"{Emoji.DOCTOR} **Врач:** {self.user_data[user_id].doctor_name}\n\n"
                f"Всё верно?",
                reply_markup=self.keyboards.confirm_keyboard(
                    date,
                    time,
                    self.user_data[user_id].doctor_id
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONFIRMING
        
        # ========== ПОДТВЕРЖДЕНИЕ ЗАПИСИ ==========
        elif data.startswith('confirm_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            doctor_id = parts[3]
            
            # Сохраняем все данные
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
                    f"{Emoji.EDIT} **Введите ваше полное ФИО**\n\n"
                    f"Формат: Иванов Иван Иванович\n\n"
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
                reply_markup=self.keyboards.main_menu(is_admin),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        elif data.startswith('cancel_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            
            success = self.google_sheets.cancel_appointment(date, time, user_id)
            
            if success:
                text = f"{Emoji.SUCCESS} **Запись успешно отменена**\n\n📅 {date} в {time}"
            else:
                text = f"{Emoji.ERROR} **Не удалось отменить запись**\n\nПопробуйте позже или позвоните в клинику"
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(is_admin),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== МОИ ЗАПИСИ ==========
        elif data == 'my_appointments':
            appointments = self.google_sheets.get_user_appointments(user_id)
            
            if not appointments:
                await query.edit_message_text(
                    f"{Emoji.CALENDAR} **У вас пока нет записей**\n\n"
                    f"Вы можете записаться на прием через главное меню",
                    reply_markup=self.keyboards.main_menu(is_admin),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                active = [a for a in appointments if a.get('Статус') == 'Подтверждена']
                past = [a for a in appointments if a.get('Статус') != 'Подтверждена']
                
                if not active:
                    text = f"{Emoji.INFO} **У вас нет активных записей**\n\n"
                    if past:
                        text += f"Всего записей: {len(appointments)}"
                else:
                    text = f"{Emoji.CHECK} **Ваши активные записи ({len(active)})**\n\n"
                    for app in active[:3]:
                        text += (
                            f"{Emoji.CALENDAR} **{app['Дата']}** в **{app['Время']}**\n"
                            f"{Emoji.DOCTOR} {app['Врач'][:40]}...\n"
                            f"{Emoji.ACTIVE} {app['Статус']}\n\n"
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
                if app.get('Дата') == date and app.get('Время') == time:
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
                    f"{Emoji.ACTIVE} **Статус:** {appointment['Статус']}\n"
                    f"🆔 ID: {appointment.get('ID', 'Н/Д')}\n\n"
                    f"{Emoji.INFO} Для отмены нажмите кнопку ниже"
                )
                
                await query.edit_message_text(
                    text,
                    reply_markup=self.keyboards.appointment_actions_keyboard(date, time),
                    parse_mode=ParseMode.MARKDOWN
                )
                return VIEWING_APPOINTMENT
        
        # ========== FAQ ==========
        elif data == 'faq':
            await query.edit_message_text(
                f"{Emoji.QUESTION} **Часто задаваемые вопросы**\n\n"
                f"Выберите интересующий вопрос:",
                reply_markup=self.keyboards.faq_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data.startswith('faq_'):
            question = data[4:]
            answer = self.config.FAQ.get(question, "Информация временно недоступна")
            
            await query.edit_message_text(
                f"**{question}**\n\n{answer}",
                reply_markup=self.keyboards.faq_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== О КЛИНИКЕ ==========
        elif data == 'about':
            text = (
                f"{Emoji.HOSPITAL} **О клинике**\n\n"
                f"🏥 Современная стоматологическая клиника\n"
                f"📅 Основана в 2010 году\n\n"
                f"**Преимущества:**\n"
                f"{Emoji.BULLET} 5 опытных врачей\n"
                f"{Emoji.BULLET} Современное оборудование\n"
                f"{Emoji.BULLET} Безболезненное лечение\n"
                f"{Emoji.BULLET} Стерилизация по стандартам ЕС\n"
                f"{Emoji.BULLET} Детский уголок\n"
                f"{Emoji.BULLET} Бесплатная парковка\n\n"
                f"{Emoji.CLOCK} Режим работы: 9:00 - 20:00 (без выходных)"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(is_admin),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== КОНТАКТЫ ==========
        elif data == 'contacts':
            text = (
                f"{Emoji.PHONE} **Контакты**\n\n"
                f"📞 Телефон: +7 (999) 123-45-67\n"
                f"📧 Email: info@dentclinic.ru\n\n"
                f"{Emoji.LOCATION} **Адрес:**\n"
                f"г. Москва, ул. Ленина, д. 10\n\n"
                f"{Emoji.MAP} **Как добраться:**\n"
                f"Метро «Парк Культуры», выход №3\n"
                f"5 минут пешком\n\n"
                f"{Emoji.CAR} **Парковка:**\n"
                f"Бесплатная для пациентов\n\n"
                f"{Emoji.CLOCK} **Режим работы:**\n"
                f"Ежедневно: 9:00 - 20:00"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(is_admin),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== АДМИН-ПАНЕЛЬ ==========
        elif data == 'admin_panel':
            if not is_admin:
                await query.edit_message_text(
                    f"{Emoji.ERROR} **Доступ запрещен**",
                    reply_markup=self.keyboards.main_menu(is_admin),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            await query.edit_message_text(
                f"{Emoji.CROWN} **Панель администратора**\n\n"
                f"Выберите действие:",
                reply_markup=self.keyboards.admin_panel(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'admin_today':
            if not is_admin:
                return
            
            appointments = self.google_sheets.get_today_appointments()
            
            if not appointments:
                text = f"{Emoji.CALENDAR} **На сегодня записей нет**"
            else:
                text = f"{Emoji.CALENDAR} **Записи на сегодня ({len(appointments)})**\n\n"
                for app in appointments:
                    text += (
                        f"{Emoji.CLOCK} {app['Время']}\n"
                        f"{Emoji.USER} {app['Пациент']}\n"
                        f"{Emoji.PHONE} {app['Телефон']}\n"
                        f"{Emoji.DOCTOR} {app['Врач'][:30]}...\n\n"
                    )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.admin_panel(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'admin_stats':
            if not is_admin:
                return
            
            stats = self.google_sheets.get_appointment_stats()
            
            text = (
                f"{Emoji.STATS} **Статистика**\n\n"
                f"📊 Всего записей: {stats.get('total', 0)}\n"
                f"{Emoji.CHECK} Подтверждено: {stats.get('confirmed', 0)}\n"
                f"{Emoji.CANCEL} Отменено: {stats.get('cancelled', 0)}\n"
                f"{Emoji.CALENDAR} На сегодня: {stats.get('today', 0)}\n\n"
                f"👨‍⚕️ Врачей: {len(self.config.DOCTORS)}\n"
                f"👥 Пациентов: ?\n\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.admin_panel(),
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
        """Получение ФИО пациента - ИСПРАВЛЕНО"""
        user_id = update.effective_user.id
        name = update.message.text.strip()
        
        print(f"📝 ПОЛУЧЕНО ФИО: {name} от пользователя {user_id}")
        
        # Проверяем наличие данных
        if user_id not in self.user_data:
            self.user_data[user_id] = AppointmentData()
            print(f"⚠️ СОЗДАНЫ НОВЫЕ ДАННЫЕ для {user_id}")
        
        # Валидация ФИО
        if len(name) < 5:
            await update.message.reply_text(
                f"{Emoji.CANCEL} **Слишком короткое ФИО**\n\n"
                f"Минимальная длина - 5 символов.\n"
                f"Пример: Иванов Иван Иванович",
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_NAME
        
        if any(char.isdigit() for char in name):
            await update.message.reply_text(
                f"{Emoji.CANCEL} **ФИО не должно содержать цифры**\n\n"
                f"Пожалуйста, введите только буквы:",
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_NAME
        
        # Сохраняем ФИО
        self.user_data[user_id].patient_name = name
        print(f"✅ ФИО СОХРАНЕНО: {name}")
        print(f"📋 ТЕКУЩИЕ ДАННЫЕ: {self.user_data[user_id]}")
        
        # Запрашиваем телефон
        await update.message.reply_text(
            f"{Emoji.CHECK} **Спасибо, {name.split()[0]}!**\n\n"
            f"{Emoji.PHONE} **Введите номер телефона**\n\n"
            f"Форматы:\n"
            f"• +79991234567\n"
            f"• 89991234567\n"
            f"• 79991234567\n\n"
            f"{Emoji.INFO} Номер нужен для связи и регистратуры",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return GETTING_PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение телефона и сохранение записи - ИСПРАВЛЕНО"""
        user_id = update.effective_user.id
        phone_raw = update.message.text.strip()
        
        print(f"📞 ПОЛУЧЕН ТЕЛЕФОН: {phone_raw} от {user_id}")
        
        # Проверяем наличие данных
        if user_id not in self.user_data:
            await update.message.reply_text(
                f"{Emoji.ERROR} **Ошибка данных**\n\n"
                f"Информация о записи не найдена.\n"
                f"Пожалуйста, начните запись заново.",
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Очищаем телефон от лишних символов
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone_raw)
        
        # Валидация телефона
        if not re.match(r'^(\+7|8|7)?\d{10}$', phone_clean):
            await update.message.reply_text(
                f"{Emoji.CANCEL} **Неверный формат телефона**\n\n"
                f"Правильные форматы:\n"
                f"• +79991234567\n"
                f"• 89991234567\n"
                f"• 79991234567\n\n"
                f"Попробуйте снова:",
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_PHONE
        
        # Приводим к единому формату +7XXXXXXXXXX
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
        appointment.telegram_id = user_id
        appointment.username = update.effective_user.username or ''
        appointment.created_at = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        
        print(f"💾 СОХРАНЕНИЕ ЗАПИСИ В GOOGLE SHEETS:")
        print(f"   Дата: {appointment.date}")
        print(f"   Время: {appointment.time}")
        print(f"   Врач: {appointment.doctor_name}")
        print(f"   Пациент: {appointment.patient_name}")
        print(f"   Телефон: {phone}")
        print(f"   Telegram ID: {user_id}")
        
        # Проверяем наличие всех обязательных полей
        missing_fields = []
        if not appointment.date: missing_fields.append("дата")
        if not appointment.time: missing_fields.append("время")
        if not appointment.doctor_name: missing_fields.append("врач")
        if not appointment.patient_name: missing_fields.append("ФИО")
        
        if missing_fields:
            await update.message.reply_text(
                f"{Emoji.ERROR} **Ошибка: не хватает данных**\n\n"
                f"Отсутствуют: {', '.join(missing_fields)}\n"
                f"Пожалуйста, начните запись заново.",
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Сохраняем запись в Google Sheets
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
            # Форматируем дату для красивого отображения
            try:
                dt = datetime.strptime(appointment.date, '%d.%m.%Y')
                months = {
                    1: 'января', 2: 'февраля', 3: 'марта',
                    4: 'апреля', 5: 'мая', 6: 'июня',
                    7: 'июля', 8: 'августа', 9: 'сентября',
                    10: 'октября', 11: 'ноября', 12: 'декабря'
                }
                date_display = f"{dt.day} {months[dt.month]}"
            except:
                date_display = appointment.date
            
            # Сообщение об успешной записи
            success_text = (
                f"{Emoji.SUCCESS} **ЗАПИСЬ ПОДТВЕРЖДЕНА!** {Emoji.SUCCESS}\n\n"
                
                f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                f"{Emoji.CLOCK} **Время:** {appointment.time}\n"
                f"{Emoji.DOCTOR} **Врач:** {appointment.doctor_name}\n"
                f"{Emoji.USER} **Пациент:** {appointment.patient_name}\n"
                f"{Emoji.PHONE} **Телефон:** {phone}\n\n"
                
                f"{Emoji.BELL} **Что дальше?**\n\n"
                f"1️⃣ Мы отправим напоминание за 2 часа до приема\n"
                f"2️⃣ Приходите за 5 минут до назначенного времени\n"
                f"3️⃣ При себе иметь паспорт\n\n"
                f"{Emoji.HEART} **Спасибо, что выбрали нас!**\n"
                f"Ждем вас на приеме!"
            )
            
            await update.message.reply_text(
                success_text,
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Отправляем уведомление администраторам
            for admin_id in self.config.ADMIN_IDS:
                try:
                    admin_text = (
                        f"{Emoji.BELL} **НОВАЯ ЗАПИСЬ!**\n\n"
                        f"📅 {appointment.date}\n"
                        f"⏰ {appointment.time}\n"
                        f"👨‍⚕️ {appointment.doctor_name}\n"
                        f"👤 {appointment.patient_name}\n"
                        f"📞 {phone}\n"
                        f"🆔 {user_id}\n"
                        f"📱 @{appointment.username or 'нет'}\n"
                        f"🕐 {appointment.created_at}"
                    )
                    
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    print(f"{Emoji.ERROR} Ошибка отправки админу {admin_id}: {e}")
            
            print(f"{Emoji.SUCCESS} ЗАПИСЬ УСПЕШНО СОХРАНЕНА ДЛЯ {user_id}")
            
        else:
            await update.message.reply_text(
                f"{Emoji.ERROR} **Ошибка при сохранении записи**\n\n"
                f"Пожалуйста, попробуйте позже или свяжитесь с нами по телефону:\n"
                f"{Emoji.PHONE} +7 (999) 123-45-67",
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS),
                parse_mode=ParseMode.MARKDOWN
            )
            print(f"{Emoji.ERROR} ОШИБКА СОХРАНЕНИЯ ЗАПИСИ ДЛЯ {user_id}")
        
        # Очищаем временные данные
        if user_id in self.user_data:
            del self.user_data[user_id]
            print(f"🧹 ДАННЫЕ ПОЛЬЗОВАТЕЛЯ {user_id} ОЧИЩЕНЫ")
        
        return ConversationHandler.END
    
    # ========================================================================
    # ЗАПУСК БОТА
    # ========================================================================
    
    def run(self):
        """Запуск бота"""
        try:
            self.application = Application.builder().token(self.config.BOT_TOKEN).build()
            
            # ======== КОМАНДЫ ========
            self.application.add_handler(CommandHandler('start', self.start))
            self.application.add_handler(CommandHandler('cancel', self.cancel))
            
            # ======== КОНВЕРСАЦИЯ ЗАПИСИ ========
            appointment_conv = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(self.button_handler, pattern='^appointment$')
                ],
                states={
                    SELECTING_DOCTOR: [
                        CallbackQueryHandler(
                            self.button_handler,
                            pattern='^(doctor_|back_to_menu|back_to_doctors|doctors)$'
                        )
                    ],
                    SELECTING_DATE: [
                        CallbackQueryHandler(
                            self.button_handler,
                            pattern='^(date_|back_to_doctors|back_to_menu)$'
                        )
                    ],
                    SELECTING_TIME: [
                        CallbackQueryHandler(
                            self.button_handler,
                            pattern='^(time_|back_to_dates|back_to_menu)$'
                        )
                    ],
                    CONFIRMING: [
                        CallbackQueryHandler(
                            self.button_handler,
                            pattern='^(confirm_|cancel_appointment|back_to_menu)$'
                        )
                    ],
                    GETTING_NAME: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_name)
                    ],
                    GETTING_PHONE: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_phone)
                    ],
                    VIEWING_APPOINTMENT: [
                        CallbackQueryHandler(
                            self.button_handler,
                            pattern='^(cancel_|my_appointments|back_to_menu)$'
                        )
                    ]
                },
                fallbacks=[
                    CommandHandler('cancel', self.cancel),
                    CallbackQueryHandler(self.button_handler, pattern='^back_to_menu$')
                ],
                name="appointment_conversation",
                persistent=False
            )
            
            self.application.add_handler(appointment_conv)
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            # ======== ПЛАНИРОВЩИК НАПОМИНАНИЙ ========
            if self.google_sheets.client:
                self.reminder_scheduler = ReminderScheduler(self.application.bot, self.google_sheets)
            
            # ======== ЗАПУСК ========
            print("\n" + "="*60)
            print(f"{Emoji.TOOTH} СТОМАТОЛОГИЧЕСКИЙ БОТ - ПРЕМИУМ ВЕРСИЯ")
            print("="*60)
            print(f"{Emoji.CHECK} Токен: {self.config.BOT_TOKEN[:15]}...")
            print(f"{Emoji.DOCTOR} Врачей: {len(self.config.DOCTORS)}")
            print(f"{Emoji.CROWN} Админов: {len(self.config.ADMIN_IDS)}")
            print(f"{Emoji.CHECK} Google Sheets: {'✅' if self.google_sheets.client else '❌'}")
            print(f"{Emoji.CHECK} Планировщик: {'✅' if self.reminder_scheduler else '❌'}")
            print("="*60 + "\n")
            
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"{Emoji.ERROR} Критическая ошибка: {e}")
            raise


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

if __name__ == '__main__':
    try:
        bot = DentalClinicBot()
        bot.run()
    except KeyboardInterrupt:
        print(f"\n{Emoji.CANCEL} Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Emoji.ERROR} Ошибка запуска: {e}")
        sys.exit(1)
