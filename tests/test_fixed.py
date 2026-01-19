# test_fixed.py
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def test_fixed():
    print("Тестирование исправленного подключения...")

    try:
        from bot.database import check_db_connection, close_db

        # Тест подключения
        success = await check_db_connection()

        if success:
            print("✅ Подключение работает!")
        else:
            print("❌ Проблемы с подключением")

        await close_db()
        return success

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_direct_asyncpg():
    """Прямой тест через asyncpg"""
    print("\nПрямой тест через asyncpg...")

    try:
        import asyncpg
        from bot.config import load_config

        config = load_config()

        conn = await asyncpg.connect(
            host=config.db.host,
            port=config.db.port,
            user=config.db.user,
            password=config.db.password,
            database=config.db.database
        )

        print("✅ Прямое подключение через asyncpg работает")

        # Проверим таблицы
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)

        print(f"✅ Таблиц в базе: {len(tables)}")
        for table in tables:
            print(f"   - {table['tablename']}")

        await conn.close()
        return True

    except Exception as e:
        print(f"❌ Ошибка asyncpg: {e}")
        return False


async def main():
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ")
    print("=" * 60)

    # Тест 1: Прямое подключение через asyncpg
    direct_ok = await test_direct_asyncpg()

    if not direct_ok:
        print("\n❌ Прямое подключение не работает")
        print("Проверьте настройки в .env файле")
        return

    # Тест 2: Подключение через SQLAlchemy
    print("\n" + "=" * 60)
    print("Тестирование SQLAlchemy подключения...")
    print("=" * 60)

    sqlalchemy_ok = await test_fixed()

    if sqlalchemy_ok:
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 60)
        print("\nТеперь можете запускать бота:")
        print("python -m bot.main")
    else:
        print("\n❌ Проблемы с SQLAlchemy")
        print("Проверьте импорты и настройки")


if __name__ == "__main__":
    asyncio.run(main())