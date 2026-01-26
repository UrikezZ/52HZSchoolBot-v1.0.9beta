# student_management.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import is_teacher, get_all_students
from database import get_user, delete_user, get_confirmed_lessons, get_student_balance
import logging

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
STUDENT_MGMT_SELECT, STUDENT_MGMT_CONFIRM = range(2)


async def start_student_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало управления студентами (удаление)"""
    user_id = update.effective_user.id

    if not is_teacher(user_id):
        await update.message.reply_text("❌ Доступ запрещен. Эта функция только для преподавателей.")
        return ConversationHandler.END

    # Получаем список студентов
    students = get_all_students()

    if not students:
        await update.message.reply_text("📭 Пока нет зарегистрированных студентов.")
        return ConversationHandler.END

    # Создаем клавиатуру со студентами
    keyboard = []
    for student in students:
        # Формируем информацию о студенте
        has_lessons = student['has_lessons']
        lessons_count = student['lessons_count']

        button_text = f"{student['fio']}"
        if has_lessons:
            button_text += f" 📅({lessons_count})"

        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"student_mgmt_select_{student['user_id']}"
        )])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="student_mgmt_cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎓 *Управление студентами*\n\n"
        "Выберите студента для удаления:\n"
        "📅 - у студента есть запланированные занятия",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

    return STUDENT_MGMT_SELECT


async def select_student_for_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора студента"""
    query = update.callback_query
    await query.answer()

    if query.data == "student_mgmt_cancel":
        await query.edit_message_text("❌ Управление студентами отменено.")
        return ConversationHandler.END

    if query.data.startswith("student_mgmt_select_"):
        student_id = int(query.data.split("_")[3])
        context.user_data['student_mgmt_student_id'] = student_id

        # Получаем информацию о студенте
        student = get_user(student_id)
        if not student:
            await query.edit_message_text("❌ Студент не найден.")
            return ConversationHandler.END

        balance = get_student_balance(student_id)
        lessons = get_confirmed_lessons(student_id)
        lessons_count = len(lessons)

        # Формируем информацию о студенте
        student_info = (
            f"⚠️ *Вы уверены, что хотите удалить этого студента?*\n\n"
            f"*Студент:* {student['fio']}\n"
            f"*Инструменты:* {', '.join(student.get('instruments', []))}\n"
            f"*Занятий:* {lessons_count} шт.\n"
            f"*Уроков осталось:* {balance['lessons_left']} шт.\n"
            f"*Финансовый баланс:* {balance['balance']} руб.\n\n"
            f"*Будут удалены:*\n"
            f"• Все данные профиля\n"
            f"• Все запланированные занятия ({lessons_count} шт.)\n"
            f"• История баланса и оплат\n"
            f"• Все заявки на расписание\n\n"
            f"*Действие необратимо!*"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data="student_mgmt_confirm"),
                InlineKeyboardButton("❌ Нет, отмена", callback_data="student_mgmt_cancel")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            student_info,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        return STUDENT_MGMT_CONFIRM


async def confirm_student_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления студента"""
    query = update.callback_query
    await query.answer()

    student_id = context.user_data.get('student_mgmt_student_id')
    if not student_id:
        await query.edit_message_text("❌ Ошибка: студент не выбран.")
        return ConversationHandler.END

    student = get_user(student_id)
    if not student:
        await query.edit_message_text("❌ Студент не найден.")
        return ConversationHandler.END

    if query.data == "student_mgmt_confirm":
        try:
            # Сохраняем информацию для сообщения
            student_name = student['fio']
            lessons_count = len(get_confirmed_lessons(student_id))

            # Удаляем студента из базы
            deleted_count = delete_user(student_id)

            # Формируем сообщение об успехе
            success_message = (
                f"✅ *Студент успешно удален!*\n\n"
                f"*Удаленный студент:* {student_name}\n"
                f"*Удалено записей:* {deleted_count} шт.\n"
                f"*Удалено занятий:* {lessons_count} шт.\n\n"
                f"Все данные студента были полностью удалены из системы."
            )

            await query.edit_message_text(
                success_message,
                parse_mode='Markdown'
            )

            logger.info(f"Teacher deleted student {student_id} ({student_name})")

        except Exception as e:
            await query.edit_message_text(
                f"❌ Ошибка при удалении студента: {e}",
                parse_mode='Markdown'
            )
            logger.error(f"Failed to delete student {student_id}: {e}")

        return ConversationHandler.END

    elif query.data == "student_mgmt_cancel":
        await query.edit_message_text(
            "❌ Удаление студента отменено.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END


async def cancel_student_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена управления студентами"""
    await update.message.reply_text(
        "❌ Управление студентами отменено.",
        reply_markup=ReplyKeyboardMarkup([["📊 Панель управления", "В главное меню"]], resize_keyboard=True)
    )
    return ConversationHandler.END


# Создаем ConversationHandler для управления студентами
student_management_conversation = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🗑 Удалить студента$"), start_student_management)],
    states={
        STUDENT_MGMT_SELECT: [
            CallbackQueryHandler(select_student_for_management, pattern="^student_mgmt_")
        ],
        STUDENT_MGMT_CONFIRM: [
            CallbackQueryHandler(confirm_student_deletion, pattern="^student_mgmt_")
        ],
    },
    fallbacks=[
        MessageHandler(filters.Regex("^❌ Отмена$"), cancel_student_management),
        MessageHandler(filters.Regex("^В главное меню$"), cancel_student_management),
    ],
    per_message=False
)