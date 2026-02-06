# profile_conversation.py
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler, \
    CommandHandler
from config import get_user_role, init_user_profile, save_user_profile, get_user_profile
from utils.validators import is_valid_date
from datetime import datetime

# Состояния для создания профиля (последовательное заполнение)
CREATE_FIO, CREATE_BIRTHDATE, CREATE_INSTRUMENTS, CREATE_GOALS = range(4)

# Состояния для редактирования профиля (выбор поля)
EDIT_MAIN, EDIT_FIO, EDIT_BIRTHDATE, EDIT_INSTRUMENTS, EDIT_GOALS = range(5, 10)

# Валидные инструменты
VALID_INSTRUMENTS = {
    "🎹 Фортепиано": ["Фортепиано"],
    "🎤 Вокал": ["Вокал"],
    "🎧 Аранжировка": ["Аранжировка"],
    "🎹 Фортепиано + 🎤 Вокал": ["Фортепиано", "Вокал"],
    "🎹 Фортепиано + 🎧 Аранжировка": ["Фортепиано", "Аранжировка"],
    "🎤 Вокал + 🎧 Аранжировка": ["Вокал", "Аранжировка"]
}


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

async def send_edit_menu(bot, user_id: int):
    """Отправляет меню редактирования профиля"""
    user_role = get_user_role(user_id)
    profile = get_user_profile(user_id)

    if user_role == "teacher":
        title = "👨‍🏫 *Редактирование профиля преподавателя:*"
    else:
        title = "👤 *Редактирование профиля студента:*"

    message_text = (
        f"{title}\n\n"
        f"*Текущие данные:*\n"
        f"• ФИО: {profile.get('fio', 'Не указано')}\n"
        f"• Дата рождения: {profile.get('birthdate', 'Не указано')}\n"
        f"• {'Специализация' if user_role == 'teacher' else 'Инструменты'}: "
        f"{', '.join(profile.get('instruments', [])) if profile.get('instruments') else 'Не выбраны'}\n"
        f"• {'О себе' if user_role == 'teacher' else 'Цели обучения'}: {profile.get('goals', 'Не указаны')}\n\n"
        f"*Что хотите изменить?*"
    )

    keyboard = [
        [InlineKeyboardButton("✏️ Изменить ФИО", callback_data="edit_fio")],
        [InlineKeyboardButton("📅 Изменить дату рождения", callback_data="edit_birthdate")],
        [InlineKeyboardButton("🎹 Изменить инструменты", callback_data="edit_instruments")],
        [InlineKeyboardButton("📝 Изменить цели", callback_data="edit_goals")],
        [
            InlineKeyboardButton("✅ Готово", callback_data="edit_done"),
            InlineKeyboardButton("❌ Отмена", callback_data="edit_cancel")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await bot.send_message(
        chat_id=user_id,
        text=message_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def show_profile_with_buttons(bot, user_id: int, user_role: str):
    """Показывает профиль с кнопками 'Изменить профиль' и 'В главное меню'"""
    profile = get_user_profile(user_id)

    if user_role == "teacher":
        profile_text = f"""
👨‍🏫 *Ваш профиль преподавателя:*

*ФИО:* {profile.get('fio', 'Не указано')}
*Дата рождения:* {profile.get('birthdate', 'Не указано')}
*Специализация:* {', '.join(profile.get('instruments', [])) if profile.get('instruments') else 'Не указана'}
*О себе:* {profile.get('goals', 'Не указано')}
"""
    else:
        profile_text = f"""
📋 *Ваш профиль студента:*

*ФИО:* {profile.get('fio', 'Не указано')}
*Дата рождения:* {profile.get('birthdate', 'Не указано')}
*Инструменты:* {', '.join(profile.get('instruments', [])) if profile.get('instruments') else 'Не выбраны'}
*Цели:* {profile.get('goals', 'Не указаны')}
"""

    keyboard = [["✏️ Изменить профиль", "В главное меню"]]

    await bot.send_message(
        chat_id=user_id,
        text=profile_text,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


# ========== СОЗДАНИЕ ПРОФИЛЯ (с нуля) ==========

async def start_create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания нового профиля с нуля"""
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)

    # Полностью сбрасываем профиль
    profile_data = {
        'user_id': user_id,
        'fio': '',
        'birthdate': '',
        'instruments': [],
        'goals': '',
        'role': user_role,
        'study_format': 'очная'
    }
    save_user_profile(user_id, profile_data)

    if user_role == "teacher":
        welcome_text = "👨‍🏫 *Заполните ваш профиль преподавателя:*"
    else:
        welcome_text = "👤 *Заполните ваш профиль студента:*"

    await update.message.reply_text(
        f"{welcome_text}\n\n"
        "*Шаг 1 из 4: ФИО*\n"
        "Введите ваше ФИО (например: Иванов Иван Иванович):",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )

    return CREATE_FIO


async def handle_create_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ФИО при создании профиля"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if len(text.split()) < 2:
        await update.message.reply_text(
            "❌ Пожалуйста, введите полное ФИО (Можно только Имя и Фамилию, например: Иван Иванов):"
        )
        return CREATE_FIO

    # Сохраняем ФИО
    profile = get_user_profile(user_id)
    profile['fio'] = text
    save_user_profile(user_id, profile)

    user_role = get_user_role(user_id)
    if user_role == "teacher":
        step_text = "👨‍🏫 *Шаг 2 из 4: Дата рождения*"
    else:
        step_text = "👤 *Шаг 2 из 4: Дата рождения*"

    await update.message.reply_text(
        f"{step_text}\n"
        "Введите вашу дату рождения в формате ДД.ММ.ГГГГ (например: 15.06.2004)\n"
        "Или нажмите кнопку ниже чтобы пропустить:",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([["Не указывать"]], resize_keyboard=True)
    )

    return CREATE_BIRTHDATE


async def handle_create_birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка даты рождения при создании профиля"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    profile = get_user_profile(user_id)

    if text == "Не указывать":
        profile['birthdate'] = "Не указано"
    else:
        if not is_valid_date(text):
            await update.message.reply_text(
                "❌ Неверный формат даты!\n"
                "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например: 15.06.2004)\n"
                "Или нажмите 'Не указывать':",
                reply_markup=ReplyKeyboardMarkup([["Не указывать"]], resize_keyboard=True)
            )
            return CREATE_BIRTHDATE
        profile['birthdate'] = text

    save_user_profile(user_id, profile)

    user_role = get_user_role(user_id)
    if user_role == "teacher":
        keyboard = [
            ["🎹 Фортепиано", "🎤 Вокал"],
            ["🎧 Аранжировка", "🎹 Фортепиано + 🎤 Вокал"],  # ← добавили
            ["🎹 Фортепиано + 🎧 Аранжировка", "🎤 Вокал + 🎧 Аранжировка"]  # ← добавили
        ]
        step_text = "👨‍🏫 *Шаг 3 из 4: Специализация*"
        prompt = "Выберите вашу специализацию:"
    else:
        keyboard = [
            ["🎹 Фортепиано", "🎤 Вокал"],
            ["🎧 Аранжировка", "🎹 Фортепиано + 🎤 Вокал"],  # ← добавили
            ["🎹 Фортепиано + 🎧 Аранжировка", "🎤 Вокал + 🎧 Аранжировка"]  # ← добавили
        ]
        step_text = "👤 *Шаг 3 из 4: Инструменты*"
        prompt = "Выберите инструмент/направление для обучения:"

    await update.message.reply_text(
        f"{step_text}\n{prompt}",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

    return CREATE_INSTRUMENTS


async def handle_create_instruments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка инструментов при создании профиля"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Обновленный список валидных вариантов с аранжировкой
    valid_options = [
        "🎹 Фортепиано", "🎤 Вокал", "🎧 Аранжировка",
        "🎹 Фортепиано + 🎤 Вокал",
        "🎹 Фортепиано + 🎧 Аранжировка",
        "🎤 Вокал + 🎧 Аранжировка"
    ]

    if text not in valid_options:
        user_role = get_user_role(user_id)
        if user_role == "teacher":
            keyboard = [
                ["🎹 Фортепиано", "🎤 Вокал"],
                ["🎧 Аранжировка", "🎹 Фортепиано + 🎤 Вокал"],
                ["🎹 Фортепиано + 🎧 Аранжировка", "🎤 Вокал + 🎧 Аранжировка"]
            ]
        else:
            keyboard = [
                ["🎹 Фортепиано", "🎤 Вокал"],
                ["🎧 Аранжировка", "🎹 Фортепиано + 🎤 Вокал"],
                ["🎹 Фортепиано + 🎧 Аранжировка", "🎤 Вокал + 🎧 Аранжировка"]
            ]

        await update.message.reply_text(
            "❌ Пожалуйста, выберите один из предложенных вариантов:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return CREATE_INSTRUMENTS

    # Сохраняем выбранные инструменты
    # Сначала определим, что выбрал пользователь
    if text == "🎹 Фортепиано":
        instruments = ["Фортепиано"]
    elif text == "🎤 Вокал":
        instruments = ["Вокал"]
    elif text == "🎧 Аранжировка":
        instruments = ["Аранжировка"]
    elif text == "🎹 Фортепиано + 🎤 Вокал":
        instruments = ["Фортепиано", "Вокал"]
    elif text == "🎹 Фортепиано + 🎧 Аранжировка":
        instruments = ["Фортепиано", "Аранжировка"]
    elif text == "🎤 Вокал + 🎧 Аранжировка":
        instruments = ["Вокал", "Аранжировка"]
    else:
        instruments = []

    profile = get_user_profile(user_id)
    profile['instruments'] = instruments
    save_user_profile(user_id, profile)

    user_role = get_user_role(user_id)
    if user_role == "teacher":
        step_text = "👨‍🏫 *Шаг 4 из 4: О себе*"
        prompt = "Расскажите о себе, вашем опыте и подходе к обучению:"
    else:
        step_text = "👤 *Шаг 4 из 4: Цели обучения*"
        prompt = "Напишите ваши цели обучения:\n(например: 'Хочу научиться играть классические произведения' или 'Подготовка к поступлению в музыкальный колледж')\n\nИли нажмите кнопку ниже если не хотите указывать цели:"

    keyboard = [["Не указывать"]]
    await update.message.reply_text(
        f"{step_text}\n{prompt}",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

    return CREATE_GOALS


async def handle_create_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка целей при создании профиля"""
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)
    text = update.message.text.strip()

    profile = get_user_profile(user_id)

    if text == "Не указывать":
        if user_role == "teacher":
            profile['goals'] = "Не указано"
        else:
            profile['goals'] = "Не указаны"
    else:
        profile['goals'] = text

    save_user_profile(user_id, profile)

    success_text = "✅ *Профиль успешно создан!*"
    keyboard = [["👤 Мой профиль", "В главное меню"]]
    if user_role == "teacher":
        keyboard = [["👨‍🏫 Мой профиль", "В главное меню"]]

    await update.message.reply_text(
        success_text,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

    # Показываем профиль
    await show_profile_with_buttons(context.bot, user_id, user_role)
    return ConversationHandler.END


async def cancel_create_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания профиля"""
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)

    # Очищаем профиль
    profile_data = {
        'user_id': user_id,
        'fio': '',
        'birthdate': '',
        'instruments': [],
        'goals': '',
        'role': user_role,
        'study_format': 'очная'
    }
    save_user_profile(user_id, profile_data)

    await update.message.reply_text(
        "❌ Создание профиля отменено.",
        reply_markup=ReplyKeyboardMarkup([["👤 Создать профиль", "В главное меню"]], resize_keyboard=True)
    )
    return ConversationHandler.END


# ========== РЕДАКТИРОВАНИЕ ПРОФИЛЯ ==========

async def start_edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало изменения профиля - показываем меню выбора поля"""
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)

    # Инициализируем профиль если его нет
    init_user_profile(user_id, user_role)

    # Показываем меню редактирования
    await send_edit_menu(context.bot, user_id)
    return EDIT_MAIN


async def send_edit_menu_with_success(bot, user_id: int, success_message: str):
    """Отправляет меню редактирования профиля с сообщением об успехе вверху"""
    user_role = get_user_role(user_id)
    profile = get_user_profile(user_id)

    if user_role == "teacher":
        title = "👨‍🏫 *Редактирование профиля преподавателя:*"
    else:
        title = "👤 *Редактирование профиля студента:*"

    # Объединяем сообщение об успехе с меню
    message_text = (
        f"{success_message}\n\n"
        f"{title}\n\n"
        f"*Текущие данные:*\n"
        f"• ФИО: {profile.get('fio', 'Не указано')}\n"
        f"• Дата рождения: {profile.get('birthdate', 'Не указано')}\n"
        f"• {'Специализация' if user_role == 'teacher' else 'Инструменты'}: "
        f"{', '.join(profile.get('instruments', [])) if profile.get('instruments') else 'Не выбраны'}\n"
        f"• {'О себе' if user_role == 'teacher' else 'Цели обучения'}: {profile.get('goals', 'Не указаны')}\n\n"
        f"*Что хотите изменить?*"
    )

    keyboard = [
        [InlineKeyboardButton("✏️ Изменить ФИО", callback_data="edit_fio")],
        [InlineKeyboardButton("📅 Изменить дату рождения", callback_data="edit_birthdate")],
        [InlineKeyboardButton("🎹 Изменить инструменты", callback_data="edit_instruments")],
        [InlineKeyboardButton("📝 Изменить цели", callback_data="edit_goals")],
        [
            InlineKeyboardButton("✅ Готово", callback_data="edit_done"),
            InlineKeyboardButton("❌ Отмена", callback_data="edit_cancel")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await bot.send_message(
        chat_id=user_id,
        text=message_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def handle_edit_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик главного меню редактирования профиля"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_role = get_user_role(user_id)

    if query.data == "edit_done":
        # Завершаем редактирование - ОДНО сообщение
        await query.edit_message_text("✅ *Профиль обновлен!*", parse_mode='Markdown')
        await show_profile_with_buttons(context.bot, user_id, user_role)
        return ConversationHandler.END

    elif query.data == "edit_cancel":
        # Отменяем редактирование - ОДНО сообщение
        await query.edit_message_text("❌ Редактирование отменено.", parse_mode='Markdown')
        await show_profile_with_buttons(context.bot, user_id, user_role)
        return ConversationHandler.END

    elif query.data == "edit_fio":
        # Переходим к редактированию ФИО - ОДНО сообщение
        await context.bot.send_message(
            chat_id=user_id,
            text="✏️ *Изменение ФИО*\n\n"
                 "Введите ваше новое ФИО (например: Иванов Иван Иванович):",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return EDIT_FIO

    elif query.data == "edit_birthdate":
        # Переходим к редактированию даты рождения - ОДНО сообщение
        await context.bot.send_message(
            chat_id=user_id,
            text="📅 *Изменение даты рождения*\n\n"
                 "Введите вашу дату рождения в формате ДД.ММ.ГГГГ (например: 15.06.2004)\n"
                 "Или нажмите кнопку 'Не указывать':",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([["Не указывать"]], resize_keyboard=True)
        )
        return EDIT_BIRTHDATE

    elif query.data == "edit_instruments":
        # Переходим к редактированию инструментов - ОДНО сообщение
        if user_role == "teacher":
            keyboard = [
                ["🎹 Фортепиано", "🎤 Вокал"],
                ["🎧 Аранжировка", "🎹 Фортепиано + 🎤 Вокал"],
                ["🎹 Фортепиано + 🎧 Аранжировка", "🎤 Вокал + 🎧 Аранжировка"]
            ]
            prompt = "Выберите вашу специализацию:"
        else:
            keyboard = [
                ["🎹 Фортепиано", "🎤 Вокал"],
                ["🎧 Аранжировка", "🎹 Фортепиано + 🎤 Вокал"],
                ["🎹 Фортепиано + 🎧 Аранжировка", "🎤 Вокал + 🎧 Аранжировка"]
            ]
            prompt = "Выберите инструмент для обучения:"

        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎹 *Изменение инструментов*\n\n{prompt}",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return EDIT_INSTRUMENTS

    elif query.data == "edit_goals":
        # Переходим к редактированию целей - ОДНО сообщение
        if user_role == "teacher":
            prompt = "Расскажите о себе, вашем опыте и подходе к обучению:\n\nИли нажмите кнопку 'Не указывать':"
        else:
            prompt = "Напишите ваши цели обучения:\n(например: 'Хочу научиться играть классические произведения' или 'Подготовка к поступлению в музыкальный колледж')\n\nИли нажмите кнопку 'Не указывать':"

        await context.bot.send_message(
            chat_id=user_id,
            text=f"📝 *Изменение целей*\n\n{prompt}",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([["Не указывать"]], resize_keyboard=True)
        )
        return EDIT_GOALS


async def handle_edit_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения ФИО"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if len(text.split()) < 2:
        await update.message.reply_text(
            "❌ Пожалуйста, введите полное ФИО (Имя и Фамилию, например: Иван Иванов):"
        )
        return EDIT_FIO

    profile = get_user_profile(user_id)
    profile['fio'] = text
    save_user_profile(user_id, profile)

    # Убираем отдельное сообщение и сразу показываем меню с сообщением об успехе
    await send_edit_menu_with_success(context.bot, user_id, "✅ ФИО обновлено!")
    return EDIT_MAIN


async def handle_edit_birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения даты рождения"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    profile = get_user_profile(user_id)

    if text == "Не указывать":
        profile['birthdate'] = "Не указано"
    else:
        if not is_valid_date(text):
            await update.message.reply_text(
                "❌ Неверный формат даты!\n"
                "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например: 15.06.2004)\n"
                "Или нажмите 'Не указывать':",
                reply_markup=ReplyKeyboardMarkup([["Не указывать"]], resize_keyboard=True)
            )
            return EDIT_BIRTHDATE
        profile['birthdate'] = text

    save_user_profile(user_id, profile)

    # Убираем отдельное сообщение
    await send_edit_menu_with_success(context.bot, user_id, "✅ Дата рождения обновлена!")
    return EDIT_MAIN


async def handle_edit_instruments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения инструментов"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Обновленный список валидных вариантов с аранжировкой
    valid_options = [
        "🎹 Фортепиано", "🎤 Вокал", "🎧 Аранжировка",
        "🎹 Фортепиано + 🎤 Вокал",
        "🎹 Фортепиано + 🎧 Аранжировка",
        "🎤 Вокал + 🎧 Аранжировка"
    ]

    if text not in valid_options:
        user_role = get_user_role(user_id)
        if user_role == "teacher":
            keyboard = [
                ["🎹 Фортепиано", "🎤 Вокал"],
                ["🎧 Аранжировка", "🎹 Фортепиано + 🎤 Вокал"],
                ["🎹 Фортепиано + 🎧 Аранжировка", "🎤 Вокал + 🎧 Аранжировка"]
            ]
        else:
            keyboard = [
                ["🎹 Фортепиано", "🎤 Вокал"],
                ["🎧 Аранжировка", "🎹 Фортепиано + 🎤 Вокал"],
                ["🎹 Фортепиано + 🎧 Аранжировка", "🎤 Вокал + 🎧 Аранжировка"]
            ]

        await update.message.reply_text(
            "❌ Пожалуйста, выберите один из предложенных вариантов:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return EDIT_INSTRUMENTS

    # Определяем выбранные инструменты
    if text == "🎹 Фортепиано":
        instruments = ["Фортепиано"]
    elif text == "🎤 Вокал":
        instruments = ["Вокал"]
    elif text == "🎧 Аранжировка":
        instruments = ["Аранжировка"]
    elif text == "🎹 Фортепиано + 🎤 Вокал":
        instruments = ["Фортепиано", "Вокал"]
    elif text == "🎹 Фортепиано + 🎧 Аранжировка":
        instruments = ["Фортепиано", "Аранжировка"]
    elif text == "🎤 Вокал + 🎧 Аранжировка":
        instruments = ["Вокал", "Аранжировка"]
    else:
        instruments = []

    profile = get_user_profile(user_id)
    profile['instruments'] = instruments
    save_user_profile(user_id, profile)

    # Убираем отдельное сообщение и сразу показываем меню с сообщением об успехе
    await send_edit_menu_with_success(context.bot, user_id, "✅ Инструменты обновлены!")
    return EDIT_MAIN


async def handle_edit_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения целей"""
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)
    text = update.message.text.strip()

    profile = get_user_profile(user_id)

    if text == "Не указывать":
        if user_role == "teacher":
            profile['goals'] = "Не указано"
        else:
            profile['goals'] = "Не указаны"
    else:
        profile['goals'] = text

    save_user_profile(user_id, profile)

    success_msg = "✅ Информация о себе обновлена!" if user_role == "teacher" else "✅ Цели обучения обновлены!"
    # Убираем отдельное сообщение
    await send_edit_menu_with_success(context.bot, user_id, success_msg)
    return EDIT_MAIN


async def cancel_edit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена редактирования профиля"""
    user_id = update.effective_user.id

    await update.message.reply_text(
        "❌ Редактирование отменено.",
        reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
    )
    return ConversationHandler.END


# ========== ConversationHandler ДЛЯ СОЗДАНИЯ ПРОФИЛЯ ==========

create_profile_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^👤 Создать профиль$"), start_create_profile),
        MessageHandler(filters.Regex("^👨‍🏫 Заполнить профиль$"), start_create_profile),
    ],
    states={
        CREATE_FIO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_fio)
        ],
        CREATE_BIRTHDATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_birthdate)
        ],
        CREATE_INSTRUMENTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_instruments)
        ],
        CREATE_GOALS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_goals)
        ],
    },
    fallbacks=[
        CommandHandler("start", cancel_create_conversation),
        CommandHandler("cancel", cancel_create_conversation),
        MessageHandler(filters.Regex("^❌ Отмена$"), cancel_create_conversation),
        MessageHandler(filters.Regex("^В главное меню$"), cancel_create_conversation),
    ],
    per_message=False
)

# ========== ConversationHandler ДЛЯ РЕДАКТИРОВАНИЯ ПРОФИЛЯ ==========

edit_profile_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^✏️ Изменить профиль$"), start_edit_profile),
    ],
    states={
        EDIT_MAIN: [
            CallbackQueryHandler(handle_edit_main, pattern="^edit_")
        ],
        EDIT_FIO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_fio)
        ],
        EDIT_BIRTHDATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_birthdate)
        ],
        EDIT_INSTRUMENTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_instruments)
        ],
        EDIT_GOALS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_goals)
        ],
    },
    fallbacks=[
        CommandHandler("start", cancel_edit_conversation),
        CommandHandler("cancel", cancel_edit_conversation),
        MessageHandler(filters.Regex("^❌ Отмена$"), cancel_edit_conversation),
        MessageHandler(filters.Regex("^В главное меню$"), cancel_edit_conversation),
    ],
    per_message=False
)

# Экспортируем оба ConversationHandler
__all__ = ['create_profile_conversation', 'edit_profile_conversation']