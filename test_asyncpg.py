# test_asyncpg.py
import asyncio
import asyncpg
from bot.config import load_config


async def test_asyncpg():
    config = load_config()

    print("Тестирование asyncpg подключения...")
    print(f"Подключение к: {config.db.host}:{config.db.port}/{config.db.database}")

    try:
        # Прямое подключение через asyncpg
        conn = await asyncpg.connect(
            host=config.db.host,
            port=config.db.port,
            user=config.db.user,
            password=config.db.password,
            database=config.db.database
        )

        print("✅ asyncpg подключение успешно")

        # Простой запрос
        result = await conn.fetch("SELECT version()")
        print(f"✅ Версия PostgreSQL: {result[0]['version']}")

        # Проверка таблиц
        result = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)

        if result:
            print(f"✅ Таблиц в базе: {len(result)}")
            for row in result:
                print(f"   - {row['table_name']}")
        else:
            print("ℹ️ Таблиц пока нет")

        await conn.close()
        return True

    except Exception as e:
        print(f"❌ Ошибка asyncpg: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_asyncpg())