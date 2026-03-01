"""
Конфигурация для pytest - общие фикстуры
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.utils.security import get_password_hash
from app.models import User, Server


# Тестовая база данных в памяти
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Создать тестовую сессию БД для каждого теста"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Создать тестовый клиент FastAPI"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Создать тестового пользователя"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=get_password_hash("TestPass123!"),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client, test_user):
    """Получить заголовки авторизации для тестового пользователя"""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "TestPass123!"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_server(db_session):
    """Создать тестовый сервер"""
    server = Server(
        name="Test Server",
        host="192.168.1.100",
        port=22,
        ssh_user="root",
        status="active"
    )
    server.set_password("test_password")
    db_session.add(server)
    db_session.commit()
    db_session.refresh(server)
    return server
