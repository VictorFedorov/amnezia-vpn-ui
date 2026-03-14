#!/bin/bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "${RED}✗ $1${NC}"; exit 1; }
info() { echo -e "${CYAN}→ $1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="/tmp/amnezia_deploy"

echo ""
echo "══════════════════════════════════════════════════"
echo "   AmneziaVPN UI — деплой через готовые образы"
echo "══════════════════════════════════════════════════"
echo ""

# ─── Ввод параметров ──────────────────────────────────────────────────────────
read -p "IP-адрес сервера: " SERVER_IP
read -p "Пользователь SSH [root]: " SERVER_USER
SERVER_USER=${SERVER_USER:-root}
read -p "SSH-порт [22]: " SERVER_PORT
SERVER_PORT=${SERVER_PORT:-22}

echo ""
echo "Аутентификация:"
echo "  1) Пароль"
echo "  2) SSH-ключ"
read -p "Выбери [1/2]: " AUTH_TYPE

CONTROL_SOCKET="$TMP_DIR/ssh_master"
CONTROL_OPTS="-o ControlMaster=auto -o ControlPath=$CONTROL_SOCKET -o ControlPersist=10m"

if [ "$AUTH_TYPE" = "2" ]; then
    read -p "Путь к приватному ключу [~/.ssh/id_rsa]: " SSH_KEY
    SSH_KEY=${SSH_KEY:-~/.ssh/id_rsa}
    BASE_OPTS="-i $SSH_KEY -p $SERVER_PORT -o StrictHostKeyChecking=no"
else
    BASE_OPTS="-p $SERVER_PORT -o StrictHostKeyChecking=no"
fi

read -p "Путь на сервере [/opt/amnezia_vpn_ui]: " REMOTE_DIR
REMOTE_DIR=${REMOTE_DIR:-/opt/amnezia_vpn_ui}

SSH="ssh $BASE_OPTS $CONTROL_OPTS $SERVER_USER@$SERVER_IP"
SCP="scp $BASE_OPTS $CONTROL_OPTS"

# Открываем мастер-соединение один раз (здесь вводится пароль)
mkdir -p "$TMP_DIR"
info "Подключаемся к серверу (введи пароль один раз)..."
ssh $BASE_OPTS -o ControlMaster=yes -o ControlPath="$CONTROL_SOCKET" \
    -o ControlPersist=10m -fN "$SERVER_USER@$SERVER_IP"

cleanup() {
    ssh -O exit -o ControlPath="$CONTROL_SOCKET" "$SERVER_USER@$SERVER_IP" 2>/dev/null || true
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo ""
echo "─── Параметры ──────────────────────────────────"
echo "  Сервер: $SERVER_USER@$SERVER_IP:$SERVER_PORT"
echo "  Путь:   $REMOTE_DIR"
echo ""
read -p "Продолжить? [y/N]: " CONFIRM
[ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ] || err "Отменено"

# ─── Проверки ──────────────────────────────────────────────────────────────────
echo ""
echo "─── Проверки ───────────────────────────────────"
command -v docker >/dev/null || err "Docker не найден локально"
[ -f "$SCRIPT_DIR/.env" ] || err ".env файл не найден"
info "Проверяем соединение с сервером..."
$SSH "command -v docker >/dev/null" || err "Не удалось подключиться или Docker не установлен на сервере"
ok "Все проверки пройдены"

mkdir -p "$TMP_DIR"

# ─── Сборка образов локально ──────────────────────────────────────────────────
echo ""
echo "─── Сборка образов локально ────────────────────"
cd "$SCRIPT_DIR"
docker compose build --build-arg BUILDPLATFORM=linux/amd64 \
    $(docker buildx version >/dev/null 2>&1 && echo "--platform linux/amd64" || true)
ok "Образы собраны"

# Определяем имена образов
BACKEND_IMAGE=$(docker compose config | grep -A2 'backend:' | grep 'image:' | awk '{print $2}' || true)
FRONTEND_IMAGE=$(docker compose config | grep -A2 'frontend:' | grep 'image:' | awk '{print $2}' || true)

# Если image не задан явно — docker compose генерирует имя из папки_сервис
PROJECT_NAME=$(basename "$SCRIPT_DIR" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g')
[ -z "$BACKEND_IMAGE" ] && BACKEND_IMAGE="${PROJECT_NAME}-backend"
[ -z "$FRONTEND_IMAGE" ] && FRONTEND_IMAGE="${PROJECT_NAME}-frontend"

info "Backend образ:  $BACKEND_IMAGE"
info "Frontend образ: $FRONTEND_IMAGE"

# ─── Сохранение образов ───────────────────────────────────────────────────────
echo ""
echo "─── Сохранение образов в архивы ────────────────"
info "Сохраняем backend (~может занять минуту)..."
docker save "$BACKEND_IMAGE" | gzip > "$TMP_DIR/backend.tar.gz"
ok "backend.tar.gz: $(du -sh $TMP_DIR/backend.tar.gz | cut -f1)"

info "Сохраняем frontend..."
docker save "$FRONTEND_IMAGE" | gzip > "$TMP_DIR/frontend.tar.gz"
ok "frontend.tar.gz: $(du -sh $TMP_DIR/frontend.tar.gz | cut -f1)"

# ─── Копирование файлов на сервер ─────────────────────────────────────────────
echo ""
echo "─── Копирование на сервер ──────────────────────"
$SSH "mkdir -p $REMOTE_DIR"

info "Копируем образы (это может занять несколько минут)..."
$SCP "$TMP_DIR/backend.tar.gz" "$TMP_DIR/frontend.tar.gz" "$SERVER_USER@$SERVER_IP:/tmp/"
ok "Образы скопированы"

info "Копируем файлы проекта..."
if command -v rsync >/dev/null; then
    rsync -az --progress \
        --exclude=".git" \
        --exclude="frontend/node_modules" \
        --exclude="backend/venv" \
        --exclude="backend/__pycache__" \
        --exclude="backend/data" \
        --exclude="*.pyc" \
        --exclude=".DS_Store" \
        --exclude="deploy.sh" \
        --exclude="deploy_images.sh" \
        -e "ssh $BASE_OPTS -o ControlPath=$CONTROL_SOCKET" \
        "$SCRIPT_DIR/" \
        "$SERVER_USER@$SERVER_IP:$REMOTE_DIR/"
else
    TMP_ARCHIVE="$TMP_DIR/project.tar.gz"
    tar -czf "$TMP_ARCHIVE" \
        --exclude=".git" \
        --exclude="frontend/node_modules" \
        --exclude="backend/venv" \
        --exclude="backend/__pycache__" \
        --exclude="backend/data" \
        --exclude="*.pyc" \
        --exclude=".DS_Store" \
        -C "$SCRIPT_DIR" .
    $SCP "$TMP_ARCHIVE" "$SERVER_USER@$SERVER_IP:/tmp/project.tar.gz"
    $SSH "tar -xzf /tmp/project.tar.gz -C $REMOTE_DIR && rm /tmp/project.tar.gz"
fi
ok "Файлы проекта скопированы"

# ─── Перенос БД ───────────────────────────────────────────────────────────────
echo ""
echo "─── Перенос базы данных ────────────────────────"
DB_FILE=""
CONTAINER=$(docker ps -a --filter "name=amnezia_backend" --format "{{.Names}}" 2>/dev/null | head -1)
if [ -n "$CONTAINER" ]; then
    docker cp "$CONTAINER:/app/data/vpn_manager.db" "$TMP_DIR/vpn_manager.db" 2>/dev/null && \
        DB_FILE="$TMP_DIR/vpn_manager.db" && warn "БД взята из контейнера $CONTAINER"
fi
[ -z "$DB_FILE" ] && [ -f "$SCRIPT_DIR/backend/vpn_manager.db" ] && \
    DB_FILE="$SCRIPT_DIR/backend/vpn_manager.db" && warn "БД взята из backend/vpn_manager.db"

if [ -n "$DB_FILE" ]; then
    $SCP "$DB_FILE" "$SERVER_USER@$SERVER_IP:/tmp/vpn_manager.db"
    $SSH "mkdir -p $REMOTE_DIR/backend/data && mv /tmp/vpn_manager.db $REMOTE_DIR/backend/data/vpn_manager.db"
    ok "БД перенесена"
else
    warn "БД не найдена — будет создана новая"
fi

# ─── Загрузка образов на сервере и запуск ────────────────────────────────────
echo ""
echo "─── Загрузка образов на сервере ────────────────"
$SSH "docker load < /tmp/backend.tar.gz && docker load < /tmp/frontend.tar.gz && rm /tmp/backend.tar.gz /tmp/frontend.tar.gz"
ok "Образы загружены"

echo ""
echo "─── Запуск приложения ──────────────────────────"
$SSH "cd $REMOTE_DIR && docker compose down 2>/dev/null; docker compose up -d --no-build"
ok "Приложение запущено"

echo ""
echo "─── Статус контейнеров ─────────────────────────"
$SSH "cd $REMOTE_DIR && docker compose ps"

# cleanup вызывается автоматически через trap EXIT

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Деплой завершён!${NC}"
echo -e "${GREEN}   Фронтенд: http://$SERVER_IP:5173${NC}"
echo -e "${GREEN}   Бэкенд:   http://$SERVER_IP:8000${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
