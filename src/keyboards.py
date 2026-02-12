from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta

class Keyboards:
    
    @staticmethod
    def main_menu():
        """Главное меню"""
        keyboard = [
            [InlineKeyboardButton("📝 Записаться на прием", callback_data='appointment')],
            [InlineKeyboardButton("❓ Часто задаваемые вопросы", callback_data='faq')],
            [InlineKeyboardButton("📋 Мои записи", callback_data='my_appointments')],
            [InlineKeyboardButton("🏥 О клинике", callback_data='about')],
            [InlineKeyboardButton("📞 Контакты", callback_data='contacts')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def doctors_keyboard():
        """Выбор врача"""
        keyboard = []
        from config import Config
        for key, doctor in Config.DOCTORS.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{doctor['name']} - {doctor['specialty']}", 
                    callback_data=f"doctor_{key}"
                )
            ])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def date_keyboard():
        """Выбор даты (следующие 7 дней)"""
        keyboard = []
        today = datetime.now()
        
        for i in range(7):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            day_name = date.strftime('%A')
            
            # Русские названия дней
            days_ru = {
                'Monday': 'Пн', 'Tuesday': 'Вт', 'Wednesday': 'Ср',
                'Thursday': 'Чт', 'Friday': 'Пт', 'Saturday': 'Сб', 'Sunday': 'Вс'
            }
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{date_str} ({days_ru[day_name]})", 
                    callback_data=f"date_{date_str}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_doctors')])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def time_keyboard(date):
        """Выбор времени"""
        keyboard = []
        from config import Config
        for time in Config.WORK_HOURS:
            keyboard.append([
                InlineKeyboardButton(
                    time, 
                    callback_data=f"time_{date}_{time}"
                )
            ])
        
        # Добавляем кнопки в ряды по 2
        rows = [keyboard[i:i+2] for i in range(0, len(keyboard), 2)]
        rows.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_dates')])
        
        return InlineKeyboardMarkup(rows)
    
    @staticmethod
    def confirm_keyboard(date, time, doctor_id):
        """Подтверждение записи"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{date}_{time}_{doctor_id}"),
                InlineKeyboardButton("❌ Отменить", callback_data='cancel_appointment')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def faq_keyboard():
        """Клавиатура FAQ"""
        keyboard = []
        from config import Config
        for question in Config.FAQ.keys():
            keyboard.append([InlineKeyboardButton(question, callback_data=f'faq_{question}')])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')])
        return InlineKeyboardMarkup(keyboard)
