# teacher.py
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from config import is_teacher, get_birthday_info, get_user_role
from database import get_all_users, get_confirmed_lessons, get_schedule_request, get_user
from keyboards.main_menu import show_main_menu
from datetime import datetime


# Обработчики для преподавателя
teacher_handlers = []


async def teacher_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель управления преподавателя"""
    user_id = update.effective_user.id

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен. Эта функция только для преподавателей.")
        return

    # Статистика
    from database import get_user_count_by_role, get_total_confirmed_lessons, get_all_schedule_requests

    total_students = get_user_count_by_role('student')
    total_lessons = get_total_confirmed_lessons()
    active_requests = len([r for r in get_all_schedule_requests() if r.get('selected_slots')])

    stats_text = (
        f"📊 *Панель управления преподавателя*\n\n"
        f"• Всего студентов: {total_students}\n"
        f"• Подтвержденных занятий: {total_lessons}\n"
        f"• Активных заявок: {active_requests}\n\n"
        f"Используйте кнопки меню для управления:"
    )

    await update.message.reply_text(stats_text, parse_mode='Markdown')


async def show_students_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех студентов"""
    user_id = update.effective_user.id

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен. Эта функция только для преподавателей.")
        return

    # Получаем всех студентов из БД
    students = get_all_users(role='student')

    if not students:
        await update.message.reply_text("📭 Пока нет зарегистрированных студентов.")
        return

    students_text = "🎓 *Список студентов:*\n\n"

    for i, student in enumerate(students, 1):
        confirmed_count = len(get_confirmed_lessons(student['user_id']))
        students_text += (
            f"{i}. *{student['fio']}*\n"
            f"   Инструменты: {', '.join(student['instruments'])}\n"
            f"   Занятий: {confirmed_count}\n"
            f"   Цели: {student.get('goals', 'Не указаны')}\n\n"
        )

    await update.message.reply_text(students_text, parse_mode='Markdown')


async def show_teacher_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает расписание преподавателя - группировка по дням с инструментами"""
    user_id = update.effective_user.id

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен. Эта функция только для преподавателей.")
        return

    # Собираем все подтвержденные занятия всех студентов
    all_lessons = get_confirmed_lessons()  # Все занятия

    if not all_lessons:
        await update.message.reply_text("📅 На этой неделе нет запланированных занятий.")
        return

    # СОРТИРУЕМ занятия по дате и времени
    all_lessons_with_details = []
    for lesson in all_lessons:
        student_profile = get_user(lesson['user_id'])
        if student_profile:
            student_name = student_profile.get('fio', 'Неизвестный студент')
            student_instruments = ', '.join(student_profile.get('instruments', []))

            # Пропускаем списания урока через баланс
            slot_name = lesson.get('slot_name', '')
            if 'Ручное списание' in slot_name:
                continue

            # Парсим дату и время из slot_name для сортировки
            date_str = ""
            time_str = ""

            parts = slot_name.split()
            for part in parts:
                if '.' in part and len(part.split('.')) == 3:
                    date_str = part
                elif ':' in part and len(part.split(':')) == 2:
                    time_str = part

            try:
                if date_str and time_str:
                    lesson_datetime = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
                else:
                    lesson_datetime = datetime.max
            except:
                lesson_datetime = datetime.max

            all_lessons_with_details.append({
                'student_id': lesson['user_id'],
                'student_name': student_name,
                'student_instruments': student_instruments,
                'slot_name': lesson['slot_name'],
                'slot_id': lesson['slot_id'],
                'date_str': date_str,
                'time_str': time_str,
                'datetime': lesson_datetime
            })

    # Сортируем занятия по дате
    all_lessons_with_details.sort(key=lambda x: x['datetime'])

    # Группируем занятия по дням
    lessons_by_day = {}

    for lesson in all_lessons_with_details:
        # Извлекаем день из названия занятия
        slot_name = lesson['slot_name']
        parts = slot_name.split()

        day_info = ""
        for part in parts:
            if part in ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']:
                day_info = part
                break

        # Ищем дату
        date_info = lesson['date_str'] if lesson['date_str'] else ""

        # Формируем ключ дня
        day_key = f"{day_info} {date_info}" if date_info else day_info

        if day_key not in lessons_by_day:
            lessons_by_day[day_key] = []

        lessons_by_day[day_key].append({
            'time': lesson['time_str'],
            'student_name': lesson['student_name'],
            'instruments': lesson['student_instruments'],
            'datetime': lesson['datetime']
        })

    # Сортируем дни по порядку (по дате, а не по названию дня)
    def get_day_datetime(day_key):
        try:
            # Извлекаем дату из ключа
            parts = day_key.split()
            for part in parts:
                if '.' in part and len(part.split('.')) == 3:
                    return datetime.strptime(part, "%d.%m.%Y")
        except:
            pass
        return datetime.max

    sorted_days = sorted(lessons_by_day.keys(), key=get_day_datetime)

    # Формируем сообщение с группировкой по дням
    schedule_text = "📋 *Ваше расписание:*\n\n"

    for day in sorted_days:
        schedule_text += f"*{day}:*\n"

        # Сортируем занятия по времени внутри дня
        day_lessons = lessons_by_day[day]
        day_lessons.sort(key=lambda x: x['datetime'])

        for lesson in day_lessons:
            schedule_text += f"• *{lesson['time']}* - {lesson['student_name']} "
            if lesson['instruments']:
                schedule_text += f"({lesson['instruments']})"
            schedule_text += "\n"

        schedule_text += "\n"

    # Добавляем общее количество занятий
    total_lessons = len(all_lessons_with_details)
    schedule_text += f"*Всего занятий:* {total_lessons}"

    await update.message.reply_text(schedule_text, parse_mode='Markdown')


async def show_student_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает заявки от студентов на занятия"""
    user_id = update.effective_user.id

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен. Эта функция только для преподавателей.")
        return

    # Фильтруем активные заявки (где есть выбранные слоты)
    from config import get_schedule_requests_dict
    schedule_requests = get_schedule_requests_dict()
    active_requests = {sid: request for sid, request in schedule_requests.items()
                       if request.get('selected_slots')}

    if not active_requests:
        await update.message.reply_text("📭 На данный момент студенты не отправили заявок на занятия.")
        return

    requests_text = "📋 *Заявки от студентов:*\n\n"

    for i, (student_id, request) in enumerate(active_requests.items(), 1):
        student_profile = get_user(student_id)
        student_name = student_profile.get('fio', 'Неизвестный студент') if student_profile else 'Неизвестный студент'
        instruments = student_profile.get('instruments', []) if student_profile else []
        goals = student_profile.get('goals', 'Не указаны') if student_profile else 'Не указаны'

        requests_text += f"*{i}. {student_name}*\n"
        requests_text += f"   Инструменты: {', '.join(instruments)}\n"
        requests_text += f"   Цели: {goals}\n"
        requests_text += f"   Выбранные слоты:\n"

        # Получаем названия слотов
        from config import get_available_slots_for_user
        all_slots = get_available_slots_for_user(student_id)
        for slot_id in request.get('selected_slots', []):
            slot_name = all_slots.get(slot_id, f"Слот {slot_id}")
            requests_text += f"   • {slot_name}\n"

        requests_text += "\n"

    await update.message.reply_text(requests_text, parse_mode='Markdown')


async def show_teacher_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает профиль преподавателя"""
    from handlers.profile import show_profile
    await show_profile(update, context)


async def help_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь для преподавателя"""
    from handlers.start import help_command
    await help_command(update, context)


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'В главное меню'"""
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)
    from database import get_user
    profile = get_user(user_id)
    has_profile = True if user_role == "teacher" else (profile and profile.get('fio'))

    await show_main_menu(update, context, has_profile=has_profile)


async def show_upcoming_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает ближайшие дни рождения студентов"""
    user_id = update.effective_user.id

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен. Эта функция только для преподавателей.")
        return

    students = get_all_users(role='student')
    upcoming_birthdays = []
    today = datetime.now()

    # Собираем все дни рождения
    for student in students:
        birthday_info = get_birthday_info(student['user_id'])
        if birthday_info:
            # ПРОВЕРЯЕМ: если ДР сегодня или в будущем этого года
            next_birthday = birthday_info['next_birthday']

            # Добавляем только если ДР в ближайшие 365 дней
            if birthday_info['days_until'] < 365:
                upcoming_birthdays.append({
                    'student_id': student['user_id'],
                    'profile': student,
                    'birthday_info': birthday_info
                })

    if not upcoming_birthdays:
        await update.message.reply_text(
            "📅 *Ближайшие дни рождения*\n\n"
            "В ближайший год дней рождения у студентов нет.",
            parse_mode='Markdown'
        )
        return

    # Сортируем по ближайшему дню рождения
    upcoming_birthdays.sort(key=lambda x: x['birthday_info']['days_until'])

    # Показываем ближайшие 10
    message = "📅 *Ближайшие дни рождения студентов:*\n\n"

    for i, student in enumerate(upcoming_birthdays[:10], 1):
        profile = student['profile']
        birthday_info = student['birthday_info']

        days_until = birthday_info['days_until']
        next_age = birthday_info['age'] + 1

        if days_until == 0:
            date_info = "🎉 *СЕГОДНЯ!*"
        elif days_until == 1:
            date_info = "Завтра"
        elif days_until < 30:
            date_info = f"Через {days_until} дней"
        elif days_until < 365:
            next_birthday = birthday_info['next_birthday']
            date_info = f"{next_birthday.strftime('%d.%m.%Y')} (через {days_until} дней)"
        else:
            # Пропускаем ДР которые больше чем через год
            continue

        message += (
            f"{i}. *{profile['fio']}*\n"
            f"   Ближайший ДР: {date_info}\n"
            f"   Исполнится: {next_age} лет\n"
            f"   Инструмент: {', '.join(profile.get('instruments', []))}\n\n"
        )

    await update.message.reply_text(message, parse_mode='Markdown')


# Регистрируем обработчики для преподавателя
teacher_handlers = [
    MessageHandler(filters.Regex("^🎂 Дни рождения$"), show_upcoming_birthdays),
]