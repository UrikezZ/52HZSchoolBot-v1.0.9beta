from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, MessageHandler, filters, ConversationHandler
from config import user_profiles, TEACHER_IDS, get_user_role

# Состояния для обратной связи
FEEDBACK = 1


# feedback.py - исправление
async def start_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса обратной связи"""
    user_id = update.effective_user.id
    user_role = get_user_role(user_id)

    # Проверяем, что это студент
    if user_role == "teacher":
        await update.message.reply_text("❌ Эта функция только для студентов.")
        return ConversationHandler.END

    # ИСПРАВЛЕННАЯ проверка профиля - используем БД
    from database import get_user  # Добавьте импорт
    student_profile = get_user(user_id)  # Используем БД вместо config

    if not student_profile or not student_profile.get('fio'):
        await update.message.reply_text(
            "❌ Сначала заполните профиль в разделе '👤 Мой профиль'",
            reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
        )
        return ConversationHandler.END


async def handle_feedback_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает сообщение с обратной связью"""
    user_id = update.effective_user.id
    feedback_text = update.message.text

    # Проверяем отмену
    if feedback_text == "❌ Отменить отправку":
        await update.message.reply_text(
            "❌ Отправка отменена.",
            reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    # Получаем информацию о студенте ИЗ БАЗЫ
    from database import get_user  # Добавьте импорт
    student_profile = get_user(user_id)  # <-- ИСПРАВЛЕНО

    if not student_profile:
        await update.message.reply_text(
            "❌ Профиль не найден. Заполните профиль.",
            reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    # Формируем сообщение для преподавателя
    teacher_message = (
        f"💌 *НОВОЕ СООБЩЕНИЕ ОТ СТУДЕНТА*\n\n"
        f"*Студент:* {student_profile.get('fio', 'Неизвестно')}\n"
        f"*Инструмент:* {', '.join(student_profile.get('instruments', []))}\n"
        f"*Username:* @{update.message.from_user.username or 'Не указан'}\n\n"
        f"*Пожелания к занятию:*\n{feedback_text}"
    )

    return FEEDBACK


async def handle_feedback_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает сообщение с обратной связью"""
    user_id = update.effective_user.id
    feedback_text = update.message.text

    # Проверяем отмену
    if feedback_text == "❌ Отменить отправку":
        await update.message.reply_text(
            "❌ Отправка отменена.",
            reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    # Получаем информацию о студенте
    student_profile = user_profiles[user_id]

    # Формируем сообщение для преподавателя
    teacher_message = (
        f"💌 *НОВОЕ СООБЩЕНИЕ ОТ СТУДЕНТА*\n\n"
        f"*Студент:* {student_profile['fio']}\n"
        f"*Инструмент:* {', '.join(student_profile['instruments'])}\n"
        f"*Username:* @{update.message.from_user.username or 'Не указан'}\n\n"
        f"*Пожелания к занятию:*\n{feedback_text}"
    )

    try:
        # Отправляем сообщение всем преподавателям
        success_count = 0
        for teacher_id in TEACHER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=teacher_id,
                    text=teacher_message,
                    parse_mode='Markdown'
                )
                success_count += 1
            except Exception as e:
                print(f"Ошибка отправки преподавателю {teacher_id}: {e}")

        if success_count > 0:
            await update.message.reply_text(
                "✅ *Ваше сообщение отправлено преподавателю!*\n\n"
                "Преподаватель свяжется с вами в ближайшее время для обсуждения деталей.",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось отправить сообщение. Попробуйте позже.",
                reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
            )

    except Exception as e:
        await update.message.reply_text(
            "❌ Ошибка при отправке сообщения. Попробуйте позже.",
            reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
        )
        print(f"Ошибка отправки обратной связи: {e}")

    return ConversationHandler.END


async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет процесс обратной связи"""
    await update.message.reply_text(
        "❌ Отправка отменена.",
        reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
    )
    return ConversationHandler.END


# Создаем ConversationHandler для обратной связи
feedback_conversation = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^👨‍🏫 Связаться с преподавателем$"), start_feedback)],
    states={
        FEEDBACK: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback_message)
        ],
    },
    fallbacks=[MessageHandler(filters.Regex("^❌ Отменить отправку$"), cancel_feedback)]
)