# AmneziaVPN Management UI — Сводка проекта

## Описание

Web-панель управления для **self-hosted** AmneziaVPN серверов. Подключение к серверам через **SSH**, управление пользователями VPN, мониторинг трафика, управление подписками, детекция шаринга конфигов.

Поддерживаемые VPN контейнеры на серверах:
- **amnezia-awg** — AmneziaWG (обфусцированный WireGuard)
- **amnezia-wg** — стандартный WireGuard
- **amnezia-xray** — XRay (VLESS, VMess, Trojan, Shadowsocks)

---

## Технологический стек

### Backend (Python)
| Пакет | Назначение |
|-------|-----------|
| FastAPI | Web framework |
| Uvicorn | ASGI server |
| SQLAlchemy 2.0 | ORM |
| Alembic | Миграции БД |
| Pydantic | Валидация данных и схемы |
| Paramiko | SSH клиент |
| APScheduler | Фоновые задачи (sync трафика) |
| python-jose | JWT токены |
| passlib + bcrypt | Хеширование паролей |
| cryptography (Fernet) | Шифрование SSH паролей |
| slowapi | Rate limiting |
| qrcode | Генерация QR кодов |

### Frontend (TypeScript)
| Пакет | Назначение |
|-------|-----------|
| React 18 | UI framework |
| Vite | Сборщик |
| TypeScript | Типизация |
| Tailwind CSS | Стили |
| Zustand | State management |
| Axios | HTTP клиент |
| Recharts | Графики |
| React Router DOM | Роутинг |

### Инфраструктура
- **SQLite** — база данных (файл `test.db`)
- **Docker Compose** — запуск backend (port 8000) + frontend (port 5173)
- **Alembic** — автоматические миграции при старте контейнера

---

## Реализованные возможности

### Управление серверами
- CRUD серверов (host, port, SSH credentials)
- SSH пароли зашифрованы Fernet
- Проверка подключения к серверу
- Импорт существующих peers/clients с сервера
- Поддержка нескольких серверов одновременно

### Управление VPN-клиентами
- CRUD клиентов (имя, email, заметки)
- Привязка клиентов к конфигурациям
- Просмотр всех конфигов клиента

### Управление конфигурациями
- Создание / редактирование / удаление конфигов
- Привязка к серверу, клиенту, протоколу
- Блокировка/разблокировка peer на сервере (toggle-active)
- Генерация QR кодов (в т.ч. чтение конфига с сервера)
- **Bulk create** — создание N конфигов одним запросом
- Импорт конфигов с сервера (сохранение в БД)

### Мониторинг трафика
- **Фоновая синхронизация** каждые 5 секунд (APScheduler):
  - AWG/WireGuard: `wg show` → bytes, endpoint, handshake
  - XRay: `xray api statsquery` → uplink/downlink по UUID
- **Online/offline детекция**:
  - AWG/WG: latest_handshake < 3 минут = online
  - XRay: изменение трафика между sync = online
- Обновление `bytes_received`, `bytes_sent`, `endpoint`, `is_online`, `last_handshake`, `last_seen`
- Страница Traffic с таблицей и фильтрами

### Подписки
- Тарифные планы (SubscriptionPlan): цена, длительность, лимит трафика
- Подписки (Subscription): привязка к клиенту/конфигу, даты, лимит
- **Авто-блокировка при истечении подписки**: peer блокируется на сервере через SSH
- **Авто-блокировка при превышении трафика**: subscription.traffic_limit_gb
- Продление подписок

### WebSocket (Realtime)
- Endpoint: `/api/ws?token=JWT`
- JWT аутентификация через query parameter
- Типы сообщений:
  - `traffic_update` — после каждой синхронизации
  - `config_blocked` — при авто-блокировке (expiry / traffic limit)
- Frontend: Zustand store `realtimeStore.ts`
- Auto-reconnect через 5 секунд
- Dashboard и Traffic получают push-уведомления, polling как fallback (120с)

### Детекция шаринга конфигов
- Трекинг endpoint IP в таблице `endpoint_logs`
- Scoring: 1 IP = OK, 2 IPs = Suspicious, 3+ IPs = Sharing
- API:
  - `GET /configs/sharing-alerts` — все подозрительные конфиги с per-IP деталями
  - `GET /configs/{id}/endpoint-history` — последние 50 записей IP
  - `GET /configs/{id}/sharing-status` — distinct IPs + score
- `sharing_score` включён в `GET /configs/` (batch)
- Dashboard: красная карточка с expandable IP-деталями (first_seen, last_seen, times_seen)
- UsersOnServers: clickable badges рядом с peers → модалка endpoint history

### Dashboard
- Статистика: клиенты, серверы, устройства (online/total), общий трафик
- Графики: распределение по протоколам (PieChart), топ-5 по трафику (BarChart)
- Sharing Alerts карточка
- "Live" badge при активном WebSocket
- Быстрые действия (ссылки на страницы)

### Аутентификация
- JWT токены (login → access_token)
- Auto-создание admin при первом запуске
- Защита всех API endpoints через `get_current_active_user`

---

## API Endpoints

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/auth/login` | Вход (username/password → JWT) |
| GET | `/api/auth/me` | Текущий пользователь |
| GET/POST/PUT/DELETE | `/api/users/*` | CRUD администраторов |
| GET/POST/PUT/DELETE | `/api/vpn-clients/*` | CRUD VPN-клиентов |
| GET/POST/PUT/DELETE | `/api/servers/*` | CRUD серверов |
| GET | `/api/servers/{id}/fetch-users` | Импорт peers с сервера |
| GET/POST/PUT/DELETE | `/api/configs/*` | CRUD конфигураций |
| POST | `/api/configs/bulk` | Массовое создание конфигов |
| GET | `/api/configs/sharing-alerts` | Подозрения на шаринг |
| GET | `/api/configs/{id}/endpoint-history` | История IP |
| GET | `/api/configs/{id}/sharing-status` | Статус шаринга |
| GET | `/api/configs/{id}/qrcode` | QR код конфига |
| POST | `/api/configs/{id}/toggle-active` | Блок/разблок peer |
| GET | `/api/traffic/realtime` | Текущий трафик |
| GET | `/api/traffic/top-users` | Топ по трафику |
| GET/POST/PUT/DELETE | `/api/subscriptions/*` | CRUD подписок |
| GET/POST/PUT/DELETE | `/api/subscription-plans/*` | CRUD тарифов |
| WS | `/api/ws?token=JWT` | WebSocket realtime |

---

## Ограничения

### Протокольные
- **WireGuard/AWG**: 1 public_key = 1 одновременное устройство (ограничение протокола)
- **XRay**: Stats API не показывает количество одновременных подключений и IP адреса клиентов
- Имена конфигов хранятся только в нашей БД, не на VPN серверах

### Технические
- SQLite (single-writer) — подходит для малых/средних инсталляций
- SSH подключение к серверу при каждом sync цикле (нет connection pooling)
- History трафика не реализована (только текущие cumulative значения)

---

## Запуск

```bash
# Запуск через Docker Compose
docker compose up -d

# Backend: http://localhost:8000/api/docs
# Frontend: http://localhost:5173
```

При первом запуске:
1. `alembic upgrade head` — применяются миграции
2. Создаётся admin пользователь (пароль в логах или из .env)
3. APScheduler стартует sync_all_traffic каждые 5 сек
