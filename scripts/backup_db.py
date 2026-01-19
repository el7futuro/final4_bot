# scripts/backup_db.py
"""
Скрипт резервного копирования базы данных.
"""

import asyncio
import logging
import os
from datetime import datetime
from sqlalchemy import text

from bot.database import engine
from bot.config import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backup_database():
    """Создает резервную копию базы данных"""
    config = load_config()

    # Создаем папку для бэкапов
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)

    # Формируем имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_dir}/final4_backup_{timestamp}.sql"

    try:
        # Команда для pg_dump
        db_config = config.db
        cmd = (
            f"pg_dump -h {db_config.host} -p {db_config.port} "
            f"-U {db_config.user} -d {db_config.database} "
            f"-f {backup_file}"
        )

        # Устанавливаем пароль в переменную окружения
        os.environ['PGPASSWORD'] = db_config.password

        # Выполняем команду
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"✅ Backup created: {backup_file}")

            # Удаляем старые бэкапы (оставляем последние 7)
            await cleanup_old_backups(backup_dir, keep=7)
        else:
            logger.error(f"❌ Backup failed: {stderr.decode()}")

    except Exception as e:
        logger.error(f"❌ Error creating backup: {e}")
    finally:
        # Очищаем пароль из переменной окружения
        if 'PGPASSWORD' in os.environ:
            del os.environ['PGPASSWORD']


async def cleanup_old_backups(backup_dir: str, keep: int = 7):
    """Удаляет старые резервные копии"""
    try:
        files = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.sql') and filename.startswith('final4_backup_'):
                filepath = os.path.join(backup_dir, filename)
                files.append((os.path.getmtime(filepath), filepath))

        # Сортируем по времени создания (новые сначала)
        files.sort(reverse=True)

        # Удаляем старые файлы
        for _, filepath in files[keep:]:
            os.remove(filepath)
            logger.info(f"🗑️ Deleted old backup: {filepath}")

    except Exception as e:
        logger.error(f"❌ Error cleaning up old backups: {e}")


async def restore_database(backup_file: str):
    """Восстанавливает базу данных из резервной копии"""
    config = load_config()

    if not os.path.exists(backup_file):
        logger.error(f"❌ Backup file not found: {backup_file}")
        return

    try:
        # Команда для восстановления
        db_config = config.db
        cmd = (
            f"psql -h {db_config.host} -p {db_config.port} "
            f"-U {db_config.user} -d {db_config.database} "
            f"-f {backup_file}"
        )

        # Устанавливаем пароль в переменную окружения
        os.environ['PGPASSWORD'] = db_config.password

        # Выполняем команду
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"✅ Database restored from: {backup_file}")
        else:
            logger.error(f"❌ Restore failed: {stderr.decode()}")

    except Exception as e:
        logger.error(f"❌ Error restoring database: {e}")
    finally:
        # Очищаем пароль из переменной окружения
        if 'PGPASSWORD' in os.environ:
            del os.environ['PGPASSWORD']


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "backup":
            asyncio.run(backup_database())
        elif command == "restore":
            if len(sys.argv) > 2:
                backup_file = sys.argv[2]
                asyncio.run(restore_database(backup_file))
            else:
                print("Usage: python -m scripts.backup_db restore <backup_file>")
        else:
            print("Usage: python -m scripts.backup_db [backup|restore]")
    else:
        print("Usage: python -m scripts.backup_db [backup|restore]")