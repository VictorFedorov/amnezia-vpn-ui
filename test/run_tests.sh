#!/bin/bash
# Скрипт для быстрого запуска интеграционных тестов

set -e

echo "🚀 Запуск интеграционных тестов Amnezia VPN UI"
echo "="*50

# Проверяем, что мы в правильной директории
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Ошибка: запустите скрипт из корневой директории проекта"
    exit 1
fi

# Проверяем, что контейнеры работают
echo "📋 Проверяем статус контейнеров..."
if ! docker ps | grep -q amnezia_backend; then
    echo "❌ Backend контейнер не запущен. Запустите: docker-compose up -d"
    exit 1
fi

if ! docker ps | grep -q amnezia_frontend; then
    echo "❌ Frontend контейнер не запущен. Запустите: docker-compose up -d"
    exit 1
fi

echo "✅ Контейнеры работают"

# Проверяем наличие виртуального окружения
if [ ! -d "backend/venv" ]; then
    echo "⚠️  Виртуальное окружение не найдено. Создаем..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

# Активируем виртуальное окружение
echo "🐍 Активируем виртуальное окружение..."
source backend/venv/bin/activate

# Проверяем наличие токена
TOKEN_FILE="/tmp/api_token.txt"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "🔑 API токен не найден. Получим его..."
    echo "Введите учетные данные администратора:"
    read -p "Username: " username
    read -s -p "Password: " password
    echo ""

    if python test/get_token.py --username "$username" --password "$password"; then
        echo "✅ Токен получен"
    else
        echo "❌ Не удалось получить токен"
        exit 1
    fi
fi

# Читаем токен
TOKEN=$(cat "$TOKEN_FILE")

echo ""
echo "📝 Для запуска интеграционного теста:"
echo "1. Создайте клиента через веб-интерфейс (http://localhost:5173)"
echo "2. Получите ID клиента и сервера"
echo "3. Запустите тест:"
echo ""
echo "python test/integration_test.py --client-id <CLIENT_ID> --server-id <SERVER_ID> --token $TOKEN"
echo ""
echo "💡 Или используйте интерактивный режим:"
read -p "Введите ID клиента: " client_id
read -p "Введите ID сервера: " server_id

if [ -n "$client_id" ] && [ -n "$server_id" ]; then
    echo ""
    echo "🚀 Запускаем тест..."
    python test/integration_test.py --client-id "$client_id" --server-id "$server_id" --token "$TOKEN"
else
    echo "ℹ️  Тест не запущен. Запустите вручную с нужными ID."
fi