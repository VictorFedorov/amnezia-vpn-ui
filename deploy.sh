#!/bin/bash
set -e

# ─── Цвета ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "${RED}✗ $1${NC}"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "══════════════════════════════════════════════"
echo "   AmneziaVPN UI — деплой на удалённый сервер"
echo "══════════════════════════════════════════════"
echo ""

# ─── Ввод параметров ──────────────────────────────────────────────────────────
read -p "IP-адрес сервера: " SERVER_IP
read -p "Пользователь SSH (например, root): " SERVER_USER
read -p "SSH-порт [22]: " SERVER_PORT
SERVER_PORT=${SERVER_PORT:-22}

echo ""
echo "Аутентификация:"
echo "  1) Пароль"
echo "  2) SSH-ключ"
read -p "Выбери [1/2]: " AUTH_TYPE

if [ "$AUTH_TYPE" = "2" ]; then
    read -p "Путь к приватному ключу [~/.ssh/id_rsa]: " SSH_KEY
    SSH_KEY=${SSH_KEY:-~/.ssh/id_rsa}
    SSH_OPTS="-i $SSH_KEY -p $SERVER_PORT -o StrictHostKeyChecking=no"
    SCP_OPTS="-i $SSH_KEY -P $SERVER_PORT -o StrictHostKeyChecking=no"
else
    SSH_OPTS="-p $SERVER_PORT -o StrictHostKeyChecking=no"
    SCP_OPTS="-P $SERVER_PORT -o StrictHostKeyChecking=no"
    warn "Будет запрошен пароль при подключении"
fi

read -p "Путь на сервере [/opt/amnezia_vpn_ui]: " REMOTE_DIR
REMOTE_DIR=${REMOTE_DIR:-/opt/amnezia_vpn_ui}

SSH="ssh $SSH_OPTS $SERVER_USER@$SERVER_IP"
SCP="scp $SCP_OPTS"

echo ""
echo "─── Параметры деплоя ───────────────────────"
echo "  Сервер:  $SERVER_USER@$SERVER_IP:$SERVER_PORT"
echo "  Путь:    $REMOTE_DIR"
echo ""
read -p "Продолжить? [y/N]: " CONFIRM
[ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ] || err "Отменено"

# ─── Проверка зависимостей локально ──────────────────────────────────────────
echo ""
echo "─── Проверка локальных зависимостей ────────"
command -v ssh  >/dev/null || err "ssh не найден"
command -v scp  >/dev/null || err "scp не найден"
command -v rsync >/dev/null && USE_RSYNC=1 || USE_RSYNC=0
[ -f "$SCRIPT_DIR/.env" ] || err ".env файл не найден в $SCRIPT_DIR"
ok "Всё готово"

# ─── Проверка SSH-соединения ──────────────────────────────────────────────────
echo ""
echo "─── Проверка подключения к серверу ─────────"
$SSH "echo ok" >/dev/null || err "Не удалось подключиться к серверу"
ok "SSH соединение установлено"

# ─── Проверка Docker на сервере ───────────────────────────────────────────────
echo ""
echo "─── Проверка Docker на сервере ─────────────"
$SSH "command -v docker >/dev/null" || err "Docker не установлен на сервере. Установи: https://docs.docker.com/engine/install/"
$SSH "command -v docker compose >/dev/null || docker compose version >/dev/null 2>&1" || \
    err "Docker Compose не найден. Установи плагин docker compose."
ok "Docker и Docker Compose найдены"

# ─── Создание директории на сервере ──────────────────────────────────────────
echo ""
echo "─── Подготовка сервера ──────────────────────"
$SSH "mkdir -p $REMOTE_DIR"
ok "Директория $REMOTE_DIR создана"

# ─── Копирование файлов ───────────────────────────────────────────────────────
echo ""
echo "─── Копирование файлов ─────────────────────"

EXCLUDES=(
    "--exclude=.git"
    "--exclude=frontend/node_modules"
    "--exclude=backend/venv"
    "--exclude=backend/__pycache__"
    "--exclude=backend/**/__pycache__"
    "--exclude=backend/.pytest_cache"
    "--exclude=backend/data"
    "--exclude=*.pyc"
    "--exclude=.DS_Store"
    "--exclude=deploy.sh"
)

if [ "$USE_RSYNC" = "1" ]; then
    RSYNC_SSH="ssh $SSH_OPTS"
    rsync -az --progress "${EXCLUDES[@]}" \
        -e "$RSYNC_SSH" \
        "$SCRIPT_DIR/" \
        "$SERVER_USER@$SERVER_IP:$REMOTE_DIR/"
else
    warn "rsync не найден, используем scp (медленнее)"
    # Создаём временный архив без лишних папок
    TMP_ARCHIVE="/tmp/amnezia_vpn_ui_deploy.tar.gz"
    tar -czf "$TMP_ARCHIVE" \
        --exclude=".git" \
        --exclude="frontend/node_modules" \
        --exclude="backend/venv" \
        --exclude="backend/__pycache__" \
        --exclude="backend/data" \
        --exclude="*.pyc" \
        --exclude=".DS_Store" \
        --exclude="deploy.sh" \
        -C "$SCRIPT_DIR" .
    $SCP "$TMP_ARCHIVE" "$SERVER_USER@$SERVER_IP:/tmp/"
    $SSH "tar -xzf /tmp/amnezia_vpn_ui_deploy.tar.gz -C $REMOTE_DIR && rm /tmp/amnezia_vpn_ui_deploy.tar.gz"
    rm -f "$TMP_ARCHIVE"
fi
ok "Файлы скопированы"

# ─── Перенос БД (если есть) ───────────────────────────────────────────────────
echo ""
echo "─── Перенос базы данных ────────────────────"

DB_FILE="$SCRIPT_DIR/backend/vpn_manager.db"
DB_DOCKER_VOLUME=""

# Проверяем локальный Docker volume
if command -v docker >/dev/null 2>&1; then
    CONTAINER=$(docker ps -a --filter "name=amnezia_backend" --format "{{.Names}}" 2>/dev/null | head -1)
    if [ -n "$CONTAINER" ]; then
        warn "Найден локальный контейнер $CONTAINER — копируем БД из него"
        docker cp "$CONTAINER:/app/data/vpn_manager.db" /tmp/vpn_manager.db 2>/dev/null && \
            DB_FILE="/tmp/vpn_manager.db" && DB_DOCKER_VOLUME=1
    fi
fi

if [ -f "$DB_FILE" ]; then
    $SCP "$DB_FILE" "$SERVER_USER@$SERVER_IP:/tmp/vpn_manager.db"
    $SSH "mkdir -p $REMOTE_DIR/backend/data && mv /tmp/vpn_manager.db $REMOTE_DIR/backend/data/vpn_manager.db"
    ok "БД перенесена"
    [ -n "$DB_DOCKER_VOLUME" ] && rm -f /tmp/vpn_manager.db
else
    warn "БД не найдена — будет создана новая при первом запуске"
fi

# ─── Запуск на сервере ────────────────────────────────────────────────────────
echo ""
echo "─── Запуск приложения ──────────────────────"
$SSH "cd $REMOTE_DIR && docker compose down 2>/dev/null; docker compose up -d --build"
ok "Приложение запущено"

# ─── Проверка ─────────────────────────────────────────────────────────────────
echo ""
echo "─── Статус контейнеров ─────────────────────"
$SSH "cd $REMOTE_DIR && docker compose ps"

echo ""
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Деплой завершён!${NC}"
echo -e "${GREEN}   Фронтенд: http://$SERVER_IP:5173${NC}"
echo -e "${GREEN}   Бэкенд:   http://$SERVER_IP:8000${NC}"
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo ""
