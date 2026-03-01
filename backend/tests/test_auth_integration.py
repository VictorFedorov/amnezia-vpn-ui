"""
Интеграционные тесты API аутентификации
"""
import pytest
from fastapi import status


@pytest.mark.integration
class TestAuthAPI:
    """Тесты API аутентификации"""
    
    def test_login_success(self, client, test_user):
        """Успешный вход в систему"""
        response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "TestPass123!"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_wrong_password(self, client, test_user):
        """Вход с неправильным паролем"""
        response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "WrongPassword"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_nonexistent_user(self, client):
        """Вход несуществующего пользователя"""
        response = client.post(
            "/api/auth/login",
            data={"username": "nonexistent", "password": "SomePassword"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_current_user(self, client, auth_headers):
        """Получение информации о текущем пользователе"""
        response = client.get("/api/auth/me", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
    
    def test_get_current_user_unauthorized(self, client):
        """Попытка получить информацию без токена"""
        response = client.get("/api/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_current_user_invalid_token(self, client):
        """Попытка получить информацию с невалидным токеном"""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_logout(self, client, auth_headers):
        """Выход из системы"""
        response = client.post("/api/auth/logout", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.json()


@pytest.mark.integration
def test_rate_limiting_login(client, test_user):
    """Тест ограничения частоты запросов на login"""
    # Делаем более 5 попыток входа
    for i in range(6):
        response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "WrongPassword"}
        )
        
        if i < 5:
            # Первые 5 попыток должны проходить (хотя с ошибкой auth)
            assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_429_TOO_MANY_REQUESTS]
        else:
            # 6-я попытка должна быть заблокирована rate limiter
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
