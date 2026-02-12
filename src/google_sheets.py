import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import os

class GoogleSheetsManager:
    
    def __init__(self):
        self.scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Загружаем credentials из файла
        if os.path.exists('credentials.json'):
            self.creds = Credentials.from_service_account_file(
                'credentials.json', scopes=self.scope
            )
            self.client = gspread.authorize(self.creds)
            self.setup_sheets()
    
    def setup_sheets(self):
        """Создание листов, если их нет"""
        try:
            # Пробуем открыть существующую таблицу
            self.spreadsheet = self.client.open_by_key(os.getenv('GOOGLE_SHEETS_ID'))
        except:
            # Если таблицы нет, создаем новую
            self.spreadsheet = self.client.create('Стоматология - Записи')
            
        # Создаем листы, если их нет
        try:
            self.appointments_sheet = self.spreadsheet.worksheet('Записи')
        except:
            self.appointments_sheet = self.spreadsheet.add_worksheet('Записи', 1000, 20)
            # Заголовки
            headers = ['Дата', 'Время', 'Врач', 'Пациент', 'Телефон', 'Telegram ID', 
                      'Статус', 'Создано', 'Напоминание']
            self.appointments_sheet.append_row(headers)
        
        try:
            self.patients_sheet = self.spreadsheet.worksheet('Пациенты')
        except:
            self.patients_sheet = self.spreadsheet.add_worksheet('Пациенты', 1000, 10)
            headers = ['Telegram ID', 'Имя', 'Телефон', 'Дата регистрации', 'Всего записей']
            self.patients_sheet.append_row(headers)
    
    def add_appointment(self, date, time, doctor, patient_name, phone, telegram_id):
        """Добавление записи"""
        try:
            row = [
                date,
                time,
                doctor,
                patient_name,
                phone,
                str(telegram_id),
                'Подтверждена',
                datetime.now().strftime('%d.%m.%Y %H:%M'),
                'Не отправлено'
            ]
            self.appointments_sheet.append_row(row)
            return True
        except Exception as e:
            print(f"Error adding appointment: {e}")
            return False
    
    def get_available_slots(self, date):
        """Получение свободных слотов на дату"""
        try:
            all_records = self.appointments_sheet.get_all_records()
            busy_times = []
            
            for record in all_records:
                if record['Дата'] == date and record['Статус'] == 'Подтверждена':
                    busy_times.append(record['Время'])
            
            from config import Config
            available = [time for time in Config.WORK_HOURS if time not in busy_times]
            return available
            
        except Exception as e:
            print(f"Error getting slots: {e}")
            return Config.WORK_HOURS
    
    def get_user_appointments(self, telegram_id):
        """Получение записей пользователя"""
        try:
            all_records = self.appointments_sheet.get_all_records()
            user_appointments = []
            
            for record in all_records:
                if str(record['Telegram ID']) == str(telegram_id):
                    user_appointments.append(record)
            
            return user_appointments
        except Exception as e:
            print(f"Error getting user appointments: {e}")
            return []
    
    def cancel_appointment(self, date, time, telegram_id):
        """Отмена записи"""
        try:
            cell = self.appointments_sheet.find(str(telegram_id))
            if cell:
                row = cell.row
                if (self.appointments_sheet.cell(row, 1).value == date and 
                    self.appointments_sheet.cell(row, 2).value == time):
                    self.appointments_sheet.update_cell(row, 7, 'Отменена')
                    return True
            return False
        except Exception as e:
            print(f"Error canceling appointment: {e}")
            return False
    
    def get_today_appointments(self):
        """Получение записей на сегодня для напоминаний"""
        try:
            today = datetime.now().strftime('%d.%m.%Y')
            all_records = self.appointments_sheet.get_all_records()
            today_appointments = []
            
            for record in all_records:
                if record['Дата'] == today and record['Статус'] == 'Подтверждена':
                    today_appointments.append(record)
            
            return today_appointments
        except Exception as e:
            print(f"Error getting today appointments: {e}")
            return []
    
    def mark_reminder_sent(self, date, time, telegram_id):
        """Отметить, что напоминание отправлено"""
        try:
            cell = self.appointments_sheet.find(str(telegram_id))
            if cell:
                row = cell.row
                if (self.appointments_sheet.cell(row, 1).value == date and 
                    self.appointments_sheet.cell(row, 2).value == time):
                    self.appointments_sheet.update_cell(row, 9, 'Отправлено')
                    return True
            return False
        except Exception as e:
            print(f"Error marking reminder: {e}")
            return False
