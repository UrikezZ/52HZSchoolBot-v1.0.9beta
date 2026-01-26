# database.py
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


# Создание базы данных и таблиц
def init_database():
    """Инициализация базы данных и создание таблиц"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                fio TEXT,
                birthdate TEXT,
                instruments TEXT,  -- JSON массив
                goals TEXT,
                role TEXT DEFAULT 'student',
                study_format TEXT DEFAULT 'очная',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица баланса студентов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_balance (
                user_id INTEGER PRIMARY KEY,
                lessons_left INTEGER DEFAULT 0,
                balance INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                lesson_price INTEGER DEFAULT 1800,
                total_paid_lessons INTEGER DEFAULT 0,
                total_completed_lessons INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица подтвержденных занятий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS confirmed_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                slot_id TEXT,
                slot_name TEXT,
                confirmed_by INTEGER,
                date_added TEXT,
                payment_type TEXT,
                is_manual INTEGER DEFAULT 0,
                reminder_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица заявок на расписание
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                selected_slots TEXT,  -- JSON массив
                week_added INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Индексы для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_confirmed_lessons_user_id ON confirmed_lessons(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_confirmed_lessons_slot_id ON confirmed_lessons(slot_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedule_requests_user_id ON schedule_requests(user_id)')

        conn.commit()
        logger.info("База данных инициализирована")


@contextmanager
def get_connection():
    """Контекстный менеджер для подключения к БД"""
    conn = sqlite3.connect('music_school.db')
    conn.row_factory = sqlite3.Row  # Для доступа по имени столбца
    try:
        yield conn
    finally:
        conn.close()


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ==========

def save_user(user_data):
    """Сохранение или обновление пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Преобразуем список инструментов в JSON
        instruments_json = '[]'
        if 'instruments' in user_data:
            import json
            instruments_json = json.dumps(user_data['instruments'])

        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, fio, birthdate, instruments, goals, role, study_format, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            user_data['user_id'],
            user_data.get('fio', ''),
            user_data.get('birthdate', ''),
            instruments_json,
            user_data.get('goals', ''),
            user_data.get('role', 'student'),
            user_data.get('study_format', 'очная')
        ))

        conn.commit()
        logger.info(f"Сохранен пользователь {user_data['user_id']}")


def get_user(user_id):
    """Получение данных пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()

        if row:
            user = dict(row)
            # Преобразуем JSON обратно в список
            import json
            user['instruments'] = json.loads(user['instruments']) if user['instruments'] else []
            return user
        return None


def get_all_users(role=None):
    """Получение всех пользователей с фильтром по роли"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if role:
            cursor.execute('SELECT * FROM users WHERE role = ? ORDER BY fio', (role,))
        else:
            cursor.execute('SELECT * FROM users ORDER BY fio')

        users = []
        for row in cursor.fetchall():
            user = dict(row)
            import json
            user['instruments'] = json.loads(user['instruments']) if user['instruments'] else []
            users.append(user)

        return users


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БАЛАНСОМ ==========

def save_student_balance(balance_data):
    """Сохранение баланса студента"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO student_balance 
            (user_id, lessons_left, balance, notes, lesson_price, 
             total_paid_lessons, total_completed_lessons, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            balance_data['user_id'],
            balance_data.get('lessons_left', 0),
            balance_data.get('balance', 0),
            balance_data.get('notes', ''),
            balance_data.get('lesson_price', 1800),
            balance_data.get('total_paid_lessons', 0),
            balance_data.get('total_completed_lessons', 0)
        ))

        conn.commit()


def get_student_balance(user_id):
    """Получение баланса студента"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM student_balance WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()

        if row:
            return dict(row)
        else:
            # Создаем запись по умолчанию
            default_balance = {
                'user_id': user_id,
                'lessons_left': 0,
                'balance': 0,
                'notes': '',
                'lesson_price': 1800,
                'total_paid_lessons': 0,
                'total_completed_lessons': 0
            }
            save_student_balance(default_balance)
            return default_balance


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ЗАНЯТИЯМИ ==========

def save_confirmed_lesson(lesson_data):
    """Сохранение подтвержденного занятия"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO confirmed_lessons 
            (user_id, slot_id, slot_name, confirmed_by, date_added, payment_type, is_manual)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            lesson_data['user_id'],
            lesson_data.get('slot_id', ''),
            lesson_data.get('slot_name', ''),
            lesson_data.get('confirmed_by', 0),
            lesson_data.get('date_added', ''),
            lesson_data.get('payment_type', ''),
            lesson_data.get('is_manual', 0)
        ))

        conn.commit()
        logger.info(f"Сохранено занятие для пользователя {lesson_data['user_id']}")


def get_confirmed_lessons(user_id=None):
    """Получение подтвержденных занятий (всех или для конкретного пользователя)"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if user_id:
            cursor.execute('SELECT * FROM confirmed_lessons WHERE user_id = ? ORDER BY date_added', (user_id,))
        else:
            cursor.execute('SELECT * FROM confirmed_lessons ORDER BY user_id, date_added')

        lessons = []
        for row in cursor.fetchall():
            lessons.append(dict(row))

        return lessons


def delete_confirmed_lesson(lesson_id):
    """Удаление занятия по ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM confirmed_lessons WHERE id = ?', (lesson_id,))
        conn.commit()
        logger.info(f"Удалено занятие {lesson_id}")


def delete_confirmed_lesson_by_slot(user_id, slot_id):
    """Удаление занятия по user_id и slot_id"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM confirmed_lessons WHERE user_id = ? AND slot_id = ?', (user_id, slot_id))
        conn.commit()
        logger.info(f"Удалено занятие {slot_id} для пользователя {user_id}")


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ЗАЯВКАМИ НА РАСПИСАНИЕ ==========

def save_schedule_request(request_data):
    """Сохранение заявки на расписание"""
    with get_connection() as conn:
        cursor = conn.cursor()

        import json
        selected_slots_json = json.dumps(request_data.get('selected_slots', []))

        # Проверяем, есть ли уже заявка от этого пользователя
        cursor.execute('SELECT id FROM schedule_requests WHERE user_id = ?', (request_data['user_id'],))
        existing = cursor.fetchone()

        if existing:
            cursor.execute('''
                UPDATE schedule_requests 
                SET selected_slots = ?, week_added = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (selected_slots_json, request_data.get('week_added'), request_data['user_id']))
        else:
            cursor.execute('''
                INSERT INTO schedule_requests (user_id, selected_slots, week_added)
                VALUES (?, ?, ?)
            ''', (request_data['user_id'], selected_slots_json, request_data.get('week_added')))

        conn.commit()


def get_schedule_request(user_id):
    """Получение заявки на расписание пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM schedule_requests WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()

        if row:
            request = dict(row)
            import json
            request['selected_slots'] = json.loads(request['selected_slots']) if request['selected_slots'] else []
            return request
        return None


def get_all_schedule_requests():
    """Получение всех заявок на расписание"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM schedule_requests')

        requests = []
        for row in cursor.fetchall():
            request = dict(row)
            import json
            request['selected_slots'] = json.loads(request['selected_slots']) if request['selected_slots'] else []
            requests.append(request)

        return requests


def delete_schedule_request(user_id):
    """Удаление заявки на расписание"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM schedule_requests WHERE user_id = ?', (user_id,))
        conn.commit()
        logger.info(f"Удалена заявка на расписание пользователя {user_id}")


def delete_all_schedule_requests():
    """Удаление всех заявок на расписание"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM schedule_requests')
        conn.commit()
        logger.info("Удалены все заявки на расписание")


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_user_count_by_role(role):
    """Получение количества пользователей по роли"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE role = ?', (role,))
        return cursor.fetchone()['count']


def get_total_confirmed_lessons():
    """Получение общего количества подтвержденных занятий"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM confirmed_lessons')
        return cursor.fetchone()['count']


def cleanup_old_requests_weeks_ago(weeks=1):
    """Очистка старых заявок старше указанного количества недель"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Вычисляем текущую неделю
        current_week = datetime.now().isocalendar()[1]
        target_week = current_week - weeks

        cursor.execute('DELETE FROM schedule_requests WHERE week_added < ?', (target_week,))
        deleted_count = cursor.rowcount
        conn.commit()

        logger.info(f"Очищено {deleted_count} старых заявок")
        return deleted_count


def update_lesson_reminder_sent(lesson_id):
    """Отметка, что напоминание о занятии отправлено"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE confirmed_lessons SET reminder_sent = 1 WHERE id = ?', (lesson_id,))
        conn.commit()


def get_lessons_needing_reminder(target_date):
    """Получение занятий, требующих напоминания на указанную дату"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Здесь нужно добавить логику поиска занятий по дате
        # Это зависит от формата хранения дат в slot_name
        # Вернем пока пустой список
        return []


def delete_user(user_id):
    """Удаление пользователя и всех связанных данных"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Удаляем в правильном порядке (сначала зависимости)

        # 1. Удаляем занятия пользователя
        cursor.execute('DELETE FROM confirmed_lessons WHERE user_id = ?', (user_id,))

        # 2. Удаляем заявки на расписание
        cursor.execute('DELETE FROM schedule_requests WHERE user_id = ?', (user_id,))

        # 3. Удаляем баланс
        cursor.execute('DELETE FROM student_balance WHERE user_id = ?', (user_id,))

        # 4. Удаляем самого пользователя
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))

        conn.commit()
        logger.info(f"Удален пользователь {user_id} и все связанные данные")
        return cursor.rowcount  # Возвращаем количество удаленных записей


def archive_user(user_id):
    """Архивация пользователя вместо удаления"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Помечаем пользователя как архивного
        cursor.execute('''
            UPDATE users 
            SET role = 'archived', 
                archived_at = CURRENT_TIMESTAMP 
            WHERE user_id = ?
        ''', (user_id,))

        # 2. Помечаем занятия как архивные
        cursor.execute('''
            UPDATE confirmed_lessons 
            SET is_archived = 1 
            WHERE user_id = ?
        ''', (user_id,))

        conn.commit()
        logger.info(f"Заархивирован пользователь {user_id}")
        return cursor.rowcount


# Инициализация базы данных при импорте
init_database()