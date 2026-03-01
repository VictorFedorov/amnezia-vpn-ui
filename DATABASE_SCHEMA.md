# Схема базы данных

## Технологии

- **SQLite** — основная БД (файл `test.db`)
- **SQLAlchemy 2.0** — ORM
- **Alembic** — миграции (автоматически при старте контейнера)

---

## ER-диаграмма

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│     users       │      │   vpn_clients    │      │    servers      │
│ (админы панели) │      │ (клиенты VPN)    │      │  (VPS серверы)  │
├─────────────────┤      ├──────────────────┤      ├─────────────────┤
│ id PK           │      │ id PK            │      │ id PK           │
│ username        │      │ name             │      │ name            │
│ email           │      │ email            │      │ host            │
│ password_hash   │      │ notes            │      │ port            │
│ is_active       │      │ is_active        │      │ ssh_user        │
│ created_at      │      │ created_at       │      │ ssh_password_   │
│ updated_at      │      │ updated_at       │      │   encrypted     │
└────────┬────────┘      └────────┬─────────┘      │ ssh_key_path    │
         │                        │                 │ status (enum)   │
         │ user_id (FK)           │ client_id (FK)  │ created_at      │
         │                        │                 │ updated_at      │
         ▼                        ▼                 └────────┬────────┘
┌──────────────────────────────────────────────────────────────────────┐
│                        client_configs                                │
│                    (конфигурации устройств)                          │
├──────────────────────────────────────────────────────────────────────┤
│ id PK                                                                │
│ user_id FK → users.id            # Админ, создавший конфиг          │
│ client_id FK → vpn_clients.id    # VPN клиент                       │
│ server_id FK → servers.id        # VPS сервер                       │
│ device_name                      # "iPhone Ивана"                    │
│ protocol (enum: awg/wireguard/vless/vmess/trojan/shadowsocks)       │
│ config_content (text)            # Полный текст конфига              │
│ peer_public_key (unique)         # Для AWG/WireGuard                │
│ allowed_ips                      # Для AWG/WireGuard                │
│ endpoint                         # Текущий endpoint (IP:port)       │
│ client_uuid (unique)             # Для XRay                         │
│ client_email                     # Для XRay                         │
│ bytes_received                   # Кэш последнего sync              │
│ bytes_sent                       # Кэш последнего sync              │
│ is_active                        # Заблокирован ли                  │
│ is_online                        # Подключён ли сейчас              │
│ last_handshake                   # Время последнего handshake       │
│ last_seen                        # Время последней активности       │
│ created_at, updated_at                                               │
├──────────────────────────────────────────────────────────────────────┤
│ INDEXES: idx_user_server, idx_client_server                         │
└─────────┬──────────────────────────┬─────────────────────────────────┘
          │                          │
          ▼                          ▼
┌───────────────────┐    ┌────────────────────┐
│  traffic_history  │    │   endpoint_logs    │
├───────────────────┤    │ (sharing detection)│
│ id PK             │    ├────────────────────┤
│ config_id FK      │    │ id PK              │
│ bytes_received    │    │ config_id FK       │
│ bytes_sent        │    │ endpoint_ip        │
│ speed_download    │    │ seen_at            │
│ speed_upload      │    │ created_at         │
│ timestamp         │    ├────────────────────┤
├───────────────────┤    │ IDX: config_id +   │
│ IDX: config_id +  │    │   endpoint_ip +    │
│   timestamp       │    │   seen_at          │
└───────────────────┘    └────────────────────┘

┌────────────────────┐    ┌───────────────────────┐
│ subscription_plans │    │    subscriptions      │
│   (тарифы)         │    │  (подписки клиентов)  │
├────────────────────┤    ├───────────────────────┤
│ id PK              │    │ id PK                 │
│ name               │    │ client_id FK →        │
│ description        │    │   vpn_clients.id      │
│ price              │    │ config_id FK →        │
│ duration_days      │    │   client_configs.id   │
│ traffic_limit_gb   │    │ plan_id FK →          │
│ is_default         │    │   subscription_plans  │
│ is_active          │    │ subscription_type     │
│ created_at         │    │ subscription_start    │
└────────────────────┘    │ subscription_end      │
                          │ is_active             │
                          │ traffic_limit_gb      │
                          │ traffic_used_gb       │
                          │ created_at, updated_at│
                          ├───────────────────────┤
                          │ IDX: client_id +      │
                          │   is_active           │
                          │ IDX: config_id +      │
                          │   is_active           │
                          └───────────────────────┘

┌───────────────────────┐    ┌──────────────────────┐
│ traffic_stats_hourly  │    │ traffic_stats_daily  │
├───────────────────────┤    ├──────────────────────┤
│ id PK                 │    │ id PK                │
│ config_id FK          │    │ config_id FK         │
│ hour_start            │    │ date                 │
│ total_bytes_received  │    │ total_bytes_received │
│ total_bytes_sent      │    │ total_bytes_sent     │
│ avg_speed_download    │    │ avg_speed_download   │
│ avg_speed_upload      │    │ avg_speed_upload     │
│ max_speed_download    │    │ max_speed_download   │
│ max_speed_upload      │    │ max_speed_upload     │
│ created_at            │    │ connection_time_min  │
└───────────────────────┘    │ created_at           │
                             └──────────────────────┘

┌───────────────────────┐
│  connection_events    │
├───────────────────────┤
│ id PK                 │
│ config_id FK          │
│ event_type            │
│ timestamp             │
│ details               │
└───────────────────────┘
```

---

## Модели SQLAlchemy

Все модели определены в `backend/app/models/__init__.py`.

### Enums

```python
class ProtocolType(str, Enum):
    AWG = "awg"
    WIREGUARD = "wireguard"
    VLESS = "vless"
    VMESS = "vmess"
    TROJAN = "trojan"
    SHADOWSOCKS = "shadowsocks"

class SubscriptionType(str, Enum):
    TRIAL = "trial"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    LIFETIME = "lifetime"

class ServerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
```

### Таблицы

| Таблица | Описание | Записей (примерно) |
|---------|----------|-------------------|
| `users` | Администраторы панели | 1-5 |
| `servers` | VPS серверы с SSH доступом | 1-10 |
| `vpn_clients` | Клиенты VPN (люди) | 10-1000 |
| `client_configs` | Конфигурации (устройства) | 10-5000 |
| `endpoint_logs` | IP-адреса подключений | Растёт (нужна ротация) |
| `traffic_history` | Снимки трафика | Растёт |
| `traffic_stats_hourly` | Почасовая агрегация | Растёт |
| `traffic_stats_daily` | Дневная агрегация | Растёт |
| `subscriptions` | Подписки клиентов | 10-5000 |
| `subscription_plans` | Тарифные планы | 3-10 |
| `connection_events` | События подключений | Растёт |

---

## Миграции (Alembic)

Текущая цепочка миграций:

```
2163c4bf7acd  Initial migration
     ↓
22e1ff49a33a  Add client_id to ClientConfig
     ↓
363a3fc9ce31  Add cache fields to ClientConfig
     ↓
0b6b4ea58ab8  Remove protocol from server model
     ↓
a1b2c3d4e5f6  Add is_default to subscription_plans
     ↓
f1e2d3c4b5a6  Encrypt SSH passwords
     ↓
a722e84a94b3  Merge heads
     ↓
b3c4d5e6f7a8  Fix constraints and FKs
     ↓
c4d5e6f7a8b9  Add endpoint_logs  ← текущая HEAD
```

### Команды

```bash
# Применить все миграции
alembic upgrade head

# Создать новую миграцию
alembic revision --autogenerate -m "description"

# Откатить на шаг назад
alembic downgrade -1

# Посмотреть текущую ревизию
alembic current
```

---

## Ключевые связи

1. **Server → ClientConfig** (1:N) — на сервере может быть много конфигов
2. **VpnClient → ClientConfig** (1:N) — у клиента может быть много устройств
3. **ClientConfig → EndpointLog** (1:N) — история IP-адресов подключений
4. **ClientConfig → TrafficHistory** (1:N) — снимки трафика
5. **VpnClient → Subscription** (1:N) — подписки клиента
6. **ClientConfig → Subscription** (1:N) — подписка на конфиг
7. **SubscriptionPlan → Subscription** (1:N) — тарифный план

---

## Автоматические процессы

### Traffic Sync (каждые 5 секунд)
Обновляет в `client_configs`:
- `bytes_received`, `bytes_sent` — из wg show / xray stats
- `endpoint` — текущий IP:port
- `is_online` — AWG/WG: handshake < 3 мин; XRay: трафик изменился
- `last_handshake`, `last_seen`

Записывает в `endpoint_logs`:
- Новый IP, если отличается от последнего для данного config_id

Проверяет `subscriptions`:
- Если `subscription_end < now` → `is_active = false`, блокировка peer на сервере
- Если `traffic_used_gb >= traffic_limit_gb` → то же самое
