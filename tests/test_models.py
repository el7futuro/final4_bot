# tests/test_models.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.database import Base
from models.user import User
from models.team import Team
from models.match import Match


def test_models_import():
    """Тест импорта моделей"""
    print("Тестирование импорта моделей...")

    # Проверяем что модели импортируются
    models = [User, Team, Match]

    for model in models:
        assert model.__tablename__, f"У модели {model.__name__} не установлен __tablename__"
        print(f"✅ Модель: {model.__name__}")
        print(f"   Таблица: {model.__tablename__}")
        print(f"   Колонки: {[c.name for c in model.__table__.columns]}")

    # Проверяем что все модели зарегистрированы в Base
    table_count = len(Base.metadata.tables)
    print(f"\n✅ Всего таблиц в метаданных: {table_count}")

    for table_name in Base.metadata.tables.keys():
        print(f"   - {table_name}")

    return True


if __name__ == "__main__":
    success = test_models_import()

    if success:
        print("\n✅ Модели загружены правильно!")
    else:
        print("\n❌ Проблемы с моделями")
        sys.exit(1)