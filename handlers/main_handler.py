from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from config import get_user_role, is_teacher
from database import get_user
import re

# Полный список кнопок меню (добавьте все кнопки из вашей системы)
MENU_BUTTONS = [
    "В главное меню", "🛠 Техподдержка", "👨‍🏫 Мой профиль", "👤 Мой профиль",
    "📊 Панель управления", "🎓 Мои студенты", "📋 Расписание",
    "📅 Заявки студентов", "💰 Управление балансом",
    "📅 Выбрать расписание", "🕐 Мои занятия", "💰 Мой баланс",
    "👨‍🏫 Связаться с преподавателем", "✏️ Изменить профиль",
    "👤 Создать профиль", "👨‍🏫 Заполнить профиль",
    "✏️ Управление занятиями", "💬 Написать студенту",
    "🗑 Удалить студента", "🎂 Дни рождения"
]


async def main_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user_role = get_user_role(user_id)

    print(f"DEBUG MAIN_HANDLER: Received text '{text}' from user {user_id}")

    # 1. Если это кнопка меню - обрабатываем
    if text in MENU_BUTTONS:
        print(f"DEBUG MAIN_HANDLER: This is a menu button '{text}'")
        await process_menu_button(update, context, text, user_role)
        return

    # 2. Проверяем, является ли это вводом для баланса
    action = context.user_data.get('current_action')
    if action and is_teacher(user_id):
        from handlers.balance import handle_balance_input
        await handle_balance_input(update, context)
        return

    # 3. Если это не кнопка меню и не ввод баланса - игнорируем
    print(f"DEBUG MAIN_HANDLER: Text '{text}' not processed, ignoring...")


async def process_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              text: str, user_role: str):
    """Обработка кнопок меню"""
    user_id = update.effective_user.id

    print(f"DEBUG PROCESS_MENU: Processing button '{text}' for user {user_id}")

    if text == "В главное меню":
        from keyboards.main_menu import show_main_menu
        profile = get_user(user_id)
        has_profile = True if user_role == "teacher" else (profile and profile.get('fio'))
        await show_main_menu(update, context, has_profile=has_profile)


    elif text == "🛠 Техподдержка":
        # Ваши данные
        support_username = "@UrikezZ"
        support_name = "Техподдержка 52 Герца"
        support_message = f"""
    🔧 *Техническая поддержка бота*
    
    *Разработчик и поддержка:* @{support_username}
    
    *По каким вопросам писать:*
    • Ошибки и баги в работе бота
    • Проблемы с выбором расписания
    • Неверное отображение баланса
    • Технические неполадки
    • Предложения по улучшению

    *Чего НЕ решаю:*
    • Вопросы оплаты занятий
    • Переносы расписания  
    • Отмены занятий
    • Методику обучения

    _По этим вопросам обращайтесь к преподавателю через кнопку "👨‍🏫 Связаться с преподавателем"_

    *Часы работы техподдержки:*
    🕐 Ежедневно: 10:00 - 22:00
    ⏱ Ответ в течение 2-3 часов
            """
        await update.message.reply_text(
            support_message,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup(
                [["В главное меню"]],
                resize_keyboard=True
            )
        )

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
        elif text == "✏️ Управление занятиями":
            from handlers.lesson_management import start_lesson_management
            await start_lesson_management(update, context)
        elif text == "💬 Написать студенту":
            from handlers.teacher_chat import start_teacher_chat
            await start_teacher_chat(update, context)
        elif text == "🗑 Удалить студента":
            from handlers.student_management import start_student_management
            await start_student_management(update, context)
        elif text == "🎂 Дни рождения":
            from handlers.teacher import show_upcoming_birthdays
            await show_upcoming_birthdays(update, context)

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
        elif text == "✏️ Изменить профиль":
            from handlers.profile_conversation import start_edit_profile
            await start_edit_profile(update, context)
        elif text == "👤 Создать профиль" or text == "👨‍🏫 Заполнить профиль":
            from handlers.profile_conversation import start_create_profile
            await start_create_profile(update, context)


# Создаем обработчик
main_message_handler_obj = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    main_message_handler
)