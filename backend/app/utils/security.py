from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
import base64
import re
import ipaddress

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Хеширование пароля"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создание JWT токена
    
    Args:
        data: Данные для кодирования в токен
        expires_delta: Время жизни токена
        
    Returns:
        JWT токен
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Декодирование JWT токена

    Args:
        token: JWT токен

    Returns:
        Decoded payload или None при ошибке
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def validate_wg_public_key(key: str) -> bool:
    """
    Валидация WireGuard public key (base64-encoded 32 bytes).

    Returns:
        True if valid, raises ValueError otherwise.
    """
    if not key or not isinstance(key, str):
        raise ValueError("Public key must be a non-empty string")
    try:
        decoded = base64.b64decode(key)
        if len(decoded) != 32:
            raise ValueError(f"Public key must be 32 bytes, got {len(decoded)}")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Invalid base64 in public key: {e}")
    # Only allow base64 characters + padding
    if not re.match(r'^[A-Za-z0-9+/=]+$', key):
        raise ValueError("Public key contains invalid characters")
    return True


def validate_cidr(cidr: str) -> bool:
    """
    Валидация CIDR notation (e.g. '10.8.0.2/32', 'fd00::1/128').
    Supports comma-separated CIDRs.

    Returns:
        True if valid, raises ValueError otherwise.
    """
    if not cidr or not isinstance(cidr, str):
        raise ValueError("CIDR must be a non-empty string")
    for part in cidr.split(","):
        part = part.strip()
        try:
            ipaddress.ip_network(part, strict=False)
        except ValueError:
            raise ValueError(f"Invalid CIDR: {part}")
    return True
