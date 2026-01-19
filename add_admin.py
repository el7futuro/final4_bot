# add_admin.py
import asyncio
import asyncpg
from bot.config import load_config


async def add_admin_user():
    config = load_config()

    print("Добавление администратора...")

    # Ваш Telegram ID (замените на реальный)
    YOUR_TELEGRAM_ID = 123456789  # ЗАМЕНИТЕ НА ВАШ ID
    YOUR_USERNAME = "your_username"

    try:
        conn = await asyncpg.connect(
            host=config.db.host,
            port=config.db.port,
            user=config.db.user,
            password=config.db.password,
            database=config.db.database
        )

        # Добавляем или обновляем пользователя как админа
        await conn.execute("""
            INSERT INTO users (telegram_id, username, first_name, is_admin)
            VALUES ($1, $2, $3, TRUE)
            ON CONFLICT (telegram_id) 
            DO UPDATE SET is_admin = TRUE, username = EXCLUDED.username
        """, YOUR_TELEGRAM_ID, YOUR_USERNAME, "Admin")

        print(f"✅ Пользователь {YOUR_TELEGRAM_ID} добавлен как администратор")

        await conn.close()

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(add_admin_user())