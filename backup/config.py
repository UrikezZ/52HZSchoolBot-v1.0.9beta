# config.py
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import (
    get_user, save_user, get_all_users,
    get_student_balance as db_get_student_balance, save_student_balance,
    get_confirmed_lessons, save_confirmed_lesson, delete_confirmed_lesson_by_slot,
    get_schedule_request, save_schedule_request, delete_schedule_request,
    get_all_schedule_requests, delete_all_schedule_requests,
    get_user_count_by_role, get_total_confirmed_lessons,
    update_lesson_reminder_sent, get_lessons_needing_reminder
)
import json

load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID администратора/преподавателя
TEACHER_IDS = [6395169224]


# ========== ОСНОВНЫЕ ФУНКЦИИ ==========

def is_teacher(user_id):
    """Проверяет, является ли пользователь преподавателем"""
    return user_id in TEACHER_IDS


def get_user_role(user_id):
    """Возвращает роль пользователя"""
    if user_id in TEACHER_IDS:
        return "teacher"

    user = get_user(user_id)
    if user:
        return user.get('role', 'student')
    return "student"


def init_user_profile(user_id, role="student"):
    """Инициализирует профиль пользователя с указанной ролью"""
    user = get_user(user_id)
    if not user:
        user_data = {
            'user_id': user_id,
            'fio': '',
            'birthdate': '',
            'instruments': [],
            'goals': '',
            'role': role,
            'study_format': 'очная'
        }
        save_user(user_data)
        return user_data
    return user


def get_user_profile(user_id):
    """Получает профиль пользователя"""
    return get_user(user_id)


def save_user_profile(user_id, profile_data):
    """Сохраняет профиль пользователя"""
    profile_data['user_id'] = user_id
    save_user(profile_data)


# ========== ФУНКЦИИ ДЛЯ СОВМЕСТИМОСТИ СО СТАРЫМ КОДОМ ==========

# Для обратной совместимости со старым кодом
def get_user_profiles_dict():
    """Возвращает словарь профилей пользователей (для совместимости)"""
    users = get_all_users()
    return {user['user_id']: user for user in users}


# Старые переменные для совместимости (пока не все модули обновлены)
user_profiles = get_user_profiles_dict()


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БАЛАНСОМ ==========

def init_student_balance(user_id):
    """Инициализирует баланс студента"""
    return db_get_student_balance(user_id)


def get_student_balance(user_id):
    """Возвращает баланс студента"""
    return db_get_student_balance(user_id)


def get_balance_display(user_id):
    """Возвращает отображаемый баланс с правильным знаком"""
    balance_data = get_student_balance(user_id)
    bal = balance_data['balance']
    if bal >= 0:
        return f"+{bal} руб."  # Депозит
    else:
        return f"{bal} руб."  # Долг (уже с минусом)


def add_lessons_to_student(user_id, lessons_count):
    """Добавляет уроки в баланс студента"""
    balance = get_student_balance(user_id)
    balance['lessons_left'] += lessons_count
    balance['total_paid_lessons'] = balance.get('total_paid_lessons', 0) + lessons_count
    save_student_balance(balance)
    return balance


def use_lesson(user_id):
    """Использует один урок (если есть предоплаченные) ИЛИ добавляет долг"""
    balance = get_student_balance(user_id)
    lesson_price = balance.get('lesson_price', 1800)

    if balance['lessons_left'] > 0:
        # Есть предоплаченные уроки - списываем один
        balance['lessons_left'] -= 1
    else:
        # Нет уроков - добавляем долг (уменьшаем баланс)
        balance['balance'] -= lesson_price

    save_student_balance(balance)
    return True


def add_deposit(user_id, amount):
    """Добавляет депозит (увеличивает баланс)"""
    balance = get_student_balance(user_id)
    balance['balance'] += amount
    save_student_balance(balance)
    return balance


def set_student_notes(user_id, notes):
    """Устанавливает примечания для студента"""
    balance = get_student_balance(user_id)
    balance['notes'] = notes
    save_student_balance(balance)
    return balance


def set_student_price(user_id, price):
    """Устанавливает цену урока для студента"""
    balance = get_student_balance(user_id)
    balance['lesson_price'] = price
    save_student_balance(balance)
    return balance


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ЗАНЯТИЯМИ ==========

def get_confirmed_lessons_dict(user_id=None):
    """Возвращает словарь подтвержденных занятий (для совместимости)"""
    lessons = get_confirmed_lessons(user_id)
    if user_id:
        return {user_id: lessons}
    else:
        # Группируем по user_id
        result = {}
        for lesson in lessons:
            if lesson['user_id'] not in result:
                result[lesson['user_id']] = []
            result[lesson['user_id']].append(lesson)
        return result


# Старая переменная для совместимости
confirmed_lessons = get_confirmed_lessons_dict()


def add_confirmed_lesson(lesson_data):
    """Добавляет подтвержденное занятие"""
    save_confirmed_lesson(lesson_data)
    # Обновляем кэш для совместимости
    user_id = lesson_data['user_id']
    if user_id not in confirmed_lessons:
        confirmed_lessons[user_id] = []
    confirmed_lessons[user_id].append(lesson_data)


def remove_confirmed_lesson(user_id, slot_id):
    """Удаляет подтвержденное занятие"""
    delete_confirmed_lesson_by_slot(user_id, slot_id)
    # Обновляем кэш
    if user_id in confirmed_lessons:
        confirmed_lessons[user_id] = [l for l in confirmed_lessons[user_id] if l['slot_id'] != slot_id]


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ЗАЯВКАМИ НА РАСПИСАНИЕ ==========

def get_schedule_requests_dict():
    """Возвращает словарь заявок на расписание (для совместимости)"""
    requests = get_all_schedule_requests()
    return {req['user_id']: req for req in requests}


# Старая переменная для совместимости
schedule_requests = get_schedule_requests_dict()


def save_schedule_request_dict(user_id, request_data):
    """Сохраняет заявку на расписание (для совместимости)"""
    request_data['user_id'] = user_id
    save_schedule_request(request_data)
    schedule_requests[user_id] = request_data


def remove_slot_from_all_requests(slot_id: str):
    """Удаляет слот из всех запросов всех студентов"""
    for user_id, request in list(schedule_requests.items()):
        if slot_id in request.get('selected_slots', []):
            request['selected_slots'].remove(slot_id)
            save_schedule_request(request)


def cleanup_old_requests():
    """Очищает старые заявки на прошедшие недели"""
    from database import cleanup_old_requests_weeks_ago
    return cleanup_old_requests_weeks_ago(1)


def clear_all_requests():
    """Очищает все заявки студентов"""
    delete_all_schedule_requests()
    schedule_requests.clear()
    return len(schedule_requests)


# ========== ФУНКЦИИ РАСПИСАНИЯ ==========

def get_next_week_dates():
    """Возвращает даты на следующую неделю (среда - воскресенье)"""
    today = datetime.now()

    # Находим следующую среду
    days_until_wednesday = (2 - today.weekday() + 7) % 7
    if days_until_wednesday == 0:  # Если сегодня среда
        days_until_wednesday = 7

    next_wednesday = today + timedelta(days=days_until_wednesday)

    # Генерируем даты со среды по воскресенье (5 дней)
    week_dates = {}
    days = ['Ср', 'Чт', 'Пт', 'Сб', 'Вс']

    for i in range(5):  # Ср-Вс
        current_date = next_wednesday + timedelta(days=i)
        week_dates[i] = {
            'date': current_date.strftime('%d.%m.%Y'),
            'day_name': days[i]
        }

    return week_dates


def get_day_slots(day_index):
    """Возвращает слоты для конкретного дня (13:00-21:00 для всех дней)"""
    week_dates = get_next_week_dates()
    day_info = week_dates.get(day_index, {})

    time_slots = {}
    for hour in range(13, 22):  # 13:00 до 21:00 включительно
        slot_id = f'day{day_index}_{hour:02d}00'
        time_slots[slot_id] = f"{hour:02d}:00"

    return time_slots, day_info


def get_available_slots_for_user(user_id):
    """Возвращает все слоты на неделю для пользователя"""
    all_slots = {}
    week_dates = get_next_week_dates()

    for day_index in range(5):  # Пн-Пт
        day_slots, day_info = get_day_slots(day_index)
        for slot_id, time in day_slots.items():
            all_slots[slot_id] = f"{day_info['day_name']} {day_info['date']} {time}"

    return all_slots


# ========== СТАТИСТИЧЕСКИЕ ФУНКЦИИ ==========

def get_total_lessons_count(user_id):
    """Возвращает общее количество подтвержденных занятий студента"""
    lessons = get_confirmed_lessons(user_id)
    return len(lessons)


def update_lesson_count(user_id):
    """Обновляет счетчик уроков на основе подтвержденных занятий"""
    # В базе данных это теперь вычисляется автоматически
    return get_student_balance(user_id)


def update_completed_lessons(user_id):
    """Обновляет счетчик проведенных уроков на основе прошедших занятий"""
    balance = get_student_balance(user_id)
    lessons = get_confirmed_lessons(user_id)

    # Считаем только прошедшие занятия
    now = datetime.now()
    completed_count = 0

    for lesson in lessons:
        try:
            # Пытаемся получить дату занятия из slot_name
            slot_name = lesson['slot_name']
            parts = slot_name.split()

            date_str = None
            time_str = None

            for part in parts:
                if '.' in part and len(part.split('.')) == 3:
                    date_str = part
                elif ':' in part and len(part.split(':')) == 2:
                    time_str = part

            if date_str and time_str:
                lesson_date = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")

                # Если занятие уже прошло
                if lesson_date < now:
                    completed_count += 1

        except Exception as e:
            continue

    # Обновляем счетчик
    balance['total_completed_lessons'] = completed_count
    save_student_balance(balance)

    return balance


# ========== ФУНКЦИИ ДЛЯ ДНЕЙ РОЖДЕНИЯ ==========

def get_birthday_info(user_id):
    """Получает информацию о дне рождения пользователя"""
    user = get_user(user_id)
    if not user:
        return None

    birthdate_str = user.get('birthdate', '')

    if not birthdate_str or birthdate_str == 'Не указано':
        return None

    try:
        # Парсим дату в формате ДД.ММ.ГГГГ
        birthdate = datetime.strptime(birthdate_str, "%d.%m.%Y")

        # Вычисляем возраст и ближайший день рождения
        today = datetime.now()

        # Возраст
        age = today.year - birthdate.year
        if (today.month, today.day) < (birthdate.month, birthdate.day):
            age -= 1

        # Следующий день рождения
        next_birthday_year = today.year
        next_birthday = datetime(next_birthday_year, birthdate.month, birthdate.day)

        # Если день рождения в этом году уже прошел, берем следующий год
        if next_birthday < today:
            next_birthday = datetime(next_birthday_year + 1, birthdate.month, birthdate.day)

        days_until_birthday = (next_birthday - today).days

        return {
            'birthdate': birthdate,
            'age': age,
            'next_birthday': next_birthday,
            'days_until': days_until_birthday,
            'formatted': birthdate_str
        }
    except ValueError:
        return None


# ========== ФУНКЦИИ ДЛЯ НАПОМИНАНИЙ ==========

def mark_reminder_sent(lesson_id):
    """Отмечает, что напоминание отправлено"""
    update_lesson_reminder_sent(lesson_id)


def get_lessons_for_reminder(target_date):
    """Получает занятия, требующие напоминания на указанную дату"""
    return get_lessons_needing_reminder(target_date)


# ========== ФУНКЦИИ ОЧИСТКИ ==========

async def cleanup_weekly_requests(context):
    """Еженедельная очистка старых заявок"""
    from datetime import datetime

    print("🧹 Начало еженедельной очистки заявок...")

    today = datetime.now()
    removed_count = 0

    requests = get_all_schedule_requests()

    for request in requests:
        user_id = request['user_id']

        # Проверяем, есть ли у студента подтвержденные занятия
        lessons = get_confirmed_lessons(user_id)
        has_confirmed_lessons = len(lessons) > 0

        if not has_confirmed_lessons:
            # У студента нет подтвержденных занятий - удаляем заявку
            delete_schedule_request(user_id)
            removed_count += 1
            print(f"DEBUG: Removed request for student {user_id} (no confirmed lessons)")

    print(f"🧹 Еженедельная очистка завершена. Удалено {removed_count} заявок")

    # Отправляем уведомление преподавателю
    if removed_count > 0 and TEACHER_IDS:
        try:
            await context.bot.send_message(
                chat_id=TEACHER_IDS[0],
                text=f"🧹 *Еженедельная очистка заявок*\n\n"
                     f"Удалено {removed_count} старых заявок студентов.\n"
                     f"Студенты без подтвержденных занятий будут выбирать расписание заново."
            )
        except Exception as e:
            print(f"ERROR sending cleanup notification: {e}")