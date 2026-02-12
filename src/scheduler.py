from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

class ReminderScheduler:
    
    def __init__(self, bot, google_sheets):
        self.bot = bot
        self.google_sheets = google_sheets
        self.scheduler = BackgroundScheduler()
        self.setup_jobs()
    
    def setup_jobs(self):
        """Настройка задач"""
        # Проверяем записи каждый день в 9:00 и 18:00
        self.scheduler.add_job(
            self.send_reminders,
            CronTrigger(hour=9, minute=0),
            id='morning_reminders'
        )
        
        self.scheduler.add_job(
            self.send_reminders,
            CronTrigger(hour=18, minute=0),
            id='evening_reminders'
        )
        
        self.scheduler.start()
    
    async def send_reminders(self):
        """Отправка напоминаний"""
        try:
            appointments = self.google_sheets.get_today_appointments()
            
            for appointment in appointments:
                if appointment['Напоминание'] == 'Не отправлено':
                    telegram_id = int(appointment['Telegram ID'])
                    time = appointment['Время']
                    doctor = appointment['Врач']
                    
                    message = (
                        f"🦷 Напоминание о приеме!\n\n"
                        f"Вы записаны к стоматологу сегодня.\n"
                        f"🕐 Время: {time}\n"
                        f"👨‍⚕️ Врач: {doctor}\n\n"
                        f"Пожалуйста, не опаздывайте. "
                        f"Если нужно отменить запись, свяжитесь с нами."
                    )
                    
                    try:
                        await self.bot.send_message(
                            chat_id=telegram_id,
                            text=message
                        )
                        
                        self.google_sheets.mark_reminder_sent(
                            appointment['Дата'],
                            appointment['Время'],
                            appointment['Telegram ID']
                        )
                        
                    except Exception as e:
                        logging.error(f"Failed to send reminder to {telegram_id}: {e}")
                        
        except Exception as e:
            logging.error(f"Error in send_reminders: {e}")
