# ARC42 — Архитектурная документация AmneziaVPN Management UI

**Версия:** 1.0
**Дата:** 2026-03-01
**Статус проекта:** MVP (частичная реализация)

---

## Содержание

1. [Введение и цели](#1-введение-и-цели)
2. [Ограничения](#2-ограничения)
3. [Контекст и область применения](#3-контекст-и-область-применения)
4. [Стратегия решения](#4-стратегия-решения)
5. [Представление строительных блоков](#5-представление-строительных-блоков)
6. [Представление времени выполнения](#6-представление-времени-выполнения)
7. [Представление развёртывания](#7-представление-развёртывания)
8. [Сквозные концепции](#8-сквозные-концепции)
9. [Архитектурные решения](#9-архитектурные-решения)
10. [Требования к качеству](#10-требования-к-качеству)
11. [Риски и технический долг](#11-риски-и-технический-долг)
12. [Глоссарий](#12-глоссарий)

---

## 1. Введение и цели

### 1.1 Описание системы

AmneziaVPN Management UI — веб-панель управления для self-hosted VPN-серверов на базе AmneziaVPN. Система позволяет администратору централизованно управлять VPS-серверами, VPN-клиентами, конфигурациями устройств, подписками и мониторить трафик в реальном времени.

### 1.2 Основные цели

| Приоритет | Цель | Описание |
|-----------|------|----------|
| 1 | Централизованное управление | Единая точка управления несколькими VPN-серверами через веб-интерфейс |
| 2 | Мульти-протокольность | Поддержка AWG, WireGuard, VLESS, VMess, Trojan, Shadowsocks |
| 3 | Мониторинг трафика | Сбор и визуализация статистики трафика в реальном времени |
| 4 | Управление подписками | Тарифные планы, лимиты трафика, сроки действия |
| 5 | Простота развёртывания | Развёртывание через Docker Compose на VPS |

### 1.3 Заинтересованные стороны (Stakeholders)

| Роль | Ожидания |
|------|----------|
| Администратор VPN-сервиса | Удобный веб-интерфейс для управления серверами, клиентами и мониторинга |
| VPN-клиент (конечный пользователь) | Стабильное VPN-подключение, получение конфигурации |
| Разработчик / DevOps | Простота развёртывания, понятная кодовая база, тесты |

### 1.4 Функциональные требования

- **FR-1**: Аутентификация администраторов через JWT
- **FR-2**: CRUD-операции над системными пользователями (администраторами)
- **FR-3**: Управление VPS-серверами (добавление, SSH-подключение, мониторинг статуса)
- **FR-4**: Управление VPN-клиентами и их конфигурациями
- **FR-5**: Поддержка нескольких VPN-протоколов (AWG, WireGuard, XRay-based)
- **FR-6**: Мониторинг трафика в реальном времени с историческими данными
- **FR-7**: Управление тарифными планами и подписками
- **FR-8**: Генерация QR-кодов для конфигураций
- **FR-9**: Импорт существующих конфигураций
- **FR-10**: Dashboard с агрегированной статистикой

---

## 2. Ограничения

### 2.1 Технические ограничения

| ID | Ограничение | Обоснование |
|----|-------------|-------------|
| TC-1 | Python 3.10+ для бэкенда | Требуется для FastAPI, async/await, type hints |
| TC-2 | Node.js 22+ для фронтенда | Требуется Vite 7, React 19 |
| TC-3 | PostgreSQL (прод) / SQLite (dev) | Единственные поддерживаемые СУБД |
| TC-4 | Docker и Docker Compose | Обязательны для развёртывания |
| TC-5 | SSH-доступ к VPN-серверам | Управление VPN-сервисами через SSH (Paramiko) |
| TC-6 | AmneziaVPN Docker-контейнеры | На целевых серверах должны работать `amnezia-awg` и/или `amnezia-xray` |

### 2.2 Организационные ограничения

| ID | Ограничение | Обоснование |
|----|-------------|-------------|
| OC-1 | Self-hosted only | Панель предназначена для самостоятельного развёртывания |
| OC-2 | Веб-интерфейс (desktop-браузеры) | Нет мобильных приложений |
| OC-3 | Однопользовательская авторизация | Все администраторы имеют равные права (нет RBAC) |

### 2.3 Конвенции

- REST API с JSON
- Pydantic для валидации запросов/ответов
- Alembic для миграций БД
- Conventional naming: snake_case (Python), camelCase (TypeScript)
- Git-flow (фича-ветки)

---

## 3. Контекст и область применения

### 3.1 Бизнес-контекст

```
                    ┌──────────────────────────────────────────────┐
                    │        AmneziaVPN Management UI              │
                    │                                              │
  ┌──────────┐     │  ┌────────────┐      ┌──────────────────┐   │     ┌──────────────┐
  │          │ HTTP │  │            │ REST │                  │   │ SSH │              │
  │ Админи-  │─────┼─▶│  Frontend  │─────▶│    Backend       │───┼────▶│ VPN-сервер 1 │
  │ стратор  │     │  │  (React)   │      │   (FastAPI)      │   │     │ (VPS + AWG)  │
  │          │◀────┼──│            │◀─────│                  │   │     └──────────────┘
  └──────────┘     │  └────────────┘      │                  │   │     ┌──────────────┐
                    │                      │                  │───┼────▶│ VPN-сервер 2 │
                    │                      └────────┬─────────┘   │     │ (VPS + XRay) │
                    │                               │             │     └──────────────┘
                    │                      ┌────────▼─────────┐   │     ┌──────────────┐
                    │                      │   PostgreSQL /   │   │     │ VPN-сервер N │
                    │                      │     SQLite       │   │     │              │
                    │                      └──────────────────┘   │     └──────────────┘
                    └──────────────────────────────────────────────┘
```

**Внешние участники:**

| Участник | Описание | Протокол |
|----------|----------|----------|
| Администратор | Управляет VPN-инфраструктурой через веб-браузер | HTTPS |
| VPN-серверы (VPS) | Серверы с AmneziaVPN (Docker-контейнеры `amnezia-awg`, `amnezia-xray`) | SSH (TCP/22) |
| VPN-клиенты (устройства) | Конечные пользователи, подключающиеся к VPN-серверам | WireGuard/XRay |

### 3.2 Технический контекст

```
  ┌─────────────────────┐          ┌────────────────────────────────────────────┐
  │     Браузер          │          │            Docker Compose                  │
  │  (Chrome/Firefox)    │          │                                            │
  │                      │  :5173   │  ┌────────────────┐   ┌─────────────────┐ │
  │  React SPA           │◀────────▶│  │  frontend      │   │   backend       │ │
  │  (Vite Dev / Nginx)  │          │  │  Node 22       │   │   Python 3.10   │ │
  │                      │          │  │  :5173         │   │   :8000         │ │
  └─────────────────────┘          │  └────────────────┘   └───────┬─────────┘ │
                                    │                               │           │
                                    │                      ┌───────▼─────────┐ │
                                    │                      │   PostgreSQL    │ │
                                    │                      │   :5432         │ │
                                    │                      └─────────────────┘ │
                                    └────────────────────────────────────────────┘
                                                                    │
                                                             SSH :22 │
                                                                    ▼
                                                    ┌───────────────────────────┐
                                                    │  Remote VPS               │
                                                    │  ┌───────────────────┐    │
                                                    │  │ amnezia-awg       │    │
                                                    │  │ (Docker container)│    │
                                                    │  └───────────────────┘    │
                                                    │  ┌───────────────────┐    │
                                                    │  │ amnezia-xray      │    │
                                                    │  │ (Docker container)│    │
                                                    │  └───────────────────┘    │
                                                    └───────────────────────────┘
```

**Интерфейсы:**

| Интерфейс | Технология | Описание |
|-----------|------------|----------|
| Frontend ↔ Backend | REST API (HTTP/JSON) | Axios с JWT Bearer-токеном |
| Backend ↔ Database | SQLAlchemy ORM | Async-совместимый доступ |
| Backend ↔ VPN-серверы | SSH (Paramiko) | Выполнение команд в Docker-контейнерах |
| Backend ↔ XRay API | gRPC / HTTP | Stats API для XRay (через SSH-туннель) |

---

## 4. Стратегия решения

### 4.1 Ключевые технологические решения

| Решение | Выбор | Альтернативы | Обоснование |
|---------|-------|-------------|-------------|
| Бэкенд-фреймворк | FastAPI | Django, Flask | Async, авто-документация (OpenAPI), Pydantic, высокая производительность |
| Фронтенд-фреймворк | React 19 + TypeScript | Vue.js, Svelte, Angular | Большая экосистема, TypeScript-поддержка, зрелость |
| Сборщик фронтенда | Vite 7 | Webpack, Parcel | Быстрая сборка, HMR, нативная поддержка TS |
| State Management | Zustand | Redux, MobX, Context API | Минимальный boilerplate, простота API |
| CSS-фреймворк | Tailwind CSS | Bootstrap, Material UI | Utility-first, минимальный bundle, гибкость |
| ORM | SQLAlchemy 2.0 | Tortoise ORM, Django ORM | Зрелость, миграции (Alembic), гибкость |
| SSH-клиент | Paramiko | asyncssh, fabric | Стабильность, документация, широкое использование |
| Аутентификация | JWT (python-jose) | Session-based, OAuth2 | Stateless, подходит для SPA |
| Контейнеризация | Docker Compose | Kubernetes, bare-metal | Простота для self-hosted, низкий порог входа |

### 4.2 Архитектурные паттерны

| Паттерн | Где применяется | Описание |
|---------|----------------|----------|
| Client-Server | Общая архитектура | SPA-клиент + REST API-сервер |
| Layered Architecture | Backend | Routes → Services → Models → Database |
| Repository Pattern | Backend (implicit) | SQLAlchemy ORM абстрагирует доступ к данным |
| Dependency Injection | Backend (FastAPI) | `Depends()` для DB-сессий, аутентификации |
| Observer (Polling + Push) | Traffic Sync + WebSocket | Фоновый сбор статистики (5 мин) + WebSocket push для мгновенных обновлений |
| Strategy Pattern | Protocol Managers | AWGManager, WireGuardManager, XRayManager — единый интерфейс |

### 4.3 Подходы к достижению качества

| Атрибут качества | Подход |
|------------------|--------|
| Безопасность | JWT, bcrypt, шифрование SSH-паролей, rate limiting |
| Масштабируемость | Мульти-серверная архитектура, агрегация статистики |
| Надёжность | Обработка ошибок SSH, переподключение, логирование |
| Сопровождаемость | Типизация (TypeScript + Pydantic), миграции БД |
| Тестируемость | pytest, раздельные unit/integration тесты |

---

## 5. Представление строительных блоков

### 5.1 Уровень 1 — Общая декомпозиция

```
┌──────────────────────────────────────────────────────────────────────┐
│                     AmneziaVPN Management UI                         │
│                                                                      │
│  ┌─────────────────────────┐     ┌──────────────────────────────┐   │
│  │       Frontend          │     │          Backend              │   │
│  │     (React SPA)         │────▶│        (FastAPI)              │   │
│  │                         │     │                              │   │
│  │  - Pages                │     │  - API Routes               │   │
│  │  - Components           │     │  - Services                 │   │
│  │  - Stores               │     │  - Models                   │   │
│  │  - Services (API)       │     │  - Core (Config, DB)        │   │
│  │  - Hooks                │     │  - Utils (Security, Crypto) │   │
│  └─────────────────────────┘     └──────────────┬───────────────┘   │
│                                                  │                   │
│                                         ┌────────▼────────┐         │
│                                         │    Database      │         │
│                                         │ PostgreSQL/SQLite│         │
│                                         └─────────────────┘         │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 Уровень 2 — Backend

```
backend/app/
├── main.py                      # Точка входа: FastAPI app, CORS, роуты, startup
│
├── api/                         # Слой представления (Presentation Layer)
│   ├── schemas.py               # Pydantic-модели (request/response DTO)
│   └── routes/                  # HTTP-обработчики
│       ├── auth.py              # POST /login, /logout, GET /me
│       ├── users.py             # CRUD /users
│       ├── vpn_clients.py       # CRUD /vpn-clients
│       ├── servers.py           # CRUD /servers, GET /servers/{id}/configs
│       ├── configs.py           # CRUD /configs
│       ├── traffic.py           # GET /traffic/realtime, /top-users, /by-server
│       ├── subscriptions.py     # CRUD /subscriptions
│       ├── subscription_plans.py # CRUD /subscription-plans
│       └── ws.py                # WebSocket endpoint (realtime updates)
│
├── services/                    # Слой бизнес-логики (Business Logic Layer)
│   ├── ssh_manager.py           # SSH-подключения к VPS (Paramiko)
│   ├── awg_manager.py           # Управление AmneziaWG-протоколом
│   ├── wireguard_manager.py     # Управление стандартным WireGuard
│   ├── xray_manager.py          # Управление XRay (VLESS/VMess/Trojan/SS)
│   └── traffic_sync.py          # Фоновая синхронизация трафика (APScheduler)
│
├── models/                      # Слой данных (Data Layer)
│   └── __init__.py              # SQLAlchemy ORM-модели (11 таблиц)
│
├── core/                        # Инфраструктурный слой
│   ├── config.py                # Pydantic Settings (env-переменные)
│   └── database.py              # SQLAlchemy Engine + SessionLocal
│
└── utils/                       # Утилиты
    ├── security.py              # JWT-токены, хеширование паролей
    └── encryption.py            # Шифрование SSH-паролей (Fernet)
```

**Описание компонентов Backend:**

| Компонент | Ответственность | Зависимости |
|-----------|----------------|-------------|
| `main.py` | Инициализация приложения, middleware, startup-события | FastAPI, routes, database, scheduler |
| `api/routes/*` | Обработка HTTP-запросов, валидация, авторизация | schemas, models, services, security |
| `api/schemas.py` | Определение структуры request/response (DTO) | Pydantic |
| `services/ssh_manager.py` | SSH-подключения к удалённым серверам | Paramiko |
| `services/awg_manager.py` | Команды для AmneziaWG (`wg show awg0 dump`) | ssh_manager |
| `services/wireguard_manager.py` | Команды для WireGuard | ssh_manager |
| `services/xray_manager.py` | Взаимодействие с XRay Stats API | ssh_manager |
| `services/traffic_sync.py` | Периодический сбор статистики с серверов | protocol managers, models, APScheduler |
| `models/__init__.py` | ORM-сущности и связи | SQLAlchemy |
| `core/config.py` | Конфигурация из env-переменных | Pydantic Settings |
| `core/database.py` | Подключение к БД, фабрика сессий | SQLAlchemy |
| `utils/security.py` | JWT-создание/валидация, bcrypt | python-jose, passlib |
| `utils/encryption.py` | Шифрование SSH-паролей в БД | cryptography (Fernet) |

### 5.3 Уровень 2 — Frontend

```
frontend/src/
├── main.tsx                     # Точка входа React
├── App.tsx                      # React Router, ProtectedRoute
│
├── pages/                       # Страницы (Route-level компоненты)
│   ├── Login.tsx                # Авторизация
│   ├── Dashboard.tsx            # Главная: статистика, графики
│   ├── Users.tsx                # Управление системными админами
│   ├── Servers.tsx              # Управление VPS-серверами
│   ├── UsersOnServers.tsx       # Конфигурации клиентов на серверах
│   ├── Subscriptions.tsx        # Управление подписками
│   ├── SubscriptionPlans.tsx    # Тарифные планы
│   ├── Traffic.tsx              # Мониторинг трафика
│   └── ImportConfig.tsx         # Импорт конфигураций
│
├── components/                  # Переиспользуемые UI-компоненты
│   ├── Layout.tsx               # Основной layout (sidebar + content)
│   ├── common/                  # Общие компоненты (кнопки, формы, таблицы)
│   ├── dashboard/               # Виджеты дашборда
│   ├── users/                   # Компоненты управления пользователями
│   ├── servers/                 # Компоненты управления серверами
│   └── traffic/                 # Компоненты мониторинга трафика
│
├── stores/                      # Глобальное состояние
│   ├── authStore.ts             # Zustand: user, token, login/logout
│   └── realtimeStore.ts         # Zustand: WebSocket, auto-reconnect
│
├── services/                    # HTTP-клиент
│   └── api.ts                   # Axios: interceptors, API-namespace'ы
│
├── hooks/                       # Кастомные React-хуки
├── types/                       # TypeScript-типы
├── utils/                       # Утилиты
│   └── configDecoder.ts         # Парсинг VPN-конфигураций
├── styles/                      # CSS-стили
└── assets/                      # Статические ресурсы
```

### 5.4 Уровень 3 — Модель данных (Database)

```
┌───────────────┐       ┌──────────────────┐       ┌───────────────────┐
│    users      │       │    servers        │       │   vpn_clients     │
│───────────────│       │──────────────────│       │───────────────────│
│ id (PK)       │       │ id (PK)          │       │ id (PK)           │
│ username      │       │ name             │       │ name              │
│ email         │       │ host             │       │ email             │
│ password_hash │       │ port             │       │ notes             │
│ is_active     │       │ ssh_user         │       │ is_active         │
│ created_at    │       │ ssh_password_enc │       │ created_at        │
│ updated_at    │       │ ssh_key_path     │       │ updated_at        │
└───────────────┘       │ status           │       └────────┬──────────┘
                        │ created_at       │                │
                        │ updated_at       │                │
                        └────────┬─────────┘                │
                                 │                          │
                          1:N    │           1:N            │
                                 ▼                          ▼
                        ┌──────────────────────────────────────┐
                        │         client_configs               │
                        │──────────────────────────────────────│
                        │ id (PK)                              │
                        │ user_id (FK → users)                 │
                        │ client_id (FK → vpn_clients)         │
                        │ server_id (FK → servers)             │
                        │ device_name, protocol                │
                        │ config_content                       │
                        │ peer_public_key / client_uuid        │
                        │ bytes_received, bytes_sent           │
                        │ is_active, is_online                 │
                        │ last_handshake, last_seen            │
                        └───────────┬──────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
          ┌─────────────┐ ┌──────────────┐ ┌────────────────┐
          │ traffic_    │ │ traffic_     │ │ traffic_       │
          │ history     │ │ stats_hourly │ │ stats_daily    │
          │─────────────│ │──────────────│ │────────────────│
          │ id          │ │ id           │ │ id             │
          │ config_id   │ │ config_id    │ │ config_id      │
          │ bytes_recv  │ │ hour_start   │ │ date           │
          │ bytes_sent  │ │ total_recv   │ │ total_recv     │
          │ speed_dl    │ │ total_sent   │ │ total_sent     │
          │ speed_ul    │ │ avg/max speed│ │ avg/max speed  │
          │ timestamp   │ │ created_at   │ │ conn_time_min  │
          └─────────────┘ └──────────────┘ └────────────────┘

┌────────────────────┐      ┌──────────────────┐     ┌──────────────────┐
│ subscription_plans │      │  subscriptions   │     │ connection_events│
│────────────────────│      │──────────────────│     │──────────────────│
│ id (PK)            │◀──┐  │ id (PK)          │     │ id (PK)          │
│ name               │   └──│ plan_id (FK)     │     │ config_id (FK)   │
│ price              │      │ client_id (FK)   │     │ event_type       │
│ duration_days      │      │ config_id (FK)   │     │ timestamp        │
│ traffic_limit_gb   │      │ type             │     │ details          │
│ is_default         │      │ start / end      │     └──────────────────┘
│ is_active          │      │ traffic_limit_gb │
└────────────────────┘      │ traffic_used_gb  │
                            │ is_active        │
                            └──────────────────┘
```

---

## 6. Представление времени выполнения

### 6.1 Сценарий: Аутентификация администратора

```
  Браузер              Frontend (React)          Backend (FastAPI)         Database
    │                       │                          │                      │
    │  Ввод логин/пароль    │                          │                      │
    │──────────────────────▶│                          │                      │
    │                       │  POST /api/auth/login    │                      │
    │                       │─────────────────────────▶│                      │
    │                       │                          │  SELECT user WHERE   │
    │                       │                          │  username=...        │
    │                       │                          │─────────────────────▶│
    │                       │                          │◀─────────────────────│
    │                       │                          │  bcrypt.verify()     │
    │                       │                          │  create_jwt_token()  │
    │                       │    { access_token }      │                      │
    │                       │◀─────────────────────────│                      │
    │                       │  localStorage.set(token) │                      │
    │                       │  Zustand: setUser()      │                      │
    │  Redirect → /dashboard│                          │                      │
    │◀──────────────────────│                          │                      │
```

### 6.2 Сценарий: Сбор статистики трафика (фоновый процесс)

```
  APScheduler           TrafficSync            SSHManager         VPN Server (VPS)
    │                       │                      │                      │
    │  trigger (каждые 5м)  │                      │                      │
    │──────────────────────▶│                      │                      │
    │                       │  get_all_servers()    │                      │
    │                       │─────────────────────▶ DB                    │
    │                       │◀───── [servers]       │                      │
    │                       │                      │                      │
    │                       │  ┌─ Для каждого сервера ──────────────────┐ │
    │                       │  │  ssh_connect(host)  │                  │ │
    │                       │  │───────────────────▶│                  │ │
    │                       │  │                    │  SSH session     │ │
    │                       │  │                    │─────────────────▶│ │
    │                       │  │                    │                  │ │
    │                       │  │  AWG: "docker exec amnezia-awg       │ │
    │                       │  │       wg show awg0 dump"             │ │
    │                       │  │                    │◀─────────────────│ │
    │                       │  │  parse peers data  │                  │ │
    │                       │  │                    │                  │ │
    │                       │  │  XRay: stats API query               │ │
    │                       │  │                    │◀─────────────────│ │
    │                       │  │                    │                  │ │
    │                       │  │  match peers to configs              │ │
    │                       │  │  update bytes_received/sent          │ │
    │                       │  │  insert traffic_history              │ │
    │                       │  │  aggregate hourly/daily stats        │ │
    │                       │  │───────────────────▶ DB               │ │
    │                       │  └──────────────────────────────────────┘ │
    │                       │                      │                      │
```

### 6.3 Сценарий: Загрузка дашборда

```
  Браузер              Dashboard.tsx             api.ts              Backend
    │                       │                      │                    │
    │  Navigate /dashboard  │                      │                    │
    │──────────────────────▶│                      │                    │
    │                       │  useEffect()         │                    │
    │                       │──┐                   │                    │
    │                       │  │ Параллельные запросы:                  │
    │                       │  │                   │                    │
    │                       │  ├─ GET /api/traffic/realtime ──────────▶│
    │                       │  ├─ GET /api/traffic/top-users ─────────▶│
    │                       │  ├─ GET /api/traffic/by-server ─────────▶│
    │                       │  ├─ GET /api/vpn-clients ───────────────▶│
    │                       │  └─ GET /api/servers ───────────────────▶│
    │                       │                      │                    │
    │                       │◀─────── Responses ───│◀───────────────────│
    │                       │                      │                    │
    │                       │  setState(data)      │                    │
    │  Render: stats,       │                      │                    │
    │  charts, tables       │                      │                    │
    │◀──────────────────────│                      │                    │
    │                       │                      │                    │
    │                       │  setInterval(30s)    │                    │
    │                       │  → повторный polling │                    │
```

### 6.4 Сценарий: Добавление VPN-сервера

```
  Админ               Servers.tsx             Backend              SSHManager        VPS
    │                       │                    │                      │              │
    │  Заполнить форму      │                    │                      │              │
    │  (host, SSH creds)    │                    │                      │              │
    │──────────────────────▶│                    │                      │              │
    │                       │ POST /api/servers  │                      │              │
    │                       │───────────────────▶│                      │              │
    │                       │                    │  encrypt(ssh_pass)   │              │
    │                       │                    │  validate input      │              │
    │                       │                    │  INSERT server       │              │
    │                       │                    │─────────────────────▶ DB            │
    │                       │                    │                      │              │
    │                       │                    │  ssh_connect(host)   │              │
    │                       │                    │─────────────────────▶│              │
    │                       │                    │                      │──── test ───▶│
    │                       │                    │                      │◀─── ok ──────│
    │                       │                    │                      │              │
    │                       │  { server created } │                      │              │
    │                       │◀───────────────────│                      │              │
    │  Обновить список      │                    │                      │              │
    │◀──────────────────────│                    │                      │              │
```

---

## 7. Представление развёртывания

### 7.1 Среда разработки (Development)

```
  ┌────────────────── Developer Machine ──────────────────┐
  │                                                        │
  │  ┌──────────────┐    ┌──────────────┐                 │
  │  │  Vite Dev     │    │  Uvicorn     │                 │
  │  │  Server       │    │  (reload)    │                 │
  │  │  :5173        │    │  :8000       │                 │
  │  │  (frontend)   │───▶│  (backend)   │                 │
  │  └──────────────┘    └──────┬───────┘                 │
  │                             │                          │
  │                      ┌──────▼───────┐                 │
  │                      │  SQLite      │                 │
  │                      │  vpn_manager │                 │
  │                      │  .db         │                 │
  │                      └──────────────┘                 │
  └────────────────────────────────────────────────────────┘
```

**Запуск:**
```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

### 7.2 Продуктивная среда (Production / Docker)

```
  ┌───────────── Management Server (VPS) ─────────────────┐
  │                                                        │
  │  Docker Compose                                        │
  │  ┌──────────────────────────────────────────────────┐  │
  │  │                                                  │  │
  │  │  ┌────────────┐   ┌────────────┐                │  │
  │  │  │ frontend   │   │  backend   │                │  │
  │  │  │ node:22    │   │  python    │                │  │
  │  │  │ :5173      │──▶│  3.10      │                │  │
  │  │  │            │   │  :8000     │                │  │
  │  │  └────────────┘   └─────┬──────┘                │  │
  │  │                         │                        │  │
  │  │                  ┌──────▼──────┐                 │  │
  │  │                  │ PostgreSQL  │                 │  │
  │  │                  │ :5432       │                 │  │
  │  │                  │ (volume:    │                 │  │
  │  │                  │  pgdata)    │                 │  │
  │  │                  └─────────────┘                 │  │
  │  └──────────────────────────────────────────────────┘  │
  │                         │ SSH :22                       │
  └─────────────────────────┼──────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
  │  VPN Server 1 │ │  VPN Server 2 │ │  VPN Server N │
  │  (VPS)        │ │  (VPS)        │ │  (VPS)        │
  │               │ │               │ │               │
  │  amnezia-awg  │ │  amnezia-xray │ │  amnezia-awg  │
  │  (Docker)     │ │  (Docker)     │ │  amnezia-xray │
  └───────────────┘ └───────────────┘ └───────────────┘
```

### 7.3 Docker Compose — конфигурация

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    volumes:
      - ./backend:/app
      - /app/venv
      - db_data:/app/data
    env_file: .env
    environment:
      - DATABASE_URL=sqlite:///./data/vpn_manager.db
    command: >
      sh -c "alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on: [backend]

volumes:
  db_data:
```

> **Примечание:** PostgreSQL поддерживается через `DATABASE_URL=postgresql://...`, но по умолчанию используется SQLite. Для prod с PostgreSQL добавьте сервис `db` в docker-compose.

---

## 8. Сквозные концепции

### 8.1 Безопасность

```
┌─────────────────────────────────────────────────────┐
│                   Уровни безопасности                │
│                                                     │
│  ┌─────────────────┐                                │
│  │  Transport       │  HTTPS (рекомендуется Nginx)  │
│  ├─────────────────┤                                │
│  │  Authentication  │  JWT Bearer Token (HS256)     │
│  │                  │  Token expiry: 30 дней        │
│  ├─────────────────┤                                │
│  │  Authorization   │  get_current_active_user()    │
│  │                  │  FastAPI Depends()             │
│  ├─────────────────┤                                │
│  │  Password Store  │  bcrypt (passlib)             │
│  ├─────────────────┤                                │
│  │  SSH Credentials │  Fernet encryption at rest    │
│  ├─────────────────┤                                │
│  │  Rate Limiting   │  slowapi: 5 req/min на login  │
│  ├─────────────────┤                                │
│  │  Input Validation│  Pydantic schemas             │
│  ├─────────────────┤                                │
│  │  CORS            │  Настраивается через env      │
│  └─────────────────┘                                │
└─────────────────────────────────────────────────────┘
```

**Ключевые механизмы:**
- JWT-токены создаются при логине, передаются в заголовке `Authorization: Bearer <token>`
- SSH-пароли шифруются Fernet перед записью в БД, расшифровываются при SSH-подключении
- Валидация пароля: минимум 8 символов, обязательные цифры и спецсимволы
- Автоматический logout на фронтенде при HTTP 401

### 8.2 Обработка ошибок

| Слой | Подход |
|------|--------|
| Frontend (Axios) | Interceptor: 401 → logout + redirect; toast-уведомления |
| Backend (Routes) | HTTPException с кодами 400/401/403/404/500 |
| Backend (Services) | try/except с логированием; SSH-ошибки обрабатываются gracefully |
| Background Tasks | Логирование ошибок, продолжение работы по расписанию |

### 8.3 Логирование

- Python `logging` модуль
- Уровни: DEBUG (dev), INFO/WARNING/ERROR (prod)
- Логирование SSH-операций, ошибок синхронизации, аутентификации

### 8.4 Конфигурация

Все параметры управляются через переменные окружения (`.env` файл):

| Параметр | Описание | Пример |
|----------|----------|--------|
| `DATABASE_URL` | Строка подключения к БД | `postgresql://user:pass@db:5432/vpn` |
| `SECRET_KEY` | Ключ для JWT-подписи | `<random-256-bit>` |
| `ENCRYPTION_KEY` | Ключ для шифрования SSH-паролей | `<Fernet key>` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни JWT | `43200` (30 дней) |
| `CORS_ORIGINS` | Разрешённые домены | `http://localhost:5173` |
| `ADMIN_USERNAME` | Логин первого админа | `admin` |
| `ADMIN_PASSWORD` | Пароль первого админа | `<strong-password>` |

### 8.5 Стратегия тестирования

```
┌──────────────────────────────────────────────┐
│              Пирамида тестирования            │
│                                              │
│                    ┌───┐                     │
│                   / E2E \       (планируется) │
│                  /───────\                    │
│                 / Integr.  \   test_*_integr. │
│                /─────────────\                │
│               /    Unit Tests  \  test_models  │
│              /───────────────────\ test_auth   │
│             /    Validation Tests  \           │
│            /─────────────────────────\         │
└──────────────────────────────────────────────┘
```

- **Unit-тесты**: Модели, валидация, утилиты безопасности
- **Integration-тесты**: API-эндпоинты с тестовой БД
- **Инструменты**: pytest, pytest-asyncio, pytest-cov
- **Запуск**: `cd backend && pytest --cov`

---

## 9. Архитектурные решения

### ADR-1: FastAPI как бэкенд-фреймворк

**Статус:** Принято
**Контекст:** Нужен Python-фреймворк для REST API с высокой производительностью.
**Решение:** FastAPI с Uvicorn (ASGI).
**Последствия:**
- (+) Автоматическая OpenAPI-документация
- (+) Нативная поддержка async/await
- (+) Pydantic для валидации
- (+) Dependency injection
- (−) Менее зрелая экосистема по сравнению с Django

### ADR-2: SSH как механизм управления VPN-серверами

**Статус:** Принято
**Контекст:** Нужен способ выполнять команды на удалённых VPN-серверах.
**Решение:** Paramiko SSH-клиент с прямым выполнением команд.
**Последствия:**
- (+) Универсальность: работает с любым Linux-сервером
- (+) Не требуется агент на VPN-серверах
- (−) Зависимость от стабильности SSH-соединения
- (−) Необходимость хранить SSH-учётные данные

### ADR-3: Zustand для state management на фронтенде

**Статус:** Принято
**Контекст:** Нужно глобальное состояние для аутентификации.
**Решение:** Zustand — минимальный state manager.
**Последствия:**
- (+) Минимальный boilerplate
- (+) Простая интеграция с React hooks
- (+) Достаточен для текущего масштаба
- (−) При росте может потребоваться миграция на более мощное решение

### ADR-4: WebSocket + Polling fallback для real-time данных

**Статус:** Обновлено (ранее: только Polling)
**Контекст:** Дашборд должен показывать актуальные данные с минимальной задержкой.
**Решение:** WebSocket (`/api/ws`) для push-уведомлений (traffic_update, config_blocked) + HTTP-polling каждые 120 секунд как fallback. Фоновая синхронизация трафика каждые 5 минут (бэкенд, APScheduler).
**Реализация:**
- `backend/app/api/routes/ws.py` — ConnectionManager + JWT-аутентификация через query param
- `frontend/src/stores/realtimeStore.ts` — Zustand store с auto-reconnect (5 сек)
- Dashboard.tsx, Traffic.tsx — подписка на `lastUpdate` из store
**Последствия:**
- (+) Мгновенные обновления при изменении трафика / автоблокировке
- (+) Fallback polling при обрыве WebSocket
- (+) JWT-аутентификация на WebSocket
- (−) Дополнительная сложность с управлением соединениями

### ADR-5: SQLite для разработки, PostgreSQL для продакшена

**Статус:** Принято
**Контекст:** Нужна СУБД для хранения всех данных.
**Решение:** Двойная поддержка через SQLAlchemy.
**Последствия:**
- (+) Лёгкий старт разработки без внешних зависимостей
- (+) Надёжность PostgreSQL в продакшене
- (−) Возможные различия в поведении SQL между SQLite и PostgreSQL

### ADR-6: Strategy Pattern для VPN-протоколов

**Статус:** Принято
**Контекст:** Система должна поддерживать несколько VPN-протоколов.
**Решение:** Отдельные менеджеры (`AWGManager`, `WireGuardManager`, `XRayManager`) с общим подходом к управлению.
**Последствия:**
- (+) Изолированная логика каждого протокола
- (+) Простое добавление новых протоколов
- (−) Нет формального интерфейса (abstract base class)

---

## 10. Требования к качеству

### 10.1 Дерево качества

```
                        Качество системы
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
    Функциональность    Надёжность          Удобство использования
          │                   │                   │
    ┌─────┴─────┐      ┌─────┴─────┐      ┌─────┴─────┐
    │           │      │           │      │           │
  Безопасн.  Коррект.  Доступн. Устойч.  Простота  Понятность
```

### 10.2 Сценарии качества

| ID | Атрибут | Сценарий | Приоритет |
|----|---------|----------|-----------|
| QS-1 | Безопасность | Неавторизованный пользователь не может получить доступ к API (кроме /login) | Высокий |
| QS-2 | Безопасность | SSH-пароли хранятся в зашифрованном виде и не передаются в API-ответах | Высокий |
| QS-3 | Надёжность | При недоступности VPN-сервера система продолжает работу, ошибка логируется | Высокий |
| QS-4 | Надёжность | При перезапуске бэкенда фоновый сбор трафика автоматически возобновляется | Средний |
| QS-5 | Производительность | Дашборд загружается за < 3 секунды при < 100 клиентах | Средний |
| QS-6 | Сопровождаемость | Добавление нового VPN-протокола требует создания 1 нового файла-менеджера | Средний |
| QS-7 | Удобство | Администратор может добавить новый сервер за < 5 кликов | Средний |
| QS-8 | Развёртывание | Система запускается через `docker-compose up` одной командой | Высокий |

---

## 11. Риски и технический долг

### 11.1 Технические риски

| ID | Риск | Вероятность | Влияние | Меры |
|----|------|-------------|---------|------|
| R-1 | SSH-соединения нестабильны при плохой сети | Средняя | Высокое | Таймауты, retry-логика, graceful error handling |
| R-2 | Утечка SSH-паролей при компрометации БД | Низкая | Критическое | Fernet-шифрование, ротация ключей |
| R-3 | Потеря данных трафика при сбое синхронизации | Средняя | Среднее | Кеширование в `client_configs`, повторная синхронизация |
| R-4 | JWT-токен с 30-дневным сроком перехвачен | Низкая | Высокое | HTTPS обязателен в продакшене, token revocation (не реализован) |
| R-5 | Несовместимость SQLite/PostgreSQL при миграции | Низкая | Среднее | Тестирование миграций на обеих СУБД |

### 11.2 Технический долг

| ID | Описание | Приоритет | Рекомендация |
|----|----------|-----------|-------------|
| TD-1 | Нет RBAC — все админы имеют равные права | Средний | Добавить роли (admin, viewer) |
| TD-2 | Нет token revocation / refresh token | Средний | Реализовать refresh-token и blacklist |
| TD-3 | Отсутствие абстрактного интерфейса для протокол-менеджеров | Низкий | Создать ABC `ProtocolManager` |
| TD-4 | CORS разрешает все origin'ы в dev | Средний | Строго ограничить в продакшене |
| TD-5 | Нет rate limiting на все эндпоинты (только /login) | Средний | Добавить глобальный rate limiter |
| TD-6 | Отсутствие E2E-тестов | Средний | Добавить Playwright / Cypress тесты |
| ~~TD-7~~ | ~~Нет health-check эндпоинта~~ | — | ~~Решено: healthcheck через Docker~~ |
| ~~TD-8~~ | ~~Polling вместо WebSocket для real-time~~ | — | ~~Решено: WebSocket реализован (ws.py + realtimeStore.ts)~~ |
| TD-9 | Нет HTTPS-конфигурации из коробки | Средний | Добавить Nginx + Let's Encrypt в docker-compose |
| TD-10 | Нет pagination на list-эндпоинтах | Средний | Добавить limit/offset параметры |

---

## 12. Глоссарий

| Термин | Определение |
|--------|-------------|
| **AmneziaVPN** | Открытый VPN-клиент/протокол с обфускацией трафика |
| **AWG (AmneziaWG)** | AmneziaWireGuard — модифицированный WireGuard с обфускацией |
| **WireGuard** | Современный VPN-протокол, ядро ОС-уровня |
| **XRay** | Платформа для проксирования трафика (поддерживает VLESS, VMess, Trojan, Shadowsocks) |
| **VLESS** | Лёгкий proxy-протокол (часть XRay/V2Ray) |
| **VMess** | Протокол шифрованного проксирования (часть V2Ray) |
| **Trojan** | Proxy-протокол, маскирующийся под HTTPS |
| **Shadowsocks** | Протокол шифрованного SOCKS5-прокси |
| **VPS** | Virtual Private Server — виртуальный выделенный сервер |
| **Peer** | Участник WireGuard-сети (клиентское устройство) |
| **JWT** | JSON Web Token — стандарт токенов аутентификации |
| **Fernet** | Симметричное шифрование (из библиотеки cryptography) |
| **SPA** | Single Page Application — одностраничное веб-приложение |
| **ORM** | Object-Relational Mapping — объектно-реляционное отображение |
| **DTO** | Data Transfer Object — объект передачи данных |
| **CRUD** | Create, Read, Update, Delete — базовые операции над данными |
| **CORS** | Cross-Origin Resource Sharing — междоменный обмен ресурсами |
| **RBAC** | Role-Based Access Control — ролевое управление доступом |
| **ADR** | Architecture Decision Record — запись архитектурного решения |
| **APScheduler** | Advanced Python Scheduler — библиотека планирования задач |
| **Zustand** | Минимальный state manager для React |
| **Alembic** | Инструмент миграций БД для SQLAlchemy |
