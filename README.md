# AmneziaVPN Management UI

Веб-панель управления для self-hosted VPN-серверов на базе AmneziaVPN. Позволяет централизованно управлять VPS-серверами, VPN-клиентами, конфигурациями устройств, подписками и мониторить трафик в реальном времени.

## Возможности

- Управление несколькими VPS-серверами (добавление, SSH-подключение, мониторинг статуса)
- Управление VPN-клиентами и конфигурациями устройств
- Мульти-протокольность: AmneziaWG, WireGuard, XRay (VLESS, VMess, Trojan, Shadowsocks)
- Мониторинг трафика в реальном времени с историческими данными
- WebSocket push-уведомления (обновления трафика, автоблокировки)
- Управление тарифными планами и подписками (с автоблокировкой по сроку и лимиту трафика)
- Генерация QR-кодов для конфигураций
- Импорт существующих конфигураций
- Детекция шаринга конфигов (трекинг endpoint IP)
- Массовое создание конфигов (Bulk Create)
- Dashboard с агрегированной статистикой

## Технологический стек

| Компонент | Технология |
|-----------|-----------|
| Backend | Python 3.10+ / FastAPI / Uvicorn |
| ORM | SQLAlchemy 2.0 + Alembic (9 миграций) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| SSH | Paramiko (управление VPN-серверами) |
| Auth | JWT (python-jose) + bcrypt |
| Шифрование | Fernet (SSH-пароли в БД) |
| Фоновые задачи | APScheduler |
| Frontend | React 19 + TypeScript + Vite |
| Стилизация | Tailwind CSS |
| State | Zustand (auth + realtime WebSocket) |
| Таблицы | TanStack React Table |
| Графики | Recharts |
| HTTP-клиент | Axios |

## Структура проекта

```
amnezia_vpn_ui/
├── backend/                # Backend API (Python / FastAPI)
│   ├── app/
│   │   ├── main.py         # Точка входа: FastAPI, CORS, роуты, startup
│   │   ├── api/
│   │   │   ├── schemas.py  # Pydantic-модели (request/response)
│   │   │   └── routes/     # HTTP-обработчики
│   │   │       ├── auth.py, users.py, vpn_clients.py
│   │   │       ├── servers.py, configs.py, traffic.py
│   │   │       ├── subscriptions.py, subscription_plans.py
│   │   │       └── ws.py   # WebSocket endpoint
│   │   ├── services/       # Бизнес-логика
│   │   │   ├── ssh_manager.py, awg_manager.py
│   │   │   ├── wireguard_manager.py, xray_manager.py
│   │   │   └── traffic_sync.py  # Фоновая синхронизация трафика
│   │   ├── models/         # SQLAlchemy ORM-модели (11 таблиц)
│   │   ├── core/           # config.py, database.py
│   │   └── utils/          # security.py, encryption.py
│   ├── alembic/            # Миграции БД
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/               # Frontend UI (React / TypeScript)
│   ├── src/
│   │   ├── pages/          # 9 страниц (Login, Dashboard, Servers, ...)
│   │   ├── components/     # UI-компоненты (Layout, dashboard/, users/, ...)
│   │   ├── stores/         # Zustand (authStore, realtimeStore)
│   │   ├── services/       # api.ts (Axios + все API-namespace'ы)
│   │   ├── hooks/, types/, utils/
│   │   └── styles/
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── test/                   # Интеграционные тесты
├── docker-compose.yml
├── .env.example            # Шаблон переменных окружения
├── ARCHITECTURE.md         # Подробная архитектура
├── ARC42.md                # ARC42 архитектурная документация
├── SUMMARY.md              # Описание функциональности
├── DATABASE_SCHEMA.md      # ER-диаграмма и модели
└── CHECKLIST.md            # Контрольный список реализации
```

## Установка и запуск

### Требования

- Python 3.10+
- Node.js 22+
- npm
- SSH-доступ к VPN-серверам с AmneziaVPN (Docker-контейнеры `amnezia-awg`, `amnezia-xray`)

### Быстрый старт (Docker)

```bash
# 1. Клонирование
git clone <repo-url>
cd amnezia_vpn_ui

# 2. Настройка окружения
cp .env.example .env
# Отредактируйте .env: задайте SECRET_KEY, SSH-credentials, ADMIN_PASSWORD

# 3. Запуск
docker compose up --build

# 4. Доступ
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

### Запуск для разработки

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
cp ../.env.example .env   # Настройте .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (отдельный терминал)
cd frontend
npm install
npm run dev
```

## Переменные окружения

Создайте `.env` на основе `.env.example`:

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `DATABASE_URL` | Строка подключения к БД | `sqlite:///./vpn_manager.db` |
| `SECRET_KEY` | Ключ для подписи JWT-токенов | **Обязательно задать** |
| `ALGORITHM` | Алгоритм JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни JWT (минуты) | `43200` (30 дней) |
| `ENCRYPTION_KEY` | Ключ Fernet для SSH-паролей | Fallback на SECRET_KEY |
| `SSH_HOST` / `SSH_PORT` / `SSH_USER` | SSH по умолчанию (per-server в БД) | — |
| `CORS_ORIGINS` | Разрешённые CORS-домены | `http://localhost:5173` |
| `TRAFFIC_POLL_INTERVAL` | Интервал синхронизации трафика (сек) | `300` (5 мин) |
| `ADMIN_USERNAME` | Логин первого админа | `admin` |
| `ADMIN_PASSWORD` | Пароль первого админа | Авто (в логах) |

Генерация ключей:
```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## API Endpoints

| Группа | Путь | Описание |
|--------|------|----------|
| Auth | `POST /api/auth/login` | Авторизация (JWT) |
| Auth | `GET /api/auth/me` | Текущий пользователь |
| Users | `GET/POST /api/users` | CRUD системных администраторов |
| VPN Clients | `GET/POST /api/vpn-clients` | CRUD VPN-клиентов |
| Servers | `GET/POST /api/servers` | CRUD VPS-серверов |
| Servers | `POST /api/servers/{id}/fetch-users` | Импорт пиров с сервера |
| Configs | `GET/POST /api/configs` | CRUD конфигураций |
| Configs | `POST /api/configs/bulk` | Массовое создание |
| Configs | `GET /api/configs/{id}/endpoint-history` | История endpoint IP |
| Configs | `GET /api/configs/sharing-alerts` | Детекция шаринга |
| Traffic | `GET /api/traffic/realtime` | Текущий трафик |
| Traffic | `GET /api/traffic/top-users` | Топ по трафику |
| Traffic | `GET /api/traffic/by-server` | Трафик по серверам |
| Subscriptions | `GET/POST /api/subscriptions` | CRUD подписок |
| Plans | `GET/POST /api/subscription-plans` | CRUD тарифных планов |
| WebSocket | `WS /api/ws?token=...` | Realtime-обновления |

Полная документация: http://localhost:8000/docs (Swagger UI)

## Безопасность

- JWT-аутентификация на всех API endpoints (кроме `/login`)
- bcrypt для хеширования паролей
- Fernet-шифрование SSH-паролей в БД
- Rate limiting на `/login` (slowapi)
- CORS настраивается через env
- Валидация входных данных (Pydantic)
- Защита от command injection в SSH-командах (shlex.quote)

## Лицензия

MIT
