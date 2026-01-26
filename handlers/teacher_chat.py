from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import user_profiles, is_teacher
import logging

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
TEACHER_CHOOSE_STUDENT, TEACHER_WRITE_MESSAGE = range(2)


async def start_teacher_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало отправки сообщения студенту"""
    user_id = update.effective_user.id

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен.")
        return ConversationHandler.END

    # Получаем список студентов ИЗ БАЗЫ ДАННЫХ
    from database import get_all_users
    all_users = get_all_users()
    students = {}
    for user in all_users:
        if not is_teacher(user['user_id']) and user.get('fio'):
            students[user['user_id']] = user

    if not students:
        await update.message.reply_text("📭 Пока нет зарегистрированных студентов.")
        return ConversationHandler.END

    # Создаем клавиатуру со студентами
    keyboard = []
    for student_id, profile in students.items():
        # Проверяем есть ли у студента занятия
        from config import confirmed_lessons
        has_lessons = student_id in confirmed_lessons and confirmed_lessons[student_id]

        button_text = f"{profile['fio']}"
        if has_lessons:
            button_text += " 📅"

        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"teacher_chat_{student_id}")])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="teacher_chat_cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💬 *Выберите студента для отправки сообщения:*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

    return TEACHER_CHOOSE_STUDENT


async def choose_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора студента"""
    query = update.callback_query
    await query.answer()

    if query.data == "teacher_chat_cancel":
        await query.edit_message_text("❌ Отправка сообщения отменена.")
        return ConversationHandler.END

    if query.data.startswith("teacher_chat_"):
        student_id = int(query.data.split("_")[2])
        context.user_data['chat_student_id'] = student_id

        # ИСПРАВЛЕНО: Используем БД
        from database import get_user
        student_profile = get_user(student_id)

        if student_profile:
            student_name = student_profile.get('fio', 'Студент')
        else:
            student_name = 'Студент'

        await query.edit_message_text(
            f"✏️ *Напишите сообщение для {student_name}:*\n\n"
            f"Сообщение будет отправлено студенту одним сообщением.\n"
            f"Для отмены отправьте /cancel",
            parse_mode='Markdown'
        )

        return TEACHER_WRITE_MESSAGE


async def send_message_to_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка сообщения студенту"""
    user_id = update.effective_user.id
    message_text = update.message.text.strip()

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен.")
        return ConversationHandler.END

    student_id = context.user_data.get('chat_student_id')
    if not student_id:
        await update.message.reply_text("❌ Ошибка: студент не выбран.")
        return ConversationHandler.END

    # ИСПРАВЛЕНО: Используем БД вместо user_profiles
    from database import get_user
    student_profile = get_user(student_id)
    teacher_profile = get_user(user_id)

    if not student_profile:
        await update.message.reply_text("❌ Профиль студента не найден.")
        return ConversationHandler.END

    student_name = student_profile.get('fio', 'Студент')
    teacher_name = teacher_profile.get('fio', 'Преподаватель') if teacher_profile else 'Преподаватель'

    # Формируем сообщение для студента
    student_message = (
        f"💌 *Сообщение от преподавателя:*\n\n"
        f"*От:* {teacher_name}\n\n"
        f"{message_text}\n\n"
        f"_Чтобы ответить, используйте кнопку '👨‍🏫 Связаться с преподавателем'_"
    )

    # ДОБАВЛЕНО: Формируем подтверждение для преподавателя
    teacher_confirmation = (
        f"✅ *Сообщение отправлено студенту:*\n\n"
        f"*Студент:* {student_name}\n"
        f"*Сообщение:* {message_text[:100]}{'...' if len(message_text) > 100 else ''}"
    )

    try:
        # Отправляем студенту
        await context.bot.send_message(
            chat_id=student_id,
            text=student_message,
            parse_mode='Markdown'
        )

        # Подтверждаем преподавателю
        await update.message.reply_text(
            teacher_confirmation,  # Теперь эта переменная существует
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([["📊 Панель управления", "В главное меню"]], resize_keyboard=True)
        )

        logger.info(f"Teacher {user_id} sent message to student {student_id}")

    except Exception as e:
        await update.message.reply_text(
            f"❌ Не удалось отправить сообщение студенту.\n"
            f"Ошибка: {e}",
            reply_markup=ReplyKeyboardMarkup([["📊 Панель управления", "В главное меню"]], resize_keyboard=True)
        )
        logger.error(f"Failed to send message from teacher {user_id} to student {student_id}: {e}")

    # Очищаем данные
    if 'chat_student_id' in context.user_data:
        del context.user_data['chat_student_id']

    return ConversationHandler.END


async def cancel_teacher_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена отправки сообщения"""
    await update.message.reply_text(
        "❌ Отправка сообщения отменена.",
        reply_markup=ReplyKeyboardMarkup([["📊 Панель управления", "В главное меню"]], resize_keyboard=True)
    )

    if 'chat_student_id' in context.user_data:
        del context.user_data['chat_student_id']

    return ConversationHandler.END


# Создаем ConversationHandler
teacher_chat_conversation = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^💬 Написать студенту$"), start_teacher_chat)],
    states={
        TEACHER_CHOOSE_STUDENT: [
            CallbackQueryHandler(choose_student, pattern="^teacher_chat_")
        ],
        TEACHER_WRITE_MESSAGE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, send_message_to_student)
        ],
    },
    fallbacks=[
        MessageHandler(filters.Regex("^/cancel$"), cancel_teacher_chat),
        MessageHandler(filters.Regex("^В главное меню$"), cancel_teacher_chat)
    ],
    per_message=False
)