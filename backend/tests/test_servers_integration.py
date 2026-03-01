"""
Интеграционные тесты API серверов
"""
import pytest
from fastapi import status
from unittest.mock import Mock, patch


@pytest.mark.integration
class TestServersAPI:
    """Тесты API серверов"""
    
    def test_get_servers_list(self, client, auth_headers, test_server):
        """Получение списка серверов"""
        response = client.get("/api/servers", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "Test Server"
    
    def test_get_servers_unauthorized(self, client):
        """Попытка получить список серверов без авторизации"""
        response = client.get("/api/servers")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @patch('app.api.routes.servers.create_ssh_manager')
    def test_create_server_success(self, mock_ssh, client, auth_headers):
        """Создание нового сервера"""
        # Мокаем SSH подключение
        mock_ssh_instance = Mock()
        mock_ssh_instance.connect.return_value = True
        mock_ssh.return_value = mock_ssh_instance
        
        server_data = {
            "name": "New Server",
            "host": "192.168.1.200",
            "port": 22,
            "ssh_user": "root",
            "ssh_password": "secret_pass"
        }
        
        response = client.post(
            "/api/servers",
            json=server_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "New Server"
        assert data["host"] == "192.168.1.200"
        # Пароль не должен возвращаться в ответе
        assert "ssh_password" not in data
    
    def test_create_server_duplicate_name(self, client, auth_headers, test_server):
        """Попытка создать сервер с существующим именем"""
        server_data = {
            "name": "Test Server",  # Дубликат
            "host": "192.168.1.201",
            "port": 22,
            "ssh_user": "root",
            "ssh_password": "secret_pass"
        }
        
        response = client.post(
            "/api/servers",
            json=server_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_create_server_invalid_port(self, client, auth_headers):
        """Попытка создать сервер с невалидным портом"""
        server_data = {
            "name": "Invalid Server",
            "host": "192.168.1.200",
            "port": 99999,  # Невалидный порт
            "ssh_user": "root"
        }
        
        response = client.post(
            "/api/servers",
            json=server_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_get_server_by_id(self, client, auth_headers, test_server):
        """Получение сервера по ID"""
        response = client.get(
            f"/api/servers/{test_server.id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_server.id
        assert data["name"] == "Test Server"
    
    def test_get_nonexistent_server(self, client, auth_headers):
        """Попытка получить несуществующий сервер"""
        response = client.get(
            "/api/servers/99999",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @patch('app.api.routes.servers.create_ssh_manager')
    def test_update_server(self, mock_ssh, client, auth_headers, test_server):
        """Обновление сервера"""
        # Мокаем SSH подключение
        mock_ssh_instance = Mock()
        mock_ssh_instance.connect.return_value = True
        mock_ssh.return_value = mock_ssh_instance
        
        update_data = {
            "name": "Updated Server",
            "port": 2222
        }
        
        response = client.put(
            f"/api/servers/{test_server.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Server"
        assert data["port"] == 2222
    
    def test_delete_server(self, client, auth_headers, test_server):
        """Удаление сервера"""
        response = client.delete(
            f"/api/servers/{test_server.id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Проверяем что сервер действительно удален
        response = client.get(
            f"/api/servers/{test_server.id}",
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestServersValidation:
    """Тесты валидации данных серверов"""
    
    def test_create_server_invalid_host(self, client, auth_headers):
        """Создание сервера с невалидным хостом"""
        server_data = {
            "name": "Invalid Host Server",
            "host": "invalid host with spaces",
            "port": 22,
            "ssh_user": "root"
        }
        
        response = client.post(
            "/api/servers",
            json=server_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_create_server_empty_name(self, client, auth_headers):
        """Создание сервера с пустым именем"""
        server_data = {
            "name": "",
            "host": "192.168.1.1",
            "port": 22,
            "ssh_user": "root"
        }
        
        response = client.post(
            "/api/servers",
            json=server_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
