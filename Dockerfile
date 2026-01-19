# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

# Создание папок для логов и бэкапов
RUN mkdir -p logs backups

# Запуск скрипта инициализации при старте
COPY scripts/init_db.py .
RUN chmod +x scripts/init_db.py

# Команда запуска
CMD ["python", "-m", "bot.main"]