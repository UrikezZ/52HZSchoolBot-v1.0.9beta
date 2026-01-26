# balance.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import is_teacher, get_student_balance, add_lessons_to_student, \
    add_deposit, set_student_notes, init_student_balance, set_student_price, \
    use_lesson, get_balance_display, get_total_lessons_count
from database import get_all_users, get_confirmed_lessons, get_user
import re
import logging

logger = logging.getLogger(__name__)


async def start_balance_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало управления балансом студентов"""
    user_id = update.effective_user.id

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен. Эта функция только для преподавателей.")
        return

    # Получаем список студентов из БД
    students_data = get_all_users(role='student')
    students = {}
    for student in students_data:
        if student.get('fio'):
            students[student['user_id']] = student

    if not students:
        await update.message.reply_text("📭 Пока нет зарегистрированных студентов.")
        return

    # Создаем клавиатуру со студентами
    keyboard = []
    for student_id, profile in students.items():
        balance = get_student_balance(student_id)
        total_lessons = get_total_lessons_count(student_id)
        balance_display = get_balance_display(student_id)

        button_text = f"{profile['fio']} (уроков: {balance['lessons_left']}, занятий: {total_lessons})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"balance_select_{student_id}")])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="balance_cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎓 *Выберите студента для управления балансом:*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def select_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора студента"""
    query = update.callback_query
    await query.answer()

    if query.data == "balance_cancel":
        await query.edit_message_text("❌ Управление балансом отменено.")
        # Очищаем все данные
        for key in ['selected_student_id', 'current_action']:
            if key in context.user_data:
                del context.user_data[key]
        return

    # Если это выбор студента: balance_select_12345
    elif query.data.startswith("balance_select_"):
        try:
            parts = query.data.split("_")
            if len(parts) >= 3:
                student_id = int(parts[2])
                context.user_data['selected_student_id'] = student_id
            else:
                await query.edit_message_text("❌ Ошибка: неверный формат данных.")
                return
        except (IndexError, ValueError) as e:
            await query.edit_message_text("❌ Ошибка: неверный ID студента.")
            return

    # Показываем меню студента
    student_id = context.user_data.get('selected_student_id')
    if not student_id:
        await query.edit_message_text("❌ Ошибка: студент не выбран.")
        return

    await show_student_menu(query, context, student_id)


async def show_student_menu(message_or_query, context, student_id: int):
    """Показывает меню действий для студента"""
    # Определяем, что пришло: сообщение или query
    if hasattr(message_or_query, 'message'):  # Это query
        chat_id = message_or_query.message.chat_id
        edit_func = message_or_query.edit_message_text
        reply_func = message_or_query.message.reply_text
    else:  # Это сообщение
        chat_id = message_or_query.chat_id
        edit_func = None
        reply_func = message_or_query.reply_text

    student_profile = get_user(student_id)
    if not student_profile:
        if edit_func:
            await edit_func("❌ Профиль студента не найден.")
        else:
            await reply_func("❌ Профиль студента не найден.")
        return

    balance = get_student_balance(student_id)
    balance_display = get_balance_display(student_id)
    total_lessons = get_total_lessons_count(student_id)

    student_info = (
        f"🎹 *Студент:* {student_profile['fio']}\n"
        f"📱 *Инструмент:* {', '.join(student_profile.get('instruments', []))}\n\n"
        f"💰 *Баланс:*\n"
        f"• Уроков осталось: {balance['lessons_left']} шт.\n"
        f"• Всего занятий: {total_lessons} шт.\n"
        f"• Баланс: {balance_display}\n"
        f"• Цена урока: {balance.get('lesson_price', 1000)} руб.\n"
        f"• Примечания: {balance.get('notes', 'Нет')}"
    )

    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить уроки", callback_data="balance_add_lessons"),
            InlineKeyboardButton("🎹 Списать урок", callback_data="balance_charge_lesson"),
        ],
        [
            InlineKeyboardButton("💰 Внести депозит", callback_data="balance_add_deposit"),
            InlineKeyboardButton("📊 Статистика", callback_data="balance_statistics"),
        ],
        [
            InlineKeyboardButton("💲 Цена урока", callback_data="balance_set_price"),
            InlineKeyboardButton("📝 Примечание", callback_data="balance_add_notes"),
        ],
        [
            InlineKeyboardButton("✅ Завершить", callback_data="balance_finish"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if edit_func:
            await edit_func(
                student_info,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await reply_func(
                student_info,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except Exception as e:
        # Если не получается отредактировать, отправляем новое сообщение
        await reply_func(
            student_info,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )


async def handle_action_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора действия"""
    query = update.callback_query
    await query.answer()

    # Проверяем, есть ли выбранный студент
    student_id = context.user_data.get('selected_student_id')
    if not student_id:
        await query.edit_message_text("❌ Ошибка: студент не выбран.")
        return

    action = query.data.replace("balance_", "")

    if action == "finish":
        await query.edit_message_text("✅ Управление балансом завершено.")
        # Очищаем данные
        for key in ['selected_student_id', 'current_action']:
            if key in context.user_data:
                del context.user_data[key]
        return

    elif action == "statistics":
        await show_student_statistics(update, context)
        return

    # Для остальных действий
    messages = {
        "add_deposit": "💰 *Внести депозит*\n\nВведите сумму депозита в рублях (только цифры):",
        "add_lessons": "➕ *Добавление уроков*\n\nВведите количество уроков для добавления (только цифры):",
        "add_notes": "📝 *Добавление примечания*\n\nВведите примечание для студента:",
        "set_price": "💲 *Установка цены урока*\n\nВведите новую цену урока в рублях (только цифры):",
        "charge_lesson": "🎹 *Списание урока*\n\nСписать 1 проведенный урок у студента?"
    }

    if action in messages:
        if action == "charge_lesson":
            # Для списания урока сразу выполняем действие
            await charge_lesson(update, context)
            return
        else:
            # Сохраняем выбранное действие
            context.user_data['current_action'] = action
            await query.edit_message_text(messages[action], parse_mode='Markdown')


async def handle_balance_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода данных для баланса (вызывается из main_handler)"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Проверяем, есть ли текущее действие для баланса
    action = context.user_data.get('current_action')
    if not action:
        return  # Выходим, не наше сообщение

    # Проверяем, что это преподаватель
    if not is_teacher(user_id):
        return

    student_id = context.user_data.get('selected_student_id')
    if not student_id:
        await update.message.reply_text("❌ Ошибка: студент не выбран.")
        if 'current_action' in context.user_data:
            del context.user_data['current_action']
        return

    student_profile = get_user(student_id)
    student_name = student_profile.get('fio', 'Студент') if student_profile else 'Студент'

    # Обработка числовых действий
    if action in ['add_deposit', 'add_lessons', 'set_price']:
        if not re.match(r'^\d+$', text):
            await update.message.reply_text("❌ Неверный формат! Введите только цифры.")
            return

        amount = int(text)
        if amount <= 0:
            await update.message.reply_text("❌ Значение должно быть положительным!")
            return

        # Выполняем действие
        if action == 'add_deposit':
            balance = add_deposit(student_id, amount)
            new_balance_display = get_balance_display(student_id)
            message = f"✅ *{amount} руб. внесено студентом {student_name}*\n\n• Новый баланс: {new_balance_display}"

            # Уведомляем студента
            await notify_student_about_balance_change(context, student_id, "deposit_added", "", amount)

        elif action == 'add_lessons':
            balance = add_lessons_to_student(student_id, amount)
            message = f"✅ *{amount} уроков добавлено студенту {student_name}*\n\n• Новый баланс: {balance['lessons_left']} уроков"

            # Уведомляем студента
            await notify_student_about_balance_change(context, student_id, "lessons_added", "", amount)

        elif action == 'set_price':
            balance = set_student_price(student_id, amount)
            message = f"💲 *Цена урока установлена для {student_name}*\n\n• Новая цена: {balance.get('lesson_price', amount)} руб."

            # Уведомляем студента
            await notify_student_about_balance_change(context, student_id, "price_changed", "", amount)

        await update.message.reply_text(message, parse_mode='Markdown')

    # Обработка примечания
    elif action == 'add_notes':
        balance = set_student_notes(student_id, text)
        message = f"📝 *Примечание добавлено студенту {student_name}*\n\nПримечание: {text}"

        # Уведомляем студента
        await notify_student_about_balance_change(context, student_id, "notes_updated", text)

        await update.message.reply_text(message, parse_mode='Markdown')

    else:
        await update.message.reply_text("❌ Неизвестное действие.")
        return

    # Очищаем текущее действие
    if 'current_action' in context.user_data:
        del context.user_data['current_action']

    # Показываем меню студента заново
    await show_student_menu(update.message, context, student_id)


async def charge_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Списание одного урока у студента с добавлением записи"""
    query = update.callback_query
    await query.answer()

    student_id = context.user_data.get('selected_student_id')
    if not student_id:
        await query.edit_message_text("❌ Ошибка: студент не выбран.")
        return

    student_profile = get_user(student_id)
    student_name = student_profile.get('fio', 'Студент') if student_profile else 'Студент'
    balance_before = get_student_balance(student_id)
    lesson_price = balance_before.get('lesson_price', 1000)

    # 1. Списываем урок
    if use_lesson(student_id):
        # 3. Обновляем статистику
        balance_after = get_student_balance(student_id)
        new_balance_display = get_balance_display(student_id)
        total_lessons = get_total_lessons_count(student_id)

        # Формируем сообщение для преподавателя
        if balance_before['lessons_left'] > 0:
            message = (
                f"✅ *Списан 1 урок у студента {student_name}*\n\n"
                f"• Оплачено уроком из предоплаты\n"
                f"• Осталось уроков: {balance_after['lessons_left']}\n"
                f"• Всего занятий: {total_lessons} шт.\n"
                f"• Новый баланс: {new_balance_display}"
            )
        else:
            message = (
                f"✅ *Списан 1 урок у студента {student_name}*\n\n"
                f"• Нет предоплаченных уроков\n"
                f"• Добавлен долг: {lesson_price} руб.\n"
                f"• Осталось уроков: {balance_after['lessons_left']}\n"
                f"• Всего занятий: {total_lessons} шт.\n"
                f"• Новый баланс: {new_balance_display}"
            )

        await query.edit_message_text(message, parse_mode='Markdown')

        # Уведомление студенту
        await notify_student_about_lesson(context, student_id, balance_before, balance_after, lesson_price)

        # Показываем обновленное меню студента
        await show_student_menu(query, context, student_id)
    else:
        await query.edit_message_text("❌ Ошибка при списании урока.")


async def notify_student_about_lesson(context: ContextTypes.DEFAULT_TYPE, student_id: int, balance_before: dict, balance_after: dict, lesson_price: int):
    """Отправляет уведомление студенту о списании урока"""
    from database import get_user
    from config import get_balance_display

    student_profile = get_user(student_id)
    if not student_profile:
        return

    student_name = student_profile.get('fio', 'Студент')

    # Определяем тип списания
    if balance_before['lessons_left'] > 0:
        notification = (
            f"📝 *Уведомление об уроке*\n\n"
            f"Проведен 1 урок.\n"
            f"• Списано с предоплаты\n"
            f"• Осталось уроков: {balance_after['lessons_left']}\n"
            f"• Баланс: {get_balance_display(student_id)}"
        )
    else:
        notification = (
            f"📝 *Уведомление об уроке*\n\n"
            f"Проведен 1 урок.\n"
            f"• Нет предоплаченных уроков\n"
            f"• Добавлен долг: {lesson_price} руб.\n"
            f"• Новый баланс: {get_balance_display(student_id)}"
        )

    # Отправляем уведомление студенту
    try:
        from telegram.error import BadRequest
        await context.bot.send_message(
            chat_id=student_id,
            text=notification,
            parse_mode='Markdown'
        )
        print(f"✅ Уведомление отправлено студенту {student_id}")
    except BadRequest as e:
        print(f"❌ Не удалось отправить уведомление студенту {student_id}: {e}")
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомления: {e}")


async def show_student_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детальную статистику студента"""
    query = update.callback_query
    await query.answer()

    student_id = context.user_data.get('selected_student_id')
    if not student_id:
        await query.edit_message_text("❌ Ошибка: студент не выбран.")
        return

    student_profile = get_user(student_id)
    balance = get_student_balance(student_id)

    # Расчет статистики
    lessons_left = balance['lessons_left']
    total_lessons = get_total_lessons_count(student_id)
    lesson_price = balance.get('lesson_price', 1000)

    # Финансовые расчеты
    total_lessons_value = total_lessons * lesson_price
    remaining_value = lessons_left * lesson_price

    statistics_text = (
        f"📊 *Статистика студента*\n\n"
        f"*Студент:* {student_profile.get('fio', 'Неизвестно') if student_profile else 'Неизвестно'}\n"
        f"*Инструмент:* {', '.join(student_profile.get('instruments', [])) if student_profile else 'Не указан'}\n\n"
        f"*Статистика уроков:*\n"
        f"• Уроков осталось: {lessons_left} шт.\n"
        f"• Всего занятий: {total_lessons} шт.\n"
        f"• Цена урока: {lesson_price} руб.\n\n"
        f"*Финансовая статистика:*\n"
        f"• Стоимость всех занятий: {total_lessons_value} руб.\n"
        f"• Стоимость оставшихся уроков: {remaining_value} руб.\n"
        f"• Текущий баланс: {get_balance_display(student_id)}\n\n"
    )

    if balance.get('notes'):
        statistics_text += f"*Примечания:*\n{balance['notes']}\n\n"

    # Кнопка возврата
    keyboard = [[InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"balance_select_{student_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        statistics_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def cancel_balance_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена управления балансом"""
    query = update.callback_query
    await query.edit_message_text("❌ Управление балансом отменено.")


async def show_my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает баланс студента"""
    user_id = update.effective_user.id

    if is_teacher(user_id):
        await update.message.reply_text("❌ Эта функция только для студентов.")
        return

    # Инициализируем баланс если его нет
    init_student_balance(user_id)

    balance = get_student_balance(user_id)
    profile = get_user(user_id)
    total_lessons = get_total_lessons_count(user_id)

    balance_text = (
        f"💰 *Ваш баланс*\n\n"
        f"*ФИО:* {profile.get('fio', 'Не указано') if profile else 'Не указано'}\n"
        f"*Инструмент:* {', '.join(profile.get('instruments', [])) if profile else 'Не указано'}\n\n"
        f"*Статистика уроков:*\n"
        f"• Уроков осталось: {balance['lessons_left']} шт.\n"
        f"• Всего занятий: {total_lessons} шт.\n"
        f"*Финансы:*\n"
        f"• Баланс: {get_balance_display(user_id)}\n"
        f"• Цена урока: {balance.get('lesson_price', 1000)} руб.\n\n"
    )

    if balance.get('notes'):
        balance_text += f"*Примечания преподавателя:*\n{balance['notes']}\n\n"

    # Ближайшие занятия - ВСЕ, кроме созданных через "Списать урок"
    from database import get_confirmed_lessons
    lessons = get_confirmed_lessons(user_id)
    if lessons:
        # Фильтруем: пропускаем ТОЛЬКО списания урока
        real_lessons = []
        for lesson in lessons:
            # Пропускаем ТОЛЬКО списания урока (через баланс)
            slot_name = lesson.get('slot_name', '')
            payment_type = lesson.get('payment_type', '')

            # Если это списание урока через баланс (создано в charge_lesson)
            if 'Ручное списание' in slot_name:
                continue

            real_lessons.append(lesson)

        if real_lessons:
            balance_text += "📅 *Ближайшие занятия:*\n"

            # Сортируем по дате
            def get_lesson_date(lesson):
                try:
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
                        from datetime import datetime
                        return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
                except:
                    from datetime import datetime
                    return datetime.max

                return datetime.max

            # Сортируем занятия по дате (от ближайших к дальним)
            real_lessons.sort(key=get_lesson_date)

            # Показываем все занятия
            for lesson in real_lessons:
                balance_text += f"• {lesson['slot_name']}\n"
        else:
            balance_text += "📅 Пока нет запланированных занятий"
    else:
        balance_text += "📅 Пока нет запланированных занятий"

    await update.message.reply_text(balance_text, parse_mode='Markdown')


async def notify_student_about_balance_change(context: ContextTypes.DEFAULT_TYPE, student_id: int, change_type: str, details: str, amount: int = None):
    """Отправляет уведомление студенту об изменении баланса"""
    from database import get_user
    from config import get_balance_display, get_student_balance, get_total_lessons_count

    student_profile = get_user(student_id)
    if not student_profile:
        print(f"❌ Профиль студента {student_id} не найден для уведомления")
        return

    student_name = student_profile.get('fio', 'Студент')
    balance = get_student_balance(student_id)
    balance_display = get_balance_display(student_id)
    total_lessons = get_total_lessons_count(student_id)

    # Формируем уведомление в зависимости от типа изменения
    if change_type == "deposit_added":
        notification = (
            f"💰 *Баланс пополнен!*\n\n"
            f"На ваш баланс внесено: *{amount} руб.*\n\n"
            f"*Текущий баланс:*\n"
            f"• Финансовый баланс: {balance_display}\n"
            f"• Уроков осталось: {balance['lessons_left']} шт.\n"
            f"• Всего занятий: {total_lessons} шт.\n"
            f"• Цена урока: {balance.get('lesson_price', 1000)} руб.\n\n"
            f"Спасибо за оплату!"
        )

    elif change_type == "lessons_added":
        notification = (
            f"🎹 *Уроки добавлены!*\n\n"
            f"Вам добавлено: *{amount} уроков*\n\n"
            f"*Текущий баланс:*\n"
            f"• Уроков осталось: {balance['lessons_left']} шт.\n"
            f"• Всего занятий: {total_lessons} шт.\n"
            f"• Финансовый баланс: {balance_display}\n"
            f"• Цена урока: {balance.get('lesson_price', 1000)} руб.\n\n"
            f"Приятных занятий!"
        )

    elif change_type == "price_changed":
        notification = (
            f"💲 *Изменена цена урока!*\n\n"
            f"Новая цена урока: *{amount} руб.*\n\n"
            f"*Текущий баланс:*\n"
            f"• Уроков осталось: {balance['lessons_left']} шт.\n"
            f"• Всего занятий: {total_lessons} шт.\n"
            f"• Финансовый баланс: {balance_display}\n"
            f"• Цена урока: {balance.get('lesson_price', 1000)} руб.\n\n"
            f"Все изменения согласованы с вами."
        )

    elif change_type == "notes_updated":
        notification = (
            f"📝 *Обновлено примечание!*\n\n"
            f"*Новое примечание:*\n{details}\n\n"
            f"*Текущий баланс:*\n"
            f"• Уроков осталось: {balance['lessons_left']} шт.\n"
            f"• Всего занятий: {total_lessons} шт.\n"
            f"• Финансовый баланс: {balance_display}\n"
            f"• Цена урока: {balance.get('lesson_price', 1000)} руб.\n\n"
            f"Если есть вопросы - обращайтесь!"
        )

    elif change_type == "lesson_charged":
        # Это уже есть в notify_student_about_lesson
        return

    else:
        print(f"❌ Неизвестный тип уведомления: {change_type}")
        return

    # Отправляем уведомление студенту
    try:
        await context.bot.send_message(
            chat_id=student_id,
            text=notification,
            parse_mode='Markdown'
        )
        print(f"✅ Уведомление отправлено студенту {student_id} ({student_name}) - {change_type}")
    except Exception as e:
        print(f"❌ Не удалось отправить уведомление студенту {student_id}: {e}")


# Регистрируем обработчики
balance_handlers = [
    # Callback handlers
    CallbackQueryHandler(select_student, pattern="^balance_select_"),
    CallbackQueryHandler(handle_action_choice, pattern="^balance_"),
    CallbackQueryHandler(show_student_statistics, pattern="^balance_statistics$"),
    CallbackQueryHandler(charge_lesson, pattern="^balance_charge_lesson$"),
    CallbackQueryHandler(cancel_balance_management, pattern="^balance_cancel$"),
]