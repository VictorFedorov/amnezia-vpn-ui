"""
Утилиты для шифрования/дешифрования чувствительных данных
"""
from cryptography.fernet import Fernet
from app.core.config import settings
from typing import Optional
import base64
import hashlib


def _get_encryption_key() -> bytes:
    """
    Получить ключ шифрования.
    Использует ENCRYPTION_KEY если задан, иначе fallback на SECRET_KEY.
    Fernet требует 32-байтовый URL-safe base64-encoded ключ.
    """
    source_key = settings.ENCRYPTION_KEY if settings.ENCRYPTION_KEY else settings.SECRET_KEY
    key = hashlib.sha256(source_key.encode()).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_password(password: str) -> str:
    """
    Зашифровать пароль
    
    Args:
        password: Пароль в открытом виде
        
    Returns:
        Зашифрованный пароль (base64 string)
    """
    if not password:
        return ""
    
    key = _get_encryption_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(encrypted_password: str) -> Optional[str]:
    """
    Расшифровать пароль
    
    Args:
        encrypted_password: Зашифрованный пароль
        
    Returns:
        Пароль в открытом виде или None при ошибке
    """
    if not encrypted_password:
        return None
    
    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception:
        # Если не удалось расшифровать, возможно это старый незашифрованный пароль
        return None
