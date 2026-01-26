# profile.py
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, MessageHandler, filters
from config import get_user_role, init_user_profile, get_user_profile
from keyboards.main_menu import show_main_menu


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)

    # Инициализируем профиль если его нет
    profile = init_user_profile(user_id, user_role)
    profile = get_user_profile(user_id)  # Получаем актуальные данные

    if user_role == "teacher":
        # Для преподавателя всегда показываем профиль
        profile_text = f"""
👨‍🏫 *Ваш профиль преподавателя:*

*ФИО:* {profile.get('fio', 'Не указано')}
*Дата рождения:* {profile.get('birthdate', 'Не указано')}
*Специализация:* {', '.join(profile.get('instruments', [])) if profile.get('instruments') else 'Не указана'}
*О себе:* {profile.get('goals', 'Не указано')}

Для изменения данных нажмите '✏️ Изменить профиль'
"""
        keyboard = [["✏️ Изменить профиль", "В главное меню"]]
    else:
        # Для студента
        if not profile.get('fio'):
            button_text = "👤 Создать профиль"
            await update.message.reply_text(
                f"❌ Профиль не заполнен.\n"
                f"Нажмите '{button_text}' для заполнения.",
                reply_markup=ReplyKeyboardMarkup([[button_text, "В главное меню"]], resize_keyboard=True)
            )
            return

        profile_text = f"""
📋 *Ваш профиль студента:*

*ФИО:* {profile['fio']}
*Дата рождения:* {profile.get('birthdate', 'Не указано')}
*Инструменты:* {', '.join(profile['instruments']) if profile.get('instruments') else 'Не выбраны'}
*Цели:* {profile.get('goals', 'Не указаны')}

Для изменения данных нажмите '✏️ Изменить профиль'
"""
        keyboard = [["✏️ Изменить профиль", "В главное меню"]]

    await update.message.reply_text(
        profile_text,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


# Теперь здесь НЕ регистрируем обработчики - они все в menu_buttons.py
profile_handlers = []