# Контрольный список проекта AmneziaVPN Management UI

## Этап 1: Исследование (ЗАВЕРШЕН)

- [x] ARCHITECTURE.md — диаграммы и архитектура
- [x] SUMMARY.md — описание функциональности
- [x] DATABASE_SCHEMA.md — ER-диаграмма и модели
- [x] ARC42.md — ARC42 архитектурная документация

## Этап 2: Backend (ЗАВЕРШЕН)

### Инфраструктура
- [x] FastAPI + Uvicorn
- [x] SQLAlchemy ORM + Alembic миграции (9 миграций)
- [x] SQLite (dev) / PostgreSQL (prod)
- [x] JWT аутентификация (python-jose, passlib)
- [x] Rate limiting (slowapi)
- [x] Шифрование SSH-паролей (Fernet)
- [x] APScheduler — фоновая синхронизация трафика
- [x] Docker-контейнер (Python 3.10-slim)

### Модели данных
- [x] User — администраторы системы
- [x] VpnClient — VPN клиенты (конечные пользователи)
- [x] Server — VPS серверы с SSH credentials
- [x] ClientConfig — конфигурации устройств
- [x] TrafficHistory / TrafficStatsHourly / TrafficStatsDaily
- [x] SubscriptionPlan / Subscription
- [x] ConnectionEvent
- [x] EndpointLog — трекинг endpoint IP для детекции шаринга

### API Routes (9 групп)
- [x] `/api/auth` — login, logout, me
- [x] `/api/users` — CRUD админов
- [x] `/api/vpn-clients` — CRUD VPN клиентов
- [x] `/api/servers` — CRUD серверов + fetch-users + enable-xray-stats
- [x] `/api/configs` — CRUD конфигов + toggle-active + QR + bulk + endpoint-history + sharing-alerts
- [x] `/api/traffic` — realtime, top-users, by-server
- [x] `/api/subscriptions` — CRUD + extend
- [x] `/api/subscription-plans` — CRUD тарифных планов
- [x] `/api/ws` — WebSocket (realtime push-уведомления)

### Сервисы
- [x] ssh_manager.py — SSH подключения
- [x] awg_manager.py — AmneziaWG
- [x] wireguard_manager.py — стандартный WireGuard
- [x] xray_manager.py — VLESS, VMESS, Trojan, Shadowsocks
- [x] traffic_sync.py — фоновый polling трафика

### Тесты
- [x] test_auth.py, test_auth_integration.py
- [x] test_models.py
- [x] test_servers_integration.py
- [x] test_users_integration.py
- [x] test_ssh_manager.py
- [x] test_validation.py

## Этап 3: Frontend (ЗАВЕРШЕН)

### Инфраструктура
- [x] React 19 + TypeScript + Vite
- [x] Tailwind CSS
- [x] Zustand (state management)
- [x] React Router DOM
- [x] Axios (HTTP клиент)
- [x] Recharts (графики)
- [x] qrcode.react
- [x] TanStack React Table
- [x] Docker-контейнер (Node 22-alpine)

### Страницы (9)
- [x] Login.tsx — авторизация
- [x] Dashboard.tsx — статистика, графики протоколов, топ пользователей
- [x] Users.tsx — управление админами
- [x] Servers.tsx — управление серверами
- [x] UsersOnServers.tsx — клиенты/устройства на серверах
- [x] Subscriptions.tsx — подписки
- [x] SubscriptionPlans.tsx — тарифные планы
- [x] Traffic.tsx — мониторинг трафика
- [x] ImportConfig.tsx — импорт конфигураций

### Компоненты и сервисы
- [x] Layout.tsx — навигация, sidebar
- [x] authStore.ts — Zustand store (аутентификация)
- [x] realtimeStore.ts — Zustand store (WebSocket, auto-reconnect)
- [x] api.ts — API клиент (auth, users, vpnClients, servers, configs, traffic, subscriptions, plans, sharing)
- [x] configDecoder.ts — парсинг VPN конфигов

## Этап 4: Docker и деплой (ЗАВЕРШЕН)

- [x] docker-compose.yml (backend + frontend)
- [x] backend/Dockerfile
- [x] frontend/Dockerfile
- [x] Alembic миграции при старте
- [x] Автосоздание admin при первом запуске
- [x] Volume mount для live-reload в dev
- [x] .env / .env.example

## Этап 5: Безопасность (ЗАВЕРШЕН — 01.03.2026)

- [x] Убраны hardcoded credentials из Login.tsx (блок "Default credentials")
- [x] Аутентификация на VPN clients endpoints (все 5)
- [x] Аутентификация на Traffic endpoints (все 3)
- [x] Аутентификация на GET subscription plans
- [x] CORS — используются настроенные origins вместо `["*"]`
- [x] Защита от command injection в SSH-командах (validate_wg_public_key, validate_cidr, shlex.quote)
- [x] Отдельный ENCRYPTION_KEY (с fallback на SECRET_KEY)
- [x] Удалены скрипты с hardcoded credentials (sync_peers.py, create_config.py, check_server_peers.py, create_user.py)
- [x] Убран hardcoded ADMIN_PASSWORD=admin123 из .env

## Что ещё можно сделать

### Безопасность
- [ ] HTTPS / TLS терминация (nginx reverse proxy)
- [ ] Secure headers (HSTS, CSP, X-Frame-Options)
- [ ] Валидация входных данных на фронте (Zod)
- [ ] Ротация JWT токенов (refresh tokens)
- [ ] Аудит-лог действий админа
- [ ] SSH_STRICT_HOST_KEY_CHECKING=true для production

### Production
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Nginx reverse proxy с SSL
- [ ] PostgreSQL вместо SQLite для production
- [ ] Мониторинг (healthcheck, alerting)
- [ ] Backup стратегия для БД
- [ ] Логирование в файл / external logging

### Функциональность
- [x] WebSocket для real-time трафика (ws.py + realtimeStore.ts)
- [ ] Экспорт статистики (CSV/PDF)
- [ ] Уведомления (истечение подписок, проблемы с серверами)
- [ ] Мультиязычность (i18n)
- [ ] Тёмная тема
