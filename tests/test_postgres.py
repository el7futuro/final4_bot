# test_postgres.py
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_db, check_connection, SessionLocal, User


def test_database():
    print("Тестирование подключения к PostgreSQL...")

    # Проверяем подключение
    if not check_connection():
        return

    # Создаем таблицы
    print("\nСоздание таблиц...")
    init_db()

    # Тестовая запись
    print("\nДобавление тестового пользователя...")
    with SessionLocal() as db:
        # Проверяем, есть ли уже пользователи
        count = db.query(User).count()
        print(f"Пользователей в базе: {count}")

        # Добавляем тестового пользователя
        test_user = User(
            telegram_id=123456789,
            username="test_bot_user",
            first_name="Test",
            last_name="User"
        )
        db.add(test_user)
        db.commit()
        print("✅ Тестовый пользователь добавлен!")

        # Проверяем добавление
        users = db.query(User).all()
        print(f"\nВсе пользователи в базе ({len(users)}):")
        for user in users:
            print(f"  - {user.username} (ID: {user.telegram_id})")


if __name__ == "__main__":
    test_database()