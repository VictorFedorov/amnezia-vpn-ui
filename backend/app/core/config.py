from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Основные настройки
    ENV: str = "development"
    DEBUG: bool = False

    # База данных
    DATABASE_URL: str

    # JWT аутентификация
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 час

    # Отдельный ключ шифрования (если не задан, используется SECRET_KEY)
    ENCRYPTION_KEY: Optional[str] = None
    
    # Администратор по умолчанию
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: Optional[str] = None  # Если не задан, генерируется случайный
    
    # SSH настройки
    SSH_HOST: str
    SSH_PORT: int = 22
    SSH_USER: str
    SSH_PASSWORD: Optional[str] = None
    SSH_KEY_PATH: Optional[str] = None
    SSH_STRICT_HOST_KEY_CHECKING: bool = False  # В production должно быть True
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"
    
    # Polling интервалы
    TRAFFIC_POLL_INTERVAL: int = 300  # секунд (5 минут)
    SUBSCRIPTION_CHECK_INTERVAL: int = 3600  # секунд
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Получить список CORS origins"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()
