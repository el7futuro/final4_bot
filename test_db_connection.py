# test_db_connection.py
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.database import check_db_connection, init_db, close_db
from bot.config import load_config


async def test_connection():
    print("=" * 50)
    print("Тестирование подключения к PostgreSQL")
    print("=" * 50)

    # Загружаем конфиг
    config = load_config()
    print(f"Хост: {config.db.host}:{config.db.port}")
    print(f"База данных: {config.db.database}")
    print(f"Пользователь: {config.db.user}")
    print("-" * 50)

    # Проверка подключения
    print("\n1. Проверка подключения к БД...")
    is_connected = await check_db_connection()

    if not is_connected:
        print("❌ Не удалось подключиться к базе данных")
        print("\nВозможные причины:")
        print("1. База данных не создана (запустите create_database.py)")
        print("2. Неправильный пароль в .env файле")
        print("3. PostgreSQL не запущен")
        print("4. Порт 5432 занят Docker (выполните: docker-compose down)")
        return False

    # Инициализация таблиц
    print("\n2. Инициализация таблиц...")
    try:
        await init_db()
        print("✅ Таблицы созданы успешно")
    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")
        return False

    print("\n" + "=" * 50)
    print("✅ Все тесты пройдены успешно!")
    print("=" * 50)

    return True


async def main():
    success = await test_connection()

    # Закрываем соединение
    await close_db()

    if success:
        print("\nБаза данных готова к использованию!")
        print("Можете запускать бота: python -m bot.main")
    else:
        print("\nТребуется исправить ошибки перед запуском бота")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())