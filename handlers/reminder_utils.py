# reminder_utils.py
from telegram.ext import ContextTypes
from database import update_lesson_reminder_sent


async def send_reminder_to_student(context: ContextTypes.DEFAULT_TYPE, student_id: int, lesson: dict):
    """Отправляет напоминание студенту о занятии"""
    try:
        reminder_text = (
            f"🔔 *Напоминание о занятии!*\n\n"
            f"*Завтра у вас запланирован урок:*\n"
            f"• {lesson['slot_name']}\n\n"
            f"*Адрес:*\n"
            f"4-й Сыромятнический переулок, 3/5с3\n"
            f"[Яндекс Карты](https://yandex.ru/maps/-/CLdYmDK3)\n\n"
            f"Пожалуйста, не опаздывайте и возьмите с собой все необходимое!"
        )

        await context.bot.send_message(
            chat_id=student_id,
            text=reminder_text,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

        # Отмечаем что напоминание отправлено
        update_lesson_reminder_sent(lesson['id'])
        print(f"🔔 Sent reminder to student {student_id} for {lesson['slot_name']}")

    except Exception as e:
        print(f"ERROR sending reminder to student {student_id}: {e}")