from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import pytz
from config import user_profiles, TEACHER_IDS, get_birthday_info, is_teacher

# Московское время
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


async def check_and_send_birthday_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет и отправляет уведомления о днях рождения студентов"""
    print("🎂 Проверяю дни рождения...")

    # Текущая дата
    today = datetime.now(MOSCOW_TZ).date()

    # Завтрашняя дата
    tomorrow = today + timedelta(days=1)

    today_birthdays = []
    tomorrow_birthdays = []

    # Проверяем всех пользователей
    for user_id, profile in user_profiles.items():
        # Пропускаем преподавателей
        if is_teacher(user_id):
            continue

        # Получаем информацию о дне рождения
        birthday_info = get_birthday_info(user_id)
        if not birthday_info:
            continue

        birthdate = birthday_info['birthdate']

        # Проверяем, день рождения сегодня
        if birthdate.month == today.month and birthdate.day == today.day:
            today_birthdays.append({
                'user_id': user_id,
                'profile': profile,
                'age': birthday_info['age']
            })

        # Проверяем, день рождения завтра
        elif birthdate.month == tomorrow.month and birthdate.day == tomorrow.day:
            tomorrow_birthdays.append({
                'user_id': user_id,
                'profile': profile,
                'age': birthday_info['age']
            })

    # Отправляем уведомления преподавателям
    await send_birthday_notifications(context, today_birthdays, tomorrow_birthdays)


async def send_birthday_notifications(context: ContextTypes.DEFAULT_TYPE,
                                      today_birthdays: list,
                                      tomorrow_birthdays: list):
    """Отправляет уведомления о днях рождения преподавателям"""

    # Сегодняшние дни рождения
    if today_birthdays:
        message = "🎉 *Сегодня день рождения у студентов:*\n\n"

        for student in today_birthdays:
            profile = student['profile']
            age = student['age'] + 1  # +1 потому что сегодня ему исполняется age+1 лет

            instruments = profile.get('instruments', [])
            goals = profile.get('goals', 'Не указаны')

            message += (
                f"• *{profile['fio']}*\n"
                f"  Исполняется: {age} лет\n"
                f"  Инструмент: {', '.join(instruments) if instruments else 'Не указан'}\n"
                f"  Цели: {goals[:50]}{'...' if len(goals) > 50 else ''}\n\n"
            )

        # Отправляем всем преподавателям
        for teacher_id in TEACHER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=teacher_id,
                    text=message,
                    parse_mode='Markdown'
                )
                print(f"🎂 Отправил уведомление о днях рождения преподавателю {teacher_id}")
            except Exception as e:
                print(f"ERROR sending birthday notification to teacher {teacher_id}: {e}")

    # Завтрашние дни рождения
    if tomorrow_birthdays:
        message = "📅 *Завтра день рождения у студентов:*\n\n"

        for student in tomorrow_birthdays:
            profile = student['profile']
            age = student['age'] + 1

            instruments = profile.get('instruments', [])
            goals = profile.get('goals', 'Не указаны')

            message += (
                f"• *{profile['fio']}*\n"
                f"  Исполнится: {age} лет\n"
                f"  Инструмент: {', '.join(instruments) if instruments else 'Не указан'}\n\n"
            )

        # Отправляем всем преподавателям
        for teacher_id in TEACHER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=teacher_id,
                    text=message,
                    parse_mode='Markdown'
                )
                print(f"🎂 Отправил уведомление о завтрашних днях рождения преподавателю {teacher_id}")
            except Exception as e:
                print(f"ERROR sending tomorrow birthday notification to teacher {teacher_id}: {e}")

    if not today_birthdays and not tomorrow_birthdays:
        print("🎂 Сегодня и завтра нет дней рождения у студентов")