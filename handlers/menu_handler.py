from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from config import get_user_role
from handlers.profile import show_profile
from handlers.teacher import teacher_panel, show_students_list, show_teacher_schedule, show_student_requests
from handlers.balance import start_balance_management, show_my_balance
from handlers.start import help_command
from handlers.schedule import choose_schedule, show_my_lessons
from keyboards.main_menu import show_main_menu
from config import user_profiles


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик всех кнопок меню"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)

    print(f"DEBUG MENU: Button '{text}' from user {user_id}")

    # СПИСОК ВСЕХ КНОПОК МЕНЮ
    menu_buttons = [
        "В главное меню", "❓ Помощь", "👨‍🏫 Мой профиль", "👤 Мой профиль",
        "📊 Панель управления", "🎓 Мои студенты", "📋 Расписание",
        "📅 Заявки студентов", "💰 Управление балансом",
        "📅 Выбрать расписание", "🕐 Мои занятия", "💰 Мой баланс",
        "👨‍🏫 Связаться с преподавателем", "✏️ Изменить профиль",
        "👤 Создать профиль", "👨‍🏫 Заполнить профиль"
    ]

    # Если это НЕ кнопка меню - сразу выходим
    if text not in menu_buttons:
        print(f"DEBUG MENU: '{text}' is NOT a menu button, skipping")
        return False  # False = не обработано, пусть другие обработчики работают

    # В главное меню
    if text == "В главное меню":
        has_profile = True if user_role == "teacher" else (
                user_id in user_profiles and user_profiles[user_id].get('fio'))
        await show_main_menu(update, context, has_profile=has_profile)
        return True

    # Помощь
    elif text == "❓ Помощь":
        await help_command(update, context)
        return True

    # Мой профиль
    elif text == "👨‍🏫 Мой профиль" or text == "👤 Мой профиль":
        await show_profile(update, context)
        return True

    # Преподаватель
    elif user_role == "teacher":
        if text == "📊 Панель управления":
            await teacher_panel(update, context)
            return True
        elif text == "🎓 Мои студенты":
            await show_students_list(update, context)
            return True
        elif text == "📋 Расписание":
            await show_teacher_schedule(update, context)
            return True
        elif text == "📅 Заявки студентов":
            await show_student_requests(update, context)
            return True
        elif text == "💰 Управление балансом":
            await start_balance_management(update, context)
            return True

    # Студент
    else:
        if text == "📅 Выбрать расписание":
            await choose_schedule(update, context)
            return True
        elif text == "🕐 Мои занятия":
            await show_my_lessons(update, context)
            return True
        elif text == "💰 Мой баланс":
            await show_my_balance(update, context)
            return True
        elif text == "👨‍🏫 Связаться с преподавателем":
            from handlers.feedback import start_feedback
            await start_feedback(update, context)
            return True

    # Не кнопка меню
    return False


# Обработчик для кнопок меню
menu_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_menu
)