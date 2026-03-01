from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.utils.encryption import encrypt_password, decrypt_password
import enum


class ProtocolType(str, enum.Enum):
    """Типы VPN протоколов"""
    AWG = "awg"  # AmneziaWG
    WIREGUARD = "wireguard"  # Standard WireGuard
    VLESS = "vless"  # XRay VLESS
    VMESS = "vmess"  # XRay VMess
    TROJAN = "trojan"  # XRay Trojan
    SHADOWSOCKS = "shadowsocks"  # XRay Shadowsocks


class SubscriptionType(str, enum.Enum):
    """Типы подписки"""
    TRIAL = "trial"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    LIFETIME = "lifetime"


class ServerStatus(str, enum.Enum):
    """Статус сервера"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class Server(Base):
    """Модель VPS сервера"""
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22)
    ssh_user = Column(String(100), nullable=False)
    ssh_password_encrypted = Column(Text, nullable=True)  # Зашифрованный пароль
    ssh_key_path = Column(String(500), nullable=True)
    # protocol убран - на сервере могут быть оба контейнера (AWG + XRay)
    status = Column(SQLEnum(ServerStatus), default=ServerStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    configs = relationship("ClientConfig", back_populates="server", cascade="all, delete-orphan")

    def set_password(self, password: str):
        """Установить и зашифровать SSH пароль"""
        if password:
            self.ssh_password_encrypted = encrypt_password(password)
    
    def get_password(self) -> str:
        """Получить расшифрованный SSH пароль"""
        if self.ssh_password_encrypted:
            return decrypt_password(self.ssh_password_encrypted)
        return None

    def __repr__(self):
        return f"<Server(id={self.id}, name={self.name}, protocol={self.protocol})>"


class User(Base):
    """Модель администратора панели (System User)"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    # Removed direct config ownership for admins. Admins manage everything.

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class VpnClient(Base):
    """Модель клиента VPN (человек)"""
    __tablename__ = "vpn_clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True) # "Ivan"
    email = Column(String(255), nullable=True) # Optional contact email
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    configs = relationship("ClientConfig", back_populates="client", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<VpnClient(id={self.id}, name={self.name})>"


class ClientConfig(Base):
    """Модель конфигурации клиента (устройства)"""
    __tablename__ = "client_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # Администратор, создавший конфиг
    client_id = Column(Integer, ForeignKey("vpn_clients.id", ondelete="CASCADE"), nullable=True, index=True) # Link to VPN Client
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    device_name = Column(String(255), nullable=False)
    protocol = Column(SQLEnum(ProtocolType), nullable=False)
    config_content = Column(Text, nullable=False)
    
    # WireGuard specific
    peer_public_key = Column(String(255), nullable=True, unique=True, index=True)  # Для AWG
    allowed_ips = Column(String(255), nullable=True)  # Для AWG
    endpoint = Column(String(255), nullable=True)  # Текущий endpoint (если подключен)
    
    # XRay specific
    client_uuid = Column(String(255), nullable=True, unique=True, index=True)  # Для XRay
    client_email = Column(String(255), nullable=True)  # Для XRay
    
    # Статистика (кэш из последнего запроса)
    bytes_received = Column(Integer, default=0)  # Последние данные RX
    bytes_sent = Column(Integer, default=0)  # Последние данные TX
    
    is_active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)  # Подключен ли сейчас
    last_handshake = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)  # Последняя активность
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="client_configs")
    client = relationship("VpnClient", back_populates="configs")
    server = relationship("Server", back_populates="configs")
    traffic_history = relationship("TrafficHistory", back_populates="config", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_user_server', 'user_id', 'server_id'),
        Index('idx_client_server', 'client_id', 'server_id'),
    )

    def __repr__(self):
        return f"<ClientConfig(id={self.id}, client_id={self.client_id}, device={self.device_name})>"


class TrafficHistory(Base):
    """Модель истории трафика"""
    __tablename__ = "traffic_history"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("client_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    bytes_received = Column(Integer, default=0)
    bytes_sent = Column(Integer, default=0)
    speed_download = Column(Float, default=0.0)  # Мбит/с
    speed_upload = Column(Float, default=0.0)  # Мбит/с
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    config = relationship("ClientConfig", back_populates="traffic_history")

    # Indexes
    __table_args__ = (
        Index('idx_config_timestamp', 'config_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<TrafficHistory(id={self.id}, config_id={self.config_id}, timestamp={self.timestamp})>"


class TrafficStatsHourly(Base):
    """Модель почасовой статистики трафика"""
    __tablename__ = "traffic_stats_hourly"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("client_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    hour_start = Column(DateTime, nullable=False, index=True)
    total_bytes_received = Column(Integer, default=0)
    total_bytes_sent = Column(Integer, default=0)
    avg_speed_download = Column(Float, default=0.0)
    avg_speed_upload = Column(Float, default=0.0)
    max_speed_download = Column(Float, default=0.0)
    max_speed_upload = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_config_hour', 'config_id', 'hour_start'),
    )

    def __repr__(self):
        return f"<TrafficStatsHourly(id={self.id}, config_id={self.config_id}, hour={self.hour_start})>"


class TrafficStatsDaily(Base):
    """Модель дневной статистики трафика"""
    __tablename__ = "traffic_stats_daily"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("client_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    total_bytes_received = Column(Integer, default=0)
    total_bytes_sent = Column(Integer, default=0)
    avg_speed_download = Column(Float, default=0.0)
    avg_speed_upload = Column(Float, default=0.0)
    max_speed_download = Column(Float, default=0.0)
    max_speed_upload = Column(Float, default=0.0)
    connection_time_minutes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_config_date', 'config_id', 'date'),
    )

    def __repr__(self):
        return f"<TrafficStatsDaily(id={self.id}, config_id={self.config_id}, date={self.date})>"


class SubscriptionPlan(Base):
    """Модель тарифного плана"""
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, default=0.0)
    duration_days = Column(Integer, default=30)
    traffic_limit_gb = Column(Integer, default=0)  # 0 = безлимит
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)  # Доступен ли для выбора
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SubscriptionPlan(id={self.id}, name={self.name})>"


class Subscription(Base):
    """Модель подписки клиента"""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("vpn_clients.id", ondelete="CASCADE"), nullable=True, index=True) # Link to VPN Client
    config_id = Column(Integer, ForeignKey("client_configs.id", ondelete="CASCADE"), nullable=True, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=True)
    
    subscription_type = Column(SQLEnum(SubscriptionType), nullable=True) # Deprecated in favor of plan_id
    subscription_start = Column(DateTime, nullable=False)
    subscription_end = Column(DateTime, nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    traffic_limit_gb = Column(Integer, nullable=True)  # Лимит трафика в ГБ
    traffic_used_gb = Column(Float, default=0.0)  # Использовано ГБ
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = relationship("VpnClient", back_populates="subscriptions")
    config = relationship("ClientConfig")
    plan = relationship("SubscriptionPlan")

    # Indexes
    __table_args__ = (
        Index('idx_client_active', 'client_id', 'is_active'),
        Index('idx_config_active', 'config_id', 'is_active'),
    )

    def __repr__(self):
        return f"<Subscription(id={self.id}, client_id={self.client_id}, plan={self.plan_id})>"


class ConnectionEvent(Base):
    """Модель событий подключения/отключения"""
    __tablename__ = "connection_events"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("client_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # 'connected', 'disconnected'
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    details = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_config_event_time', 'config_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<ConnectionEvent(id={self.id}, config_id={self.config_id}, type={self.event_type})>"


class EndpointLog(Base):
    """Модель лога IP-адресов подключений для детекции шаринга"""
    __tablename__ = "endpoint_logs"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("client_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint_ip = Column(String(45), nullable=False)
    seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    config = relationship("ClientConfig", backref="endpoint_logs")

    __table_args__ = (
        Index('idx_endpoint_config_ip_seen', 'config_id', 'endpoint_ip', 'seen_at'),
    )

    def __repr__(self):
        return f"<EndpointLog(id={self.id}, config_id={self.config_id}, ip={self.endpoint_ip})>"
