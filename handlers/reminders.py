from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import pytz
from config import confirmed_lessons
from handlers.reminder_utils import send_reminder_to_student

# Московское время
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


async def send_reminder_to_student(context, student_id, lesson):
    """Отправляет напоминание студенту о занятии"""
    try:
        # Извлекаем дату из названия занятия
        slot_name = lesson['slot_name']
        parts = slot_name.split()
        lesson_date = None
        for part in parts:
            if '.' in part and len(part.split('.')) == 3:
                lesson_date = part
                break

        # Рассчитываем дату для отмены (сегодня)
        today_date = "сегодняшнего дня"
        if lesson_date:
            try:
                from datetime import datetime
                # Сегодняшняя дата для отмены (т.к. напоминание за день до)
                today = datetime.now()
                today_date = today.strftime("%d.%m")
            except:
                pass

        reminder_text = (
            f"🔔 *Напоминание о занятии!*\n\n"
            f"*Завтра у вас запланирован урок:*\n"
            f"• {lesson['slot_name']}\n\n"
            f"*Адрес:*\n"
            f"4-й Сыромятнический переулок, 3/5с3\n"
            f"[Яндекс Карты](https://yandex.ru/maps/-/CLdYmDK3)\n\n"
            f"ℹ️ *Бесплатная отмена урока доступна НЕ позже 10:00 {today_date}*\n\n"
            f"Пожалуйста, не опаздывайте и возьмите с собой все необходимое!"
        )

        await context.bot.send_message(
            chat_id=student_id,
            text=reminder_text,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

        lesson['reminder_sent'] = True
        print(f"🔔 Sent reminder to student {student_id}")

    except Exception as e:
        print(f"ERROR sending reminder to student {student_id}: {e}")
async def check_and_send_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет и отправляет напоминания о занятиях (вызывается ежедневно)"""
    print("🔔 Checking for reminders...")

    # Текущее время в Москве
    now_moscow = datetime.now(MOSCOW_TZ)

    # Считаем завтрашнюю дату
    tomorrow_date = (now_moscow + timedelta(days=1)).date()

    reminders_sent = 0

    for student_id, lessons in list(confirmed_lessons.items()):
        for lesson in lessons:
            # Пропускаем если напоминание уже отправлено
            if lesson.get('reminder_sent', False):
                continue

            try:
                # Пытаемся распарсить дату занятия
                lesson_datetime_str = lesson.get('lesson_datetime', lesson['slot_name'])

                # Разные форматы дат: "Пн 02.12.2024 14:00" или "02.12.2024 14:00"
                parts = lesson_datetime_str.split()

                # Пытаемся найти дату и время
                date_str = None
                time_str = None

                for part in parts:
                    if '.' in part and len(part.split('.')) == 3:
                        # Нашли дату в формате DD.MM.YYYY
                        date_str = part
                    elif ':' in part and len(part.split(':')) == 2:
                        # Нашли время в формате HH:MM
                        time_str = part

                if date_str and time_str:
                    # Парсим дату занятия
                    lesson_date = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
                    lesson_date_moscow = MOSCOW_TZ.localize(lesson_date)

                    # Проверяем, что занятие завтра
                    if lesson_date_moscow.date() == tomorrow_date:
                        # Отправляем напоминание!
                        await send_reminder_to_student(context, student_id, lesson)
                        reminders_sent += 1

            except Exception as e:
                print(
                    f"ERROR parsing lesson date for reminder (student {student_id}, lesson {lesson.get('slot_name')}): {e}")
                continue

    print(f"🔔 Sent {reminders_sent} reminders")