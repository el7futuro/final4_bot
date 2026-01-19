# init_database.py
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def initialize_database():
    """Инициализация базы данных - создание таблиц"""
    print("=" * 60)
    print("Инициализация базы данных final4_bot")
    print("=" * 60)

    try:
        # Импортируем необходимые модули
        from bot.database import init_db, check_db_connection, close_db
        from bot.config import load_config

        # Загружаем конфигурацию
        config = load_config()
        print(f"Подключение к: {config.db.host}:{config.db.port}/{config.db.database}")
        print(f"Пользователь: {config.db.user}")
        print("-" * 60)

        # Шаг 1: Проверка подключения
        print("1. Проверка подключения к PostgreSQL...")
        is_connected = await check_db_connection()

        if not is_connected:
            print("❌ Не удалось подключиться к базе данных")
            print("\nВозможные причины:")
            print(f"  1. Неправильный пароль в .env файле")
            print(f"  2. База {config.db.database} не существует (но мы её создали)")
            print(f"  3. Проблемы с правами пользователя {config.db.user}")
            print("\nПроверьте пароль в .env файле!")
            return False

        print("✅ Подключение установлено")

        # Шаг 2: Инициализация таблиц
        print("\n2. Создание таблиц в базе данных...")
        try:
            await init_db()
            print("✅ Таблицы успешно созданы!")
        except Exception as e:
            print(f"❌ Ошибка при создании таблиц: {e}")
            print("\nИнформация об ошибке поможет её исправить.")
            return False

        # Шаг 3: Проверка таблиц
        print("\n3. Проверка созданных таблиц...")
        try:
            from bot.database import engine
            from sqlalchemy import text

            async with engine.connect() as conn:
                # Получаем список таблиц
                result = await conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """))

                tables = [row[0] for row in result.fetchall()]

                if tables:
                    print(f"✅ Найдено таблиц: {len(tables)}")
                    for table in tables:
                        print(f"   - {table}")
                else:
                    print("⚠️ Таблицы не найдены")

        except Exception as e:
            print(f"⚠️ Не удалось проверить таблицы: {e}")

        print("\n" + "=" * 60)
        print("✅ ИНИЦИАЛИЗАЦИЯ УСПЕШНО ЗАВЕРШЕНА!")
        print("=" * 60)
        print("\nБаза данных готова к использованию.")
        print("Теперь можете запускать бота командой:")
        print("python -m bot.main")

        return True

    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("\nУстановите необходимые библиотеки:")
        print("pip install asyncpg sqlalchemy[asyncio] python-dotenv")
        return False

    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Закрываем соединение
        if 'close_db' in locals():
            await close_db()


async def test_connection_simple():
    """Простая проверка подключения"""
    print("\nПростая проверка подключения...")
    try:
        import psycopg2

        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            dbname="final4_bot",
            user="postgres",
            password="postgres"  # измените если другой пароль
        )

        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]

        print(f"✅ PostgreSQL версия: {version}")

        cursor.execute("SELECT current_database();")
        db_name = cursor.fetchone()[0]
        print(f"✅ Текущая база данных: {db_name}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def main():
    # Сначала простая проверка
    print("=" * 60)
    print("ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА")
    print("=" * 60)

    if not await test_connection_simple():
        print("\n❌ Не удалось подключиться к базе данных.")
        print("Проверьте пароль в .env файле!")
        print("Ожидаемый пароль: 'postgres' (если не меняли при установке)")
        return

    print("\n" + "=" * 60)
    print("НАЧАЛО ИНИЦИАЛИЗАЦИИ")
    print("=" * 60)

    # Запускаем инициализацию
    success = await initialize_database()

    if not success:
        print("\n❌ Инициализация не удалась.")
        print("Проверьте настройки и попробуйте снова.")
        input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    asyncio.run(main())