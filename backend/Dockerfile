# Используем официальный image Python
FROM python:3.10-slim

# Рабочая директория
WORKDIR /app

# Переменные окружения для Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Установка системных зависимостей (если нужны для сборки пакетов)
# Например, для psycopg2 (хотя используем binary), или для paramiko/cryptography
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    musl-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements.txt .

# Устанавливаем зависимости
# Используем bcrypt 4.0.1 как фикс для passlib, если проблема сохранится
RUN pip install --no-cache-dir -r requirements.txt
# Принудительно ставим совместимый bcrypt, если он не указан явно в requirements
RUN pip install "bcrypt==4.0.1"

# Копируем исходный код
COPY . .

# Команда запуска (будет переопределена в docker-compose для dev режима, но хороша для default)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
