# schedule.py
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from config import is_teacher, get_student_balance, get_balance_display, get_total_lessons_count, get_user
from config import get_next_week_dates, get_day_slots, get_available_slots_for_user
from database import get_confirmed_lessons, get_schedule_request, save_schedule_request, get_user as db_get_user, save_confirmed_lesson, delete_schedule_request
from config import TEACHER_IDS, add_confirmed_lesson, remove_confirmed_lesson, save_schedule_request_dict

def get_previous_day_date(lesson_date_str: str) -> str:
    """Возвращает дату предыдущего дня от даты занятия в формате DD.MM"""
    try:
        # Парсим дату занятия (берем только дату без времени)
        if ' ' in lesson_date_str:
            date_part = lesson_date_str.split()[0]  # Берем только дату если есть время
        else:
            date_part = lesson_date_str

        lesson_datetime = datetime.strptime(date_part, "%d.%m.%Y")
        # Вычисляем предыдущий день
        previous_day = lesson_datetime - timedelta(days=1)
        # Форматируем как ДД.ММ
        return previous_day.strftime("%d.%m")
    except:
        return ""

# Вспомогательная функция для безопасного редактирования
async def safe_edit_message(query, text, parse_mode=None, reply_markup=None):
    """Безопасное редактирование сообщения с обработкой ошибки 'Message is not modified'"""
    try:
        await query.edit_message_text(
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        return True
    except Exception as e:
        if "Message is not modified" in str(e):
            print(f"DEBUG: Message already up to date")
            return True
        elif "Inline keyboard expected" in str(e):
            # Если нужна инлайн-клавиатура, но мы ее не передали, отправляем новое сообщение
            print(f"DEBUG: Sending new message instead of editing")
            try:
                await query.message.reply_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return True
            except Exception as e2:
                print(f"ERROR sending new message: {e2}")
                return False
        else:
            print(f"ERROR editing message: {e}")
            return False


# Обработчики для расписания
schedule_handlers = []


async def choose_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало выбора расписания - показываем дни недели"""
    user_id = update.effective_user.id

    # Проверяем, заполнен ли профиль
    profile = get_user(user_id)
    if not profile or not profile.get('fio'):
        await update.message.reply_text(
            "❌ Сначала заполните профиль в разделе '👤 Мой профиль'",
            reply_markup=ReplyKeyboardMarkup([["👤 Мой профиль", "В главное меню"]], resize_keyboard=True)
        )
        return

    # Инициализируем выбор студента если нужно
    request = get_schedule_request(user_id)
    if not request:
        request_data = {
            'selected_slots': [],
            'user_info': profile
        }
        save_schedule_request_dict(user_id, request_data)

    # Показываем выбор дня
    await show_day_selection(update, context, user_id, day_index=0)


async def show_day_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, day_index: int):
    """Показывает выбор дня недели"""
    week_dates = get_next_week_dates()

    keyboard = []

    # Заголовок с датами недели
    # Получаем первую (среду) и последнюю (воскресенье) даты
    first_day = week_dates[0]['date'] if week_dates else ""
    last_day = week_dates[4]['date'] if len(week_dates) > 4 else ""
    week_range = f"{first_day} - {last_day}"

    # Собираем уже занятые слоты
    occupied_slots = set()
    all_lessons = get_confirmed_lessons()
    for lesson in all_lessons:
        occupied_slots.add(lesson['slot_id'])

    # Кнопки дней недели (Ср-Вс)
    days_row = []
    for i in range(5):  # Ср-Вс
        day_info = week_dates[i]
        # Проверяем, есть ли выбранные слоты в этом дне
        request = get_schedule_request(user_id)
        selected_slots = request.get('selected_slots', []) if request else []
        has_selected_slots = any(slot.startswith(f'day{i}_') for slot in selected_slots)
        day_button = f"✅ {day_info['day_name']}" if has_selected_slots else day_info['day_name']
        days_row.append(InlineKeyboardButton(day_button, callback_data=f"select_day_{i}"))

    keyboard.append(days_row)

    # Показываем слоты времени для выбранного дня
    day_info = week_dates[day_index]
    keyboard.append([InlineKeyboardButton(f"📅 {day_info['day_name']} {day_info['date']}", callback_data="ignore")])

    # Показываем слоты времени для выбранного дня (13:00-21:00)
    time_slots, _ = get_day_slots(day_index)
    time_row = []
    slot_items = list(time_slots.items())

    # Группируем по 3 времени в строку
    for i in range(0, len(slot_items), 3):
        time_row = []
        for slot_id, time in slot_items[i:i + 3]:
            # Проверяем, занят ли слот
            is_occupied = slot_id in occupied_slots
            request = get_schedule_request(user_id)
            selected_slots = request.get('selected_slots', []) if request else []
            is_selected = slot_id in selected_slots

            if is_occupied:
                # Занят - нельзя выбрать
                slot_button = f"⛔ {time}"
                callback_data = "ignore"
            elif is_selected:
                # Выбран студентом
                slot_button = f"✅ {time}"
                callback_data = f"select_time_{slot_id}"
            else:
                # Свободный
                slot_button = time
                callback_data = f"select_time_{slot_id}"

            time_row.append(InlineKeyboardButton(slot_button, callback_data=callback_data))

        if time_row:
            keyboard.append(time_row)

    # Кнопки навигации и завершения
    nav_row = []
    if day_index > 0:
        nav_row.append(InlineKeyboardButton("◀️ Назад", callback_data=f"nav_day_{day_index - 1}"))

    nav_row.append(InlineKeyboardButton("📋 Выбранные", callback_data="show_selected"))

    if day_index < 4:  # Всего 5 дней (0-4)
        nav_row.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"nav_day_{day_index + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data="finish_schedule")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Формируем текст выбранных слотов
    request = get_schedule_request(user_id)
    selected_slots = request.get('selected_slots', []) if request else []
    if selected_slots:
        all_slots = get_available_slots_for_user(user_id)
        selected_text = "\n".join([f"• {all_slots[slot_id]}" for slot_id in selected_slots])
    else:
        selected_text = "Пока нет"

    message_text = (
        f"📅 *Выберите удобные время на неделю {week_range} (Среда-Воскресенье):*\n\n"
        f"• Дни: Ср, Чт, Пт, Сб, Вс\n"
        f"• Время: 13:00 - 21:00\n"
        f"• Нажимайте на дни чтобы выбрать время\n"
        f"• ⛔ - время уже занято\n"
        f"• ✅ - ваши выбранные время\n"
        f"• Можно выбрать несколько слотов в разные дни\n\n"
        f"*Выбранные слоты:*\n{selected_text}"
    )

    if hasattr(update, 'callback_query') and update.callback_query:
        await safe_edit_message(update.callback_query, message_text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, parse_mode='Markdown', reply_markup=reply_markup)


async def handle_schedule_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки расписания"""
    query = update.callback_query
    user_id = query.from_user.id
    callback_data = query.data

    await query.answer()

    request = get_schedule_request(user_id)
    if not request:
        await safe_edit_message(query, "❌ Сессия выбора расписания устарела. Начните заново.")
        return

    if callback_data == "finish_schedule":
        # Завершаем выбор и отправляем преподавателю
        await finish_schedule_selection(update, context, user_id)
        return

    elif callback_data == "show_selected":
        # Показываем только выбранные слоты
        await show_selected_slots(update, context, user_id)
        return

    elif callback_data.startswith("nav_day_"):
        # Навигация по дням
        day_index = int(callback_data.split("_")[2])
        await show_day_selection(update, context, user_id, day_index)
        return

    elif callback_data.startswith("select_day_"):
        # Выбор дня для просмотра времени
        day_index = int(callback_data.split("_")[2])
        await show_day_selection(update, context, user_id, day_index)
        return

    elif callback_data.startswith("select_time_"):
        # Выбор/отмена времени
        slot_id = callback_data.replace("select_time_", "")

        # ПРОВЕРЯЕМ, НЕ ЗАНЯТ ЛИ УЖЕ ЭТОТ СЛОТ
        slot_occupied = False
        all_lessons = get_confirmed_lessons()
        for lesson in all_lessons:
            if lesson['slot_id'] == slot_id:
                slot_occupied = True
                break

        if slot_occupied:
            await query.answer("❌ Это время уже занято!", show_alert=True)
            return

        request = get_schedule_request(user_id)
        selected_slots = request.get('selected_slots', [])

        if slot_id in selected_slots:
            selected_slots.remove(slot_id)
        else:
            selected_slots.append(slot_id)

        # Обновляем заявку
        request['selected_slots'] = selected_slots
        save_schedule_request(request)

        # Определяем день из slot_id (day0, day1, etc.)
        day_index = int(slot_id[3])  # "day0_14" -> 0
        await show_day_selection(update, context, user_id, day_index)


async def show_selected_slots(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Показывает только выбранные слоты"""
    request = get_schedule_request(user_id)
    selected_slots = request.get('selected_slots', []) if request else []

    if not selected_slots:
        await update.callback_query.answer("Вы еще не выбрали ни одного слота", show_alert=True)
        return

    all_slots = get_available_slots_for_user(user_id)
    selected_text = "\n".join([f"• {all_slots[slot_id]}" for slot_id in selected_slots])

    keyboard = [
        [InlineKeyboardButton("◀️ Вернуться к выбору", callback_data="nav_day_0")],
        [InlineKeyboardButton("✅ Завершить выбор", callback_data="finish_schedule")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await safe_edit_message(
        update.callback_query,
        f"📋 *Ваши выбранные слоты:*\n\n{selected_text}\n\n"
        f"Всего выбрано: {len(selected_slots)} слотов",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def finish_schedule_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Завершает выбор расписания и отправляет преподавателю"""
    from database import get_user  # Добавляем импорт

    request = get_schedule_request(user_id)
    if not request:
        await safe_edit_message(update.callback_query, "❌ Ошибка: данные не найдены")
        return

    selected_slots = request.get('selected_slots', [])
    user_info = request.get('user_info', {})

    if not selected_slots:
        await safe_edit_message(
            update.callback_query,
            "❌ Вы не выбрали ни одного времени.\n"
            "Нажмите '📅 Выбрать расписание' чтобы попробовать снова."
        )
        return

    # Получаем АКТУАЛЬНЫЕ данные студента из БАЗЫ ДАННЫХ
    db_user = get_user(user_id)
    if db_user:
        # Используем данные из БД
        student_name = db_user.get('fio', 'Неизвестно')
        student_instruments = ', '.join(db_user.get('instruments', []))
        student_goals = db_user.get('goals', 'Не указаны')
    else:
        # Fallback на старые данные
        student_name = user_info.get('fio', 'Неизвестно')
        student_instruments = ', '.join(user_info.get('instruments', []))
        student_goals = user_info.get('goals', 'Не указаны')

    # Формируем сообщение для преподавателя
    all_slots = get_available_slots_for_user(user_id)
    slots_text = "\n".join([f"• {all_slots[slot_id]}" for slot_id in selected_slots])

    # Получаем даты недели для заголовка
    week_dates = get_next_week_dates()
    week_range = f"{week_dates[0]['date']} - {week_dates[4]['date']}"

    teacher_message = (
        f"🎹 НОВАЯ ЗАЯВКА НА РАСПИСАНИЕ\n"
        f"Неделя: {week_range}\n\n"
        f"👤Студент: {student_name}\n"
        f"🎸Инструмент: {student_instruments}\n"
        f"Цели: {student_goals}\n"
        f"Username: @{update.callback_query.from_user.username or 'Не указан'}\n"
        f"User ID: {user_id}\n\n"
        f"Выбранные слоты:\n{slots_text}\n\n"
        f"Выберите подходящие слоты для подтверждения (можно выбрать несколько):"
    )

    # Создаем клавиатуру для преподавателя с возможностью выбора нескольких
    teacher_keyboard = []
    for slot_id in selected_slots:
        slot_name = all_slots[slot_id]
        teacher_keyboard.append([
            InlineKeyboardButton(f"◻️ {slot_name}", callback_data=f"confirm_{user_id}_{slot_id}")
        ])

    # Кнопка для подтверждения всех выбранных слотов
    teacher_keyboard.append([
        InlineKeyboardButton("✅ Подтвердить выбранные", callback_data=f"confirm_multiple_{user_id}")
    ])

    teacher_keyboard.append([
        InlineKeyboardButton("❌ Отклонить все", callback_data=f"reject_all_{user_id}")
    ])

    reply_markup = InlineKeyboardMarkup(teacher_keyboard)

    try:
        # Отправляем сообщение всем преподавателям
        for teacher_id in TEACHER_IDS:
            await context.bot.send_message(
                chat_id=teacher_id,
                text=teacher_message,
                parse_mode=None,
                reply_markup=reply_markup
            )

        # Сообщаем студенту
        await safe_edit_message(
            update.callback_query,
            f"✅ *Заявка отправлена преподавателю!*\n"
            f"*Неделя:* {week_range}\n\n"
            f"Вы выбрали {len(selected_slots)} слотов. "
            f"Ожидайте подтверждения в течение дня.\n\n"
            "Преподаватель свяжется с вами для окончательного подтверждения времени.",
            parse_mode='Markdown'
        )

    except Exception as e:
        await safe_edit_message(
            update.callback_query,
            "❌ Ошибка при отправке заявки. Попробуйте позже."
        )
        print(f"Ошибка отправки преподавателю: {e}")


async def handle_teacher_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения слотов преподавателем с возможностью выбора нескольких"""
    query = update.callback_query
    teacher_id = query.from_user.id
    callback_data = query.data

    await query.answer()

    # Проверяем, что это преподаватель
    if not is_teacher(teacher_id):
        await safe_edit_message(query, "❌ Доступ запрещен")
        return

    if callback_data.startswith("confirm_"):
        if "multiple" in callback_data:
            # Подтверждение всех выбранных слотов
            student_id = int(callback_data.split("_")[2])
            await confirm_all_selected_slots(update, context, student_id, teacher_id)
        else:
            # Подтверждение/отмена конкретного слота
            _, student_id, slot_id = callback_data.split("_", 2)
            student_id = int(student_id)

            # Получаем текущее сообщение
            original_text = query.message.text

            # Создаем новую клавиатуру
            new_keyboard = []
            has_changes = False

            for row in query.message.reply_markup.inline_keyboard:
                new_row = []
                for button in row:
                    # Ищем кнопку с этим слотом
                    if button.callback_data == f"confirm_{student_id}_{slot_id}":
                        # Определяем по тексту, выбрана ли уже кнопка
                        is_selected = "✅" in button.text

                        if not is_selected:
                            # Выбираем слот
                            slot_name = button.text.replace("◻️ ", "")
                            new_button = InlineKeyboardButton(
                                f"✅ {slot_name}",
                                callback_data=f"confirm_{student_id}_{slot_id}"
                            )
                        else:
                            # Отменяем выбор
                            slot_name = button.text.replace("✅ ", "")
                            new_button = InlineKeyboardButton(
                                f"◻️ {slot_name}",
                                callback_data=f"confirm_{student_id}_{slot_id}"
                            )

                        new_row.append(new_button)
                        has_changes = True
                    else:
                        # Оставляем остальные кнопки как есть
                        new_row.append(button)
                new_keyboard.append(new_row)

            if has_changes:
                await safe_edit_message(
                    query,
                    text=original_text,
                    parse_mode=None,
                    reply_markup=InlineKeyboardMarkup(new_keyboard)
                )
            else:
                await query.answer("Кнопка не найдена", show_alert=True)

    elif callback_data.startswith("reject_all_"):
        # Отклонение всех слотов
        student_id = int(callback_data.split("_")[2])
        await reject_student_request(update, context, student_id, teacher_id)


async def confirm_all_selected_slots(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                     student_id: int, teacher_id: int):
    """Подтверждает все ВЫБРАННЫЕ (с галочкой) слоты в одном сообщении"""
    from config import get_balance_display, use_lesson, get_student_balance

    query = update.callback_query
    original_text = query.message.text

    # Находим все выбранные слоты (с ✅ в тексте)
    selected_slots = []
    slot_names = []  # Сохраняем названия слотов для уведомления

    for row in query.message.reply_markup.inline_keyboard:
        for button in row:
            if ("✅" in button.text and
                    button.callback_data and
                    button.callback_data.startswith("confirm_") and
                    "multiple" not in button.callback_data):

                try:
                    parts = button.callback_data.split("_")
                    if len(parts) >= 3:
                        slot_student_id = int(parts[1])
                        slot_id = "_".join(parts[2:])

                        if slot_student_id == student_id:
                            selected_slots.append(slot_id)
                            # Извлекаем название слота из текста кнопки
                            slot_name = button.text.replace("✅ ", "").replace("◻️ ", "")
                            slot_names.append(slot_name)
                except (ValueError, IndexError) as e:
                    print(f"DEBUG: Error parsing callback_data {button.callback_data}: {e}")
                    continue

    if not selected_slots:
        await query.answer("Вы не выбрали ни одного слота! Нажмите на слоты чтобы отметить их галочкой.",
                           show_alert=True)
        return

    print(f"DEBUG: Found {len(selected_slots)} selected slots for student {student_id}: {selected_slots}")

    # Получаем баланс до списаний
    balance_before = get_student_balance(student_id)
    lessons_before = balance_before['lessons_left']
    money_before = balance_before['balance']
    lesson_price = balance_before.get('lesson_price', 2000)

    # Подтверждаем ВСЕ выбранные слоты сначала
    confirmed_slots = []
    payment_info = []

    for slot_id, slot_name in zip(selected_slots, slot_names):
        try:
            success = await confirm_single_slot_in_batch(context, student_id, slot_id, teacher_id, slot_name)
            if success:
                confirmed_slots.append({
                    'slot_id': slot_id,
                    'slot_name': slot_name
                })
                print(f"DEBUG: Successfully confirmed slot {slot_id}")
            else:
                print(f"DEBUG: Failed to confirm slot {slot_id}")
        except Exception as e:
            print(f"DEBUG: Error confirming slot {slot_id}: {e}")

    if not confirmed_slots:
        await query.answer("Не удалось подтвердить ни одного занятия", show_alert=True)
        print(f"DEBUG: No slots were confirmed for student {student_id}")
        return

    # Получаем баланс после списаний
    balance_after = get_student_balance(student_id)
    lessons_after = balance_after['lessons_left']
    money_after = balance_after['balance']

    # Вычисляем изменения
    lessons_spent = max(0, lessons_before - lessons_after)
    money_spent = max(0, money_before - money_after)
    debt_added = max(0, -(money_after - money_before))

    # Формируем информацию о списаниях
    if lessons_spent > 0:
        payment_info.append(f"Списано уроков: {lessons_spent} шт.")
    if money_spent > 0:
        payment_info.append(f"Списано с депозита: {money_spent} руб.")
    if debt_added > 0:
        payment_info.append(f"Добавлен долг: {debt_added} руб.")

    payment_text = "\n".join(payment_info) if payment_info else "Нет изменений в балансе"

    # Формируем ОДНО сообщение для студента со ВСЕМИ занятиями
    notification = f"✅ *Запись на уроки подтверждена!*\n\n*Подтвержденные занятия:*\n"

    # Для каждого занятия вычисляем дату отмены
    for i, slot in enumerate(confirmed_slots, 1):
        slot_name = slot['slot_name']

        # Извлекаем дату из названия
        parts = slot_name.split()
        lesson_date = None
        for part in parts:
            if '.' in part and len(part.split('.')) == 3:
                lesson_date = part
                break

        # Добавляем дату в скобках если нашли
        if lesson_date:
            try:
                # Вычисляем предыдущий день
                lesson_datetime = datetime.strptime(lesson_date, "%d.%m.%Y")
                previous_day = lesson_datetime - timedelta(days=1)
                cancellation_date = previous_day.strftime("%d.%m")
                notification += f"{i}. {slot_name} (отмена до 10:00 {cancellation_date})\n"
            except:
                notification += f"{i}. {slot_name}\n"
        else:
            notification += f"{i}. {slot_name}\n"

    notification += (
        f"\n*Всего подтверждено: {len(confirmed_slots)} занятий*\n\n"
        f"*Адрес:*\n"
        f"4-й Сыромятнический переулок, 3/5с3\n"
        f"[Яндекс Карты](https://yandex.ru/maps/-/CLdYmDK3)\n\n"
        f"ℹ️ *Бесплатная отмена урока доступна не позже 10:00 предыдущего дня*\n\n"
    )

    if payment_text != "Нет изменений в балансе":
        notification += f"*Изменения баланса:*\n{payment_text}\n\n"

    notification += (
        f"Уроков осталось: {lessons_after} шт.\n"
        f"Баланс: {get_balance_display(student_id)}\n"
    )

    # Добавляем примечание если есть
    if balance_after.get('notes'):
        notification += f"\n*Примечание:*\n{balance_after['notes']}\n"

    print(f"DEBUG: Sending single notification to student {student_id}")

    # Отправляем студенту ОДНО сообщение
    await context.bot.send_message(
        chat_id=student_id,
        text=notification,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

    # Получаем данные студента из БД
    from database import get_user
    db_user = get_user(student_id)
    student_name = db_user.get('fio', 'Неизвестно') if db_user else 'Неизвестно'
    student_instruments = ', '.join(db_user.get('instruments', [])) if db_user else 'Не указан'

    new_text = (
        f"{original_text}\n\n"
        f"✅ Подтверждено {len(confirmed_slots)} занятий.\n"
        f"👤Студент: {student_name}\n"
        f"🎸Инструмент: {student_instruments}\n"
        f"Уведомлен одним сообщением.\n\n"
        f"*Изменения баланса:*\n"
        f"{payment_text}\n\n"
        f"*Текущий баланс студента:*\n"
        f"Уроков осталось: {lessons_after} шт.\n"
        f"Финансовый баланс: {get_balance_display(student_id)}"
    )

    await safe_edit_message(
        query,
        text=new_text,
        parse_mode='Markdown'
    )
    print(f"DEBUG: Successfully confirmed {len(confirmed_slots)} slots for student {student_id}")


# Новая вспомогательная функция для подтверждения слотов в пакете
async def confirm_single_slot_in_batch(context: ContextTypes.DEFAULT_TYPE,
                                       student_id: int, slot_id: str,
                                       teacher_id: int, slot_name: str):
    """Подтверждает один слот студента (для использования в пакетном режиме)"""
    from config import get_balance_display, use_lesson, get_student_balance
    from datetime import datetime

    print(f"DEBUG: Starting confirm_single_slot_in_batch for student {student_id}, slot {slot_id}")

    # 1. ПРОВЕРЯЕМ, НЕ ПОДТВЕРЖДЕН ЛИ УЖЕ ЭТОТ СЛОТ
    all_lessons = get_confirmed_lessons()
    for lesson in all_lessons:
        if lesson['slot_id'] == slot_id:
            print(f"DEBUG: Slot {slot_id} already confirmed for student {lesson['user_id']}")
            return False

    try:
        # СПИСЫВАЕМ УРОК ИЛИ ДЕНЬГИ С БАЛАНСА
        balance_before = get_student_balance(student_id)
        print(
            f"DEBUG: Balance before lesson: lessons_left={balance_before['lessons_left']}, balance={balance_before['balance']}")

        # Используем урок (списываем с баланса или добавляем долг)
        use_lesson(student_id)

        balance_after = get_student_balance(student_id)
        print(
            f"DEBUG: Balance after lesson: lessons_left={balance_after['lessons_left']}, balance={balance_after['balance']}")

        # Определяем тип списания
        lesson_price = balance_before.get('lesson_price', 2000)
        if balance_before['lessons_left'] > 0:
            payment_type = "списан 1 урок из предоплаты"
        else:
            if balance_before['balance'] > 0:
                payment_type = f"списано {lesson_price} руб. с депозита"
            elif balance_before['balance'] == 0:
                payment_type = f"добавлен долг {lesson_price} руб."
            else:
                payment_type = f"долг увеличен на {lesson_price} руб."

        # Сохраняем занятие
        lesson_data = {
            'user_id': student_id,
            'slot_id': slot_id,
            'slot_name': slot_name,
            'confirmed_by': teacher_id,
            'date_added': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'payment_type': payment_type
        }
        add_confirmed_lesson(lesson_data)

        print(f"DEBUG: Added to confirmed_lessons for student {student_id}")

        # УДАЛЯЕМ ЭТОТ СЛОТ ИЗ ВСЕХ ЗАПРОСОВ ВСЕХ СТУДЕНТОВ
        from config import remove_slot_from_all_requests
        remove_slot_from_all_requests(slot_id)
        print(f"DEBUG: Removed slot {slot_id} from all requests")

        return True

    except Exception as e:
        print(f"ERROR: Failed to confirm slot {slot_id} for student {student_id}: {e}")
        return False


async def confirm_single_slot(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              student_id: int, slot_id: str, teacher_id: int):
    """Подтверждает один слот студента (используется при одиночном подтверждении)"""
    # Эта функция остается для одиночных подтверждений через другие кнопки
    # Она все еще отправляет отдельное сообщение студенту

    from config import get_balance_display, use_lesson, get_student_balance
    from datetime import datetime

    print(f"DEBUG: Starting confirm_single_slot for student {student_id}, slot {slot_id}")

    # 1. ПРОВЕРЯЕМ, НЕ ПОДТВЕРЖДЕН ЛИ УЖЕ ЭТОТ СЛОТ
    all_lessons = get_confirmed_lessons()
    for lesson in all_lessons:
        if lesson['slot_id'] == slot_id:
            print(f"DEBUG: Slot {slot_id} already confirmed for student {lesson['user_id']}")
            await update.callback_query.answer(f"Это время уже занято!", show_alert=True)
            return False

    # Получаем актуальное название слота
    all_slots = get_available_slots_for_user(student_id)
    slot_name = all_slots.get(slot_id, f"Слот {slot_id}")

    # Проверяем, не подтвержден ли уже этот слот у этого студента
    student_lessons = get_confirmed_lessons(student_id)
    existing_slots = [lesson['slot_id'] for lesson in student_lessons]
    if slot_id in existing_slots:
        print(f"DEBUG: Slot {slot_id} already confirmed for this student {student_id}")
        await update.callback_query.answer(f"У вас уже есть занятие на это время!", show_alert=True)
        return False

    try:
        # СПИСЫВАЕМ УРОК ИЛИ ДЕНЬГИ С БАЛАНСА
        balance_before = get_student_balance(student_id)
        print(
            f"DEBUG: Balance before lesson: lessons_left={balance_before['lessons_left']}, balance={balance_before['balance']}")

        # Используем урок (списываем с баланса или добавляем долг)
        use_lesson(student_id)

        balance_after = get_student_balance(student_id)
        print(
            f"DEBUG: Balance after lesson: lessons_left={balance_after['lessons_left']}, balance={balance_after['balance']}")

        # Определяем тип списания
        lesson_price = balance_before.get('lesson_price', 2000)
        if balance_before['lessons_left'] > 0:
            payment_type = "списан 1 урок из предоплаты"
        else:
            if balance_before['balance'] > 0:
                payment_type = f"списано {lesson_price} руб. с депозита"
            elif balance_before['balance'] == 0:
                payment_type = f"добавлен долг {lesson_price} руб."
            else:
                payment_type = f"долг увеличен на {lesson_price} руб."

        # Сохраняем занятие
        lesson_data = {
            'user_id': student_id,
            'slot_id': slot_id,
            'slot_name': slot_name,
            'confirmed_by': teacher_id,
            'date_added': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'payment_type': payment_type
        }
        add_confirmed_lesson(lesson_data)

        print(f"DEBUG: Added to confirmed_lessons for student {student_id}")

        # УДАЛЯЕМ ЭТОТ СЛОТ ИЗ ВСЕХ ЗАПРОСОВ ВСЕХ СТУДЕНТОВ
        from config import remove_slot_from_all_requests
        remove_slot_from_all_requests(slot_id)
        print(f"DEBUG: Removed slot {slot_id} from all requests")

        # Получаем обновленный баланс
        balance = get_student_balance(student_id)
        print(
            f"DEBUG: Got final balance for student {student_id}: lessons_left={balance['lessons_left']}, balance={balance['balance']}")

        # Извлекаем дату и время из названия слота
        lesson_date = None
        lesson_time = None
        parts = slot_name.split()
        for part in parts:
            if '.' in part and len(part.split('.')) == 3:
                lesson_date = part
            elif ':' in part:
                lesson_time = part

        # Рассчитываем дату для отмены
        cancellation_date = "предыдущего дня"
        if lesson_date and lesson_time:
            # Получаем только день и месяц (29.01)
            try:
                lesson_datetime = datetime.strptime(f"{lesson_date} {lesson_time}", "%d.%m.%Y %H:%M")
                previous_day = lesson_datetime - timedelta(days=1)
                cancellation_date = previous_day.strftime("%d.%m")  # Формат: 29.01
            except:
                pass

        # В формировании notification добавьте:
        notification = (
            f"✅ *Запись на урок подтверждена!*\n\n"
            f"*Дата и время:*\n"
            f"{slot_name}\n\n"
            f"*Адрес:*\n"
            f"4-й Сыромятнический переулок, 3/5с3\n"
            f"[Яндекс Карты](https://yandex.ru/maps/-/CLdYmDK3)\n\n"
            f"*Оплата:* {payment_type}\n\n"
            f"ℹ️ *Бесплатная отмена урока доступна НЕ позже 10:00 {cancellation_date}*\n\n"
            f"Уроков осталось: {balance['lessons_left']} шт.\n"
            f"Баланс: {get_balance_display(student_id)}\n"
        )

        # Добавляем примечание если есть
        if balance.get('notes'):
            notification += f"\n*Примечание:*\n{balance['notes']}\n"

        print(f"DEBUG: Sending notification to student {student_id}")

        # Отправляем студенту
        await context.bot.send_message(
            chat_id=student_id,
            text=notification,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

        print(f"DEBUG: Successfully confirmed slot {slot_id} for student {student_id}")
        return True

    except Exception as e:
        print(f"ERROR: Failed to confirm slot {slot_id} for student {student_id}: {e}")
        return False


async def reject_student_request(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 student_id: int, teacher_id: int):
    """Отклоняет заявку студента"""

    try:
        # Уведомляем студента
        student_message = (
            f"❌ *По вашей заявке на расписание*\n\n"
            f"К сожалению, на выбранные вами слоты нет свободных окон.\n"
            f"Пожалуйста, выберите другое время в разделе '📅 Выбрать расписание'"
        )

        await context.bot.send_message(
            chat_id=student_id,
            text=student_message,
            parse_mode='Markdown'
        )

        # Обновляем сообщение преподавателю
        await safe_edit_message(
            update.callback_query,
            text="❌ Заявка отклонена. Студент уведомлен.",
            parse_mode='Markdown'
        )

    except Exception as e:
        await safe_edit_message(
            update.callback_query,
            f"❌ Ошибка уведомления студента: {e}"
        )


async def show_my_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подтвержденные занятия студента"""
    user_id = update.effective_user.id

    lessons = get_confirmed_lessons(user_id)
    if not lessons:
        await update.message.reply_text(
            "📭 У вас пока нет подтвержденных занятий.\n"
            "Выберите удобное время в разделе '📅 Выбрать расписание'"
        )
        return

    lessons_text = "📋 *Ваши подтвержденные занятия:*\n\n"

    for lesson in lessons:
        lessons_text += f"• {lesson['slot_name']}\n"

    await update.message.reply_text(lessons_text, parse_mode='Markdown')


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'В главное меню'"""
    from handlers.start import start
    await start(update, context)


async def send_reminder_to_student(context, student_id, lesson):
    """Отправляет напоминание студенту о занятии (для reminders.py)"""
    try:
        reminder_text = (
            f"🔔 *Напоминание о занятии!*\n\n"
            f"*Завтра у вас запланирован урок:*\n"
            f"• {lesson['slot_name']}\n\n"
            f"*Адрес:*\n"
            f"4-й Сыромятнический переулок, 3/5с3\n"
            f"[Яндекс Карты](https://yandex.ru/maps/-/CLdYmDK3)\n\n"
            f"Пожалуйста, не опаздывайте и возьмите с собой все необходимое!"
        )

        await context.bot.send_message(
            chat_id=student_id,
            text=reminder_text,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

        # Отмечаем что напоминание отправлено
        from database import update_lesson_reminder_sent
        update_lesson_reminder_sent(lesson['id'])
        print(f"🔔 Sent reminder to student {student_id} for {lesson['slot_name']}")

    except Exception as e:
        print(f"ERROR sending reminder to student {student_id}: {e}")


def get_lesson_order(lesson):
    """Получает порядок занятия для сортировки"""
    try:
        slot_id = lesson['slot_id']

        # Если это ручное занятие (начинается с manual_)
        if slot_id.startswith('manual_'):
            try:
                # Пытаемся извлечь дату из названия занятия
                slot_name = lesson['slot_name']
                parts = slot_name.split()

                date_str = None
                time_str = None

                for part in parts:
                    if '.' in part and len(part.split('.')) == 3:
                        date_str = part
                    elif ':' in part and len(part.split(':')) == 2:
                        time_str = part

                if date_str and time_str:
                    lesson_date = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
                    day_num = lesson_date.weekday()  # 0-6 (пн=0)
                    time_val = lesson_date.hour * 100 + lesson_date.minute
                    return (day_num, time_val)
            except:
                return (0, 0)

        # Если это обычное занятие из расписания (формат: dayX_YY)
        elif slot_id.startswith('day'):
            try:
                # Извлекаем день из slot_id (формат: "day0_14")
                day_num = int(slot_id[3])  # "day0_14" -> 0
                time_part = slot_id.split('_')[1]
                time_val = int(time_part) if time_part.isdigit() else 0
                return (day_num, time_val)
            except:
                return (0, 0)

        # Для любых других форматов
        else:
            return (0, 0)

    except Exception as e:
        print(f"Ошибка парсинга занятия {lesson.get('slot_name')}: {e}")
        return (0, 0)

# Регистрируем обработчики
schedule_handlers = [
    MessageHandler(filters.Regex("^📅 Выбрать расписание$"), choose_schedule),
    MessageHandler(filters.Regex("^🕐 Мои занятия$"), show_my_lessons),
    CallbackQueryHandler(handle_schedule_buttons, pattern="^select_day_"),
    CallbackQueryHandler(handle_schedule_buttons, pattern="^select_time_"),
    CallbackQueryHandler(handle_schedule_buttons, pattern="^nav_day_"),
    CallbackQueryHandler(handle_schedule_buttons, pattern="^show_selected"),
    CallbackQueryHandler(handle_schedule_buttons, pattern="^finish_schedule"),
    CallbackQueryHandler(handle_teacher_confirmation, pattern="^confirm_"),
    CallbackQueryHandler(handle_teacher_confirmation, pattern="^reject_all_"),
    CallbackQueryHandler(handle_teacher_confirmation, pattern="^confirmed_"),
    CallbackQueryHandler(lambda update, context: update.callback_query.answer(), pattern="^ignore$"),
]