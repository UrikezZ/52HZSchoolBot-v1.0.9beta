# reminders.py - ОБНОВЛЕННАЯ версия
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import pytz
from database import get_confirmed_lessons, update_lesson_reminder_sent
from config import TEACHER_IDS

MOSCOW_TZ = pytz.timezone('Europe/Moscow')


async def check_and_send_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет и отправляет напоминания о занятиях"""
    print(f"🔔 [{datetime.now()}] Проверка напоминаний...")

    now_moscow = datetime.now(MOSCOW_TZ)
    tomorrow_date = (now_moscow + timedelta(days=1)).date()

    print(f"🔔 Завтрашняя дата: {tomorrow_date}")

    all_lessons = get_confirmed_lessons()  # Из БД!
    print(f"🔔 Всего занятий в БД: {len(all_lessons)}")

    reminders_sent = 0

    for lesson in all_lessons:
        # Пропускаем если напоминание уже отправлено
        if lesson.get('reminder_sent', 0) == 1:
            print(f"  Пропуск: напоминание уже отправлено для урока {lesson.get('id')}")
            continue

        slot_name = lesson.get('slot_name', '')
        print(f"  Проверка урока: {slot_name}")

        try:
            # Ищем дату и время в названии
            date_str = None
            time_str = None

            for part in slot_name.split():
                if '.' in part and len(part.split('.')) == 3:
                    date_str = part
                elif ':' in part and len(part.split(':')) == 2:
                    time_str = part

            if date_str and time_str:
                # Парсим дату занятия
                lesson_datetime = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
                lesson_datetime = MOSCOW_TZ.localize(lesson_datetime)

                print(f"    Дата урока: {lesson_datetime.date()}")
                print(f"    Завтра: {tomorrow_date}")

                if lesson_datetime.date() == tomorrow_date:
                    print(f"    ✅ Найдено занятие на завтра!")

                    # Отправляем напоминание
                    student_id = lesson['user_id']

                    # Рассчитываем дату для отмены
                    today = datetime.now(MOSCOW_TZ)
                    cancellation_date = today.strftime("%d.%m")

                    reminder_text = (
                        f"🔔 *Напоминание о занятии!*\n\n"
                        f"*Завтра у вас запланирован урок:*\n"
                        f"• {slot_name}\n\n"
                        f"*Адрес:*\n"
                        f"4-й Сыромятнический переулок, 3/5с3\n"
                        f"[Яндекс Карты](https://yandex.ru/maps/-/CLdYmDK3)\n\n"
                        f"ℹ️ *Бесплатная отмена урока доступна НЕ позже 10:00 {cancellation_date}*\n\n"
                        f"Пожалуйста, не опаздывайте и возьмите с собой все необходимое!"
                    )

                    try:
                        await context.bot.send_message(
                            chat_id=student_id,
                            text=reminder_text,
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )

                        # Отмечаем как отправленное
                        update_lesson_reminder_sent(lesson['id'])
                        reminders_sent += 1
                        print(f"    ✅ Напоминание отправлено студенту {student_id}")

                    except Exception as e:
                        print(f"    ❌ Ошибка отправки студенту {student_id}: {e}")

        except Exception as e:
            print(f"    ❌ Ошибка парсинга даты '{slot_name}': {e}")
            continue

    print(f"🔔 Отправлено напоминаний: {reminders_sent}")

    # Уведомляем преподавателя
    if reminders_sent > 0 and TEACHER_IDS:
        try:
            await context.bot.send_message(
                chat_id=TEACHER_IDS[0],
                text=f"🔔 Отправлено {reminders_sent} напоминаний студентам о занятиях на завтра"
            )
        except Exception as e:
            print(f"❌ Ошибка уведомления преподавателя: {e}")