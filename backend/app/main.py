from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.background import BackgroundScheduler
from app.core.config import settings
from app.core.database import init_db, SessionLocal
from app.api.routes import users, servers, traffic, auth, configs, subscriptions, subscription_plans, vpn_clients, ws
from app.models import User
from app.utils.security import get_password_hash
from app.services.traffic_sync import sync_all_traffic
import secrets
import string

scheduler = BackgroundScheduler()

# Создание FastAPI приложения
app = FastAPI(
    title="AmneziaVPN Management API",
    description="API для управления self-hosted AmneziaVPN сервером",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
cors_origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(vpn_clients.router, prefix="/api/vpn-clients", tags=["vpn-clients"])
app.include_router(servers.router, prefix="/api/servers", tags=["servers"])
app.include_router(configs.router, prefix="/api/configs", tags=["configs"])
app.include_router(traffic.router, prefix="/api/traffic", tags=["traffic"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])
app.include_router(subscription_plans.router, prefix="/api/subscription-plans", tags=["subscription_plans"])
app.include_router(ws.router, prefix="/api", tags=["websocket"])


@app.on_event("startup")
async def startup_event():
    """Выполняется при запуске приложения"""
    print("🚀 Запуск AmneziaVPN Management API...")
    
    # Миграции применяются через docker-compose команду перед стартом
    # init_db() теперь не создает таблицы напрямую
    init_db() 
    
    # Создание админа если нет
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if not admin:
            # Генерируем сильный пароль если не задан в .env
            if settings.ADMIN_PASSWORD:
                admin_password = settings.ADMIN_PASSWORD
                print(f"👤 Создание администратора ({settings.ADMIN_USERNAME}) с паролем из .env...")
            else:
                # Генерируем случайный пароль: 16 символов с буквами, цифрами и спецсимволами
                alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                admin_password = ''.join(secrets.choice(alphabet) for _ in range(16))
                print(f"👤 Создание администратора ({settings.ADMIN_USERNAME})...")
                print(f"🔐 СГЕНЕРИРОВАННЫЙ ПАРОЛЬ: {admin_password}")
                print(f"⚠️  СОХРАНИТЕ ЕГО! Пароль показывается только один раз!")
            
            admin_user = User(
                username=settings.ADMIN_USERNAME,
                email="admin@example.com",
                password_hash=get_password_hash(admin_password),
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("✅ Администратор создан")
    except Exception as e:
        print(f"❌ Ошибка при проверке/создании админа: {e}")
    finally:
        db.close()

    # Запускаем планировщик синхронизации трафика
    scheduler.add_job(
        sync_all_traffic,
        trigger="interval",
        seconds=settings.TRAFFIC_POLL_INTERVAL,
        id="traffic_sync",
        replace_existing=True,
    )
    scheduler.start()
    print(f"⏱️  Планировщик трафика запущен (каждые {settings.TRAFFIC_POLL_INTERVAL} сек)")
    print("✅ API запущен успешно")


@app.on_event("shutdown")
async def shutdown_event():
    """Выполняется при остановке приложения"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
    print("👋 Остановка API...")


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "message": "AmneziaVPN Management API",
        "version": "1.0.0",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
