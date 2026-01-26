# migrate.py
import json
from database import (
    init_database, save_user, save_student_balance,
    save_confirmed_lesson, save_schedule_request
)


def migrate_from_old_config():
    """Миграция данных из старых словарей config.py в базу данных"""
    print("🔄 Начинаем миграцию данных...")

    # Импортируем старые данные
    try:
        # Временный импорт старых данных
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))

        # Создаем временный модуль для импорта старых данных
        old_data = {}
        try:
            import config as old_config
            old_data['user_profiles'] = old_config.user_profiles
            old_data['student_balance'] = old_config.student_balance
            old_data['confirmed_lessons'] = old_config.confirmed_lessons
            old_data['schedule_requests'] = old_config.schedule_requests
        except:
            print("⚠️ Не удалось импортировать старые данные. Возможно, файл config.py уже обновлен.")
            return

    except Exception as e:
        print(f"❌ Ошибка при импорте старых данных: {e}")
        return

    # 1. Миграция пользователей
    print("📊 Миграция пользователей...")
    migrated_users = 0
    for user_id, profile in old_data.get('user_profiles', {}).items():
        try:
            # Преобразуем данные для сохранения
            user_data = {
                'user_id': user_id,
                'fio': profile.get('fio', ''),
                'birthdate': profile.get('birthdate', ''),
                'instruments': profile.get('instruments', []),
                'goals': profile.get('goals', ''),
                'role': profile.get('role', 'student'),
                'study_format': profile.get('study_format', 'очная')
            }
            save_user(user_data)
            migrated_users += 1
        except Exception as e:
            print(f"⚠️ Ошибка при миграции пользователя {user_id}: {e}")

    print(f"✅ Мигрировано пользователей: {migrated_users}")

    # 2. Миграция балансов
    print("💰 Миграция балансов...")
    migrated_balances = 0
    for user_id, balance in old_data.get('student_balance', {}).items():
        try:
            balance_data = {
                'user_id': user_id,
                'lessons_left': balance.get('lessons_left', 0),
                'balance': balance.get('balance', 0),
                'notes': balance.get('notes', ''),
                'lesson_price': balance.get('lesson_price', 2000),
                'total_paid_lessons': balance.get('total_paid_lessons', 0),
                'total_completed_lessons': balance.get('total_completed_lessons', 0)
            }
            save_student_balance(balance_data)
            migrated_balances += 1
        except Exception as e:
            print(f"⚠️ Ошибка при миграции баланса {user_id}: {e}")

    print(f"✅ Мигрировано балансов: {migrated_balances}")

    # 3. Миграция занятий
    print("📅 Миграция занятий...")
    migrated_lessons = 0
    for user_id, lessons in old_data.get('confirmed_lessons', {}).items():
        for lesson in lessons:
            try:
                lesson_data = {
                    'user_id': user_id,
                    'slot_id': lesson.get('slot_id', ''),
                    'slot_name': lesson.get('slot_name', ''),
                    'confirmed_by': lesson.get('confirmed_by', 0),
                    'date_added': lesson.get('date_added', ''),
                    'payment_type': lesson.get('payment_type', ''),
                    'is_manual': lesson.get('is_manual', 0)
                }
                save_confirmed_lesson(lesson_data)
                migrated_lessons += 1
            except Exception as e:
                print(f"⚠️ Ошибка при миграции занятия {user_id}: {e}")

    print(f"✅ Мигрировано занятий: {migrated_lessons}")

    # 4. Миграция заявок на расписание
    print("📋 Миграция заявок на расписание...")
    migrated_requests = 0
    for user_id, request in old_data.get('schedule_requests', {}).items():
        try:
            request_data = {
                'user_id': user_id,
                'selected_slots': request.get('selected_slots', []),
                'week_added': request.get('week_added', 0)
            }
            save_schedule_request(request_data)
            migrated_requests += 1
        except Exception as e:
            print(f"⚠️ Ошибка при миграции заявки {user_id}: {e}")

    print(f"✅ Мигрировано заявок: {migrated_requests}")

    print("\n🎉 Миграция завершена!")
    print("=" * 50)
    print("📊 Итоговая статистика:")
    print(f"• Пользователи: {migrated_users}")
    print(f"• Балансы: {migrated_balances}")
    print(f"• Занятия: {migrated_lessons}")
    print(f"• Заявки: {migrated_requests}")
    print("=" * 50)
    print("\n✅ Теперь можно запускать бота с новой базой данных!")


if __name__ == "__main__":
    # Инициализируем базу данных
    init_database()

    # Запускаем миграцию
    migrate_from_old_config()