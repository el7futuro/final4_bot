import asyncio
from bot.database import engine
from sqlalchemy import text


async def check_table():
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'matches' ORDER BY ordinal_position")
        )
        columns = result.fetchall()

        print("Структура таблицы 'matches':")
        print("=" * 50)
        for col_name, data_type in columns:
            print(f"{col_name:<25} {data_type}")
        print("=" * 50)

        # Проверяем наличие match_type
        column_names = [col[0] for col in columns]
        if 'match_type' in column_names:
            print("✅ Колонка 'match_type' существует")
        else:
            print("❌ Колонка 'match_type' НЕ существует")
            print("\nСуществующие колонки:", column_names)


asyncio.run(check_table())