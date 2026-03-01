from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
import re


# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# User schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    email: Optional[EmailStr] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    
    @validator('password')
    def password_strength(cls, v):
        """Проверка надежности пароля"""
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Пароль должен содержать хотя бы одну заглавную букву')
        if not re.search(r'[a-z]', v):
            raise ValueError('Пароль должен содержать хотя бы одну строчную букву')
        if not re.search(r'\d', v):
            raise ValueError('Пароль должен содержать хотя бы одну цифру')
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Server schemas
class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(..., min_length=1, max_length=100)
    
    @validator('host')
    def validate_host(cls, v):
        """Проверка формата хоста (IP или домен)"""
        # Простая проверка на валидность IP или hostname
        if not v or len(v) == 0:
            raise ValueError('Host не может быть пустым')
        # Проверка на недопустимые символы
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('Host содержит недопустимые символы')
        return v


class ServerCreate(ServerBase):
    ssh_password: Optional[str] = None
    ssh_key_path: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    status: Optional[str] = None


class ServerResponse(ServerBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# VPN Client schemas
class VpnClientBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
    is_active: bool = True


class VpnClientResponse(VpnClientBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Client Config schemas
class ClientConfigBase(BaseModel):
    client_id: int
    server_id: int
    device_name: str
    protocol: str


class ClientConfigCreate(ClientConfigBase):
    config_content: str
    peer_public_key: Optional[str] = None
    client_uuid: Optional[str] = None
    client_email: Optional[str] = None
    endpoint: Optional[str] = None
    allowed_ips: Optional[str] = None


class ClientConfigUpdate(BaseModel):
    device_name: Optional[str] = None
    is_active: Optional[bool] = None
    config_content: Optional[str] = None


class ClientConfigResponse(ClientConfigBase):
    id: int
    user_id: int
    config_content: str
    peer_public_key: Optional[str] = None
    client_uuid: Optional[str] = None
    client_email: Optional[str] = None
    endpoint: Optional[str] = None
    allowed_ips: Optional[str] = None
    bytes_received: int = 0
    bytes_sent: int = 0
    is_active: bool
    is_online: bool = False
    last_handshake: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    created_at: datetime
    client: Optional["VpnClientResponse"] = None
    sharing_score: int = 0

    class Config:
        from_attributes = True


# Traffic schemas
class TrafficStats(BaseModel):
    config_id: int
    bytes_received: int
    bytes_sent: int
    speed_download: float
    speed_upload: float
    timestamp: datetime


class TrafficHistoryResponse(BaseModel):
    id: int
    config_id: int
    bytes_received: int
    bytes_sent: int
    speed_download: float
    speed_upload: float
    timestamp: datetime
    
    class Config:
        from_attributes = True


# Subscription schemas
class SubscriptionBase(BaseModel):
    client_id: Optional[int] = None
    config_id: Optional[int] = None
    subscription_type: Optional[str] = None
    subscription_start: datetime
    subscription_end: datetime
    traffic_limit_gb: Optional[int] = None


class SubscriptionCreate(SubscriptionBase):
    plan_id: int


class SubscriptionUpdate(BaseModel):
    subscription_end: Optional[datetime] = None
    is_active: Optional[bool] = None
    traffic_limit_gb: Optional[int] = None


class SubscriptionResponse(SubscriptionBase):
    id: int
    is_active: bool
    traffic_used_gb: float
    created_at: datetime

    class Config:
        from_attributes = True


# Endpoint Log schemas (Sharing Detection)
class EndpointLogResponse(BaseModel):
    id: int
    config_id: int
    endpoint_ip: str
    seen_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class SharingStatusResponse(BaseModel):
    config_id: int
    distinct_ips_24h: int
    sharing_score: int  # 0=ok, 1=suspicious, 2=sharing


class SharingAlertIpDetail(BaseModel):
    ip: str
    first_seen: datetime
    last_seen: datetime
    times_seen: int


class SharingAlertItem(BaseModel):
    config_id: int
    device_name: str
    client_name: Optional[str] = None
    protocol: Optional[str] = None
    is_online: bool = False
    is_active: bool = True
    distinct_ips_24h: int
    sharing_score: int
    ips: list[SharingAlertIpDetail] = []


# Bulk Config Creation
class BulkConfigCreate(BaseModel):
    client_id: int
    server_id: int
    protocol: str
    count: int = Field(..., ge=1, le=50)
    device_name_prefix: str = Field(default="Device", max_length=200)
    config_content_template: Optional[str] = ""
