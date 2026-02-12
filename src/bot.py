"""
ПОЛНЫЙ ФАЙЛ БОТА ДЛЯ СТОМАТОЛОГИЧЕСКОЙ КЛИНИКИ
Версия: 1.0.0
Все права защищены © 2024
"""

import logging
import re
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

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
# КОНФИГУРАЦИЯ
# ============================================================================

class Config:
    """Конфигурация бота"""
    
    # Токен бота из переменных окружения
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Google Sheets
    GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
    SPREADSHEET_URL = os.getenv('SPREADSHEET_URL')
    
    # ID администраторов (через запятую в .env)
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
    
    # Врачи клиники
    DOCTORS = {
        '1': {
            'id': '1',
            'name': 'Иванова Мария Петровна',
            'specialty': 'Стоматолог-терапевт',
            'description': 'Стаж 15 лет, лечение кариеса, пульпита, профессиональная гигиена'
        },
        '2': {
            'id': '2',
            'name': 'Петров Сергей Иванович',
            'specialty': 'Стоматолог-хирург',
            'description': 'Стаж 12 лет, удаление зубов, имплантация, костная пластика'
        },
        '3': {
            'id': '3',
            'name': 'Сидорова Анна Викторовна',
            'specialty': 'Стоматолог-ортодонт',
            'description': 'Стаж 10 лет, исправление прикуса, брекеты, элайнеры'
        },
        '4': {
            'id': '4',
            'name': 'Козлов Алексей Николаевич',
            'specialty': 'Стоматолог-ортопед',
            'description': 'Стаж 20 лет, протезирование, коронки, виниры'
        },
        '5': {
            'id': '5',
            'name': 'Соколова Елена Дмитриевна',
            'specialty': 'Детский стоматолог',
            'description': 'Стаж 8 лет, лечение детей с 3 лет, адаптация'
        }
    }
    
    # Часы работы (доступное время для записи)
    WORK_HOURS = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '14:00', '14:30', '15:00', '15:30',
        '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]
    
    # Часто задаваемые вопросы
    FAQ = {
        'Режим работы': '🕐 Мы работаем ежедневно с 9:00 до 20:00, без выходных.\n'
                       'Прием по предварительной записи.',
        
        'Стоимость услуг': '💰 Стоимость услуг:\n'
                          '• Первичная консультация - 500 руб.\n'
                          '• Лечение кариеса - от 3000 руб.\n'
                          '• Удаление зуба - от 2000 руб.\n'
                          '• Профессиональная чистка - 2500 руб.\n'
                          '• Имплантация - от 25000 руб.\n'
                          'Точная стоимость после осмотра врача.',
        
        'Как добраться': '📍 Наш адрес: г. Москва, ул. Ленина, д. 10\n\n'
                        '🚇 Метро: ст. "Парк Культуры", выход №3, 5 минут пешком.\n'
                        '🚌 Автобусы: 12, 45, остановка "Клиника".\n'
                        '🚗 Парковка: бесплатная парковка для пациентов.',
        
        'Больно ли лечить': '😊 Мы используем современные анестетики.\n'
                           'Лечение проходит абсолютно безболезненно.\n'
                           'При необходимости можем использовать седацию.',
        
        'Детский прием': '👶 Принимаем детей с 3 лет.\n'
                        'Первый осмотр - бесплатно.\n'
                        'Есть игровая зона, работаем с адаптацией.',
        
        'Акции': '🎁 Действующие акции:\n'
                '• Скидка 10% на первое посещение\n'
                '• Профессиональная чистка + консультация - 2500 руб.\n'
                '• Семейная скидка 15% при записи двух и более членов семьи',
        
        'Оплата': '💳 Способы оплаты:\n'
                 '• Наличные\n'
                 '• Банковские карты (Visa, Mastercard, МИР)\n'
                 '• Перевод на карту\n'
                 '• ДМС (уточняйте по телефону)',
        
        'Запись по телефону': '📞 Запись по телефону: +7 (999) 123-45-67\n'
                             'Ежедневно с 9:00 до 20:00'
    }
    
    # Время напоминаний (за сколько часов до приема)
    REMINDER_HOURS = 2


# ============================================================================
# GOOGLE SHEETS ИНТЕГРАЦИЯ
# ============================================================================

class GoogleSheetsManager:
    """Класс для работы с Google Sheets"""
    
    def __init__(self):
        self.scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        
        # Инициализируем клиент при наличии credentials
        self.client = None
        self.spreadsheet = None
        self.appointments_sheet = None
        self.patients_sheet = None
        
        self.authenticate()
    
    def authenticate(self):
        """Аутентификация в Google Sheets API"""
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
                print("✅ Google Sheets аутентификация успешна")
            else:
                print("⚠️ Файл credentials.json не найден")
        except Exception as e:
            print(f"❌ Ошибка аутентификации Google Sheets: {e}")
    
    def setup_sheets(self):
        """Создание листов, если их нет"""
        try:
            if Config.GOOGLE_SHEETS_ID:
                self.spreadsheet = self.client.open_by_key(Config.GOOGLE_SHEETS_ID)
            else:
                self.spreadsheet = self.client.create('Стоматология - Записи')
                
            # Создаем или открываем лист записей
            try:
                self.appointments_sheet = self.spreadsheet.worksheet('Записи')
            except:
                self.appointments_sheet = self.spreadsheet.add_worksheet('Записи', 1000, 20)
                headers = [
                    'Дата', 'Время', 'Врач', 'Пациент', 'Телефон', 
                    'Telegram ID', 'Telegram Username', 'Статус', 
                    'Создано', 'Напоминание'
                ]
                self.appointments_sheet.append_row(headers)
            
            # Создаем или открываем лист пациентов
            try:
                self.patients_sheet = self.spreadsheet.worksheet('Пациенты')
            except:
                self.patients_sheet = self.spreadsheet.add_worksheet('Пациенты', 1000, 10)
                headers = ['Telegram ID', 'Имя', 'Телефон', 'Username', 'Дата регистрации', 'Всего записей']
                self.patients_sheet.append_row(headers)
                
        except Exception as e:
            print(f"❌ Ошибка настройки таблиц: {e}")
    
    def add_appointment(self, date: str, time: str, doctor: str, patient_name: str, 
                       phone: str, telegram_id: int, username: str = '') -> bool:
        """Добавление новой записи"""
        try:
            if not self.appointments_sheet:
                print("⚠️ Google Sheets не инициализирован")
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
                'Не отправлено'
            ]
            self.appointments_sheet.append_row(row)
            
            # Обновляем информацию о пациенте
            self.update_patient_info(telegram_id, patient_name, phone, username)
            
            print(f"✅ Запись добавлена: {date} {time} - {patient_name}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка добавления записи: {e}")
            return False
    
    def update_patient_info(self, telegram_id: int, name: str, phone: str, username: str = ''):
        """Обновление информации о пациенте"""
        try:
            if not self.patients_sheet:
                return False
                
            # Проверяем, есть ли уже пациент
            all_patients = self.patients_sheet.get_all_records()
            patient_exists = False
            row_index = 2  # начинаем со 2 строки (1 - заголовки)
            
            for i, patient in enumerate(all_patients, start=2):
                if str(patient.get('Telegram ID', '')) == str(telegram_id):
                    patient_exists = True
                    row_index = i
                    break
            
            now = datetime.now().strftime('%d.%m.%Y %H:%M')
            
            if patient_exists:
                # Обновляем существующего пациента
                current_appointments = int(self.patients_sheet.cell(row_index, 6).value or '0')
                self.patients_sheet.update_cell(row_index, 2, name)
                self.patients_sheet.update_cell(row_index, 3, phone)
                self.patients_sheet.update_cell(row_index, 4, username or '-')
                self.patients_sheet.update_cell(row_index, 6, str(current_appointments + 1))
            else:
                # Добавляем нового пациента
                row = [
                    str(telegram_id),
                    name,
                    phone,
                    username or '-',
                    now,
                    '1'
                ]
                self.patients_sheet.append_row(row)
                
            return True
            
        except Exception as e:
            print(f"❌ Ошибка обновления пациента: {e}")
            return False
    
    def get_available_slots(self, date: str) -> List[str]:
        """Получение свободных временных слотов на дату"""
        try:
            if not self.appointments_sheet:
                return Config.WORK_HOURS
                
            all_records = self.appointments_sheet.get_all_records()
            busy_times = []
            
            for record in all_records:
                if (record.get('Дата') == date and 
                    record.get('Статус') == 'Подтверждена'):
                    busy_times.append(record.get('Время'))
            
            available = [time for time in Config.WORK_HOURS if time not in busy_times]
            return available
            
        except Exception as e:
            print(f"❌ Ошибка получения слотов: {e}")
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
            
            return user_appointments
            
        except Exception as e:
            print(f"❌ Ошибка получения записей пользователя: {e}")
            return []
    
    def get_today_appointments(self) -> List[Dict]:
        """Получение записей на сегодня для напоминаний"""
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
            print(f"❌ Ошибка получения записей на сегодня: {e}")
            return []
    
    def get_upcoming_appointments(self) -> List[Dict]:
        """Получение предстоящих записей"""
        try:
            if not self.appointments_sheet:
                return []
                
            today = datetime.now()
            all_records = self.appointments_sheet.get_all_records()
            upcoming = []
            
            for record in all_records:
                if record.get('Статус') != 'Подтверждена':
                    continue
                    
                try:
                    date_str = record.get('Дата')
                    time_str = record.get('Время')
                    appointment_datetime = datetime.strptime(
                        f"{date_str} {time_str}", 
                        '%d.%m.%Y %H:%M'
                    )
                    
                    if appointment_datetime > today:
                        upcoming.append(record)
                except:
                    continue
            
            return sorted(upcoming, key=lambda x: x.get('Дата', ''))
            
        except Exception as e:
            print(f"❌ Ошибка получения предстоящих записей: {e}")
            return []
    
    def cancel_appointment(self, date: str, time: str, telegram_id: int) -> bool:
        """Отмена записи"""
        try:
            if not self.appointments_sheet:
                return False
                
            cell = self.appointments_sheet.find(str(telegram_id))
            if cell:
                row = cell.row
                if (self.appointments_sheet.cell(row, 1).value == date and 
                    self.appointments_sheet.cell(row, 2).value == time):
                    self.appointments_sheet.update_cell(row, 8, 'Отменена пациентом')
                    return True
            return False
            
        except Exception as e:
            print(f"❌ Ошибка отмены записи: {e}")
            return False
    
    def mark_reminder_sent(self, date: str, time: str, telegram_id: int) -> bool:
        """Отметить, что напоминание отправлено"""
        try:
            if not self.appointments_sheet:
                return False
                
            cell = self.appointments_sheet.find(str(telegram_id))
            if cell:
                row = cell.row
                if (self.appointments_sheet.cell(row, 1).value == date and 
                    self.appointments_sheet.cell(row, 2).value == time):
                    self.appointments_sheet.update_cell(row, 10, f'Отправлено {datetime.now().strftime("%d.%m.%Y %H:%M")}')
                    return True
            return False
            
        except Exception as e:
            print(f"❌ Ошибка отметки напоминания: {e}")
            return False


# ============================================================================
# КЛАВИАТУРЫ
# ============================================================================

class Keyboards:
    """Класс для создания клавиатур"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Главное меню"""
        keyboard = [
            [InlineKeyboardButton("📝 Записаться на прием", callback_data='appointment')],
            [InlineKeyboardButton("👨‍⚕️ Наши врачи", callback_data='doctors')],
            [InlineKeyboardButton("❓ Часто задаваемые вопросы", callback_data='faq')],
            [InlineKeyboardButton("📋 Мои записи", callback_data='my_appointments')],
            [InlineKeyboardButton("🏥 О клинике", callback_data='about')],
            [InlineKeyboardButton("📞 Контакты", callback_data='contacts')],
            [InlineKeyboardButton("💰 Цены", callback_data='prices')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def doctors_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура выбора врача"""
        keyboard = []
        for key, doctor in Config.DOCTORS.items():
            button_text = f"{doctor['name']} - {doctor['specialty']}"
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"doctor_{key}")
            ])
        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def date_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура выбора даты (следующие 14 дней)"""
        keyboard = []
        today = datetime.now()
        
        days_ru = {
            'Monday': 'Понедельник',
            'Tuesday': 'Вторник',
            'Wednesday': 'Среда',
            'Thursday': 'Четверг',
            'Friday': 'Пятница',
            'Saturday': 'Суббота',
            'Sunday': 'Воскресенье'
        }
        
        months_ru = {
            '01': 'января', '02': 'февраля', '03': 'марта',
            '04': 'апреля', '05': 'мая', '06': 'июня',
            '07': 'июля', '08': 'августа', '09': 'сентября',
            '10': 'октября', '11': 'ноября', '12': 'декабря'
        }
        
        for i in range(14):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            day_name = days_ru[date.strftime('%A')]
            day_num = date.strftime('%d')
            month = months_ru[date.strftime('%m')]
            
            if i == 0:
                button_text = f"📅 Сегодня ({day_num} {month})"
            elif i == 1:
                button_text = f"📅 Завтра ({day_num} {month})"
            else:
                button_text = f"📅 {day_num} {month}, {day_name}"
                
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"date_{date_str}")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад к врачам", callback_data='back_to_doctors')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def time_keyboard(date: str, available_times: List[str] = None) -> InlineKeyboardMarkup:
        """Клавиатура выбора времени"""
        keyboard = []
        
        if available_times is None:
            available_times = Config.WORK_HOURS
        
        # Разбиваем время на утро, день, вечер
        morning = [t for t in available_times if '09' <= t[:2] <= '11']
        afternoon = [t for t in available_times if '12' <= t[:2] <= '16']
        evening = [t for t in available_times if '17' <= t[:2] <= '18']
        
        if morning:
            keyboard.append([InlineKeyboardButton("🌅 Утро", callback_data="ignore")])
            for time in morning:
                keyboard.append([InlineKeyboardButton(f"🕐 {time}", callback_data=f"time_{date}_{time}")])
        
        if afternoon:
            keyboard.append([InlineKeyboardButton("☀️ День", callback_data="ignore")])
            for i in range(0, len(afternoon), 2):
                row = []
                row.append(InlineKeyboardButton(f"🕐 {afternoon[i]}", callback_data=f"time_{date}_{afternoon[i]}"))
                if i + 1 < len(afternoon):
                    row.append(InlineKeyboardButton(f"🕐 {afternoon[i+1]}", callback_data=f"time_{date}_{afternoon[i+1]}"))
                keyboard.append(row)
        
        if evening:
            keyboard.append([InlineKeyboardButton("🌙 Вечер", callback_data="ignore")])
            for time in evening:
                keyboard.append([InlineKeyboardButton(f"🕐 {time}", callback_data=f"time_{date}_{time}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад к датам", callback_data='back_to_dates')])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_keyboard(date: str, time: str, doctor_id: str) -> InlineKeyboardMarkup:
        """Клавиатура подтверждения записи"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить запись", callback_data=f"confirm_{date}_{time}_{doctor_id}"),
                InlineKeyboardButton("❌ Отменить", callback_data='cancel_appointment')
            ],
            [InlineKeyboardButton("◀️ Назад ко времени", callback_data='back_to_times')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def faq_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура FAQ"""
        keyboard = []
        for question in Config.FAQ.keys():
            keyboard.append([InlineKeyboardButton(question, callback_data=f'faq_{question}')])
        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура администратора"""
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
            [InlineKeyboardButton("📅 Записи на сегодня", callback_data='admin_today')],
            [InlineKeyboardButton("📋 Все записи", callback_data='admin_all')],
            [InlineKeyboardButton("👥 Пациенты", callback_data='admin_patients')],
            [InlineKeyboardButton("🔔 Отправить рассылку", callback_data='admin_broadcast')],
            [InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def appointments_actions_keyboard(date: str, time: str) -> InlineKeyboardMarkup:
        """Клавиатура действий с записью"""
        keyboard = [
            [InlineKeyboardButton("❌ Отменить запись", callback_data=f"cancel_appointment_{date}_{time}")],
            [InlineKeyboardButton("◀️ Назад", callback_data='my_appointments')]
        ]
        return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ПЛАНИРОВЩИК НАПОМИНАНИЙ
# ============================================================================

class ReminderScheduler:
    """Класс для планирования и отправки напоминаний"""
    
    def __init__(self, bot, google_sheets):
        self.bot = bot
        self.google_sheets = google_sheets
        self.scheduler = None
        self.setup_scheduler()
    
    def setup_scheduler(self):
        """Настройка планировщика"""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            
            self.scheduler = BackgroundScheduler()
            
            # Проверяем записи каждый час с 8:00 до 20:00
            for hour in range(8, 21):
                self.scheduler.add_job(
                    self.send_reminders,
                    CronTrigger(hour=hour, minute=0),
                    id=f'reminder_{hour}'
                )
            
            self.scheduler.start()
            print("✅ Планировщик напоминаний запущен")
            
        except Exception as e:
            print(f"❌ Ошибка настройки планировщика: {e}")
    
    async def send_reminders(self):
        """Отправка напоминаний о предстоящих приемах"""
        try:
            appointments = self.google_sheets.get_today_appointments()
            now = datetime.now()
            
            for appointment in appointments:
                try:
                    # Проверяем, отправляли ли уже напоминание
                    if 'Отправлено' in str(appointment.get('Напоминание', '')):
                        continue
                    
                    time_str = appointment.get('Время')
                    appointment_time = datetime.strptime(time_str, '%H:%M')
                    appointment_time = now.replace(
                        hour=appointment_time.hour,
                        minute=appointment_time.minute,
                        second=0
                    )
                    
                    # Отправляем за 2 часа до приема
                    time_diff = (appointment_time - now).total_seconds() / 3600
                    
                    if 1.5 <= time_diff <= 2.5:  # За 1.5-2.5 часа до приема
                        telegram_id = int(appointment.get('Telegram ID', 0))
                        doctor = appointment.get('Врач', '')
                        time = appointment.get('Время', '')
                        
                        message = (
                            f"🦷 **Напоминание о приеме!**\n\n"
                            f"Здравствуйте, {appointment.get('Пациент', '')}!\n\n"
                            f"Напоминаем, что вы записаны к стоматологу **сегодня**.\n"
                            f"🕐 **Время:** {time}\n"
                            f"👨‍⚕️ **Врач:** {doctor}\n\n"
                            f"📍 **Адрес:** г. Москва, ул. Ленина, д. 10\n"
                            f"📞 **Телефон для связи:** +7 (999) 123-45-67\n\n"
                            f"Пожалуйста, не опаздывайте. "
                            f"Если вам нужно отменить или перенести запись, "
                            f"свяжитесь с нами по телефону или через бота."
                        )
                        
                        try:
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
                            
                            print(f"✅ Напоминание отправлено пользователю {telegram_id}")
                            
                        except Exception as e:
                            print(f"❌ Ошибка отправки напоминания: {e}")
                            
                except Exception as e:
                    print(f"❌ Ошибка обработки записи: {e}")
                    continue
                    
        except Exception as e:
            print(f"❌ Ошибка в send_reminders: {e}")


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
    ADMIN_BROADCAST
) = range(7)


# ============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# ============================================================================

class DentalClinicBot:
    """Основной класс бота стоматологической клиники"""
    
    def __init__(self):
        self.config = Config()
        self.keyboards = Keyboards()
        self.google_sheets = GoogleSheetsManager()
        self.reminder_scheduler = None
        self.application = None
        
        # Настройка логирования
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)
    
    # ========================================================================
    # ОБРАБОТЧИКИ КОМАНД
    # ========================================================================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        # Приветственное сообщение
        welcome_text = (
            f"👋 **Здравствуйте, {user.first_name}!**\n\n"
            f"Добро пожаловать в официальный бот стоматологической клиники.\n\n"
            f"🦷 **С помощью бота вы можете:**\n"
            f"✅ Записаться на прием к любому врачу\n"
            f"✅ Выбрать удобную дату и время\n"
            f"✅ Узнать ответы на частые вопросы\n"
            f"✅ Просмотреть историю записей\n"
            f"✅ Получить контактную информацию\n"
            f"✅ Отменить или перенести запись\n\n"
            f"📅 **Режим работы:** ежедневно с 9:00 до 20:00\n"
            f"📍 **Адрес:** г. Москва, ул. Ленина, д. 10\n\n"
            f"**Выберите действие в меню ниже:**"
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=self.keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "🆘 **Помощь по боту**\n\n"
            "**Доступные команды:**\n"
            "/start - Главное меню\n"
            "/help - Помощь\n"
            "/appointment - Записаться на прием\n"
            "/my - Мои записи\n"
            "/contacts - Контакты\n"
            "/cancel - Отменить действие\n\n"
            "**Если у вас возникли проблемы:**\n"
            "• Проверьте, что вы ввели корректный номер телефона\n"
            "• Убедитесь, что выбрали все параметры записи\n"
            "• Свяжитесь с нами по телефону: +7 (999) 123-45-67"
        )
        
        await update.message.reply_text(
            help_text,
            reply_markup=self.keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена текущего действия"""
        await update.message.reply_text(
            "❌ Действие отменено.\n"
            "Вы можете начать заново через главное меню.",
            reply_markup=self.keyboards.main_menu()
        )
        return ConversationHandler.END
    
    # ========================================================================
    # ОБРАБОТЧИКИ КНОПОК
    # ========================================================================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на инлайн-кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Игнорируем информационные кнопки
        if data == 'ignore':
            return
        
        # ======== НАВИГАЦИЯ ========
        if data == 'back_to_menu':
            await query.edit_message_text(
                "📌 **Главное меню**\n\nВыберите необходимое действие:",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # ======== ЗАПИСЬ НА ПРИЕМ ========
        elif data == 'appointment':
            context.user_data['appointment_data'] = {}
            await query.edit_message_text(
                "👨‍⚕️ **Выберите врача**\n\n"
                "Ознакомьтесь с нашими специалистами и выберите подходящего:",
                reply_markup=self.keyboards.doctors_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DOCTOR
        
        # ======== ВРАЧИ ========
        elif data == 'doctors':
            text = "👨‍⚕️ **Наши специалисты**\n\n"
            for doctor in Config.DOCTORS.values():
                text += f"**{doctor['name']}**\n"
                text += f"└ {doctor['specialty']}\n"
                text += f"└ {doctor['description']}\n\n"
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ======== ВЫБОР ВРАЧА ========
        elif data.startswith('doctor_'):
            doctor_id = data.split('_')[1]
            doctor = self.config.DOCTORS[doctor_id]
            
            context.user_data['appointment_data'] = {
                'doctor': f"{doctor['name']} ({doctor['specialty']})",
                'doctor_id': doctor_id
            }
            
            text = (
                f"✅ Вы выбрали врача:\n"
                f"**{doctor['name']}**\n"
                f"*{doctor['specialty']}*\n\n"
                f"{doctor['description']}\n\n"
                f"📅 Теперь выберите удобную дату для приема:"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.date_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DATE
        
        # ======== ВЫБОР ДАТЫ ========
        elif data.startswith('date_'):
            date = data.split('_')[1]
            
            # Сохраняем дату
            if 'appointment_data' not in context.user_data:
                context.user_data['appointment_data'] = {}
            context.user_data['appointment_data']['date'] = date
            
            # Получаем свободное время
            available_times = self.google_sheets.get_available_slots(date)
            
            if not available_times:
                # Нет свободного времени
                await query.edit_message_text(
                    "❌ **К сожалению, на выбранную дату нет свободного времени.**\n\n"
                    "Пожалуйста, выберите другую дату:",
                    reply_markup=self.keyboards.date_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                return SELECTING_DATE
            
            # Форматируем дату для отображения
            date_obj = datetime.strptime(date, '%d.%m.%Y')
            date_display = date_obj.strftime('%d %B %Y')
            month_ru = {
                'January': 'января', 'February': 'февраля', 'March': 'марта',
                'April': 'апреля', 'May': 'мая', 'June': 'июня',
                'July': 'июля', 'August': 'августа', 'September': 'сентября',
                'October': 'октября', 'November': 'ноября', 'December': 'декабря'
            }
            month = month_ru[date_obj.strftime('%B')]
            date_display = f"{date_obj.day} {month}"
            
            await query.edit_message_text(
                f"📅 **Дата:** {date_display}\n"
                f"🕐 **Доступное время:**\n\n"
                f"Выберите удобное время для приема:",
                reply_markup=self.keyboards.time_keyboard(date, available_times),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_TIME
        
        # ======== ВЫБОР ВРЕМЕНИ ========
        elif data.startswith('time_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            
            context.user_data['appointment_data']['time'] = time
            
            doctor_id = context.user_data['appointment_data'].get('doctor_id')
            doctor_name = context.user_data['appointment_data'].get('doctor', '')
            
            # Форматируем дату для отображения
            date_obj = datetime.strptime(date, '%d.%m.%Y')
            month_ru = {
                'January': 'января', 'February': 'февраля', 'March': 'марта',
                'April': 'апреля', 'May': 'мая', 'June': 'июня',
                'July': 'июля', 'August': 'августа', 'September': 'сентября',
                'October': 'октября', 'November': 'ноября', 'December': 'декабря'
            }
            month = month_ru[date_obj.strftime('%B')]
            date_display = f"{date_obj.day} {month}"
            
            text = (
                "📋 **Проверьте данные записи:**\n\n"
                f"📅 **Дата:** {date_display}\n"
                f"🕐 **Время:** {time}\n"
                f"👨‍⚕️ **Врач:** {doctor_name}\n\n"
                f"Всё верно?"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.confirm_keyboard(date, time, doctor_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONFIRMING
        
        # ======== ПОДТВЕРЖДЕНИЕ ЗАПИСИ ========
        elif data.startswith('confirm_'):
            parts = data.split('_')
            date = parts[1]
            time = parts[2]
            doctor_id = parts[3]
            
            await query.edit_message_text(
                "📝 **Для завершения записи**\n\n"
                "Пожалуйста, введите ваше **ФИО** полностью:\n"
                "(например: Иванов Иван Иванович)",
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_NAME
        
        # ======== ОТМЕНА ЗАПИСИ ========
        elif data == 'cancel_appointment':
            await query.edit_message_text(
                "❌ **Запись отменена.**\n\n"
                "Вы можете записаться заново в любое время.",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        elif data.startswith('cancel_appointment_'):
            parts = data.split('_')
            date = parts[2]
            time = parts[3]
            user_id = update.effective_user.id
            
            success = self.google_sheets.cancel_appointment(date, time, user_id)
            
            if success:
                await query.edit_message_text(
                    "✅ **Запись успешно отменена!**\n\n"
                    f"📅 Дата: {date}\n"
                    f"🕐 Время: {time}\n\n"
                    f"Если вы хотите записаться на другое время, "
                    f"воспользуйтесь главным меню.",
                    reply_markup=self.keyboards.main_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(
                    "❌ **Не удалось отменить запись.**\n\n"
                    "Пожалуйста, попробуйте позже или свяжитесь с нами по телефону.",
                    reply_markup=self.keyboards.main_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
        
        # ======== FAQ ========
        elif data == 'faq':
            await query.edit_message_text(
                "❓ **Часто задаваемые вопросы**\n\n"
                "Выберите интересующий вас вопрос:",
                reply_markup=self.keyboards.faq_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data.startswith('faq_'):
            question = data[4:]
            answer = self.config.FAQ.get(question, "Информация временно недоступна")
            
            text = f"**❓ {question}**\n\n{answer}"
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.faq_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ======== МОИ ЗАПИСИ ========
        elif data == 'my_appointments':
            user_id = update.effective_user.id
            appointments = self.google_sheets.get_user_appointments(user_id)
            
            if not appointments:
                await query.edit_message_text(
                    "📋 **У вас пока нет записей на прием.**\n\n"
                    "Вы можете записаться через главное меню.",
                    reply_markup=self.keyboards.main_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                # Сортируем записи по дате
                future_appointments = []
                past_appointments = []
                today = datetime.now().strftime('%d.%m.%Y')
                
                for app in appointments:
                    if app['Статус'] == 'Подтверждена' and app['Дата'] >= today:
                        future_appointments.append(app)
                    else:
                        past_appointments.append(app)
                
                text = "📋 **Ваши записи:**\n\n"
                
                if future_appointments:
                    text += "🔹 **Предстоящие записи:**\n"
                    for app in future_appointments[:3]:  # Показываем только 3 ближайших
                        text += f"├ 📅 {app['Дата']} в {app['Время']}\n"
                        text += f"├ 👨‍⚕️ {app['Врач']}\n"
                        text += f"└ ✅ {app['Статус']}\n\n"
                
                if past_appointments:
                    text += "🔸 **Прошедшие записи:**\n"
                    for app in past_appointments[:3]:
                        text += f"├ 📅 {app['Дата']} в {app['Время']}\n"
                        text += f"└ 👨‍⚕️ {app['Врач']}\n\n"
                
                if len(appointments) > 6:
                    text += f"*Всего записей: {len(appointments)}*\n"
                
                # Добавляем кнопку для отмены, если есть будущие записи
                keyboard = []
                if future_appointments:
                    for app in future_appointments[:1]:  # Только первую запись для простоты
                        keyboard.append([
                            InlineKeyboardButton(
                                f"❌ Отменить запись на {app['Дата']}",
                                callback_data=f"cancel_appointment_{app['Дата']}_{app['Время']}"
                            )
                        ])
                
                keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')])
                
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else self.keyboards.main_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
        
        # ======== О КЛИНИКЕ ========
        elif data == 'about':
            text = (
                "🏥 **О нашей клинике**\n\n"
                "Мы - современная стоматологическая клиника полного цикла, "
                "работающая с 2010 года.\n\n"
                "**Наши преимущества:**\n"
                "✅ Новейшее оборудование\n"
                "✅ Опытные врачи (средний стаж 12+ лет)\n"
                "✅ Безболезненное лечение\n"
                "✅ Доступные цены\n"
                "✅ Комфортная атмосфера\n"
                "✅ Индивидуальный подход\n\n"
                "📅 **Режим работы:**\n"
                "Пн-Вс: 9:00 - 20:00 (без выходных)\n\n"
                "📍 **Адрес:**\n"
                "г. Москва, ул. Ленина, д. 10\n\n"
                "🚇 **Как добраться:**\n"
                "Метро Парк Культуры, выход №3"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ======== КОНТАКТЫ ========
        elif data == 'contacts':
            text = (
                "📞 **Контакты**\n\n"
                "**Телефон:** +7 (999) 123-45-67\n"
                "**Email:** info@dentclinic.ru\n"
                "**Сайт:** www.dentclinic.ru\n\n"
                "📍 **Адрес:**\n"
                "г. Москва, ул. Ленина, д. 10\n\n"
                "⏰ **Часы работы:**\n"
                "Пн-Вс: 9:00 - 20:00\n\n"
                "🚇 **Метро:**\n"
                "ст. Парк Культуры, выход №3\n\n"
                "📱 **Мы в соцсетях:**\n"
                "Telegram: @dentclinic\n"
                "Instagram: @dentclinic\n"
                "VK: vk.com/dentclinic"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ======== ЦЕНЫ ========
        elif data == 'prices':
            text = (
                "💰 **Прайс-лист**\n\n"
                "**Консультация:**\n"
                "• Первичная консультация - 500 ₽\n"
                "• Повторная консультация - 300 ₽\n\n"
                "**Лечение:**\n"
                "• Лечение кариеса - от 3 000 ₽\n"
                "• Лечение пульпита - от 5 000 ₽\n"
                "• Лечение периодонтита - от 6 000 ₽\n\n"
                "**Хирургия:**\n"
                "• Удаление зуба - от 2 000 ₽\n"
                "• Сложное удаление - от 4 000 ₽\n"
                "• Имплантация - от 25 000 ₽\n\n"
                "**Гигиена:**\n"
                "• Профессиональная чистка - 2 500 ₽\n"
                "• Отбеливание - 15 000 ₽\n\n"
                "**Протезирование:**\n"
                "• Коронка металлокерамика - 7 000 ₽\n"
                "• Коронка керамика - 15 000 ₽\n"
                "• Виниры - 18 000 ₽\n\n"
                "**Детская стоматология:**\n"
                "• Первичный осмотр - бесплатно\n"
                "• Лечение кариеса - от 2 000 ₽\n"
                "• Герметизация фиссур - 1 500 ₽\n\n"
                "⚠️ *Цены являются ориентировочными. "
                "Точная стоимость определяется после осмотра врача.*"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ======== АДМИН-ПАНЕЛЬ ========
        elif data == 'admin_stats':
            # Проверяем, является ли пользователь администратором
            user_id = update.effective_user.id
            if user_id not in self.config.ADMIN_IDS:
                await query.edit_message_text(
                    "⛔ **Доступ запрещен**\n\n"
                    "Эта функция доступна только администраторам.",
                    reply_markup=self.keyboards.main_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Получаем статистику
            today = datetime.now().strftime('%d.%m.%Y')
            today_appointments = self.google_sheets.get_today_appointments()
            upcoming = self.google_sheets.get_upcoming_appointments()
            
            text = (
                "📊 **Статистика клиники**\n\n"
                f"📅 **Записи на сегодня:** {len(today_appointments)}\n"
                f"📋 **Всего предстоящих записей:** {len(upcoming)}\n\n"
                f"👥 **Пациентов в базе:** ?\n"
                f"👨‍⚕️ **Врачей:** {len(Config.DOCTORS)}\n\n"
                f"🕐 **Последнее обновление:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'admin_today':
            user_id = update.effective_user.id
            if user_id not in self.config.ADMIN_IDS:
                await query.edit_message_text("⛔ Доступ запрещен", reply_markup=self.keyboards.main_menu())
                return
            
            today_appointments = self.google_sheets.get_today_appointments()
            
            if not today_appointments:
                text = "📅 **На сегодня записей нет.**"
            else:
                text = f"📅 **Записи на сегодня ({len(today_appointments)}):**\n\n"
                for app in today_appointments:
                    text += f"🕐 {app['Время']}\n"
                    text += f"├ 👤 {app['Пациент']}\n"
                    text += f"├ 📞 {app['Телефон']}\n"
                    text += f"└ 👨‍⚕️ {app['Врач']}\n\n"
            
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        # ======== НАВИГАЦИЯ ========
        elif data == 'back_to_doctors':
            await query.edit_message_text(
                "👨‍⚕️ **Выберите врача:**",
                reply_markup=self.keyboards.doctors_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DOCTOR
        
        elif data == 'back_to_dates':
            await query.edit_message_text(
                "📅 **Выберите дату приема:**",
                reply_markup=self.keyboards.date_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_DATE
        
        elif data == 'back_to_times':
            date = context.user_data.get('appointment_data', {}).get('date')
            if date:
                available_times = self.google_sheets.get_available_slots(date)
                await query.edit_message_text(
                    f"📅 **Дата:** {date}\n"
                    f"🕐 **Доступное время:**",
                    reply_markup=self.keyboards.time_keyboard(date, available_times),
                    parse_mode=ParseMode.MARKDOWN
                )
            return SELECTING_TIME
        
        return ConversationHandler.END
    
    # ========================================================================
    # ОБРАБОТЧИКИ ТЕКСТА
    # ========================================================================
    
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение ФИО пациента"""
        name = update.message.text.strip()
        
        # Валидация ФИО
        if len(name) < 5:
            await update.message.reply_text(
                "❌ **Пожалуйста, введите корректное ФИО**\n\n"
                "Минимум 5 символов. Например: Иванов Иван Иванович",
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_NAME
        
        # Проверка на наличие цифр
        if any(char.isdigit() for char in name):
            await update.message.reply_text(
                "❌ **ФИО не должно содержать цифры**\n\n"
                "Пожалуйста, введите корректное ФИО:",
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_NAME
        
        context.user_data['appointment_data']['name'] = name
        
        await update.message.reply_text(
            f"✅ Спасибо, **{name}**!\n\n"
            f"📞 Теперь укажите ваш **номер телефона** для связи:\n"
            f"(например: +79991234567 или 89991234567)",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return GETTING_PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение номера телефона"""
        phone = update.message.text.strip()
        
        # Валидация телефона
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Проверяем формат
        phone_pattern = re.compile(r'^(\+7|8|7)?\d{10}$')
        
        if not phone_pattern.match(phone_clean):
            await update.message.reply_text(
                "❌ **Неверный формат телефона**\n\n"
                "Пожалуйста, введите номер в одном из форматов:\n"
                "• +79991234567\n"
                "• 89991234567\n"
                "• 79991234567\n\n"
                "Или просто 10 цифр: 9991234567",
                parse_mode=ParseMode.MARKDOWN
            )
            return GETTING_PHONE
        
        # Приводим к единому формату
        if len(phone_clean) == 10:
            phone_clean = f"+7{phone_clean}"
        elif phone_clean.startswith('8'):
            phone_clean = f"+7{phone_clean[1:]}"
        elif phone_clean.startswith('7'):
            phone_clean = f"+7{phone_clean[1:]}"
        
        appointment_data = context.user_data['appointment_data']
        appointment_data['phone'] = phone_clean
        appointment_data['user_id'] = update.effective_user.id
        
        # Получаем username
        username = update.effective_user.username or ''
        
        # Сохраняем запись в Google Sheets
        success = self.google_sheets.add_appointment(
            date=appointment_data['date'],
            time=appointment_data['time'],
            doctor=appointment_data['doctor'],
            patient_name=appointment_data['name'],
            phone=phone_clean,
            telegram_id=update.effective_user.id,
            username=username
        )
        
        if success:
            # Форматируем дату для отображения
            date_obj = datetime.strptime(appointment_data['date'], '%d.%m.%Y')
            month_ru = {
                'January': 'января', 'February': 'февраля', 'March': 'марта',
                'April': 'апреля', 'May': 'мая', 'June': 'июня',
                'July': 'июля', 'August': 'августа', 'September': 'сентября',
                'October': 'октября', 'November': 'ноября', 'December': 'декабря'
            }
            month = month_ru[date_obj.strftime('%B')]
            date_display = f"{date_obj.day} {month}"
            
            text = (
                "✅ **Запись успешно создана!**\n\n"
                f"📅 **Дата:** {date_display}\n"
                f"🕐 **Время:** {appointment_data['time']}\n"
                f"👨‍⚕️ **Врач:** {appointment_data['doctor']}\n"
                f"👤 **Пациент:** {appointment_data['name']}\n"
                f"📞 **Телефон:** {phone_clean}\n\n"
                "🔔 **Что дальше?**\n"
                "• Мы отправим вам напоминание за 2 часа до приема\n"
                "• При необходимости вы можете отменить запись в разделе 'Мои записи'\n"
                "• Если у вас изменились планы, пожалуйста, предупредите нас заранее\n\n"
                "🙏 Спасибо за выбор нашей клиники! Ждем вас на приеме."
            )
            
            await update.message.reply_text(
                text,
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Отправляем уведомление администраторам
            for admin_id in self.config.ADMIN_IDS:
                try:
                    admin_text = (
                        f"🔔 **НОВАЯ ЗАПИСЬ!**\n\n"
                        f"📅 Дата: {appointment_data['date']}\n"
                        f"🕐 Время: {appointment_data['time']}\n"
                        f"👨‍⚕️ Врач: {appointment_data['doctor']}\n"
                        f"👤 Пациент: {appointment_data['name']}\n"
                        f"📞 Телефон: {phone_clean}\n"
                        f"🆔 Telegram ID: {update.effective_user.id}\n"
                        f"👤 Username: @{username if username else 'не указан'}"
                    )
                    
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    self.logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
            
        else:
            await update.message.reply_text(
                "❌ **Произошла ошибка при создании записи**\n\n"
                "Пожалуйста, попробуйте позже или свяжитесь с нами по телефону:\n"
                "📞 +7 (999) 123-45-67",
                reply_markup=self.keyboards.main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        
        return ConversationHandler.END
    
    # ========================================================================
    # ЗАПУСК БОТА
    # ========================================================================
    
    def run(self):
        """Запуск бота"""
        try:
            # Создаем приложение
            self.application = Application.builder().token(self.config.BOT_TOKEN).build()
            
            # ======== ОБРАБОТЧИКИ КОМАНД ========
            self.application.add_handler(CommandHandler('start', self.start))
            self.application.add_handler(CommandHandler('help', self.help_command))
            self.application.add_handler(CommandHandler('cancel', self.cancel))
            
            # ======== CONVERSATION HANDLER ДЛЯ ЗАПИСИ ========
            conv_handler = ConversationHandler(
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
                },
                fallbacks=[
                    CommandHandler('cancel', self.cancel),
                    CallbackQueryHandler(self.button_handler, pattern='^back_to_menu$')
                ],
                name="appointment_conversation",
                persistent=False
            )
            
            self.application.add_handler(conv_handler)
            
            # ======== ОБРАБОТЧИК ВСЕХ КНОПОК ========
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            # ======== ЗАПУСК ПЛАНИРОВЩИКА ========
            if self.google_sheets.client:
                self.reminder_scheduler = ReminderScheduler(self.application.bot, self.google_sheets)
            
            # ======== ИНФОРМАЦИЯ О ЗАПУСКЕ ========
            print("\n" + "="*50)
            print("🚀 СТОМАТОЛОГИЧЕСКИЙ БОТ ЗАПУЩЕН")
            print("="*50)
            print(f"🤖 Токен: {self.config.BOT_TOKEN[:10]}...{self.config.BOT_TOKEN[-10:]}")
            print(f"👨‍⚕️ Врачей в базе: {len(self.config.DOCTORS)}")
            print(f"👑 Администраторов: {len(self.config.ADMIN_IDS)}")
            print(f"📊 Google Sheets: {'✅ Подключен' if self.google_sheets.client else '❌ Не подключен'}")
            print(f"⏰ Планировщик: {'✅ Запущен' if self.reminder_scheduler else '❌ Не запущен'}")
            print("="*50 + "\n")
            
            # Запускаем бота
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            raise


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

if __name__ == '__main__':
    try:
        bot = DentalClinicBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка запуска бота: {e}")
        sys.exit(1)
