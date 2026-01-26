# main_handler.py
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from config import get_user_role, is_teacher
from database import get_user
import re


async def main_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ГЛАВНЫЙ обработчик ВСЕХ текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user_role = get_user_role(user_id)

    print(f"DEBUG MAIN HANDLER: Text='{text}', user_id={user_id}, role={user_role}")

    # 1. Проверяем, является ли это кнопкой меню
    menu_buttons = [
        "В главное меню", "❓ Помощь", "👨‍🏫 Мой профиль", "👤 Мой профиль",
        "📊 Панель управления", "🎓 Мои студенты", "📋 Расписание",
        "📅 Заявки студентов", "💰 Управление балансом",
        "📅 Выбрать расписание", "🕐 Мои занятия", "💰 Мой баланс",
        "👨‍🏫 Связаться с преподавателем", "✏️ Изменить профиль",
        "👤 Создать профиль", "👨‍🏫 Заполнить профиль"
    ]

    if text in menu_buttons:
        print(f"DEBUG: Processing as menu button: {text}")
        await process_menu_button(update, context, text, user_role)
        return

    # 2. Проверяем, является ли это вводом для баланса
    action = context.user_data.get('current_action')
    if action and is_teacher(user_id):
        print(f"DEBUG: Processing as balance input: {text}, action={action}")
        await handle_balance_input(update, context, text)
        return

    # 3. Если ничего не подошло - игнорируем
    print(f"DEBUG: Text '{text}' not processed")


async def process_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              text: str, user_role: str):
    """Обработка кнопок меню"""
    user_id = update.effective_user.id

    if text == "В главное меню":
        from keyboards.main_menu import show_main_menu
        profile = get_user(user_id)
        has_profile = True if user_role == "teacher" else (profile and profile.get('fio'))
        await show_main_menu(update, context, has_profile=has_profile)

    elif text == "❓ Помощь":
        from handlers.start import help_command
        await help_command(update, context)

    elif text == "👨‍🏫 Мой профиль" or text == "👤 Мой профиль":
        from handlers.profile import show_profile
        await show_profile(update, context)

    elif user_role == "teacher":
        if text == "📊 Панель управления":
            from handlers.teacher import teacher_panel
            await teacher_panel(update, context)
        elif text == "🎓 Мои студенты":
            from handlers.teacher import show_students_list
            await show_students_list(update, context)
        elif text == "📋 Расписание":
            from handlers.teacher import show_teacher_schedule
            await show_teacher_schedule(update, context)
        elif text == "📅 Заявки студентов":
            from handlers.teacher import show_student_requests
            await show_student_requests(update, context)
        elif text == "💰 Управление балансом":
            from handlers.balance import start_balance_management
            await start_balance_management(update, context)

    else:  # student
        if text == "📅 Выбрать расписание":
            from handlers.schedule import choose_schedule
            await choose_schedule(update, context)
        elif text == "🕐 Мои занятия":
            from handlers.schedule import show_my_lessons
            await show_my_lessons(update, context)
        elif text == "💰 Мой баланс":
            from handlers.balance import show_my_balance
            await show_my_balance(update, context)
        elif text == "👨‍🏫 Связаться с преподавателем":
            from handlers.feedback import start_feedback
            await start_feedback(update, context)


async def handle_balance_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Обработка ввода для баланса"""
    from database import get_user
    from handlers.balance import (
        add_deposit, add_lessons_to_student,
        set_student_price, set_student_notes, show_student_menu, get_balance_display,
        notify_student_about_balance_change
    )

    user_id = update.effective_user.id
    student_id = context.user_data.get('selected_student_id')
    action = context.user_data.get('current_action')

    if not student_id:
        await update.message.reply_text("❌ Ошибка: студент не выбран.")
        if 'current_action' in context.user_data:
            del context.user_data['current_action']
        return

    student_profile = get_user(student_id)
    student_name = student_profile.get('fio', 'Студент') if student_profile else 'Студент'

    if action in ['add_deposit', 'add_lessons', 'set_price']:
        if not re.match(r'^\d+$', text):
            await update.message.reply_text("❌ Неверный формат! Введите только цифры.")
            return

        amount = int(text)
        if amount <= 0:
            await update.message.reply_text("❌ Значение должно быть положительным!")
            return

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

    elif action == 'add_notes':
        balance = set_student_notes(student_id, text)
        message = f"📝 *Примечание добавлено студенту {student_name}*\n\nПримечание: {text}"

        # Уведомляем студента
        await notify_student_about_balance_change(context, student_id, "notes_updated", text)

        await update.message.reply_text(message, parse_mode='Markdown')

    # Очищаем действие
    if 'current_action' in context.user_data:
        del context.user_data['current_action']

    # Показываем меню студента заново
    await show_student_menu(update.message, context, student_id)


# Создаем обработчик
main_message_handler_obj = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    main_message_handler
)