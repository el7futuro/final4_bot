# tests/test_database.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncpg
from bot.config import load_config
from bot.database import check_db_connection, init_db, close_db


@pytest.mark.asyncio
async def test_direct_asyncpg_connection(db_connection):
    """Тест прямого подключения через asyncpg"""
    # Используем фикстуру db_connection

    # Проверяем версию PostgreSQL
    version = await db_connection.fetchval("SELECT version()")
    print(f"PostgreSQL: {version}")
    assert "PostgreSQL" in version

    # Проверяем текущую базу данных
    db_name = await db_connection.fetchval("SELECT current_database()")
    config = load_config()
    assert db_name == config.db.database, f"Ожидалась база {config.db.database}, получили {db_name}"

    print("✅ Прямое подключение через asyncpg работает")


@pytest.mark.asyncio
async def test_sqlalchemy_connection():
    """Тест подключения через SQLAlchemy"""
    is_connected = await check_db_connection()
    assert is_connected, "Не удалось подключиться через SQLAlchemy"
    print("✅ Подключение через SQLAlchemy работает")

    # Закрываем соединение после теста
    await close_db()


@pytest.mark.asyncio
async def test_database_tables(db_connection):
    """Тест наличия таблиц в базе данных"""
    # Получаем список таблиц
    tables = await db_connection.fetch("""
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename;
    """)

    table_names = [table['tablename'] for table in tables]
    print(f"Таблицы в базе: {table_names}")

    # Проверяем обязательные таблицы (которые мы создали ранее)
    required_tables = ['users', 'teams', 'matches']
    for table in required_tables:
        assert table in table_names, f"Отсутствует таблица: {table}"

    print("✅ Все необходимые таблицы существуют")


@pytest.mark.asyncio
async def test_init_db():
    """Тест инициализации базы данных"""
    try:
        # Сначала попробуем инициализировать
        await init_db()
        print("✅ Инициализация БД выполнена успешно")

        # Проверим что таблицы созданы
        from bot.database import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            tables = result.fetchall()
            print(f"✅ Таблиц в базе: {len(tables)}")

    except Exception as e:
        pytest.fail(f"Ошибка инициализации БД: {e}")
    finally:
        await close_db()


@pytest.mark.asyncio
async def test_user_table_structure(db_connection):
    """Тест структуры таблицы users"""
    # Получаем информацию о колонках таблицы users
    columns = await db_connection.fetch("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'users'
        ORDER BY ordinal_position;
    """)

    print("\nСтруктура таблицы 'users':")
    required_columns = ['telegram_id', 'username', 'created_at']

    for column in columns:
        print(f"  - {column['column_name']} ({column['data_type']})")

        # Проверяем обязательные колонки
        if column['column_name'] in required_columns:
            required_columns.remove(column['column_name'])

    # Все обязательные колонки должны быть найдены
    assert len(required_columns) == 0, f"Отсутствуют колонки: {required_columns}"
    print("✅ Структура таблицы users корректна")


# Функция для ручного запуска тестов без pytest
async def run_all_tests_manual():
    """Ручной запуск всех тестов"""
    print("=" * 60)
    print("РУЧНОЙ ЗАПУСК ТЕСТОВ БАЗЫ ДАННЫХ")
    print("=" * 60)

    config = load_config()
    results = {}

    try:
        # Тест 1: Прямое подключение через asyncpg
        print("\n1. Тест прямого подключения через asyncpg...")
        conn = await asyncpg.connect(
            host=config.db.host,
            port=config.db.port,
            user=config.db.user,
            password=config.db.password,
            database=config.db.database
        )

        version = await conn.fetchval("SELECT version()")
        print(f"   ✅ PostgreSQL: {version}")

        db_name = await conn.fetchval("SELECT current_database()")
        assert db_name == config.db.database
        print(f"   ✅ База данных: {db_name}")

        await conn.close()
        results['direct_connection'] = True

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        results['direct_connection'] = False

    try:
        # Тест 2: Подключение через SQLAlchemy
        print("\n2. Тест подключения через SQLAlchemy...")
        is_connected = await check_db_connection()
        if is_connected:
            print("   ✅ Подключение установлено")
            results['sqlalchemy_connection'] = True
        else:
            print("   ❌ Не удалось подключиться")
            results['sqlalchemy_connection'] = False

        await close_db()

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        results['sqlalchemy_connection'] = False

    try:
        # Тест 3: Проверка таблиц
        print("\n3. Проверка таблиц в базе данных...")
        conn = await asyncpg.connect(
            host=config.db.host,
            port=config.db.port,
            user=config.db.user,
            password=config.db.password,
            database=config.db.database
        )

        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)

        table_names = [table['tablename'] for table in tables]
        print(f"   ✅ Таблиц в базе: {len(table_names)}")

        for table in table_names:
            print(f"     - {table}")

        # Проверяем обязательные таблицы
        required_tables = ['users', 'teams', 'matches']
        missing_tables = [t for t in required_tables if t not in table_names]

        if missing_tables:
            print(f"   ❌ Отсутствуют таблицы: {missing_tables}")
            results['tables_check'] = False
        else:
            print("   ✅ Все необходимые таблицы присутствуют")
            results['tables_check'] = True

        await conn.close()

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        results['tables_check'] = False

    # Вывод результатов
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ТЕСТОВ:")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ УСПЕХ" if passed else "❌ ОШИБКА"
        print(f"{test_name:25} : {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        print("=" * 60)
        return False


if __name__ == "__main__":
    # Запуск тестов без pytest
    import asyncio

    success = asyncio.run(run_all_tests_manual())

    if success:
        print("\nБаза данных готова к использованию!")
        print("Запустите бота: python -m bot.main")
        sys.exit(0)
    else:
        print("\nТребуется исправить ошибки перед запуском бота")
        sys.exit(1)