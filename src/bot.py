import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from config import Config
from keyboards import Keyboards
from google_sheets import GoogleSheetsManager
from scheduler import ReminderScheduler
import re

# Состояния для разговора
(
    SELECTING_DOCTOR,
    SELECTING_DATE,
    SELECTING_TIME,
    CONFIRMING,
    GETTING_NAME,
    GETTING_PHONE
) = range(6)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DentalClinicBot:
    
    def __init__(self):
        self.config = Config()
        self.keyboards = Keyboards()
        self.google_sheets = GoogleSheetsManager()
        self.user_data = {}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        message = (
            f"👋 Здравствуйте, {user.first_name}!\n\n"
            f"Добро пожаловать в бот стоматологической клиники.\n"
            f"Здесь вы можете:\n"
            f"✅ Записаться на прием\n"
            f"✅ Узнать ответы на частые вопросы\n"
            f"✅ Просмотреть свои записи\n"
            f"✅ Получить информацию о клинике\n\n"
            f"Выберите действие:"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=self.keyboards.main_menu()
        )
        
        return ConversationHandler.END
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Главное меню
        if data == 'back_to_menu':
            await query.edit_message_text(
                "Выберите действие:",
                reply_markup=self.keyboards.main_menu()
            )
        
        # Запись на прием
        elif data == 'appointment':
            context.user_data['appointment_data'] = {}
            await query.edit_message_text(
                "Выберите врача:",
                reply_markup=self.keyboards.doctors_keyboard()
            )
            return SELECTING_DOCTOR
        
        # Выбор врача
        elif data.startswith('doctor_'):
            doctor_id = data.split('_')[1]
            doctor = self.config.DOCTORS[doctor_id]
            context.user_data['appointment_data']['doctor'] = f"{doctor['name']} ({doctor['specialty']})"
            context.user_data['appointment_data']['doctor_id'] = doctor_id
            
            await query.edit_message_text(
                f"Вы выбрали: {doctor['name']}\n"
                f"Специализация: {doctor['specialty']}\n\n"
                f"Выберите удобную дату:",
                reply_markup=self.keyboards.date_keyboard()
            )
            return SELECTING_DATE
        
        # Выбор даты
        elif data.startswith('date_'):
            date = data.split('_')[1]
            context.user_data['appointment_data']['date'] = date
            
            available_times = self.google_sheets.get_available_slots(date)
            
            if not available_times:
                await query.edit_message_text(
                    "❌ На выбранную дату нет свободного времени.\n"
                    "Пожалуйста, выберите другую дату:",
                    reply_markup=self.keyboards.date_keyboard()
                )
                return SELECTING_DATE
            
            await query.edit_message_text(
                f"Выбрана дата: {date}\n"
                f"Выберите удобное время:",
                reply_markup=self.keyboards.time_keyboard(date)
            )
            return SELECTING_TIME
        
        # Выбор времени
        elif data.startswith('time_'):
            _, date, time = data.split('_', 2)
            context.user_data['appointment_data']['time'] = time
            
            doctor_id = context.user_data['appointment_data'].get('doctor_id')
            
            await query.edit_message_text(
                f"📅 Дата: {date}\n"
                f"🕐 Время: {time}\n"
                f"👨‍⚕️ Врач: {context.user_data['appointment_data']['doctor']}\n\n"
                f"Подтвердите запись:",
                reply_markup=self.keyboards.confirm_keyboard(date, time, doctor_id)
            )
            return CONFIRMING
        
        # Подтверждение записи
        elif data.startswith('confirm_'):
            _, date, time, doctor_id = data.split('_', 3)
            
            # Запрашиваем имя пациента
            await query.edit_message_text(
                "Пожалуйста, введите ваше ФИО:"
            )
            context.user_data['appointment_data']['date'] = date
            context.user_data['appointment_data']['time'] = time
            context.user_data['appointment_data']['doctor_id'] = doctor_id
            
            return GETTING_NAME
        
        # FAQ
        elif data == 'faq':
            await query.edit_message_text(
                "Часто задаваемые вопросы:",
                reply_markup=self.keyboards.faq_keyboard()
            )
        
        elif data.startswith('faq_'):
            question = data[4:]
            answer = self.config.FAQ.get(question, "Информация временно недоступна")
            await query.edit_message_text(
                f"❓ {question}\n\n{answer}",
                reply_markup=self.keyboards.faq_keyboard()
            )
        
        # Мои записи
        elif data == 'my_appointments':
            user_id = update.effective_user.id
            appointments = self.google_sheets.get_user_appointments(user_id)
            
            if not appointments:
                await query.edit_message_text(
                    "У вас пока нет записей на прием.",
                    reply_markup=self.keyboards.main_menu()
                )
            else:
                text = "📋 Ваши записи:\n\n"
                for app in appointments:
                    text += f"📅 {app['Дата']} в {app['Время']}\n"
                    text += f"👨‍⚕️ {app['Врач']}\n"
                    text += f"Статус: {app['Статус']}\n\n"
                
                await query.edit_message_text(
                    text,
                    reply_markup=self.keyboards.main_menu()
                )
        
        # О клинике
        elif data == 'about':
            text = (
                "🏥 О нашей клинике\n\n"
                "Мы - современная стоматологическая клиника "
                "с опытом работы более 10 лет.\n\n"
                "✅ Современное оборудование\n"
                "✅ Опытные врачи\n"
                "✅ Доступные цены\n"
                "✅ Комфортные условия\n\n"
                "Работаем без выходных с 9:00 до 20:00"
            )
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu()
            )
        
        # Контакты
        elif data == 'contacts':
            text = (
                "📞 Контакты:\n\n"
                "Телефон: +7 (999) 123-45-67\n"
                "Адрес: г. Москва, ул. Ленина, д. 10\n"
                "Email: info@dentclinic.ru\n\n"
                "⏰ Часы работы:\n"
                "Пн-Вс: 9:00 - 20:00"
            )
            await query.edit_message_text(
                text,
                reply_markup=self.keyboards.main_menu()
            )
        
        # Отмена записи
        elif data == 'cancel_appointment':
            await query.edit_message_text(
                "Запись отменена.",
                reply_markup=self.keyboards.main_menu()
            )
            return ConversationHandler.END
        
        # Навигация
        elif data == 'back_to_doctors':
            await query.edit_message_text(
                "Выберите врача:",
                reply_markup=self.keyboards.doctors_keyboard()
            )
            return SELECTING_DOCTOR
        
        elif data == 'back_to_dates':
            await query.edit_message_text(
                "Выберите дату:",
                reply_markup=self.keyboards.date_keyboard()
            )
            return SELECTING_DATE
        
        return ConversationHandler.END
    
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение имени пациента"""
        name = update.message.text
        
        if len(name) < 3:
            await update.message.reply_text(
                "Пожалуйста, введите корректное ФИО (минимум 3 символа):"
            )
            return GETTING_NAME
        
        context.user_data['appointment_data']['name'] = name
        
        await update.message.reply_text(
            f"Спасибо, {name}!\n"
            f"Теперь укажите ваш номер телефона для связи:"
        )
        
        return GETTING_PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение телефона и финальное подтверждение"""
        phone = update.message.text
        
        # Простая валидация телефона
        phone_pattern = re.compile(r'^(\+7|8)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$')
        
        if not phone_pattern.match(phone):
            await update.message.reply_text(
                "Пожалуйста, введите корректный номер телефона "
                "(например: +79991234567 или 89991234567):"
            )
            return GETTING_PHONE
        
        appointment_data = context.user_data['appointment_data']
        appointment_data['phone'] = phone
        appointment_data['user_id'] = update.effective_user.id
        
        # Сохраняем запись в Google Sheets
        success = self.google_sheets.add_appointment(
            date=appointment_data['date'],
            time=appointment_data['time'],
            doctor=appointment_data['doctor'],
            patient_name=appointment_data['name'],
            phone=phone,
            telegram_id=update.effective_user.id
        )
        
        if success:
            text = (
                "✅ Запись успешно создана!\n\n"
                f"📅 Дата: {appointment_data['date']}\n"
                f"🕐 Время: {appointment_data['time']}\n"
                f"👨‍⚕️ Врач: {appointment_data['doctor']}\n"
                f"👤 Пациент: {appointment_data['name']}\n"
                f"📞 Телефон: {phone}\n\n"
                f"Мы отправим вам напоминание за 2 часа до приема.\n"
                f"Если нужно изменить или отменить запись, "
                f"свяжитесь с нами по телефону или в боте."
            )
            
            await update.message.reply_text(
                text,
                reply_markup=self.keyboards.main_menu()
            )
            
            # Отправляем уведомление админу
            for admin_id in self.config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🔔 Новая запись!\n\n{text}"
                    )
                except:
                    pass
        
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при создании записи.\n"
                "Пожалуйста, попробуйте позже или свяжитесь с нами по телефону.",
                reply_markup=self.keyboards.main_menu()
            )
        
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена действия"""
        await update.message.reply_text(
            "Действие отменено.",
            reply_markup=self.keyboards.main_menu()
        )
        return ConversationHandler.END
    
    def run(self):
        """Запуск бота"""
        # Создаем приложение
        application = Application.builder().token(self.config.BOT_TOKEN).build()
        
        # Создаем ConversationHandler для записи
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
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel),
                CallbackQueryHandler(self.button_handler, pattern='^back_to_menu$')
            ],
            name="appointment_conversation"
        )
        
        # Добавляем обработчики
        application.add_handler(CommandHandler('start', self.start))
        application.add_handler(conv_handler)
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Запускаем планировщик напоминаний
        scheduler = ReminderScheduler(application.bot, self.google_sheets)
        
        # Запускаем бота
        print("Бот запущен...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = DentalClinicBot()
    bot.run()
