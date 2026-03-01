"""
Интеграционные тесты API пользователей
"""
import pytest
from fastapi import status


@pytest.mark.integration
class TestUsersAPI:
    """Тесты API пользователей"""
    
    def test_get_users_list(self, client, auth_headers, test_user):
        """Получение списка пользователей"""
        response = client.get("/api/users", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_create_user(self, client, auth_headers):
        """Создание нового пользователя"""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePass123!"
        }
        
        response = client.post(
            "/api/users",
            json=user_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "password" not in data  # Пароль не должен возвращаться
    
    def test_create_user_weak_password(self, client, auth_headers):
        """Попытка создать пользователя со слабым паролем"""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "weak"  # Слишком короткий
        }
        
        response = client.post(
            "/api/users",
            json=user_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_create_user_invalid_username(self, client, auth_headers):
        """Создание пользователя с невалидным username"""
        user_data = {
            "username": "us",  # Слишком короткий (минимум 3)
            "email": "user@example.com",
            "password": "SecurePass123!"
        }
        
        response = client.post(
            "/api/users",
            json=user_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_create_duplicate_user(self, client, auth_headers, test_user):
        """Попытка создать пользователя с существующим username"""
        user_data = {
            "username": "testuser",  # Уже существует
            "email": "another@example.com",
            "password": "SecurePass123!"
        }
        
        response = client.post(
            "/api/users",
            json=user_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_get_user_by_id(self, client, auth_headers, test_user):
        """Получение пользователя по ID"""
        response = client.get(
            f"/api/users/{test_user.id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_user.id
        assert data["username"] == "testuser"
    
    def test_update_user(self, client, auth_headers, test_user):
        """Обновление пользователя"""
        update_data = {
            "email": "updated@example.com"
        }
        
        response = client.put(
            f"/api/users/{test_user.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "updated@example.com"
    
    def test_update_user_password(self, client, auth_headers, test_user):
        """Обновление пароля пользователя"""
        update_data = {
            "password": "NewSecurePass456!"
        }
        
        response = client.put(
            f"/api/users/{test_user.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем что можем войти с новым паролем
        login_response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "NewSecurePass456!"}
        )
        assert login_response.status_code == status.HTTP_200_OK
    
    def test_delete_user(self, client, auth_headers, db_session):
        """Удаление пользователя"""
        from app.models import User
        from app.utils.security import get_password_hash
        
        # Создаем пользователя для удаления
        user_to_delete = User(
            username="todelete",
            email="delete@example.com",
            password_hash=get_password_hash("TestPass123!")
        )
        db_session.add(user_to_delete)
        db_session.commit()
        db_session.refresh(user_to_delete)
        
        response = client.delete(
            f"/api/users/{user_to_delete.id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Проверяем что пользователь удален
        get_response = client.get(
            f"/api/users/{user_to_delete.id}",
            headers=auth_headers
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_deactivate_user(self, client, auth_headers, db_session):
        """Деактивация пользователя"""
        from app.models import User
        from app.utils.security import get_password_hash
        
        # Создаем пользователя
        user = User(
            username="activeuser",
            email="active@example.com",
            password_hash=get_password_hash("TestPass123!"),
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Деактивируем
        update_data = {"is_active": False}
        response = client.put(
            f"/api/users/{user.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_active"] is False
