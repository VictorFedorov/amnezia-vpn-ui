# Быстрый старт: Тестирование

## Установка зависимостей

```bash
cd backend
pip install -r requirements.txt
```

## Запуск тестов

### Все тесты
```bash
pytest
```

### С отчетом о покрытии
```bash
pytest --cov=app --cov-report=term-missing --cov-report=html
```

После этого откройте `htmlcov/index.html` в браузере для просмотра детального отчета.

### Только unit тесты
```bash
pytest -m unit
```

### Только интеграционные тесты
```bash
pytest -m integration
```

### С подробным выводом
```bash
pytest -v
```

### Конкретный файл
```bash
pytest tests/test_auth.py
```

## Запуск приложения

### 1. Настройка окружения

Создайте `.env` файл из примера:
```bash
cp .env.example .env
```

Отредактируйте `.env` и как минимум задайте:
- `DATABASE_URL`
- `SECRET_KEY` (сгенерируйте: `openssl rand -hex 32`)
- `SSH_HOST`, `SSH_USER`, `SSH_PASSWORD` или `SSH_KEY_PATH`

### 2. Применение миграций

```bash
cd backend
alembic upgrade head
```

### 3. Запуск сервера

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Или через Docker:
```bash
cd ..
docker-compose up
```

### 4. Проверка работы

API документация доступна по адресу: http://localhost:8000/api/docs

## Проверка безопасности

### 1. Проверка шифрования паролей

```python
from app.utils.encryption import encrypt_password, decrypt_password

password = "test_password_123"
encrypted = encrypt_password(password)
decrypted = decrypt_password(encrypted)

print(f"Original: {password}")
print(f"Encrypted: {encrypted}")
print(f"Decrypted: {decrypted}")
assert password == decrypted
```

### 2. Проверка rate limiting

Выполните 6 неуспешных попыток входа подряд:
```bash
for i in {1..6}; do
  curl -X POST "http://localhost:8000/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin&password=wrong"
  echo "\nAttempt $i"
  sleep 0.5
done
```

После 5-й попытки должна вернуться ошибка 429.

### 3. Проверка валидации

Попробуйте создать пользователя со слабым паролем:
```bash
curl -X POST "http://localhost:8000/api/users" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "weak"
  }'
```

Должна вернуться ошибка 422 с описанием проблем валидации.

## Troubleshooting

### Ошибка при импорте модулей

Убедитесь что находитесь в правильной директории и установлены все зависимости:
```bash
cd backend
pip install -r requirements.txt
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Ошибка при подключении к БД

Проверьте `DATABASE_URL` в `.env`. Для тестов используется in-memory SQLite, для dev можно использовать файловый SQLite:
```
DATABASE_URL=sqlite:///./test.db
```

### Ошибки при миграции

Удалите БД и примените миграции заново:
```bash
rm test.db  # или vpn_manager.db
alembic upgrade head
```

## Полезные команды

### Создать нового администратора
```bash
python scripts/create_admin.py
```

### Проверить покрытие конкретного модуля
```bash
pytest --cov=app.utils.security --cov-report=term-missing tests/test_auth.py
```

### Запустить тесты с выводом print statements
```bash
pytest -s
```

### Остановить на первой ошибке
```bash
pytest -x
```

### Запустить последние упавшие тесты
```bash
pytest --lf
```
