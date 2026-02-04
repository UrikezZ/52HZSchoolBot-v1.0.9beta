# start.py
from telegram import Update
from telegram.ext import ContextTypes
from keyboards.main_menu import show_main_menu
from config import is_teacher, init_user_profile, get_user_role
from database import get_user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id

    # Определяем роль пользователя по ID (а не по профилю)
    user_role = "teacher" if is_teacher(user_id) else "student"

    # Инициализируем профиль с правильной ролью
    init_user_profile(user_id, user_role)

    # Для преподавателя считаем, что профиль всегда есть
    profile = get_user(user_id)
    has_profile = True if user_role == "teacher" else (profile and profile.get('fio'))

    if has_profile:
        if user_role == "teacher":
            welcome_text = (
                f"👨‍🏫 Добро пожаловать, {user.first_name}!\n"
                f"Рады видеть вас в панели преподавателя!"
            )
        else:
            welcome_text = (
                f"🎵 С возвращением, {user.first_name}!\n"
                f"Рады видеть вас снова в музыкальной школе!"
            )
    else:
        if user_role == "teacher":
            welcome_text = (
                f"👨‍🏫 Здравствуйте, {user.first_name}!\n"
                f"Добро пожаловать в панель преподавателя музыкальной школы!\n\n"
                f"📝 *Для начала заполните ваш профиль* - это поможет студентам узнать о вас больше!"
            )
        else:
            welcome_text = (
                f"🎵 Привет, {user.first_name}!\n"
                f"Добро пожаловать в музыкальную школу!\n\n"
                f"📝 *Для начала заполните ваш профиль* - это поможет нам подобрать "
                f"лучшую программу обучения именно для вас!"
            )

    await update.message.reply_text(welcome_text, parse_mode='Markdown')
    await show_main_menu(update, context, has_profile=has_profile)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает помощь с контактом техподдержки (вас)"""
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)

    # Ваши контактные данные
    support_username = "UrikezZ"
    support_name = "Юрий"

    if user_role == "teacher":
        help_text = f"""
👨‍🏫 *Панель преподавателя*

*Техническая поддержка бота:*
📞 Написать разработчику: @{support_username} ({support_name})

*По вопросам:*
• Ошибки и баги в боте
• Предложения по улучшению
• Технические проблемы

*Часы поддержки:*
Пн-Вс: 10:00 - 22:00

_Отвечаю в течение нескольких часов_
        """
    else:
        help_text = f"""
🎹 *Панель студента*

*Техническая поддержка бота:*
📞 Написать разработчику: @{support_username} ({support_name})

*По вопросам:*
• Ошибки и баги в боте  
• Проблемы с расписанием
• Вопросы по балансу
• Технические неполадки

*Часы поддержки:*
Пн-Вс: 10:00 - 22:00

_Отвечаю в течение нескольких часов_
        """

    await update.message.reply_text(help_text, parse_mode='Markdown')


# Добавляем команду /profile
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.profile import show_profile
    await show_profile(update, context)


# Добавляем обработку кнопки "В главное меню" - эта функция должна быть,
# но не нужно добавлять ее в teacher_handlers здесь
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'В главное меню'"""
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)
    profile = get_user(user_id)
    has_profile = True if user_role == "teacher" else (profile and profile.get('fio'))

    await show_main_menu(update, context, has_profile=has_profile)