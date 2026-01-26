from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, \
    ConversationHandler, ContextTypes
from datetime import datetime, time
import pytz
from config import BOT_TOKEN, cleanup_weekly_requests
from handlers.start import start, help_command, profile_command
from handlers.main_handler import main_message_handler_obj
from handlers.feedback import feedback_conversation
from handlers.balance import balance_handlers
from handlers.profile_conversation import create_profile_conversation, edit_profile_conversation
from handlers.reminders import check_and_send_reminders
from handlers.birthday_reminders import check_and_send_birthday_reminders
from handlers.teacher import show_upcoming_birthdays
from handlers.teacher_chat import teacher_chat_conversation
from handlers.lesson_management import lesson_management_conversation
from handlers.schedule import schedule_handlers
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def main():
    """Главная функция запуска бота"""
    # Создаем приложение с увеличенными таймаутами
    application = Application.builder() \
        .token(BOT_TOKEN) \
        .connect_timeout(30.0) \
        .read_timeout(30.0) \
        .write_timeout(30.0) \
        .pool_timeout(30.0) \
        .build()

    try:
        from config import cleanup_old_requests
        removed = cleanup_old_requests()
        print(f"🧹 Очищено {removed} старых заявок")
    except Exception as e:
        print(f"⚠️ Не удалось очистить старые заявки: {e}")

    # 1. ConversationHandler
    application.add_handler(create_profile_conversation)
    application.add_handler(edit_profile_conversation)
    application.add_handler(feedback_conversation)
    application.add_handler(lesson_management_conversation)
    application.add_handler(teacher_chat_conversation)


    application.add_handler(MessageHandler(filters.Regex("^🎂 Дни рождения$"), show_upcoming_birthdays))

    # 2. Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("birthdays", show_upcoming_birthdays))

    # 3. ГЛАВНЫЙ обработчик сообщений
    application.add_handler(main_message_handler_obj)

    # 4. CallbackQueryHandler из balance.py
    from handlers.balance import (
        select_student, handle_action_choice, show_student_statistics,
        charge_lesson, cancel_balance_management
    )

    application.add_handler(CallbackQueryHandler(select_student, pattern="^balance_select_"))
    application.add_handler(CallbackQueryHandler(handle_action_choice, pattern="^balance_"))
    application.add_handler(CallbackQueryHandler(show_student_statistics, pattern="^balance_statistics$"))
    application.add_handler(CallbackQueryHandler(charge_lesson, pattern="^balance_charge_lesson$"))
    application.add_handler(CallbackQueryHandler(cancel_balance_management, pattern="^balance_cancel$"))

    # 5. CallbackQueryHandler из schedule.py
    try:
        from handlers.schedule import (
            handle_schedule_buttons, handle_teacher_confirmation
        )
        application.add_handler(CallbackQueryHandler(handle_schedule_buttons, pattern="^select_day_"))
        application.add_handler(CallbackQueryHandler(handle_schedule_buttons, pattern="^select_time_"))
        application.add_handler(CallbackQueryHandler(handle_schedule_buttons, pattern="^nav_day_"))
        application.add_handler(CallbackQueryHandler(handle_schedule_buttons, pattern="^show_selected"))
        application.add_handler(CallbackQueryHandler(handle_schedule_buttons, pattern="^finish_schedule"))
        application.add_handler(CallbackQueryHandler(handle_teacher_confirmation, pattern="^confirm_"))
        application.add_handler(CallbackQueryHandler(handle_teacher_confirmation, pattern="^reject_all_"))
        application.add_handler(
            CallbackQueryHandler(lambda update, context: update.callback_query.answer(), pattern="^ignore$"))
    except ImportError as e:
        print(f"⚠️ Warning: Could not import schedule handlers: {e}")

    # 6. НАСТРОЙКА ВСЕХ НАПОМИНАНИЙ - JobQueue
    job_queue = application.job_queue

    if job_queue:
        from datetime import time

        # 1. Напоминания о занятиях в 15:00
        job_queue.run_daily(
            check_and_send_reminders,
            time=time(hour=12, minute=0),
            days=(0, 1, 2, 3, 4, 5, 6),
            name="daily_reminders"
        )

        # 2. Напоминания о днях рождения в 10:00
        job_queue.run_daily(
            check_and_send_birthday_reminders,
            time=time(hour=7, minute=0),
            days=(0, 1, 2, 3, 4, 5, 6),
            name="birthday_reminders"
        )

        # 3. ОЧИСТКА СТАРЫХ ЗАЯВОК КАЖДЫЙ ПОНЕДЕЛЬНИК В 8:00
        job_queue.run_daily(
            cleanup_weekly_requests,
            time=time(hour=5, minute=0),  # 8:00 Москва = 5:00 UTC
            days=(0,),  # Только понедельник (0 = Monday)
            name="weekly_cleanup"
        )

        print("=" * 50)
        print("🎹 Бот музыкальной школы запущен!")
        print("=" * 50)
        print("🔔 Системы напоминаний активированы:")
        print("   • О занятиях: каждый день в 15:00 по Москве")
        print("   • О днях рождения: каждый день в 10:00 по Москве")
        print("   • Очистка заявок: каждый понедельник в 8:00")
        print("=" * 50)

    else:
        print("⚠️ JobQueue не доступен, напоминания не будут работать")
        print("🎹 Бот запущен без системы напоминаний")

    # 7. Обработка ошибок
    application.add_error_handler(error_handler)

    # Запуск бота
    print("\n🔄 Бот запускается...")
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        logger.error(f"Critical error: {e}", exc_info=True)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=True)

    try:
        # Пытаемся уведомить администратора об ошибке
        error_msg = f"⚠️ Ошибка в боте:\n{context.error}"

        # Отправляем администратору (первому в списке TEACHER_IDS)
        from config import TEACHER_IDS
        if TEACHER_IDS:
            await context.bot.send_message(
                chat_id=TEACHER_IDS[0],
                text=error_msg[:4000]  # Ограничение Telegram
            )
    except:
        pass


if __name__ == "__main__":
    main()