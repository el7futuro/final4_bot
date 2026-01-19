# simple_async_init.py
import asyncio
import asyncpg
from bot.config import load_config


async def create_tables():
    """Создание таблиц через чистый asyncpg"""
    config = load_config()

    print("=" * 60)
    print("Создание таблиц через asyncpg")
    print("=" * 60)

    try:
        # Подключение
        conn = await asyncpg.connect(
            host=config.db.host,
            port=config.db.port,
            user=config.db.user,
            password=config.db.password,
            database=config.db.database
        )

        print("✅ Подключено к базе данных")

        # Создание таблицы users
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(100),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                language_code VARCHAR(10),
                is_bot BOOLEAN DEFAULT FALSE,
                is_admin BOOLEAN DEFAULT FALSE,
                is_blocked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Таблица 'users' создана")

        # Создание таблицы matches
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                score_home INTEGER,
                score_away INTEGER,
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Таблица 'matches' создана")

        # Создание таблицы teams
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                country VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Таблица 'teams' создана")

        # Проверка
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)

        print(f"\n✅ Всего таблиц создано: {len(tables)}")
        for table in tables:
            print(f"   - {table['table_name']}")

        # Тестовая запись
        await conn.execute("""
            INSERT INTO users (telegram_id, username, first_name)
            VALUES (999888777, 'test_bot_user', 'Test')
            ON CONFLICT (telegram_id) DO NOTHING
        """)

        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        print(f"\n✅ Пользователей в базе: {user_count}")

        await conn.close()

        print("\n" + "=" * 60)
        print("✅ БАЗА ДАННЫХ ГОТОВА К ИСПОЛЬЗОВАНИЮ!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    # Сначала проверка asyncpg
    print("Проверка asyncpg...")
    from test_asyncpg import test_asyncpg
    if not await test_asyncpg():
        print("\n❌ Проблема с asyncpg. Установите: pip install --upgrade asyncpg")
        return

    # Создание таблиц
    print("\n" + "=" * 60)
    success = await create_tables()

    if success:
        print("\nТеперь можете запускать бота:")
        print("python -m bot.main")
    else:
        print("\n❌ Не удалось создать таблицы")


if __name__ == "__main__":
    asyncio.run(main())