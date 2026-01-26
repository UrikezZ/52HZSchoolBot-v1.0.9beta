from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import is_teacher, get_student_balance, get_balance_display
from database import get_user, get_confirmed_lessons, save_confirmed_lesson, delete_confirmed_lesson_by_slot, \
    get_all_users
from datetime import datetime, timedelta
import calendar
import re
from functools import wraps

# Состояния для ConversationHandler
LESSON_MANAGEMENT_SELECT_STUDENT, LESSON_MANAGEMENT_MAIN, LESSON_MANAGEMENT_CANCEL, \
    LESSON_MANAGEMENT_ADD_SELECT_MONTH, LESSON_MANAGEMENT_ADD_SELECT_DAY, \
    LESSON_MANAGEMENT_ADD_SELECT_TIME, LESSON_MANAGEMENT_ADD_CONFIRM = range(7)

# Времена занятий с 13:00 до 21:00
AVAILABLE_TIMES = [
    "13:00", "14:00", "15:00", "16:00", "17:00",
    "18:00", "19:00", "20:00", "21:00"
]

# Словарь для отслеживания активных обработок
active_processing = {}


def prevent_double_click(func):
    """Упрощенный декоратор для предотвращения двойного нажатия"""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Без сложной логики определения user_id
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            # Логируем ошибку, но не блокируем повторные нажатия
            print(f"Error in {func.__name__}: {e}")

    return wrapper


@prevent_double_click
async def start_lesson_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало управления занятиями"""
    user_id = update.effective_user.id

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен. Эта функция только для преподавателей.")
        return ConversationHandler.END

    # Получаем список студентов из БД
    students_data = get_all_users(role='student')
    students = {}
    for student in students_data:
        if student.get('fio'):
            students[student['user_id']] = student

    if not students:
        await update.message.reply_text("📭 Пока нет зарегистрированных студентов.")
        return ConversationHandler.END

    # Создаем клавиатуру со студентами
    keyboard = []
    for student_id, profile in students.items():
        # Проверяем есть ли у студента занятия
        lessons = get_confirmed_lessons(student_id)
        has_lessons = len(lessons) > 0
        lesson_count = len(lessons)

        button_text = f"{profile['fio']}"
        if has_lessons:
            button_text += f" 📅({lesson_count})"

        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"lesson_mgmt_select_{student_id}")])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="lesson_mgmt_cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎹 *Управление занятиями*\n\n"
        "Выберите студента:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

    return LESSON_MANAGEMENT_SELECT_STUDENT


@prevent_double_click
async def select_student_for_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора студента"""
    query = update.callback_query
    await query.answer()

    if query.data == "lesson_mgmt_cancel":
        await query.edit_message_text("❌ Управление занятиями отменено.")
        return ConversationHandler.END

    if query.data.startswith("lesson_mgmt_select_"):
        student_id = int(query.data.split("_")[3])
        context.user_data['lesson_mgmt_student_id'] = student_id

        await show_student_lessons_menu(query, context, student_id)
        return LESSON_MANAGEMENT_MAIN


@prevent_double_click
async def show_student_lessons_menu(query, context, student_id: int):
    """Показывает меню управления занятиями студента"""
    # Получаем user_id для проверки прав
    user_id = query.from_user.id

    # Проверяем права преподавателя
    if not is_teacher(user_id):
        await query.edit_message_text("❌ Доступ запрещен.")
        return

    student_profile = get_user(student_id) or {}
    student_name = student_profile.get('fio', 'Студент')

    # Получаем текущие занятия студента
    current_lessons = get_confirmed_lessons(student_id)

    # Сортируем занятия по дате
    def get_lesson_date(lesson):
        try:
            # Пытаемся извлечь дату из названия слота
            parts = lesson['slot_name'].split()
            for part in parts:
                if '.' in part and len(part.split('.')) == 3:
                    date_str = part
                    break
            else:
                return datetime.max

            for part in parts:
                if ':' in part:
                    time_str = part
                    break
            else:
                return datetime.max

            return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        except:
            return datetime.max

    # Фильтруем только будущие занятия
    now = datetime.now()
    future_lessons = []
    past_lessons = []

    for lesson in current_lessons:
        lesson_date = get_lesson_date(lesson)
        if lesson_date > now:
            future_lessons.append(lesson)
        else:
            past_lessons.append(lesson)

    future_lessons.sort(key=get_lesson_date)

    # Формируем текст с занятиями
    if future_lessons:
        lessons_text = "📋 *Текущие занятия:*\n\n"
        for i, lesson in enumerate(future_lessons, 1):
            lessons_text += f"{i}. {lesson['slot_name']}\n"

        # Сохраняем занятия для дальнейшего использования
        context.user_data['future_lessons'] = future_lessons
    else:
        lessons_text = "📭 *Нет запланированных занятий*\n\n"

    # Получаем баланс студента (только для информации)
    balance = get_student_balance(student_id)
    balance_display = get_balance_display(student_id)

    info_text = (
        f"🎹 *Студент:* {student_name}\n"
        f"💰 Баланс: {balance_display}\n"
        f"📊 Уроков осталось: {balance['lessons_left']} шт.\n"
        f"📅 Будущих занятий: {len(future_lessons)} шт.\n"
        f"📝 Прошедших занятий: {len(past_lessons)} шт.\n\n"
    )

    # Создаем клавиатуру
    keyboard = []

    if future_lessons:
        keyboard.append([InlineKeyboardButton("❌ Отменить занятие", callback_data="lesson_mgmt_cancel_lesson")])

    keyboard.append([
        InlineKeyboardButton("➕ Добавить занятие", callback_data="lesson_mgmt_add_lesson"),
        InlineKeyboardButton("📊 Баланс", callback_data="lesson_mgmt_balance")
    ])

    keyboard.append([InlineKeyboardButton("◀️ Назад к выбору студента", callback_data="lesson_mgmt_back_to_students")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    full_text = info_text + lessons_text + "\nВыберите действие:"

    try:
        await query.edit_message_text(
            full_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=full_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )


@prevent_double_click
async def handle_lesson_management_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора действия в меню управления занятиями"""
    query = update.callback_query
    await query.answer()

    student_id = context.user_data.get('lesson_mgmt_student_id')
    if not student_id:
        await query.edit_message_text("❌ Ошибка: студент не выбран.")
        return ConversationHandler.END

    if query.data == "lesson_mgmt_back_to_students":
        # Возвращаемся к выбору студента
        await start_lesson_management_from_query(query, context)
        return LESSON_MANAGEMENT_SELECT_STUDENT

    elif query.data == "lesson_mgmt_back_to_menu":
        # Возвращаемся к главному меню студента
        await show_student_lessons_menu(query, context, student_id)
        return LESSON_MANAGEMENT_MAIN

    elif query.data == "lesson_mgmt_cancel_lesson":
        await show_cancel_lesson_menu(query, context, student_id)
        return LESSON_MANAGEMENT_CANCEL

    elif query.data == "lesson_mgmt_add_lesson":
        await show_month_selection(query, context)
        return LESSON_MANAGEMENT_ADD_SELECT_MONTH

    elif query.data == "lesson_mgmt_balance":
        await show_student_balance(query, context, student_id)
        return LESSON_MANAGEMENT_MAIN


async def start_lesson_management_from_query(query, context):
    """Запуск управления занятиями из callback query"""
    # Получаем список студентов из БД
    students_data = get_all_users(role='student')
    students = {}
    for student in students_data:
        if student.get('fio'):
            students[student['user_id']] = student

    # Создаем клавиатуру со студентами
    keyboard = []
    for student_id, profile in students.items():
        # Проверяем есть ли у студента занятия
        lessons = get_confirmed_lessons(student_id)
        has_lessons = len(lessons) > 0
        lesson_count = len(lessons)

        button_text = f"{profile['fio']}"
        if has_lessons:
            button_text += f" 📅({lesson_count})"

        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"lesson_mgmt_select_{student_id}")])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="lesson_mgmt_cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🎹 *Управление занятиями*\n\n"
        "Выберите студента:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@prevent_double_click
async def show_cancel_lesson_menu(query, context, student_id: int):
    """Показывает меню для отмены занятий"""
    future_lessons = context.user_data.get('future_lessons', [])

    if not future_lessons:
        await query.answer("Нет занятий для отмены", show_alert=True)
        return LESSON_MANAGEMENT_MAIN

    keyboard = []
    for i, lesson in enumerate(future_lessons, 1):
        keyboard.append([InlineKeyboardButton(
            f"❌ {lesson['slot_name']}",
            callback_data=f"lesson_cancel_{i - 1}"  # Сохраняем индекс занятия
        )])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="lesson_mgmt_back_to_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "❌ *Отмена занятия*\n\n"
        "Выберите занятие для отмены:\n"
        "(Студент будет уведомлен об отмене)",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@prevent_double_click
async def cancel_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена выбранного занятия (БЕЗ автоматического возврата в баланс)"""
    query = update.callback_query
    await query.answer()

    if query.data == "lesson_mgmt_back_to_menu":
        student_id = context.user_data.get('lesson_mgmt_student_id')
        await show_student_lessons_menu(query, context, student_id)
        return LESSON_MANAGEMENT_MAIN

    if query.data.startswith("lesson_cancel_"):
        lesson_index = int(query.data.split("_")[2])
        student_id = context.user_data.get('lesson_mgmt_student_id')

        future_lessons = context.user_data.get('future_lessons', [])

        if 0 <= lesson_index < len(future_lessons):
            lesson = future_lessons[lesson_index]

            # 1. Удаляем занятие из БД
            delete_confirmed_lesson_by_slot(student_id, lesson.get('slot_id', ''))

            # 2. Уведомляем студента
            student_profile = get_user(student_id) or {}
            student_name = student_profile.get('fio', 'Студент')

            notification = (
                f"❌ *Занятие отменено*\n\n"
                f"*Занятие:* {lesson['slot_name']}\n\n"
                f"Занятие отменено преподавателем.\n"
                f"По вопросам возврата средств обратитесь к преподавателю.\n\n"
                f"Вы можете выбрать другое время в разделе '📅 Выбрать расписание'"
            )

            try:
                await context.bot.send_message(
                    chat_id=student_id,
                    text=notification,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Ошибка уведомления студента об отмене: {e}")

            # 3. Показываем подтверждение с кнопкой "Далее"
            keyboard = [[InlineKeyboardButton("➡️ Далее", callback_data="lesson_mgmt_back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"✅ *Занятие отменено*\n\n"
                f"*Студент:* {student_name}\n"
                f"*Занятие:* {lesson['slot_name']}\n\n"
                f"⚠️ *Важно!* Урок НЕ возвращен в баланс автоматически.\n"
                f"Для возврата средств используйте '💰 Управление балансом'.\n\n"
                f"Студент уведомлен.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

            return LESSON_MANAGEMENT_CANCEL


@prevent_double_click
async def show_month_selection(query, context):
    """Показывает выбор месяца для добавления занятия (весь год вперед)"""
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # Создаем клавиатуру со всеми месяцами на год вперед
    keyboard = []
    row = []

    # Показываем месяцы на 12 месяцев вперед
    for i in range(12):
        month_num = (current_month + i - 1) % 12 + 1
        year = current_year + (current_month + i - 1) // 12

        month_name = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ][month_num - 1]

        # Показываем только будущие месяцы (включая текущий)
        if year > current_year or (year == current_year and month_num >= current_month):
            row.append(InlineKeyboardButton(
                f"{month_name} {year}",
                callback_data=f"lesson_add_month_{month_num:02d}_{year}"
            ))

            if len(row) == 2:  # 2 кнопки в строке
                keyboard.append(row)
                row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="lesson_mgmt_back_to_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📅 *Добавление занятия*\n\n"
        "Выберите месяц (доступно на год вперед):",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@prevent_double_click
async def select_month_for_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора месяца"""
    query = update.callback_query
    await query.answer()

    if query.data == "lesson_mgmt_back_to_menu":
        student_id = context.user_data.get('lesson_mgmt_student_id')
        await show_student_lessons_menu(query, context, student_id)
        return LESSON_MANAGEMENT_MAIN

    if query.data.startswith("lesson_add_month_"):
        # Формат: lesson_add_month_MM_YYYY
        parts = query.data.split("_")
        month = int(parts[3])
        year = int(parts[4])

        context.user_data['selected_month'] = month
        context.user_data['selected_year'] = year

        await show_day_selection(query, context, month, year)
        return LESSON_MANAGEMENT_ADD_SELECT_DAY


@prevent_double_click
async def show_day_selection(query, context, month: int, year: int):
    """Показывает выбор дня в выбранном месяце"""
    # Получаем количество дней в месяце
    days_in_month = calendar.monthrange(year, month)[1]

    # Создаем клавиатуру с днями
    keyboard = []
    row = []

    now = datetime.now()

    for day in range(1, days_in_month + 1):
        date_obj = datetime(year, month, day)

        # Проверяем, не прошел ли уже этот день
        if date_obj.date() < now.date():
            continue

        # Получаем день недели
        weekday = date_obj.strftime("%a")  # "Mon", "Tue", etc.
        weekday_rus = {
            "Mon": "Пн", "Tue": "Вт", "Wed": "Ср", "Thu": "Чт",
            "Fri": "Пт", "Sat": "Сб", "Sun": "Вс"
        }.get(weekday, weekday)

        button_text = f"{day} ({weekday_rus})"

        row.append(InlineKeyboardButton(
            button_text,
            callback_data=f"lesson_add_day_{day:02d}"
        ))

        if len(row) == 3:  # 3 кнопки в строке
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    month_name = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ][month - 1]

    keyboard.append([
        InlineKeyboardButton("◀️ Назад к выбору месяца", callback_data="lesson_add_back_to_month")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"📅 *Добавление занятия*\n\n"
        f"*Месяц:* {month_name} {year}\n"
        f"Выберите день (доступны только будущие даты):",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@prevent_double_click
async def select_day_for_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора дня"""
    query = update.callback_query
    await query.answer()

    if query.data == "lesson_add_back_to_month":
        await show_month_selection(query, context)
        return LESSON_MANAGEMENT_ADD_SELECT_MONTH

    if query.data.startswith("lesson_add_day_"):
        day = int(query.data.split("_")[3])

        context.user_data['selected_day'] = day
        month = context.user_data.get('selected_month')
        year = context.user_data.get('selected_year')

        await show_time_selection(query, context, year, month, day)
        return LESSON_MANAGEMENT_ADD_SELECT_TIME


@prevent_double_click
async def show_time_selection(query, context, year: int, month: int, day: int):
    """Показывает выбор времени для занятия (13:00-21:00)"""
    date_obj = datetime(year, month, day)
    date_str = date_obj.strftime("%d.%m.%Y")

    # Проверяем, не занято ли время другими студентами
    occupied_times = set()
    all_lessons = get_confirmed_lessons()  # Все занятия из БД

    for lesson in all_lessons:
        if date_str in lesson['slot_name']:
            # Извлекаем время из названия занятия
            parts = lesson['slot_name'].split()
            for part in parts:
                if ':' in part:
                    occupied_times.add(part)
                    break

    # Создаем клавиатуру с временами (13:00-21:00)
    keyboard = []
    row = []

    for time_slot in AVAILABLE_TIMES:
        is_occupied = time_slot in occupied_times

        if is_occupied:
            button_text = f"⛔ {time_slot}"
            callback_data = "ignore"
        else:
            button_text = time_slot
            callback_data = f"lesson_add_time_{time_slot}"

        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))

        if len(row) == 3:  # 3 кнопки в строке
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("◀️ Назад к выбору дня", callback_data="lesson_add_back_to_day")
    ])

    weekday_rus = {
        0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
    }.get(date_obj.weekday(), "??")

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"🕐 *Добавление занятия*\n\n"
        f"*Дата:* {weekday_rus} {date_str}\n"
        f"Выберите время (13:00-21:00):\n"
        f"⛔ - время занято другим студентом",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@prevent_double_click
async def select_time_for_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора времени"""
    query = update.callback_query
    await query.answer()

    if query.data == "lesson_add_back_to_day":
        month = context.user_data.get('selected_month')
        year = context.user_data.get('selected_year')
        await show_day_selection(query, context, month, year)
        return LESSON_MANAGEMENT_ADD_SELECT_DAY

    if query.data.startswith("lesson_add_time_"):
        time_slot = query.data.split("_")[3]

        context.user_data['selected_time'] = time_slot

        # Формируем полную дату для подтверждения
        year = context.user_data.get('selected_year')
        month = context.user_data.get('selected_month')
        day = context.user_data.get('selected_day')

        date_obj = datetime(year, month, day)
        date_str = date_obj.strftime("%d.%m.%Y")
        weekday_rus = {
            0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
        }.get(date_obj.weekday(), "??")

        full_slot_name = f"{weekday_rus} {date_str} {time_slot}"
        context.user_data['full_slot_name'] = full_slot_name

        student_id = context.user_data.get('lesson_mgmt_student_id')
        student_profile = get_user(student_id) or {}
        student_name = student_profile.get('fio', 'Студент')

        # НЕ показываем информацию о списании - преподаватель сам управляет балансом
        payment_info = "Оплата будет обсуждена отдельно с преподавателем"

        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data="lesson_add_confirm"),
                InlineKeyboardButton("❌ Отменить", callback_data="lesson_add_cancel")
            ],
            [InlineKeyboardButton("◀️ Назад к выбору времени", callback_data="lesson_add_back_to_time")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📝 *Подтверждение добавления занятия*\n\n"
            f"*Студент:* {student_name}\n"
            f"*Дата и время:* {full_slot_name}\n"
            f"*Примечание:* {payment_info}\n\n"
            f"После подтверждения студент получит уведомление.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        return LESSON_MANAGEMENT_ADD_CONFIRM


@prevent_double_click
async def confirm_add_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение добавления занятия (БЕЗ автоматического списания)"""
    query = update.callback_query
    await query.answer()

    # Добавляем обработку кнопки "Далее"
    if query.data == "lesson_mgmt_back_to_menu":
        student_id = context.user_data.get('lesson_mgmt_student_id')
        await show_student_lessons_menu(query, context, student_id)
        return LESSON_MANAGEMENT_MAIN

    if query.data == "lesson_add_back_to_time":
        year = context.user_data.get('selected_year')
        month = context.user_data.get('selected_month')
        day = context.user_data.get('selected_day')
        await show_time_selection(query, context, year, month, day)
        return LESSON_MANAGEMENT_ADD_SELECT_TIME

    elif query.data == "lesson_add_cancel":
        student_id = context.user_data.get('lesson_mgmt_student_id')
        await show_student_lessons_menu(query, context, student_id)
        return LESSON_MANAGEMENT_MAIN

    elif query.data == "lesson_add_confirm":
        student_id = context.user_data.get('lesson_mgmt_student_id')
        full_slot_name = context.user_data.get('full_slot_name')
        selected_time = context.user_data.get('selected_time')

        if not all([student_id, full_slot_name, selected_time]):
            await query.edit_message_text("❌ Ошибка: не все данные заполнены.")
            return ConversationHandler.END

        # Генерируем уникальный slot_id
        from datetime import datetime
        slot_id = f"manual_{datetime.now().timestamp()}"

        # Сохраняем занятие в БД
        save_confirmed_lesson({
            'user_id': student_id,
            'slot_id': slot_id,
            'slot_name': full_slot_name,
            'confirmed_by': query.from_user.id,
            'date_added': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'payment_type': "Оплата обсуждается с преподавателем",
            'is_manual': True
        })

        # Уведомляем студента
        student_profile = get_user(student_id) or {}
        student_name = student_profile.get('fio', 'Студент')

        # Извлекаем дату из full_slot_name
        parts = full_slot_name.split()
        lesson_date = None
        for part in parts:
            if '.' in part and len(part.split('.')) == 3:
                lesson_date = part
                break

        # Рассчитываем дату для отмена
        cancellation_date = "предыдущего дня"
        if lesson_date:
            try:
                from datetime import datetime, timedelta
                lesson_datetime = datetime.strptime(lesson_date, "%d.%m.%Y")
                previous_day = lesson_datetime - timedelta(days=1)
                cancellation_date = previous_day.strftime("%d.%m")
            except:
                pass

        notification = (
            f"✅ *Добавлено новое занятие!*\n\n"
            f"*Дата и время:*\n"
            f"{full_slot_name}\n\n"
            f"*Адрес:*\n"
            f"4-й Сыромятнический переулок, 3/5с3\n"
            f"[Яндекс Карты](https://yandex.ru/maps/-/CLdYmDK3)\n\n"
            f"*Примечание:* Оплата будет обсуждена отдельно с преподавателем.\n\n"
            f"ℹ️ *Бесплатная отмена урока доступна НЕ позже 10:00 {cancellation_date}*\n\n"
            f"По всем вопросам обращайтесь к преподавателю."
        )

        try:
            await context.bot.send_message(
                chat_id=student_id,
                text=notification,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"Ошибка уведомления студента: {e}")

        # Показываем подтверждение с кнопкой "Далее"
        keyboard = [[InlineKeyboardButton("➡️ Далее", callback_data="lesson_mgmt_back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"✅ *Занятие добавлено!*\n\n"
            f"*Студент:* {student_name}\n"
            f"*Занятие:* {full_slot_name}\n\n"
            f"⚠️ *Важно!* Урок НЕ списан с баланса автоматически.\n"
            f"Для списания средств используйте '💰 Управление балансом'.\n\n"
            f"Студент уведомлен.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        return LESSON_MANAGEMENT_ADD_CONFIRM


@prevent_double_click
async def show_student_balance(query, context, student_id: int):
    """Показывает баланс студента"""
    balance = get_student_balance(student_id)
    balance_display = get_balance_display(student_id)

    balance_text = (
        f"💰 *Баланс студента*\n\n"
        f"• Уроков осталось: {balance['lessons_left']} шт.\n"
        f"• Финансовый баланс: {balance_display}\n"
        f"• Цена урока: {balance.get('lesson_price', 1000)} руб.\n"
        f"• Всего оплачено уроков: {balance.get('total_paid_lessons', 0)} шт.\n"
        f"• Всего проведено уроков: {balance.get('total_completed_lessons', 0)} шт.\n"
    )

    if balance.get('notes'):
        balance_text += f"\n*Примечания:*\n{balance['notes']}\n"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="lesson_mgmt_back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        balance_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@prevent_double_click
async def cancel_lesson_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена управления занятиями"""
    await update.message.reply_text(
        "❌ Управление занятиями отменено.",
        reply_markup=ReplyKeyboardMarkup([["📊 Панель управления", "В главное меню"]], resize_keyboard=True)
    )
    return ConversationHandler.END


# Создаем ConversationHandler для управления занятиями
lesson_management_conversation = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^✏️ Управление занятиями$"), start_lesson_management)],
    states={
        LESSON_MANAGEMENT_SELECT_STUDENT: [
            CallbackQueryHandler(select_student_for_management, pattern="^lesson_mgmt_")
        ],
        LESSON_MANAGEMENT_MAIN: [
            CallbackQueryHandler(handle_lesson_management_choice, pattern="^lesson_mgmt_")
        ],
        LESSON_MANAGEMENT_CANCEL: [
            CallbackQueryHandler(cancel_lesson, pattern="^lesson_|^lesson_mgmt_")
        ],
        LESSON_MANAGEMENT_ADD_SELECT_MONTH: [
            CallbackQueryHandler(select_month_for_lesson, pattern="^lesson_add_|^lesson_mgmt_")
        ],
        LESSON_MANAGEMENT_ADD_SELECT_DAY: [
            CallbackQueryHandler(select_day_for_lesson, pattern="^lesson_add_")
        ],
        LESSON_MANAGEMENT_ADD_SELECT_TIME: [
            CallbackQueryHandler(select_time_for_lesson, pattern="^lesson_add_|^ignore")
        ],
        LESSON_MANAGEMENT_ADD_CONFIRM: [
            CallbackQueryHandler(confirm_add_lesson, pattern="^lesson_add_|^lesson_mgmt_")
        ],
    },
    fallbacks=[
        MessageHandler(filters.Regex("^❌ Отмена$"), cancel_lesson_management),
        MessageHandler(filters.Regex("^В главное меню$"), cancel_lesson_management),
        CallbackQueryHandler(lambda update, context: update.callback_query.answer(), pattern="^ignore$")
    ],
    per_message=False
)