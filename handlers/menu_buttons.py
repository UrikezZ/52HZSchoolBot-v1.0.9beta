"""
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


async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text.strip()
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)

    print(f"DEBUG MENU: Checking button '{text}' for user {user_id}")

    # Обработка кнопки "В главное меню" - всегда работает
    if text == "В главное меню":
        print(f"DEBUG MENU: Processing 'В главное меню'")
        has_profile = True if user_role == "teacher" else (
                user_id in user_profiles and user_profiles[user_id].get('fio'))
        await show_main_menu(update, context, has_profile=has_profile)
        return

    # Обработка кнопки "Помощь" - всегда работает
    if text == "❓ Помощь":
        print(f"DEBUG MENU: Processing 'Помощь'")
        await help_command(update, context)
        return

    # Обработка кнопки "Мой профиль" - всегда работает
    if text == "👨‍🏫 Мой профиль" or text == "👤 Мой профиль":
        print(f"DEBUG MENU: Processing 'Мой профиль'")
        await show_profile(update, context)
        return

    # Для остальных кнопок проверяем роль
    if user_role == "teacher":
        if text == "📊 Панель управления":
            await teacher_panel(update, context)
            return
        elif text == "🎓 Мои студенты":
            await show_students_list(update, context)
            return
        elif text == "📋 Расписание":
            await show_teacher_schedule(update, context)
            return
        elif text == "📅 Заявки студентов":
            await show_student_requests(update, context)
            return
        elif text == "💰 Управление балансом":
            await start_balance_management(update, context)
            return
    else:
        if text == "📅 Выбрать расписание":
            await choose_schedule(update, context)
            return
        elif text == "🕐 Мои занятия":
            await show_my_lessons(update, context)
            return
        elif text == "💰 Мой баланс":
            await show_my_balance(update, context)
            return
        elif text == "👨‍🏫 Связаться с преподавателем":
            from handlers.feedback import start_feedback
            await start_feedback(update, context)
            return

    # Если это не кнопка меню, НИЧЕГО не делаем - пусть другие обработчики разбираются
    print(f"DEBUG MENU: Text '{text}' is not a menu button, passing through")


# Создаем обработчик для кнопок меню
menu_buttons_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_menu_buttons
)
"""