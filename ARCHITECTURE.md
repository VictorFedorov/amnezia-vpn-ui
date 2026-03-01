# Архитектура проекта AmneziaVPN Management UI

## Общая архитектура системы

```
┌─────────────────────────────────────────────────────────────┐
│                     Администратор                            │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTPS
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (React + Vite)                     │
│                                                               │
│  Pages:                                                       │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ Dashboard  │ │ UsersOn      │ │   Traffic    │           │
│  │            │ │ Servers      │ │              │           │
│  └────────────┘ └──────────────┘ └──────────────┘           │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │  Servers   │ │ Subscriptions│ │ Subscription │           │
│  │            │ │              │ │    Plans     │           │
│  └────────────┘ └──────────────┘ └──────────────┘           │
│  ┌────────────┐ ┌──────────────┐                             │
│  │   Users    │ │ ImportConfig │                             │
│  │  (Admins)  │ │              │                             │
│  └────────────┘ └──────────────┘                             │
│                                                               │
│  State: Zustand (authStore, realtimeStore)                   │
│  HTTP: Axios                                                  │
│  Charts: Recharts                                             │
│  Styling: Tailwind CSS                                        │
└───────────────────────┬─────────────────────────────────────┘
                        │ REST API + WebSocket
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                Backend (Python / FastAPI)                     │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   API Routes                            │ │
│  │  /api/auth           /api/users          /api/servers  │ │
│  │  /api/vpn-clients    /api/configs        /api/traffic  │ │
│  │  /api/subscriptions  /api/subscription-plans           │ │
│  │  /api/ws (WebSocket)                                   │ │
│  └────────────────────┬───────────────────────────────────┘ │
│                       │                                      │
│  ┌────────────────────▼───────────────────────────────────┐ │
│  │                 Services Layer                          │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌───────────────┐  │ │
│  │  │  AWGManager  │ │  WireGuard   │ │  XRayManager  │  │ │
│  │  │              │ │  Manager     │ │               │  │ │
│  │  └──────────────┘ └──────────────┘ └───────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  TrafficSync (APScheduler, каждые 5 сек)         │  │ │
│  │  │  - Синхронизация трафика с серверов               │  │ │
│  │  │  - Обновление online/offline статуса              │  │ │
│  │  │  - Трекинг endpoint IP (sharing detection)       │  │ │
│  │  │  - Проверка expired subscriptions                │  │ │
│  │  │  - Проверка traffic limits                       │  │ │
│  │  │  - WebSocket broadcast                           │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  SSH Manager (paramiko)                          │  │ │
│  │  │  - Подключение к VPS серверам                    │  │ │
│  │  │  - Выполнение команд в Docker контейнерах        │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  SQLAlchemy  │  │   Alembic    │  │   Pydantic   │       │
│  │    (ORM)     │  │ (Миграции)   │  │  (Валидация) │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐  ┌──────────┐  ┌──────────┐
│   SQLite     │  │ VPS #1   │  │ VPS #N   │
│   (БД)       │  │  (SSH)   │  │  (SSH)   │
│              │  │ ┌──────┐ │  │ ┌──────┐ │
│ - users      │  │ │amne- │ │  │ │amne- │ │
│ - servers    │  │ │zia-  │ │  │ │zia-  │ │
│ - vpn_clients│  │ │awg   │ │  │ │awg   │ │
│ - configs    │  │ ├──────┤ │  │ ├──────┤ │
│ - subs       │  │ │amne- │ │  │ │amne- │ │
│ - traffic    │  │ │zia-  │ │  │ │zia-  │ │
│ - endpoint   │  │ │xray  │ │  │ │xray  │ │
│   _logs      │  │ └──────┘ │  │ └──────┘ │
└──────────────┘  └──────────┘  └──────────┘
```

---

## Поток данных: Синхронизация трафика

```
APScheduler              Backend                      VPN Server
(каждые 5 сек)             │                              │
   │                       │                              │
   │  sync_all_traffic()   │                              │
   ├──────────────────────>│                              │
   │                       │                              │
   │                       │  SSH connect                 │
   │                       ├─────────────────────────────>│
   │                       │                              │
   │                       │  docker exec amnezia-awg     │
   │                       │  wg show awg0 dump           │
   │                       ├─────────────────────────────>│
   │                       │  peers: [{public_key,        │
   │                       │   endpoint, rx, tx,          │
   │                       │   handshake}]                │
   │                       │<─────────────────────────────┤
   │                       │                              │
   │                       │  docker exec amnezia-xray    │
   │                       │  xray api statsquery         │
   │                       ├─────────────────────────────>│
   │                       │  stats: {email: {up, down}}  │
   │                       │<─────────────────────────────┤
   │                       │                              │
   │                       │  SSH disconnect              │
   │                       ├─────────────────────────────>│
   │                       │                              │
   │  Обновление БД:       │                              │
   │  - bytes_received/sent│                              │
   │  - endpoint, is_online│                              │
   │  - last_handshake     │                              │
   │  - endpoint_logs      │                              │
   │                       │                              │
   │  Проверки:            │                              │
   │  - expired subs       │                              │
   │  - traffic limits     │                              │
   │                       │                              │
   │  WebSocket broadcast  │                              │
   │  {"type":"traffic_    │                              │
   │   update"}            │                              │
   │                       │                              │
```

---

## Поток данных: WebSocket Realtime Updates

```
Frontend                Backend                  TrafficSync
   │                       │                          │
   │  WS connect           │                          │
   │  /api/ws?token=JWT    │                          │
   ├──────────────────────>│                          │
   │                       │  Verify JWT              │
   │                       ├─────────>│               │
   │                       │  ConnectionManager       │
   │                       │  .connect(ws)            │
   │  Connection OK        │                          │
   │<──────────────────────┤                          │
   │                       │                          │
   │  ping                 │                          │
   ├──────────────────────>│                          │
   │  pong                 │                          │
   │<──────────────────────┤                          │
   │                       │                          │
   │                       │   sync_all_traffic()     │
   │                       │<─────────────────────────┤
   │                       │                          │
   │  {"type":             │   broadcast()            │
   │   "traffic_update"}   │<─────────────────────────┤
   │<──────────────────────┤                          │
   │                       │                          │
   │  Reload data          │                          │
   │  (loadStats, etc.)    │                          │
   │                       │                          │
   │                       │   config blocked          │
   │  {"type":             │   (expired sub /          │
   │   "config_blocked",   │    traffic limit)         │
   │   "reason": "..."}    │<─────────────────────────┤
   │<──────────────────────┤                          │
```

---

## Детекция шаринга конфигов

```
Sync Cycle:

1. WG/AWG peer подключается с endpoint 1.2.3.4:51820
   → traffic_sync записывает EndpointLog(config_id, ip="1.2.3.4")

2. Через время, тот же peer подключается с 5.6.7.8:51820
   → traffic_sync записывает EndpointLog(config_id, ip="5.6.7.8")

3. API GET /configs/sharing-alerts:
   → SELECT config_id, COUNT(DISTINCT endpoint_ip) as cnt
     FROM endpoint_logs
     WHERE seen_at >= NOW() - 24h
     GROUP BY config_id
     HAVING cnt >= 2

4. Scoring:
   1 IP    → score=0 (OK)
   2 IPs   → score=1 (Suspicious)
   3+ IPs  → score=2 (Sharing!)

5. Frontend:
   Dashboard: красная карточка "Подозрение на шаринг (N)"
              expandable → таблица IP с first_seen/last_seen
   UsersOnServers: badge рядом с peer "3 IP — Shared!"
                   clickable → модалка с историей endpoint
```

---

## Структура файлов проекта

```
amnezia_vpn_ui/
├── docker-compose.yml
├── ARCHITECTURE.md           ← Вы здесь
├── SUMMARY.md
├── DATABASE_SCHEMA.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/           # 9 миграций
│   └── app/
│       ├── main.py              # FastAPI app, APScheduler, startup
│       ├── api/
│       │   ├── schemas.py       # Pydantic models
│       │   └── routes/
│       │       ├── auth.py      # JWT login/logout/me
│       │       ├── users.py     # Admin CRUD
│       │       ├── vpn_clients.py  # VPN client CRUD
│       │       ├── servers.py   # Server CRUD + fetch-users
│       │       ├── configs.py   # Config CRUD + sharing + bulk
│       │       ├── traffic.py   # Realtime + top users
│       │       ├── subscriptions.py  # Subscription CRUD
│       │       ├── subscription_plans.py
│       │       └── ws.py        # WebSocket endpoint
│       ├── core/
│       │   ├── config.py        # Settings (pydantic-settings)
│       │   └── database.py      # SQLAlchemy engine + session
│       ├── models/
│       │   └── __init__.py      # All SQLAlchemy models
│       ├── services/
│       │   ├── ssh_manager.py   # SSH connection (paramiko)
│       │   ├── awg_manager.py   # AmneziaWG: peers, block/unblock
│       │   ├── wireguard_manager.py  # WireGuard: peers, block/unblock
│       │   ├── xray_manager.py  # XRay: clients, stats
│       │   └── traffic_sync.py  # Background sync + auto-block
│       └── utils/
│           ├── security.py      # JWT, password hashing
│           └── encryption.py    # SSH password encryption
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── main.tsx
│       ├── App.tsx              # React Router
│       ├── components/
│       │   └── Layout.tsx       # Sidebar + header
│       ├── pages/
│       │   ├── Login.tsx
│       │   ├── Dashboard.tsx    # Stats, charts, sharing alerts
│       │   ├── UsersOnServers.tsx  # Main management page
│       │   ├── Servers.tsx      # Server CRUD
│       │   ├── Traffic.tsx      # Traffic monitoring
│       │   ├── Users.tsx        # Admin management
│       │   ├── Subscriptions.tsx
│       │   ├── SubscriptionPlans.tsx
│       │   └── ImportConfig.tsx # Import configs from server
│       ├── services/
│       │   └── api.ts           # Axios API client
│       ├── stores/
│       │   ├── authStore.ts     # Zustand auth (JWT)
│       │   └── realtimeStore.ts # Zustand WebSocket
│       └── utils/
│           └── configDecoder.ts # WG/XRay config parser
```

---

## Безопасность

```
┌────────────────────────────────────────┐
│  Frontend                              │
│  ├─ JWT в localStorage                 │
│  ├─ Auto redirect на /login при 401    │
│  ├─ WebSocket auth через ?token=JWT    │
│  └─ CORS: только разрешённые origins   │
└────────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────┐
│  Backend                               │
│  ├─ JWT verification (python-jose)     │
│  ├─ Bcrypt для паролей                 │
│  ├─ Rate limiting (slowapi)            │
│  ├─ SSH пароли зашифрованы (Fernet)    │
│  ├─ Input валидация (Pydantic)         │
│  └─ CORS настроен                      │
└────────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────┐
│  VPN Servers                           │
│  ├─ SSH key или password auth          │
│  └─ Команды через docker exec          │
└────────────────────────────────────────┘
```

---

## Deployment (Docker Compose)

```
┌────────────────────────────────────────────────────────┐
│               docker-compose.yml                        │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  amnezia_backend (Python 3.11)                    │  │
│  │  Port: 8000                                       │  │
│  │  Volumes: ./backend → /app                        │  │
│  │  Startup: alembic upgrade head → uvicorn          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  amnezia_frontend (Node 20)                       │  │
│  │  Port: 5173                                       │  │
│  │  Volumes: ./frontend → /app                       │  │
│  │  Startup: npm run dev                             │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## Протоколы и детекция online

| Протокол | Идентификатор | Online-детекция | Sharing-детекция |
|----------|---------------|-----------------|------------------|
| AWG | peer_public_key | latest_handshake < 3 мин | endpoint IP tracking |
| WireGuard | peer_public_key | latest_handshake < 3 мин | endpoint IP tracking |
| VLESS/VMess | client_uuid + email | Изменение трафика между sync | Нет (XRay не отдаёт IP) |
| Trojan | client_uuid + email | Изменение трафика между sync | Нет |
| Shadowsocks | client_uuid + email | Изменение трафика между sync | Нет |

**Ограничения:**
- WireGuard: 1 public_key = 1 одновременное подключение (протокольное ограничение)
- XRay: Несколько одновременных подключений на 1 UUID, но Stats API не показывает кол-во подключений и IP адреса клиентов
- Имена конфигов хранятся только в нашей БД, не на VPN серверах
