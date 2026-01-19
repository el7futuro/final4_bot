# tests/test_config.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import load_config


def test_config_loading():
    """Тест загрузки конфигурации"""
    print("Тестирование загрузки конфигурации...")

    config = load_config()

    # Проверяем обязательные поля
    assert config.bot.token, "Токен бота не установлен"
    assert isinstance(config.bot.admin_ids, list), "admin_ids должен быть списком"

    # Проверяем настройки базы данных
    assert config.db.host, "DB_HOST не установлен"
    assert config.db.port, "DB_PORT не установлен"
    assert config.db.database, "DB_NAME не установлен"
    assert config.db.user, "DB_USER не установлен"
    assert config.db.password is not None, "DB_PASSWORD не установлен"

    print(f"✅ Конфигурация загружена:")
    print(f"   Бот токен: {'установлен' if config.bot.token else 'НЕТ!'}")
    print(f"   Админы: {config.bot.admin_ids}")
    print(f"   База данных: {config.db.database}")
    print(f"   Хост: {config.db.host}:{config.db.port}")

    return True


if __name__ == "__main__":
    success = test_config_loading()

    if success:
        print("\n✅ Конфигурация в порядке!")
    else:
        print("\n❌ Проблемы с конфигурацией")
        sys.exit(1)