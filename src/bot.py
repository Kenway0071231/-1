"""
СТОМАТОЛОГИЧЕСКИЙ БОТ - ПРЕМИУМ ВЕРСИЯ
Дизайн: Современный, минималистичный, дружелюбный
Механика: Интуитивная, быстрая, без лишних действий
Версия: 2.0.2 (ПОЛНОСТЬЮ ИСПРАВЛЕНА ЗАПИСЬ)
"""

import logging
import re
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
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
    """Единая система эмодзи для всего бота"""
    # Основные
    CHECK = "✅"
    CANCEL = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    SUCCESS = "🎉"
    ERROR = "‼️"
    WAITING = "⏳"
    LOCK = "🔒"
    UNLOCK = "🔓"
    
    # Навигация
    BACK = "◀️"
    HOME = "🏠"
    NEXT = "▶️"
    MENU = "📋"
    SETTINGS = "⚙️"
    
    # Медицина
    DOCTOR = "👨‍⚕️"
    DOCTOR_WOMAN = "👩‍⚕️"
    HOSPITAL = "🏥"
    TOOTH = "🦷"
    SYRINGE = "💉"
    PILLS = "💊"
    STETHOSCOPE = "🩺"
    
    # Время
    CALENDAR = "📅"
    CLOCK = "🕐"
    HOURGLASS = "⏳"
    BELL = "🔔"
    ALARM = "⏰"
    
    # Контакты
    PHONE = "📞"
    EMAIL = "📧"
    MAP = "🗺️"
    LOCATION = "📍"
    CAR = "🚗"
    
    # Действия
    ADD = "➕"
    EDIT = "✏️"
    DELETE = "🗑️"
    SEARCH = "🔍"
    SAVE = "💾"
    SEND = "📤"
    
    # Статусы
    ACTIVE = "🟢"
    INACTIVE = "🔴"
    PENDING = "🟡"
    COMPLETED = "🟣"
    
    # Другое
    STAR = "⭐"
    HEART = "❤️"
    SPARKLES = "✨"
    MONEY = "💰"
    QUESTION = "❓"
    EXCLAMATION = "❗"
    DOTS = "..."
    CROWN = "👑"
    USER = "👤"
    
    # Специальные символы
    DIVIDER = "─"
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
        """Полное описание врача"""
        stars = "⭐" * int(self.rating)
        icon = Emoji.DOCTOR_WOMAN if 'ва' in self.name else Emoji.DOCTOR
        return (
            f"{icon} **{self.name}**\n"
            f"└ {self.specialty}\n"
            f"└ Стаж: {self.experience} лет\n"
            f"└ Рейтинг: {stars} ({self.rating})\n"
            f"└ {self.description}"
        )
    
    def short_info(self) -> str:
        """Краткое описание врача"""
        icon = Emoji.DOCTOR_WOMAN if 'ва' in self.name else Emoji.DOCTOR
        return f"{icon} **{self.name}** — {self.specialty}"


@dataclass
class Appointment:
    """Модель записи"""
    date: str
    time: str
    doctor: str
    patient_name: str
    patient_phone: str
    telegram_id: int
    status: str
    created_at: str
    reminder_sent: bool = False
    
    def format_date(self) -> str:
        """Форматирование даты для отображения"""
        try:
            dt = datetime.strptime(self.date, '%d.%m.%Y')
            months = {
                1: 'января', 2: 'февраля', 3: 'марта',
                4: 'апреля', 5: 'мая', 6: 'июня',
                7: 'июля', 8: 'августа', 9: 'сентября',
                10: 'октября', 11: 'ноября', 12: 'декабря'
            }
            return f"{dt.day} {months[dt.month]}"
        except:
            return self.date
    
    def format_datetime(self) -> str:
        """Полное форматирование даты и времени"""
        return f"{self.format_date()} в {self.time}"


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


# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

class Config:
    """Конфигурация бота"""
    
    # Токен бота
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Google Sheets
    GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
    SPREADSHEET_URL = os.getenv('SPREADSHEET_URL')
    
    # ID администраторов
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
    
    # Врачи клиники (расширенная информация)
    DOCTORS = {
        '1': Doctor(
            id='1',
            name='Иванова Мария Петровна',
            specialty='Стоматолог-терапевт',
            experience=15,
            description='Специалист по лечению кариеса, пульпита, эндодонтии. Работает с микроскопом.',
            education='МГМСУ им. Сеченова, 2009',
            rating=4.9
        ),
        '2': Doctor(
            id='2',
            name='Петров Сергей Иванович',
            specialty='Стоматолог-хирург, имплантолог',
            experience=12,
            description='Проводит удаление любой сложности, одномоментную имплантацию, синус-лифтинг.',
            education='РУДН, 2012',
            rating=4.8
        ),
        '3': Doctor(
            id='3',
            name='Сидорова Анна Викторовна',
            specialty='Стоматолог-ортодонт',
            experience=10,
            description='Исправление прикуса у взрослых и детей. Брекеты, элайнеры.',
            education='МГМСУ, 2014',
            rating=4.9
        ),
        '4': Doctor(
            id='4',
            name='Козлов Алексей Николаевич',
            specialty='Стоматолог-ортопед',
            experience=20,
            description='Протезирование любой сложности. Коронки, виниры, съемные протезы.',
            education='СПбГМУ, 2004',
            rating=5.0
        ),
        '5': Doctor(
            id='5',
            name='Соколова Елена Дмитриевна',
            specialty='Детский стоматолог',
            experience=8,
            description='Лечение детей с 3 лет. Адаптация, лечение во сне, профилактика.',
            education='РНИМУ им. Пирогова, 2016',
            rating=4.9
        )
    }
    
    # Часы работы
    WORK_HOURS = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '14:00', '14:30', '15:00', '15:30',
        '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]
    
    # FAQ с категориями
    FAQ_CATEGORIES = {
        'about': {
            'name': '🏥 О клинике',
            'icon': '🏥',
            'questions': ['Режим работы', 'Как добраться', 'Оплата', 'ДМС']
        },
        'services': {
            'name': '🦷 Услуги и цены',
            'icon': '💰',
            'questions': ['Стоимость лечения', 'Акции', 'Скидки']
        },
        'appointment': {
            'name': '📝 Запись',
            'icon': '📅',
            'questions': ['Как записаться', 'Отмена записи', 'Перенос']
        },
        'treatment': {
            'name': '💊 Лечение',
            'icon': '💉',
            'questions': ['Больно ли лечить', 'Анестезия', 'Детский прием']
        }
    }
    
    # Полные ответы на FAQ
    FAQ = {
        'Режим работы': (
            f"{Emoji.HOSPITAL} **Режим работы**\n\n"
            f"{Emoji.CLOCK} **Ежедневно:** 9:00 – 20:00\n"
            f"{Emoji.CALENDAR} **Выходные:** без выходных\n\n"
            f"{Emoji.PHONE} **Запись по телефону:**\n"
            f"+7 (999) 123-45-67"
        ),
        'Как добраться': (
            f"{Emoji.MAP} **Как нас найти**\n\n"
            f"{Emoji.LOCATION} **Адрес:**\n"
            f"г. Москва, ул. Ленина, д. 10\n\n"
            f"{Emoji.SEARCH} **Ориентиры:**\n"
            f"• Метро «Парк Культуры», выход №3\n"
            f"• 5 минут пешком от метро\n"
            f"• Бизнес-центр «Плаза», 2 этаж\n\n"
            f"{Emoji.CAR} **Парковка:**\n"
            f"Бесплатная парковка для пациентов"
        ),
        'Стоимость лечения': (
            f"{Emoji.MONEY} **Прайс-лист**\n\n"
            f"**Консультация:**\n"
            f"• Первичная — 500 ₽\n"
            f"• Повторная — 300 ₽\n\n"
            f"**Лечение:**\n"
            f"• Кариес — от 3 000 ₽\n"
            f"• Пульпит — от 5 000 ₽\n\n"
            f"{Emoji.DOTS} Полный прайс доступен по кнопке ниже"
        ),
        'Акции': (
            f"{Emoji.SPARKLES} **Действующие акции**\n\n"
            f"🎁 **Новый пациент** — скидка 10%\n"
            f"🎁 **Семейная запись** — скидка 15%\n"
            f"🎁 **Чистка + осмотр** — 2 500 ₽\n\n"
            f"{Emoji.INFO} Акции суммируются"
        ),
        'Как записаться': (
            f"{Emoji.CHECK} **Способы записи**\n\n"
            f"1️⃣ **Через бота** — 24/7\n"
            f"2️⃣ **По телефону** — +7 (999) 123-45-67\n"
            f"3️⃣ **В регистратуре** — при личном визите\n\n"
            f"Выберите удобный способ!"
        ),
        'Больно ли лечить': (
            f"{Emoji.SYRINGE} **О безболезненном лечении**\n\n"
            f"✅ Современные анестетики\n"
            f"✅ Индивидуальный подбор обезболивания\n"
            f"✅ Седация (лечение во сне)\n"
            f"✅ Абсолютно комфортно!\n\n"
            f"{Emoji.HEART} Не бойтесь — мы заботимся о вас"
        ),
        'Детский прием': (
            f"{Emoji.DOCTOR_WOMAN} **Детская стоматология**\n\n"
            f"👶 **Возраст:** с 3 лет\n"
            f"🎈 **Первый осмотр:** бесплатно\n"
            f"🧸 **Адаптация:** игровая форма\n"
            f"🛏 **Лечение во сне:** по показаниям\n\n"
            f"Наши маленькие пациенты не плачут!"
        ),
        'Отмена записи': (
            f"{Emoji.CANCEL} **Отмена записи**\n\n"
            f"Вы можете отменить запись:\n\n"
            f"1️⃣ В боте: «Мои записи» → «Отменить»\n"
            f"2️⃣ По телефону: +7 (999) 123-45-67\n\n"
            f"{Emoji.INFO} Пожалуйста, отменяйте запись заранее"
        ),
        'Перенос': (
            f"{Emoji.EDIT} **Перенос записи**\n\n"
            f"Для переноса записи:\n\n"
            f"1️⃣ Отмените текущую запись\n"
            f"2️⃣ Запишитесь заново на удобное время\n\n"
            f"{Emoji.PHONE} Или позвоните нам"
        ),
        'Оплата': (
            f"{Emoji.MONEY} **Способы оплаты**\n\n"
            f"💳 Наличные\n"
            f"💳 Банковские карты\n"
            f"💳 Перевод на карту\n"
            f"💳 ДМС\n\n"
            f"Работаем с НДС"
        ),
        'ДМС': (
            f"{Emoji.CHECK} **ДМС**\n\n"
            f"Мы работаем с ведущими страховыми компаниями:\n\n"
            f"• Ингосстрах\n"
            f"• РЕСО-Гарантия\n"
            f"• АльфаСтрахование\n"
            f"• Согаз\n\n"
            f"{Emoji.PHONE} Уточните наличие полиса по телефону"
        ),
        'Скидки': (
            f"{Emoji.SPARKLES} **Скидки**\n\n"
            f"👨‍👩‍👧 **Семейная скидка** — 15%\n"
            f"👴 **Пенсионерам** — 10%\n"
            f"🎓 **Студентам** — 10%\n"
            f"🎁 **Именинникам** — 20% в день рождения\n\n"
            f"Скидки суммируются"
        ),
        'Анестезия': (
            f"{Emoji.SYRINGE} **Анестезия**\n\n"
            f"Используем:\n\n"
            f"• Ультракаин\n"
            f"• Убистезин\n"
            f"• Септанест\n\n"
            f"Противопоказания уточняйте у врача"
        )
    }


# ============================================================================
# GOOGLE SHEETS МЕНЕДЖЕР
# ============================================================================

class GoogleSheetsManager:
    """Управление Google Sheets"""
    
    def __init__(self):
        self.scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        self.client = None
        self.spreadsheet = None
        self.appointments_sheet = None
        self.patients_sheet = None
        
        self.authenticate()
    
    def authenticate(self):
        """Аутентификация"""
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            if os.path.exists('credentials.json'):
                creds = Credentials.from_service_account_file(
                    'credentials.json', 
                    scopes=self.scope
                )
                self.client = gspread.authorize(creds)
                self.setup_sheets()
                print(f"{Emoji.CHECK} Google Sheets подключен")
            else:
                print(f"{Emoji.WARNING} credentials.json не найден")
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка аутентификации: {e}")
    
    def setup_sheets(self):
        """Настройка таблиц"""
        try:
            if Config.GOOGLE_SHEETS_ID:
                self.spreadsheet = self.client.open_by_key(Config.GOOGLE_SHEETS_ID)
            else:
                self.spreadsheet = self.client.create('Стоматология - Записи')
            
            # Лист записей
            try:
                self.appointments_sheet = self.spreadsheet.worksheet('Записи')
            except:
                self.appointments_sheet = self.spreadsheet.add_worksheet('Записи', 1000, 20)
                headers = ['ID', 'Дата', 'Время', 'Врач', 'Пациент', 'Телефон', 
                          'Telegram ID', 'Username', 'Статус', 'Создано', 'Напоминание']
                self.appointments_sheet.append_row(headers)
            
            # Лист пациентов
            try:
                self.patients_sheet = self.spreadsheet.worksheet('Пациенты')
            except:
                self.patients_sheet = self.spreadsheet.add_worksheet('Пациенты', 1000, 10)
                headers = ['Telegram ID', 'Имя', 'Телефон', 'Username', 
                          'Дата регистрации', 'Всего записей', 'Последний визит']
                self.patients_sheet.append_row(headers)
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка настройки таблиц: {e}")
    
    def add_appointment(self, date: str, time: str, doctor: str, patient_name: str, 
                       phone: str, telegram_id: int, username: str = '') -> bool:
        """Добавление записи"""
        try:
            if not self.appointments_sheet:
                return False
            
            # Генерируем ID записи
            import hashlib
            import time
            unique_str = f"{date}{time}{telegram_id}{time.time()}"
            record_id = hashlib.md5(unique_str.encode()).hexdigest()[:8]
            
            row = [
                record_id,
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
            
            # Обновляем данные пациента
            self.update_patient(telegram_id, patient_name, phone, username, date)
            
            print(f"{Emoji.SUCCESS} Запись {record_id} создана")
            return True
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка добавления записи: {e}")
            return False
    
    def update_patient(self, telegram_id: int, name: str, phone: str, 
                      username: str, visit_date: str):
        """Обновление данных пациента"""
        try:
            if not self.patients_sheet:
                return
            
            all_patients = self.patients_sheet.get_all_records()
            found = False
            row_num = 2
            
            for i, patient in enumerate(all_patients, start=2):
                if str(patient.get('Telegram ID', '')) == str(telegram_id):
                    found = True
                    row_num = i
                    break
            
            now = datetime.now().strftime('%d.%m.%Y %H:%M')
            
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
                    visit_date
                ]
                self.patients_sheet.append_row(row)
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка обновления пациента: {e}")
    
    def get_available_slots(self, date: str) -> List[str]:
        """Получение свободных слотов"""
        try:
            if not self.appointments_sheet:
                return Config.WORK_HOURS
            
            all_records = self.appointments_sheet.get_all_records()
            busy_times = []
            
            for record in all_records:
                if (record.get('Дата') == date and 
                    record.get('Статус') == 'Подтверждена'):
                    busy_times.append(record.get('Время'))
            
            return [t for t in Config.WORK_HOURS if t not in busy_times]
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения слотов: {e}")
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
            
            # Сортируем по дате (сначала ближайшие)
            user_apps.sort(key=lambda x: f"{x.get('Дата', '')} {x.get('Время', '')}")
            
            return user_apps
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения записей: {e}")
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
                    return True
            
            return False
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка отмены записи: {e}")
            return False
    
    def get_today_appointments(self) -> List[Dict]:
        """Получение записей на сегодня"""
        try:
            if not self.appointments_sheet:
                return []
            
            today = datetime.now().strftime('%d.%m.%Y')
            all_records = self.appointments_sheet.get_all_records()
            today_apps = []
            
            for record in all_records:
                if record.get('Дата') == today and record.get('Статус') == 'Подтверждена':
                    today_apps.append(record)
            
            return today_apps
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения записей на сегодня: {e}")
            return []
    
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
                    
                    self.appointments_sheet.update_cell(
                        i, 11, 
                        f"Отправлено {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                    )
                    return True
            
            return False
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка отметки напоминания: {e}")
            return False


# ============================================================================
# КЛАВИАТУРЫ
# ============================================================================

class Keyboards:
    """Клавиатуры с улучшенным дизайном"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Главное меню"""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{Emoji.CALENDAR} Записаться", 
                    callback_data='appointment'
                ),
                InlineKeyboardButton(
                    f"{Emoji.DOCTOR} Врачи", 
                    callback_data='doctors'
                )
            ],
            [
                InlineKeyboardButton(
                    f"{Emoji.QUESTION} Вопросы", 
                    callback_data='faq'
                ),
                InlineKeyboardButton(
                    f"{Emoji.CHECK} Мои записи", 
                    callback_data='my_appointments'
                )
            ],
            [
                InlineKeyboardButton(
                    f"{Emoji.HOSPITAL} О нас", 
                    callback_data='about'
                ),
                InlineKeyboardButton(
                    f"{Emoji.PHONE} Контакты", 
                    callback_data='contacts'
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def doctors_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура выбора врача"""
        keyboard = []
        
        for doc_id, doctor in Config.DOCTORS.items():
            icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} {doctor.name.split()[1]} — {doctor.specialty[:15]}...",
                    callback_data=f"doctor_{doc_id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(
                f"{Emoji.BACK} Назад", 
                callback_data='back_to_menu'
            )
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def date_keyboard() -> InlineKeyboardMarkup:
        """Календарь с датами"""
        keyboard = []
        today = datetime.now()
        
        days_ru = {
            0: 'ПН', 1: 'ВТ', 2: 'СР', 3: 'ЧТ', 4: 'ПТ', 5: 'СБ', 6: 'ВС'
        }
        
        row = []
        for i in range(7):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            day_num = date.day
            day_week = days_ru[date.weekday()]
            
            if i == 0:
                label = f"📅 Сегодня ({day_num})"
            elif i == 1:
                label = f"📅 Завтра ({day_num})"
            else:
                label = f"📅 {day_num} {day_week}"
            
            row.append(InlineKeyboardButton(label, callback_data=f"date_{date_str}"))
            
            if len(row) == 3 or i == 6:
                keyboard.append(row)
                row = []
        
        keyboard.append([
            InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_doctors')
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def time_keyboard(date: str, available_times: List[str]) -> InlineKeyboardMarkup:
        """Выбор времени"""
        keyboard = []
        row = []
        
        for i, time in enumerate(available_times, 1):
            row.append(InlineKeyboardButton(time, callback_data=f"time_{date}_{time}"))
            
            if len(row) == 4:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_dates')
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_keyboard(date: str, time: str, doctor_id: str) -> InlineKeyboardMarkup:
        """Кнопки подтверждения"""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{Emoji.CHECK} Да, всё верно", 
                    callback_data=f"confirm_{date}_{time}_{doctor_id}"
                ),
                InlineKeyboardButton(
                    f"{Emoji.CANCEL} Нет, отменить", 
                    callback_data='cancel_appointment'
                )
            ],
            [
                InlineKeyboardButton(
                    f"{Emoji.BACK} Выбрать другое время", 
                    callback_data='back_to_times'
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def faq_keyboard() -> InlineKeyboardMarkup:
        """FAQ с категориями"""
        keyboard = []
        
        for cat_id, category in Config.FAQ_CATEGORIES.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{category['icon']} {category['name']}",
                    callback_data=f"faq_cat_{cat_id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def faq_questions_keyboard(category: str) -> InlineKeyboardMarkup:
        """Вопросы по категории"""
        keyboard = []
        
        for question in Config.FAQ_CATEGORIES[category]['questions']:
            keyboard.append([
                InlineKeyboardButton(
                    f"❓ {question}",
                    callback_data=f"faq_q_{question}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(f"{Emoji.BACK} К категориям", callback_data='faq')
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def my_appointments_keyboard(appointments: List[Dict]) -> InlineKeyboardMarkup:
        """Кнопки для управления записями"""
        keyboard = []
        
        for app in appointments[:3]:
            if app['Статус'] == 'Подтверждена':
                keyboard.append([
                    InlineKeyboardButton(
                        f"{Emoji.CALENDAR} {app['Дата']} в {app['Время']}",
                        callback_data=f"view_appointment_{app['Дата']}_{app['Время']}"
                    )
                ])
        
        keyboard.append([
            InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def appointment_actions_keyboard(date: str, time: str) -> InlineKeyboardMarkup:
        """Действия с записью"""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{Emoji.CANCEL} Отменить запись",
                    callback_data=f"cancel_app_{date}_{time}"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{Emoji.BACK} К списку записей",
                    callback_data='my_appointments'
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ПЛАНИРОВЩИК НАПОМИНАНИЙ
# ============================================================================

class ReminderScheduler:
    """Напоминания о приеме"""
    
    def __init__(self, bot, google_sheets):
        self.bot = bot
        self.google_sheets = google_sheets
        self.scheduler = None
        self.setup()
    
    def setup(self):
        """Настройка планировщика"""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            
            self.scheduler = BackgroundScheduler()
            
            # Проверка каждый час
            for hour in range(8, 21):
                self.scheduler.add_job(
                    self.send_reminders,
                    CronTrigger(hour=hour, minute=0),
                    id=f'reminder_{hour}'
                )
            
            self.scheduler.start()
            print(f"{Emoji.CHECK} Планировщик запущен")
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка планировщика: {e}")
    
    async def send_reminders(self):
        """Отправка напоминаний"""
        try:
            today = datetime.now().strftime('%d.%m.%Y')
            all_records = self.google_sheets.appointments_sheet.get_all_records()
            
            for record in all_records:
                if (record.get('Дата') == today and 
                    record.get('Статус') == 'Подтверждена' and
                    record.get('Напоминание') == 'Нет'):
                    
                    telegram_id = int(record.get('Telegram ID', 0))
                    time = record.get('Время')
                    doctor = record.get('Врач')
                    patient = record.get('Пациент')
                    
                    try:
                        app_time = datetime.strptime(time, '%H:%M')
                        now = datetime.now()
                        app_datetime = now.replace(
                            hour=app_time.hour,
                            minute=app_time.minute,
                            second=0
                        )
                        
                        time_diff = (app_datetime - now).total_seconds() / 3600
                        
                        if 1.5 <= time_diff <= 2.5:
                            message = (
                                f"{Emoji.BELL} **Напоминание о приеме!**\n\n"
                                f"{Emoji.HEART} Здравствуйте, {patient}!\n\n"
                                f"{Emoji.CLOCK} **Время:** {time}\n"
                                f"{Emoji.DOCTOR} **Врач:** {doctor}\n"
                                f"{Emoji.LOCATION} **Адрес:** г. Москва, ул. Ленина, д. 10\n\n"
                                f"{Emoji.INFO} Ждем вас! Если нужно отменить запись, "
                                f"сделайте это в разделе «Мои записи»."
                            )
                            
                            await self.bot.send_message(
                                chat_id=telegram_id,
                                text=message,
                                parse_mode=ParseMode.MARKDOWN
                            )
                            
                            self.google_sheets.mark_reminder_sent(
                                record.get('Дата'),
                                record.get('Время'),
                                telegram_id
                            )
                            
                    except Exception as e:
                        print(f"{Emoji.ERROR} Ошибка отправки: {e}")
                        
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка в напоминаниях: {e}")


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
        
        # Временное хранилище данных
        self.temp_data = defaultdict(dict)
        
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
        """Приветствие и главное меню"""
        user = update.effective_user
        
        welcome = (
            f"{Emoji.TOOTH * 3}\n"
            f"**Здравствуйте, {user.first_name}!**\n"
            f"{Emoji.TOOTH * 3}\n\n"
            
            f"{Emoji.HOSPITAL} Добро пожаловать в бот стоматологической клиники\n\n"
            
            f"{Emoji.SPARKLES} **Что я умею:**\n"
            f"{Emoji.CHECK} Запись к врачу за 1 минуту\n"
            f"{Emoji.CHECK} Выбор удобного времени\n"
            f"{Emoji.CHECK} Напоминания о приёме\n"
            f"{Emoji.CHECK} История записей\n\n"
            
            f"{Emoji.CLOCK} **Режим работы:** 9:00–20:00 ежедневно\n"
            f"{Emoji.LOCATION} **Адрес:** г. Москва, ул. Ленина, д. 10\n\n"
            
            f"{Emoji.HEART} **Готовы начать?**"
        )
        
        await update.message.reply_text(
            welcome,
            reply_markup=self.keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена действия"""
        await update.message.reply_text(
            f"{Emoji.CANCEL} Действие отменено\n"
            f"Вы можете начать заново из главного меню",
            reply_markup=self.keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    # ========================================================================
    # ОБРАБОТЧИКИ КНОПОК (ПОЛНОСТЬЮ ИСПРАВЛЕНО)
    # ========================================================================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        # ========== НАВИГАЦИЯ ==========
        if data == 'back_to_menu':
            await query.edit_message_text(
                f"{Emoji.MENU} **Главное меню**\n\nВыберите действие:",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # ========== ЗАПИСЬ НА ПРИЕМ ==========
        elif data == 'appointment':
            # Инициализируем данные пользователя
            self.temp_data[user_id] = {}
            print(f"✅ Начало записи для user {user_id}")
            
            text = (
                f"{Emoji.DOCTOR} **Запись на прием**\n\n"
                f"Выберите специалиста:\n\n"
                f"{Emoji.DOTS} У каждого врача своя специализация\n"
                f"{Emoji.DOTS} Можно посмотреть опыт и рейтинг"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.doctors_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DOCTOR
        
        # ========== ВРАЧИ ==========
        elif data == 'doctors':
            text = f"{Emoji.DOCTOR} **Наши специалисты**\n\n"
            
            for doctor in self.config.DOCTORS.values():
                stars = "⭐" * int(doctor.rating)
                icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
                
                text += (
                    f"{icon} **{doctor.name}**\n"
                    f"└ {doctor.specialty}\n"
                    f"└ Стаж: {doctor.experience} лет {stars}\n"
                    f"└ {doctor.description[:60]}...\n\n"
                )
            
            text += f"\n{Emoji.INFO} Выберите врача для записи через меню"
            
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
            
            # Инициализируем данные, если их нет
            if user_id not in self.temp_data:
                self.temp_data[user_id] = {}
            
            # СОХРАНЯЕМ ДАННЫЕ ВРАЧА
            self.temp_data[user_id]['doctor_id'] = doctor_id
            self.temp_data[user_id]['doctor_name'] = f"{doctor.name} ({doctor.specialty})"
            
            print(f"✅ Выбран врач: {self.temp_data[user_id]['doctor_name']}")
            
            stars = "⭐" * int(doctor.rating)
            icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
            
            text = (
                f"{icon} **{doctor.name}**\n"
                f"{Emoji.STETHOSCOPE} {doctor.specialty}\n"
                f"{Emoji.HOURGLASS} Стаж: {doctor.experience} лет\n"
                f"{stars} Рейтинг: {doctor.rating}\n\n"
                
                f"**О враче:**\n"
                f"{doctor.description}\n\n"
                
                f"**Образование:**\n"
                f"{doctor.education}\n\n"
                
                f"{Emoji.CALENDAR} **Теперь выберите дату приема:**"
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
            
            # Инициализируем данные, если их нет
            if user_id not in self.temp_data:
                self.temp_data[user_id] = {}
            
            # СОХРАНЯЕМ ДАТУ
            self.temp_data[user_id]['date'] = date
            print(f"✅ Выбрана дата: {date}")
            
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
            
            date_obj = datetime.strptime(date, '%d.%m.%Y')
            months = {
                1: 'января', 2: 'февраля', 3: 'марта',
                4: 'апреля', 5: 'мая', 6: 'июня',
                7: 'июля', 8: 'августа', 9: 'сентября',
                10: 'октября', 11: 'ноября', 12: 'декабря'
            }
            date_display = f"{date_obj.day} {months[date_obj.month]}"
            
            text = (
                f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                f"{Emoji.CLOCK} **Доступное время:**\n\n"
                f"Выберите удобное время приема:"
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
            
            # Инициализируем данные, если их нет
            if user_id not in self.temp_data:
                self.temp_data[user_id] = {}
            
            # СОХРАНЯЕМ ВРЕМЯ
            self.temp_data[user_id]['time'] = time
            self.temp_data[user_id]['date'] = date
            
            doctor_name = self.temp_data[user_id].get('doctor_name', 'Врач не выбран')
            doctor_id = self.temp_data[user_id].get('doctor_id', '')
            
            print(f"✅ Выбрано время: {date} {time}")
            print(f"📝 Текущие данные: {self.temp_data[user_id]}")
            
            date_obj = datetime.strptime(date, '%d.%m.%Y')
            months = {
                1: 'января', 2: 'февраля', 3: 'марта',
                4: 'апреля', 5: 'мая', 6: 'июня',
                7: 'июля', 8: 'августа', 9: 'сентября',
                10: 'октября', 11: 'ноября', 12: 'декабря'
            }
            date_display = f"{date_obj.day} {months[date_obj.month]}"
            
            text = (
                f"{Emoji.CHECK} **Проверьте данные записи**\n\n"
                
                f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                f"{Emoji.CLOCK} **Время:** {time}\n"
                f"{Emoji.DOCTOR} **Врач:** {doctor_name}\n\n"
                
                f"Всё верно?"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.confirm_keyboard(date, time, doctor_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONFIRMING
        
        # ========== ПОДТВЕРЖДЕНИЕ (ИСПРАВЛЕНО!) ==========
        elif data.startswith('confirm_'):
            # Извлекаем данные из callback_data
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            doctor_id = parts[3]
            
            print(f"✅ Подтверждение записи для user {user_id}")
            print(f"📅 Дата: {date}, Время: {time}, Врач ID: {doctor_id}")
            
            # Инициализируем данные, если их нет
            if user_id not in self.temp_data:
                self.temp_data[user_id] = {}
            
            # СОХРАНЯЕМ ВСЕ ДАННЫЕ ИЗ CALLBACK
            self.temp_data[user_id]['date'] = date
            self.temp_data[user_id]['time'] = time
            self.temp_data[user_id]['doctor_id'] = doctor_id
            
            # Получаем имя врача
            if doctor_id in self.config.DOCTORS:
                doctor = self.config.DOCTORS[doctor_id]
                self.temp_data[user_id]['doctor_name'] = f"{doctor.name} ({doctor.specialty})"
            
            print(f"📝 Данные после подтверждения: {self.temp_data[user_id]}")
            
            # Отправляем сообщение с запросом ФИО
            text = (
                f"{Emoji.WAITING} **Остался последний шаг!**\n\n"
                
                f"{Emoji.EDIT} **Введите ваше полное ФИО**\n"
                f"└ Например: Иванов Иван Иванович\n\n"
                
                f"{Emoji.INFO} Это необходимо для оформления "
                f"медицинской карты и записи в регистратуре"
            )
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # ВАЖНО: Возвращаем состояние GETTING_NAME
            return GETTING_NAME
        
        # ========== ОТМЕНА ЗАПИСИ ==========
        elif data == 'cancel_appointment':
            await query.edit_message_text(
                f"{Emoji.CANCEL} **Запись отменена**\n\n"
                f"Вы можете записаться в другое время",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            
            if user_id in self.temp_data:
                del self.temp_data[user_id]
                
            return ConversationHandler.END
        
        elif data.startswith('cancel_app_'):
            parts = data.split('_')
            date = parts[2]
            time = parts[3]
            
            success = self.google_sheets.cancel_appointment(date, time, user_id)
            
            if success:
                await query.edit_message_text(
                    f"{Emoji.SUCCESS} **Запись отменена**\n\n"
                    f"📅 Дата: {date}\n"
                    f"🕐 Время: {time}\n\n"
                    f"Если хотите записаться заново, используйте главное меню",
                    reply_markup=self.keyboards.main_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(
                    f"{Emoji.ERROR} **Не удалось отменить запись**\n\n"
                    f"Пожалуйста, попробуйте позже или свяжитесь с клиникой",
                    reply_markup=self.keyboards.main_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
        
        # ========== МОИ ЗАПИСИ ==========
        elif data == 'my_appointments':
            appointments = self.google_sheets.get_user_appointments(user_id)
            
            if not appointments:
                text = (
                    f"{Emoji.CALENDAR} **У вас пока нет записей**\n\n"
                    f"{Emoji.INFO} Вы можете записаться на прием прямо сейчас!\n"
                    f"Для этого нажмите кнопку «Записаться» в главном меню"
                )
                await query.edit_message_text(
                    text,
                    reply_markup=self.keyboards.main_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                active_appointments = [a for a in appointments if a['Статус'] == 'Подтверждена']
                
                if not active_appointments:
                    text = (
                        f"{Emoji.INFO} **Нет активных записей**\n\n"
                        f"Все ваши записи уже завершены или отменены"
                    )
                    await query.edit_message_text(
                        text,
                        reply_markup=self.keyboards.main_menu(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    text = f"{Emoji.CHECK} **Ваши записи ({len(active_appointments)})**\n\n"
                    
                    for app in active_appointments[:5]:
                        try:
                            dt = datetime.strptime(app['Дата'], '%d.%m.%Y')
                            date_formatted = dt.strftime('%d.%m')
                        except:
                            date_formatted = app['Дата']
                        
                        text += (
                            f"{Emoji.CALENDAR} **{date_formatted}** в **{app['Время']}**\n"
                            f"└ {Emoji.DOCTOR} {app['Врач'].split('(')[0]}\n"
                            f"└ {Emoji.ACTIVE} {app['Статус']}\n\n"
                        )
                    
                    await query.edit_message_text(
                        text,
                        reply_markup=self.keyboards.my_appointments_keyboard(active_appointments),
                        parse_mode=ParseMode.MARKDOWN
                    )
        
        # ========== ПРОСМОТР ЗАПИСИ ==========
        elif data.startswith('view_appointment_'):
            parts = data.split('_')
            date = parts[2]
            time = parts[3]
            
            appointments = self.google_sheets.get_user_appointments(user_id)
            appointment = None
            
            for app in appointments:
                if app['Дата'] == date and app['Время'] == time:
                    appointment = app
                    break
            
            if appointment:
                try:
                    dt = datetime.strptime(date, '%d.%m.%Y')
                    months = {
                        1: 'января', 2: 'февраля', 3: 'марта',
                        4: 'апреля', 5: 'мая', 6: 'июня',
                        7: 'июля', 8: 'августа', 9: 'сентября',
                        10: 'октября', 11: 'ноября', 12: 'декабря'
                    }
                    date_display = f"{dt.day} {months[dt.month]} {dt.year}"
                except:
                    date_display = date
                
                text = (
                    f"{Emoji.CHECK} **Детали записи**\n\n"
                    
                    f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                    f"{Emoji.CLOCK} **Время:** {time}\n"
                    f"{Emoji.DOCTOR} **Врач:** {appointment['Врач']}\n"
                    f"{Emoji.USER} **Пациент:** {appointment['Пациент']}\n"
                    f"{Emoji.PHONE} **Телефон:** {appointment['Телефон']}\n"
                    f"{Emoji.ACTIVE} **Статус:** {appointment['Статус']}\n\n"
                    
                    f"{Emoji.INFO} Если вы не можете прийти, "
                    f"отмените запись заранее"
                )
                
                await query.edit_message_text(
                    text,
                    reply_markup=self.keyboards.appointment_actions_keyboard(date, time),
                    parse_mode=ParseMode.MARKDOWN
                )
                return VIEWING_APPOINTMENT
        
        # ========== FAQ ==========
        elif data == 'faq':
            text = (
                f"{Emoji.QUESTION} **Часто задаваемые вопросы**\n\n"
                f"Выберите категорию:"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.faq_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data.startswith('faq_cat_'):
            category = data.split('_')[2]
            
            text = f"{Config.FAQ_CATEGORIES[category]['icon']} **{Config.FAQ_CATEGORIES[category]['name']}**\n\nВыберите вопрос:"
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.faq_questions_keyboard(category),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data.startswith('faq_q_'):
            question = data[6:]
            answer = self.config.FAQ.get(question, "Информация временно недоступна")
            
            text = f"**❓ {question}**\n\n{answer}"
            
            category = 'about'
            for cat_id, cat in self.config.FAQ_CATEGORIES.items():
                if question in cat['questions']:
                    category = cat_id
                    break
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.faq_questions_keyboard(category),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== О КЛИНИКЕ ==========
        elif data == 'about':
            text = (
                f"{Emoji.HOSPITAL} **О клинике**\n\n"
                
                f"**Современная стоматология** с 2010 года\n\n"
                
                f"{Emoji.DOCTOR} **Врачи:**\n"
                f"└ 5 опытных специалистов\n"
                f"└ Средний стаж: 13 лет\n"
                f"└ Регулярное повышение квалификации\n\n"
                
                f"{Emoji.TOOTH} **Оборудование:**\n"
                f"└ Микроскоп Carl Zeiss\n"
                f"└ 3D томограф\n"
                f"└ Лазерная стоматология\n\n"
                
                f"{Emoji.HEART} **Преимущества:**\n"
                f"└ Безболезненное лечение\n"
                f"└ Стерилизация по стандартам ЕС\n"
                f"└ Детский уголок\n"
                f"└ Бесплатная парковка"
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
                f"**Email:** info@dentclinic.ru\n\n"
                
                f"{Emoji.LOCATION} **Адрес:**\n"
                f"г. Москва, ул. Ленина, д. 10\n\n"
                
                f"{Emoji.CLOCK} **Режим работы:**\n"
                f"Ежедневно: 9:00 – 20:00\n"
                f"Без выходных\n\n"
                
                f"{Emoji.MAP} **Как добраться:**\n"
                f"Метро «Парк Культуры», выход №3\n"
                f"5 минут пешком\n\n"
                
                f"{Emoji.CAR} **Парковка:**\n"
                f"Бесплатная для пациентов"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== НАВИГАЦИЯ ПО ЗАПИСИ ==========
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
        
        elif data == 'back_to_times':
            if user_id in self.temp_data and 'date' in self.temp_data[user_id]:
                date = self.temp_data[user_id]['date']
                available_times = self.google_sheets.get_available_slots(date)
                
                await query.edit_message_text(
                    f"{Emoji.CALENDAR} **Дата:** {date}\n"
                    f"{Emoji.CLOCK} **Доступное время:**",
                    reply_markup=self.keyboards.time_keyboard(date, available_times),
                    parse_mode=ParseMode.MARKDOWN
                )
            return SELECTING_TIME
        
        return ConversationHandler.END
    
    # ========================================================================
    # ОБРАБОТЧИКИ ТЕКСТА (ИСПРАВЛЕНО)
    # ========================================================================
    
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение ФИО с валидацией"""
        user_id = update.effective_user.id
        name = update.message.text.strip()
        
        print(f"📝 Получено ФИО от user {user_id}: {name}")
        
        # Проверяем, есть ли данные пользователя
        if user_id not in self.temp_data:
            self.temp_data[user_id] = {}
            print(f"⚠️ Созданы новые данные для user {user_id}")
        
        if len(name) < 5:
            await update.message.reply_text(
                f"{Emoji.CANCEL} **Слишком короткое имя**\n\n"
                f"Пожалуйста, введите полное ФИО:\n"
                f"(например: Иванов Иван Иванович)",
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
        self.temp_data[user_id]['name'] = name
        print(f"✅ Имя сохранено: {self.temp_data[user_id]['name']}")
        print(f"📝 Текущие данные: {self.temp_data[user_id]}")
        
        await update.message.reply_text(
            f"{Emoji.CHECK} **Отлично, {name.split()[0]}!**\n\n"
            
            f"{Emoji.PHONE} **Введите номер телефона**\n"
            f"в формате: +79991234567\n\n"
            
            f"{Emoji.INFO} Он нужен для связи и регистратуры",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return GETTING_PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение телефона и завершение записи"""
        user_id = update.effective_user.id
        phone_raw = update.message.text.strip()
        
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone_raw)
        
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
        
        # Приводим к единому формату
        if len(phone_clean) == 10:
            phone = f"+7{phone_clean}"
        elif phone_clean.startswith('8'):
            phone = f"+7{phone_clean[1:]}"
        elif phone_clean.startswith('7'):
            phone = f"+7{phone_clean[1:]}"
        else:
            phone = phone_clean
        
        # Получаем данные для записи
        appointment_data = self.temp_data.get(user_id, {})
        
        print(f"📝 Данные для записи: {appointment_data}")
        
        # Проверяем наличие всех необходимых данных
        required_fields = ['doctor_name', 'date', 'time', 'name']
        missing_fields = [field for field in required_fields if field not in appointment_data]
        
        if missing_fields:
            await update.message.reply_text(
                f"{Emoji.ERROR} **Ошибка: не хватает данных**\n\n"
                f"Отсутствуют: {', '.join(missing_fields)}\n"
                f"Пожалуйста, начните запись заново",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Сохраняем запись
        success = self.google_sheets.add_appointment(
            date=appointment_data['date'],
            time=appointment_data['time'],
            doctor=appointment_data['doctor_name'],
            patient_name=appointment_data['name'],
            phone=phone,
            telegram_id=user_id,
            username=update.effective_user.username or ''
        )
        
        if success:
            try:
                dt = datetime.strptime(appointment_data['date'], '%d.%m.%Y')
                months = {
                    1: 'января', 2: 'февраля', 3: 'марта',
                    4: 'апреля', 5: 'мая', 6: 'июня',
                    7: 'июля', 8: 'августа', 9: 'сентября',
                    10: 'октября', 11: 'ноября', 12: 'декабря'
                }
                date_display = f"{dt.day} {months[dt.month]}"
            except:
                date_display = appointment_data['date']
            
            text = (
                f"{Emoji.SUCCESS * 3} **ЗАПИСЬ ПОДТВЕРЖДЕНА** {Emoji.SUCCESS * 3}\n\n"
                
                f"{Emoji.CALENDAR} **Дата:** {date_display}\n"
                f"{Emoji.CLOCK} **Время:** {appointment_data['time']}\n"
                f"{Emoji.DOCTOR} **Врач:** {appointment_data['doctor_name']}\n"
                f"{Emoji.USER} **Пациент:** {appointment_data['name']}\n"
                f"{Emoji.PHONE} **Телефон:** {phone}\n\n"
                
                f"{Emoji.BELL} **Что дальше?**\n\n"
                
                f"1️⃣ Мы отправим напоминание за 2 часа до приема\n"
                f"2️⃣ Примите талон в регистратуре за 5 минут\n"
                f"3️⃣ Если не можете прийти — отмените запись в боте\n\n"
                
                f"{Emoji.HEART} **Спасибо, что выбрали нас!**\n"
                f"Ждем вас на приеме!"
            )
            
            await update.message.reply_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Отправляем уведомление админам
            for admin_id in self.config.ADMIN_IDS:
                try:
                    admin_text = (
                        f"{Emoji.BELL} **НОВАЯ ЗАПИСЬ!**\n\n"
                        f"📅 {appointment_data['date']} в {appointment_data['time']}\n"
                        f"👨‍⚕️ {appointment_data['doctor_name']}\n"
                        f"👤 {appointment_data['name']}\n"
                        f"📞 {phone}\n"
                        f"🆔 {user_id}\n"
                        f"📱 @{update.effective_user.username or 'нет'}"
                    )
                    
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    print(f"{Emoji.ERROR} Ошибка отправки админу {admin_id}: {e}")
            
            print(f"{Emoji.SUCCESS} Запись успешно создана для user {user_id}")
            
        else:
            await update.message.reply_text(
                f"{Emoji.ERROR} **Ошибка при сохранении**\n\n"
                f"Пожалуйста, попробуйте позже или позвоните нам:\n"
                f"{Emoji.PHONE} +7 (999) 123-45-67",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Очищаем временные данные
        if user_id in self.temp_data:
            del self.temp_data[user_id]
        
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
            
            # Конверсация записи
            appointment_conv = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(self.button_handler, pattern='^appointment$')
                ],
                states={
                    SELECTING_DOCTOR: [
                        CallbackQueryHandler(self.button_handler, pattern='^(doctor_|back_to_menu|back_to_doctors)$')
                    ],
                    SELECTING_DATE: [
                        CallbackQueryHandler(self.button_handler, pattern='^(date_|back_to_doctors|back_to_menu)$')
                    ],
                    SELECTING_TIME: [
                        CallbackQueryHandler(self.button_handler, pattern='^(time_|back_to_dates|back_to_menu|back_to_times)$')
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
                        CallbackQueryHandler(self.button_handler, pattern='^(cancel_app_|my_appointments|back_to_menu)$')
                    ]
                },
                fallbacks=[
                    CommandHandler('cancel', self.cancel),
                    CallbackQueryHandler(self.button_handler, pattern='^back_to_menu$')
                ],
                name="appointment_conversation"
            )
            
            self.application.add_handler(appointment_conv)
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            if self.google_sheets.client:
                self.reminder_scheduler = ReminderScheduler(self.application.bot, self.google_sheets)
            
            print("\n" + "="*60)
            print(f"{Emoji.TOOTH} СТОМАТОЛОГИЧЕСКИЙ БОТ ПРЕМИУМ")
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
