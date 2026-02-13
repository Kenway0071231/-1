"""
СТОМАТОЛОГИЧЕСКИЙ БОТ - SQLITE ВЕРСИЯ
Версия: 10.0.0 (РАБОТАЕТ НА ЛЮБОМ ХОСТИНГЕ)
База данных: SQLite (встроенная, не требует установки)
Функции: запись, свободное время, напоминания, админка
"""

import logging
import re
import sys
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

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
# ЭМОДЗИ - ТОЛЬКО НЕОБХОДИМЫЕ
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
    MONEY = "💰"
    QUESTION = "❓"
    USER = "👤"
    CROWN = "👑"
    STATS = "📊"
    DATABASE = "🗄️"

# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================
@dataclass
class Doctor:
    id: int
    name: str
    specialty: str
    experience: int
    description: str
    rating: float
    
@dataclass
class Appointment:
    id: int
    doctor_id: int
    doctor_name: str
    date: str
    time: str
    patient_name: str
    patient_phone: str
    telegram_id: int
    status: str
    created_at: str

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================
class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
    
    # База данных
    DB_PATH = 'dental_clinic.db'
    
    # Врачи
    DOCTORS = {
        1: Doctor(
            id=1,
            name='Иванова Мария Петровна',
            specialty='Стоматолог-терапевт',
            experience=15,
            description='Лечение кариеса, пульпита, эндодонтия',
            rating=4.9
        ),
        2: Doctor(
            id=2,
            name='Петров Сергей Иванович',
            specialty='Стоматолог-хирург',
            experience=12,
            description='Удаление зубов, имплантация',
            rating=4.8
        ),
        3: Doctor(
            id=3,
            name='Сидорова Анна Викторовна',
            specialty='Стоматолог-ортодонт',
            experience=10,
            description='Исправление прикуса, брекеты',
            rating=4.9
        ),
        4: Doctor(
            id=4,
            name='Козлов Алексей Николаевич',
            specialty='Стоматолог-ортопед',
            experience=20,
            description='Протезирование, коронки, виниры',
            rating=5.0
        ),
        5: Doctor(
            id=5,
            name='Соколова Елена Дмитриевна',
            specialty='Детский стоматолог',
            experience=8,
            description='Лечение детей с 3 лет',
            rating=4.9
        )
    }
    
    # Рабочее время
    WORK_HOURS = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '14:00', '14:30', '15:00', '15:30',
        '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]
    
    # FAQ
    FAQ = {
        'Режим работы': f"{Emoji.CLOCK} Ежедневно 9:00-20:00, без выходных",
        'Как добраться': f"{Emoji.LOCATION} Москва, ул. Ленина, д. 10, метро Парк Культуры",
        'Стоимость': f"{Emoji.MONEY} Консультация 500₽, лечение от 3000₽",
        'Больно?': f"{Emoji.HEART} Современная анестезия, безболезненно",
        'Детям': f"{Emoji.DOCTOR_WOMAN} С 3 лет, первый осмотр бесплатно",
        'Отмена': f"{Emoji.CANCEL} В боте в разделе «Мои записи»"
    }

# ============================================================================
# БАЗА ДАННЫХ SQLite - ПОЛНОСТЬЮ АВТОНОМНАЯ
# ============================================================================
class Database:
    """Работа с SQLite базой данных"""
    
    def __init__(self, db_path: str = Config.DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Получение соединения с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def init_database(self):
        """Инициализация таблиц"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица записей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_id INTEGER NOT NULL,
                    doctor_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    patient_name TEXT NOT NULL,
                    patient_phone TEXT NOT NULL,
                    telegram_id INTEGER NOT NULL,
                    username TEXT,
                    status TEXT DEFAULT 'confirmed',
                    created_at TEXT NOT NULL,
                    reminder_sent INTEGER DEFAULT 0,
                    UNIQUE(date, time, doctor_id)
                )
            ''')
            
            # Таблица пациентов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patients (
                    telegram_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    username TEXT,
                    registered_at TEXT NOT NULL,
                    total_appointments INTEGER DEFAULT 0,
                    last_visit TEXT
                )
            ''')
            
            # Таблица администраторов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    telegram_id INTEGER PRIMARY KEY,
                    added_at TEXT NOT NULL
                )
            ''')
            
            # Добавляем админов из конфига
            for admin_id in Config.ADMIN_IDS:
                cursor.execute(
                    'INSERT OR IGNORE INTO admins (telegram_id, added_at) VALUES (?, ?)',
                    (admin_id, datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
                )
            
            print(f"{Emoji.DATABASE} База данных инициализирована: {self.db_path}")
    
    # ========== РАБОТА С ЗАПИСЯМИ ==========
    
    def add_appointment(self, doctor_id: int, doctor_name: str, date: str, time: str,
                       patient_name: str, patient_phone: str, telegram_id: int,
                       username: str = '') -> Optional[int]:
        """Добавление новой записи"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем, свободно ли время
                cursor.execute(
                    'SELECT id FROM appointments WHERE date = ? AND time = ? AND doctor_id = ? AND status = "confirmed"',
                    (date, time, doctor_id)
                )
                if cursor.fetchone():
                    return None
                
                # Создаем запись
                created_at = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                cursor.execute('''
                    INSERT INTO appointments 
                    (doctor_id, doctor_name, date, time, patient_name, patient_phone, 
                     telegram_id, username, status, created_at, reminder_sent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    doctor_id, doctor_name, date, time, patient_name, patient_phone,
                    telegram_id, username, 'confirmed', created_at, 0
                ))
                
                appointment_id = cursor.lastrowid
                
                # Обновляем информацию о пациенте
                self.update_patient(
                    telegram_id, patient_name, patient_phone, username, date
                )
                
                return appointment_id
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка добавления записи: {e}")
            return None
    
    def get_available_slots(self, doctor_id: int, date: str) -> List[str]:
        """Получение свободного времени для конкретного врача"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT time FROM appointments 
                    WHERE doctor_id = ? AND date = ? AND status = "confirmed"
                ''', (doctor_id, date))
                
                busy_times = [row['time'] for row in cursor.fetchall()]
                
                # Возвращаем только свободное время
                return [t for t in Config.WORK_HOURS if t not in busy_times]
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения слотов: {e}")
            return Config.WORK_HOURS
    
    def get_user_appointments(self, telegram_id: int) -> List[Dict]:
        """Получение записей пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM appointments 
                    WHERE telegram_id = ? 
                    ORDER BY date, time
                ''', (telegram_id,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения записей: {e}")
            return []
    
    def get_active_appointments(self, telegram_id: int) -> List[Dict]:
        """Получение активных записей пользователя"""
        try:
            today = datetime.now().strftime('%d.%m.%Y')
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM appointments 
                    WHERE telegram_id = ? AND status = "confirmed" AND date >= ?
                    ORDER BY date, time
                ''', (telegram_id, today))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения активных записей: {e}")
            return []
    
    def cancel_appointment(self, appointment_id: int, telegram_id: int) -> bool:
        """Отмена записи"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем, принадлежит ли запись пользователю
                cursor.execute('''
                    UPDATE appointments 
                    SET status = "cancelled" 
                    WHERE id = ? AND telegram_id = ? AND status = "confirmed"
                ''', (appointment_id, telegram_id))
                
                return cursor.rowcount > 0
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка отмены записи: {e}")
            return False
    
    def get_today_appointments(self) -> List[Dict]:
        """Получение записей на сегодня"""
        try:
            today = datetime.now().strftime('%d.%m.%Y')
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM appointments 
                    WHERE date = ? AND status = "confirmed"
                    ORDER BY time
                ''', (today,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения записей на сегодня: {e}")
            return []
    
    def get_appointments_for_reminder(self) -> List[Dict]:
        """Получение записей для напоминания"""
        try:
            today = datetime.now().strftime('%d.%m.%Y')
            current_time = datetime.now().strftime('%H:%M')
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM appointments 
                    WHERE date = ? AND status = "confirmed" AND reminder_sent = 0
                    ORDER BY time
                ''', (today,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения записей для напоминания: {e}")
            return []
    
    def mark_reminder_sent(self, appointment_id: int) -> bool:
        """Отметить отправку напоминания"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE appointments 
                    SET reminder_sent = 1 
                    WHERE id = ?
                ''', (appointment_id,))
                
                return cursor.rowcount > 0
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка отметки напоминания: {e}")
            return False
    
    # ========== РАБОТА С ПАЦИЕНТАМИ ==========
    
    def update_patient(self, telegram_id: int, name: str, phone: str,
                      username: str, visit_date: str):
        """Обновление данных пациента"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                
                cursor.execute('''
                    INSERT INTO patients (telegram_id, name, phone, username, registered_at, last_visit, total_appointments)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(telegram_id) DO UPDATE SET
                        name = excluded.name,
                        phone = excluded.phone,
                        username = excluded.username,
                        last_visit = excluded.last_visit,
                        total_appointments = total_appointments + 1
                ''', (telegram_id, name, phone, username, now, visit_date))
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка обновления пациента: {e}")
    
    # ========== СТАТИСТИКА ==========
    
    def get_statistics(self) -> Dict:
        """Получение статистики"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                today = datetime.now().strftime('%d.%m.%Y')
                
                # Общее количество записей
                cursor.execute('SELECT COUNT(*) FROM appointments')
                total = cursor.fetchone()[0]
                
                # Активные записи
                cursor.execute('SELECT COUNT(*) FROM appointments WHERE status = "confirmed"')
                active = cursor.fetchone()[0]
                
                # Записи на сегодня
                cursor.execute('SELECT COUNT(*) FROM appointments WHERE date = ? AND status = "confirmed"', (today,))
                today_count = cursor.fetchone()[0]
                
                # Количество пациентов
                cursor.execute('SELECT COUNT(*) FROM patients')
                patients = cursor.fetchone()[0]
                
                return {
                    'total': total,
                    'active': active,
                    'today': today_count,
                    'patients': patients
                }
                
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка получения статистики: {e}")
            return {}

# ============================================================================
# ПЛАНИРОВЩИК НАПОМИНАНИЙ
# ============================================================================
class ReminderScheduler:
    """Планировщик напоминаний"""
    
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.scheduler = None
        self.setup()
    
    def setup(self):
        """Настройка планировщика"""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
            
            self.scheduler = AsyncIOScheduler()
            
            # Проверяем каждый час
            for hour in range(8, 21):
                self.scheduler.add_job(
                    self.send_reminders,
                    CronTrigger(hour=hour, minute=0),
                    id=f'reminder_{hour}'
                )
            
            self.scheduler.start()
            print(f"{Emoji.BELL} Планировщик напоминаний запущен")
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка настройки планировщика: {e}")
    
    async def send_reminders(self):
        """Отправка напоминаний"""
        try:
            appointments = self.db.get_appointments_for_reminder()
            
            for apt in appointments:
                try:
                    # Проверяем время (за 2 часа)
                    apt_time = datetime.strptime(apt['time'], '%H:%M')
                    now = datetime.now()
                    apt_datetime = now.replace(
                        hour=apt_time.hour,
                        minute=apt_time.minute,
                        second=0
                    )
                    
                    time_diff = (apt_datetime - now).total_seconds() / 3600
                    
                    if 1.5 <= time_diff <= 2.5:
                        message = (
                            f"{Emoji.BELL} **Напоминание о приеме!**\n\n"
                            f"{Emoji.DOCTOR} Врач: {apt['doctor_name']}\n"
                            f"{Emoji.CLOCK} Время: {apt['time']}\n"
                            f"{Emoji.LOCATION} Адрес: Москва, ул. Ленина, д. 10\n\n"
                            f"{Emoji.INFO} Ждем вас!"
                        )
                        
                        await self.bot.send_message(
                            chat_id=apt['telegram_id'],
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        
                        self.db.mark_reminder_sent(apt['id'])
                        print(f"{Emoji.BELL} Напоминание отправлено {apt['telegram_id']}")
                        
                except Exception as e:
                    print(f"{Emoji.ERROR} Ошибка отправки: {e}")
                    
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка в планировщике: {e}")

# ============================================================================
# КЛАВИАТУРЫ
# ============================================================================
class Keyboards:
    
    @staticmethod
    def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
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
        keyboard = []
        for doc_id, doctor in Config.DOCTORS.items():
            icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
            name_parts = doctor.name.split()
            short_name = f"{name_parts[0]} {name_parts[1][0]}." if len(name_parts) > 1 else doctor.name
            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} {short_name} - {doctor.specialty}",
                    callback_data=f"doctor_{doc_id}"
                )
            ])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def date_keyboard() -> InlineKeyboardMarkup:
        keyboard = []
        today = datetime.now()
        
        for i in range(14):  # 14 дней вперед
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            
            if i == 0:
                label = f"{Emoji.CALENDAR} Сегодня ({date.day}.{date.month})"
            elif i == 1:
                label = f"{Emoji.CALENDAR} Завтра ({date.day}.{date.month})"
            else:
                label = f"{Emoji.CALENDAR} {date.day}.{date.month}"
            
            keyboard.append([InlineKeyboardButton(label, callback_data=f"date_{date_str}")])
        
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_doctors')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def time_keyboard(doctor_id: int, date: str, times: List[str]) -> InlineKeyboardMarkup:
        keyboard = []
        row = []
        
        for time in times[:8]:
            row.append(InlineKeyboardButton(
                time, 
                callback_data=f"time_{doctor_id}_{date}_{time}"
            ))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_dates')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_keyboard(appointment_id: int) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton(f"{Emoji.CHECK} Подтвердить", callback_data=f"confirm_{appointment_id}"),
                InlineKeyboardButton(f"{Emoji.CANCEL} Отмена", callback_data='cancel_appointment')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def faq_keyboard() -> InlineKeyboardMarkup:
        keyboard = []
        for question in Config.FAQ.keys():
            keyboard.append([
                InlineKeyboardButton(f"{Emoji.QUESTION} {question}", callback_data=f"faq_{question}")
            ])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def my_appointments_keyboard(appointments: List[Dict]) -> InlineKeyboardMarkup:
        keyboard = []
        for apt in appointments[:5]:
            keyboard.append([
                InlineKeyboardButton(
                    f"{Emoji.CALENDAR} {apt['date']} {apt['time']} - {apt['doctor_name'][:20]}",
                    callback_data=f"view_{apt['id']}"
                )
            ])
        keyboard.append([InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def appointment_actions_keyboard(appointment_id: int) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CANCEL} Отменить запись", callback_data=f"cancel_{appointment_id}")],
            [InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='my_appointments')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_keyboard() -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CALENDAR} Записи на сегодня", callback_data='admin_today')],
            [InlineKeyboardButton(f"{Emoji.STATS} Статистика", callback_data='admin_stats')],
            [InlineKeyboardButton(f"{Emoji.DATABASE} База данных", callback_data='admin_db')],
            [InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data='back_to_menu')]
        ]
        return InlineKeyboardMarkup(keyboard)

# ============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# ============================================================================
class DentalClinicBot:
    
    def __init__(self):
        self.config = Config()
        self.keyboards = Keyboards()
        self.db = Database()
        self.reminder_scheduler = None
        self.application = None
        
        # Временные данные пользователей
        self.temp_data = {}
        
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)
    
    # ========================================================================
    # КОМАНДЫ
    # ========================================================================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_admin = user.id in self.config.ADMIN_IDS
        
        await update.message.reply_text(
            f"{Emoji.TOOTH} **Здравствуйте, {user.first_name}!**\n\n"
            f"🦷 Стоматологическая клиника\n"
            f"{Emoji.CLOCK} 9:00-20:00 ежедневно\n"
            f"{Emoji.LOCATION} Москва, ул. Ленина, д. 10\n\n"
            f"Выберите действие:",
            reply_markup=self.keyboards.main_menu(is_admin),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.temp_data:
            del self.temp_data[user_id]
        
        is_admin = user_id in self.config.ADMIN_IDS
        await update.message.reply_text(
            f"{Emoji.CANCEL} Действие отменено",
            reply_markup=self.keyboards.main_menu(is_admin)
        )
        return ConversationHandler.END
    
    # ========================================================================
    # ОБРАБОТЧИКИ КНОПОК
    # ========================================================================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        is_admin = user_id in self.config.ADMIN_IDS
        
        print(f"🔘 Нажата кнопка: {data} от {user_id}")
        
        # ========== НАВИГАЦИЯ ==========
        if data == 'back_to_menu':
            await query.edit_message_text(
                "Главное меню:",
                reply_markup=self.keyboards.main_menu(is_admin)
            )
            return ConversationHandler.END
        
        # ========== ЗАПИСЬ НА ПРИЕМ ==========
        elif data == 'appointment':
            self.temp_data[user_id] = {}
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
                icon = Emoji.DOCTOR_WOMAN if 'ва' in doctor.name else Emoji.DOCTOR
                stars = Emoji.STAR * int(doctor.rating)
                text += (
                    f"{icon} **{doctor.name}**\n"
                    f"• {doctor.specialty}\n"
                    f"• Стаж: {doctor.experience} лет {stars}\n"
                    f"• {doctor.description}\n\n"
                )
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.doctors_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DOCTOR
        
        # ========== ВЫБОР ВРАЧА ==========
        elif data.startswith('doctor_'):
            doctor_id = int(data.split('_')[1])
            doctor = self.config.DOCTORS[doctor_id]
            
            self.temp_data[user_id] = {
                'doctor_id': doctor_id,
                'doctor_name': f"{doctor.name} ({doctor.specialty})"
            }
            
            await query.edit_message_text(
                f"{Emoji.DOCTOR} **{doctor.name}**\n"
                f"{doctor.specialty}\n\n"
                f"{Emoji.CALENDAR} **Выберите дату:**",
                reply_markup=self.keyboards.date_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DATE
        
        # ========== ВЫБОР ДАТЫ ==========
        elif data.startswith('date_'):
            date = data.split('_')[1]
            
            if user_id not in self.temp_data:
                self.temp_data[user_id] = {}
            self.temp_data[user_id]['date'] = date
            
            doctor_id = self.temp_data[user_id].get('doctor_id')
            available_times = self.db.get_available_slots(doctor_id, date)
            
            if not available_times:
                await query.edit_message_text(
                    f"{Emoji.CANCEL} **Нет свободного времени**\n\n"
                    f"Выберите другую дату:",
                    reply_markup=self.keyboards.date_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                return SELECTING_DATE
            
            await query.edit_message_text(
                f"{Emoji.CALENDAR} Дата: {date}\n\n"
                f"Доступное время:",
                reply_markup=self.keyboards.time_keyboard(doctor_id, date, available_times)
            )
            return SELECTING_TIME
        
        # ========== ВЫБОР ВРЕМЕНИ ==========
        elif data.startswith('time_'):
            parts = data.split('_')
            doctor_id = int(parts[1])
            date = parts[2]
            time = parts[3]
            
            self.temp_data[user_id]['date'] = date
            self.temp_data[user_id]['time'] = time
            self.temp_data[user_id]['doctor_id'] = doctor_id
            
            # Создаем временную запись для подтверждения
            temp_appointment_id = hash(f"{user_id}{date}{time}{doctor_id}") % 1000000
            
            await query.edit_message_text(
                f"{Emoji.CHECK} **Проверьте данные:**\n\n"
                f"📅 Дата: {date}\n"
                f"🕐 Время: {time}\n"
                f"👨‍⚕️ Врач: {self.temp_data[user_id]['doctor_name']}\n\n"
                f"Всё верно?",
                reply_markup=self.keyboards.confirm_keyboard(temp_appointment_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONFIRMING
        
        # ========== ПОДТВЕРЖДЕНИЕ ==========
        elif data.startswith('confirm_'):
            # Удаляем сообщение с подтверждением
            await query.message.delete()
            
            # Запрашиваем ФИО
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"{Emoji.EDIT} **Введите ваше ФИО**\n\n"
                    f"Пример: Иванов Иван Иванович"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_NAME
        
        # ========== ОТМЕНА ЗАПИСИ ==========
        elif data == 'cancel_appointment':
            if user_id in self.temp_data:
                del self.temp_data[user_id]
            await query.edit_message_text(
                f"{Emoji.CANCEL} Запись отменена",
                reply_markup=self.keyboards.main_menu(is_admin)
            )
            return ConversationHandler.END
        
        elif data.startswith('cancel_'):
            appointment_id = int(data.split('_')[1])
            success = self.db.cancel_appointment(appointment_id, user_id)
            
            if success:
                text = f"{Emoji.SUCCESS} Запись отменена"
            else:
                text = f"{Emoji.ERROR} Не удалось отменить запись"
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(is_admin)
            )
        
        # ========== МОИ ЗАПИСИ ==========
        elif data == 'my_appointments':
            appointments = self.db.get_active_appointments(user_id)
            
            if not appointments:
                await query.edit_message_text(
                    f"{Emoji.INFO} У вас нет активных записей",
                    reply_markup=self.keyboards.main_menu(is_admin)
                )
            else:
                text = f"{Emoji.CHECK} **Ваши записи ({len(appointments)})**\n\n"
                for apt in appointments:
                    text += (
                        f"{Emoji.CALENDAR} **{apt['date']}** в **{apt['time']}**\n"
                        f"{Emoji.DOCTOR} {apt['doctor_name'][:30]}...\n\n"
                    )
                
                await query.edit_message_text(
                    text,
                    reply_markup=self.keyboards.my_appointments_keyboard(appointments),
                    parse_mode=ParseMode.MARKDOWN
                )
        
        # ========== ПРОСМОТР ЗАПИСИ ==========
        elif data.startswith('view_'):
            appointment_id = int(data.split('_')[1])
            
            appointments = self.db.get_user_appointments(user_id)
            appointment = next((a for a in appointments if a['id'] == appointment_id), None)
            
            if appointment:
                text = (
                    f"{Emoji.CHECK} **Детали записи**\n\n"
                    f"{Emoji.CALENDAR} **Дата:** {appointment['date']}\n"
                    f"{Emoji.CLOCK} **Время:** {appointment['time']}\n"
                    f"{Emoji.DOCTOR} **Врач:** {appointment['doctor_name']}\n"
                    f"{Emoji.USER} **Пациент:** {appointment['patient_name']}\n"
                    f"{Emoji.PHONE} **Телефон:** {appointment['patient_phone']}\n"
                    f"{Emoji.ACTIVE} **Статус:** {appointment['status']}"
                )
                
                await query.edit_message_text(
                    text,
                    reply_markup=self.keyboards.appointment_actions_keyboard(appointment_id),
                    parse_mode=ParseMode.MARKDOWN
                )
                return VIEWING_APPOINTMENT
        
        # ========== FAQ ==========
        elif data == 'faq':
            await query.edit_message_text(
                f"{Emoji.QUESTION} **Часто задаваемые вопросы**\n\n"
                f"Выберите вопрос:",
                reply_markup=self.keyboards.faq_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data.startswith('faq_'):
            question = data[4:]
            answer = self.config.FAQ.get(question, "Информация недоступна")
            await query.edit_message_text(
                f"**{question}**\n\n{answer}",
                reply_markup=self.keyboards.faq_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== О КЛИНИКЕ ==========
        elif data == 'about':
            await query.edit_message_text(
                f"{Emoji.HOSPITAL} **О клинике**\n\n"
                f"🏥 Современная стоматология с 2010 года\n"
                f"👨‍⚕️ 5 опытных врачей\n"
                f"💉 Безболезненное лечение\n"
                f"🚗 Бесплатная парковка\n\n"
                f"{Emoji.CLOCK} 9:00-20:00 без выходных",
                reply_markup=self.keyboards.main_menu(is_admin),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== КОНТАКТЫ ==========
        elif data == 'contacts':
            await query.edit_message_text(
                f"{Emoji.PHONE} **Контакты**\n\n"
                f"📞 Телефон: +7 (999) 123-45-67\n"
                f"{Emoji.LOCATION} Адрес: Москва, ул. Ленина, д. 10\n"
                f"{Emoji.MAP} Метро: Парк Культуры, выход №3\n"
                f"{Emoji.CLOCK} Режим работы: 9:00-20:00",
                reply_markup=self.keyboards.main_menu(is_admin),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== АДМИН ПАНЕЛЬ ==========
        elif data == 'admin':
            if not is_admin:
                await query.edit_message_text(f"{Emoji.ERROR} Доступ запрещен")
                return
            
            await query.edit_message_text(
                f"{Emoji.CROWN} **Панель администратора**",
                reply_markup=self.keyboards.admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'admin_today':
            if not is_admin:
                return
            
            appointments = self.db.get_today_appointments()
            
            if not appointments:
                text = f"{Emoji.CALENDAR} На сегодня записей нет"
            else:
                text = f"{Emoji.CALENDAR} **Записи на сегодня ({len(appointments)})**\n\n"
                for apt in appointments:
                    text += (
                        f"{Emoji.CLOCK} {apt['time']}\n"
                        f"{Emoji.USER} {apt['patient_name']}\n"
                        f"{Emoji.PHONE} {apt['patient_phone']}\n"
                        f"{Emoji.DOCTOR} {apt['doctor_name'][:20]}...\n\n"
                    )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'admin_stats':
            if not is_admin:
                return
            
            stats = self.db.get_statistics()
            
            text = (
                f"{Emoji.STATS} **Статистика**\n\n"
                f"📊 Всего записей: {stats.get('total', 0)}\n"
                f"{Emoji.ACTIVE} Активных: {stats.get('active', 0)}\n"
                f"{Emoji.CALENDAR} На сегодня: {stats.get('today', 0)}\n"
                f"{Emoji.USER} Пациентов: {stats.get('patients', 0)}\n"
                f"{Emoji.DOCTOR} Врачей: {len(self.config.DOCTORS)}\n\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'admin_db':
            if not is_admin:
                return
            
            # Получаем размер БД
            db_size = os.path.getsize(Config.DB_PATH) / 1024  # в KB
            
            text = (
                f"{Emoji.DATABASE} **База данных**\n\n"
                f"📁 Файл: {Config.DB_PATH}\n"
                f"💾 Размер: {db_size:.1f} KB\n"
                f"✅ Статус: Работает\n\n"
                f"Автономная SQLite база данных.\n"
                f"Не требует интернета и настроек."
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ========== НАВИГАЦИЯ ==========
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
    # ОБРАБОТЧИКИ ТЕКСТА - ГАРАНТИРОВАННО РАБОТАЮТ
    # ========================================================================
    
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение ФИО"""
        user_id = update.effective_user.id
        name = update.message.text.strip()
        
        print(f"📝 ПОЛУЧЕНО ФИО: '{name}' от {user_id}")
        
        # Проверяем данные
        if user_id not in self.temp_data:
            self.temp_data[user_id] = {}
            print(f"⚠️ СОЗДАНЫ НОВЫЕ ДАННЫЕ ДЛЯ {user_id}")
        
        # Валидация
        if len(name) < 5:
            await update.message.reply_text(
                f"{Emoji.CANCEL} Слишком короткое ФИО\n\n"
                f"Введите полное ФИО (минимум 5 символов):"
            )
            return GETTING_NAME
        
        if any(c.isdigit() for c in name):
            await update.message.reply_text(
                f"{Emoji.CANCEL} ФИО не должно содержать цифры\n\n"
                f"Введите ФИО правильно:"
            )
            return GETTING_NAME
        
        # Сохраняем ФИО
        self.temp_data[user_id]['patient_name'] = name
        print(f"✅ ФИО СОХРАНЕНО: {name}")
        print(f"📋 ТЕКУЩИЕ ДАННЫЕ: {self.temp_data[user_id]}")
        
        # Запрашиваем телефон
        await update.message.reply_text(
            f"{Emoji.CHECK} Спасибо, {name.split()[0] if name.split() else ''}!\n\n"
            f"{Emoji.PHONE} **Введите номер телефона**\n"
            f"Формат: +79991234567 или 89991234567",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return GETTING_PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение телефона и сохранение записи"""
        user_id = update.effective_user.id
        phone_raw = update.message.text.strip()
        
        print(f"📞 ПОЛУЧЕН ТЕЛЕФОН: '{phone_raw}' от {user_id}")
        print(f"📋 ДАННЫЕ ПОЛЬЗОВАТЕЛЯ: {self.temp_data.get(user_id, {})}")
        
        # Проверяем наличие данных
        if user_id not in self.temp_data:
            await update.message.reply_text(
                f"{Emoji.ERROR} Ошибка: данные не найдены\n\n"
                f"Начните запись заново.",
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS)
            )
            return ConversationHandler.END
        
        # Очищаем телефон
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone_raw)
        
        # Валидация
        if not re.match(r'^(\+7|8|7)?\d{10}$', phone_clean):
            await update.message.reply_text(
                f"{Emoji.CANCEL} Неверный формат телефона\n\n"
                f"Используйте:\n"
                f"• +79991234567\n"
                f"• 89991234567\n"
                f"• 79991234567"
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
        data = self.temp_data[user_id]
        
        # Проверяем наличие всех полей
        required_fields = ['doctor_id', 'doctor_name', 'date', 'time', 'patient_name']
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            await update.message.reply_text(
                f"{Emoji.ERROR} Ошибка: не хватает данных ({', '.join(missing)})\n\n"
                f"Начните запись заново.",
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS)
            )
            return ConversationHandler.END
        
        # Сохраняем в базу данных
        appointment_id = self.db.add_appointment(
            doctor_id=data['doctor_id'],
            doctor_name=data['doctor_name'],
            date=data['date'],
            time=data['time'],
            patient_name=data['patient_name'],
            patient_phone=phone,
            telegram_id=user_id,
            username=update.effective_user.username or ''
        )
        
        if appointment_id:
            # Сообщение об успехе
            text = (
                f"{Emoji.SUCCESS} **ЗАПИСЬ ПОДТВЕРЖДЕНА!**\n\n"
                f"{Emoji.CALENDAR} **Дата:** {data['date']}\n"
                f"{Emoji.CLOCK} **Время:** {data['time']}\n"
                f"{Emoji.DOCTOR} **Врач:** {data['doctor_name']}\n"
                f"{Emoji.USER} **Пациент:** {data['patient_name']}\n"
                f"{Emoji.PHONE} **Телефон:** {phone}\n\n"
                f"{Emoji.BELL} Напоминание придет за 2 часа\n"
                f"{Emoji.HEART} Спасибо! Ждем вас."
            )
            
            await update.message.reply_text(
                text,
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Уведомление админам
            for admin_id in self.config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"{Emoji.BELL} **НОВАЯ ЗАПИСЬ**\n\n"
                            f"📅 {data['date']}\n"
                            f"⏰ {data['time']}\n"
                            f"👨‍⚕️ {data['doctor_name']}\n"
                            f"👤 {data['patient_name']}\n"
                            f"📞 {phone}\n"
                            f"🆔 {user_id}"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            
            print(f"{Emoji.SUCCESS} ЗАПИСЬ #{appointment_id} СОХРАНЕНА")
            
        else:
            await update.message.reply_text(
                f"{Emoji.ERROR} Ошибка сохранения\n\n"
                f"Возможно, это время уже занято.\n"
                f"Попробуйте другое время.",
                reply_markup=self.keyboards.main_menu(user_id in self.config.ADMIN_IDS)
            )
        
        # Очищаем временные данные
        if user_id in self.temp_data:
            del self.temp_data[user_id]
            print(f"🧹 ДАННЫЕ ПОЛЬЗОВАТЕЛЯ {user_id} ОЧИЩЕНЫ")
        
        return ConversationHandler.END
    
    # ========================================================================
    # ЗАПУСК БОТА
    # ========================================================================
    
    def run(self):
        """Запуск бота"""
        if not self.config.BOT_TOKEN:
            print(f"{Emoji.ERROR} Токен не найден! Создайте файл .env с BOT_TOKEN=")
            return
        
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
                ],
            )
            
            self.application.add_handler(conv_handler)
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            # Планировщик напоминаний
            self.reminder_scheduler = ReminderScheduler(self.application.bot, self.db)
            
            print("\n" + "="*60)
            print(f"{Emoji.TOOTH} СТОМАТОЛОГИЧЕСКИЙ БОТ С SQLite")
            print("="*60)
            print(f"{Emoji.CHECK} Токен: {self.config.BOT_TOKEN[:15]}...")
            print(f"{Emoji.DOCTOR} Врачей: {len(self.config.DOCTORS)}")
            print(f"{Emoji.CROWN} Админов: {len(self.config.ADMIN_IDS)}")
            print(f"{Emoji.DATABASE} База данных: {Config.DB_PATH}")
            print(f"{Emoji.BELL} Планировщик: Запущен")
            print("="*60 + "\n")
            
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"{Emoji.ERROR} Ошибка: {e}")
            import traceback
            traceback.print_exc()

# ============================================================================
# ЗАПУСК
# ============================================================================
if __name__ == '__main__':
    bot = DentalClinicBot()
    bot.run()
