"""
Unit тесты для моделей
"""
import pytest
from app.models import Server, User
from app.utils.security import get_password_hash, verify_password


@pytest.mark.unit
class TestServerModel:
    """Тесты модели Server"""
    
    def test_server_password_encryption(self, db_session):
        """Тест шифрования пароля сервера"""
        server = Server(
            name="Test Server",
            host="192.168.1.1",
            port=22,
            ssh_user="root"
        )
        
        password = "secure_password_123"
        server.set_password(password)
        
        assert server.ssh_password_encrypted is not None
        assert server.ssh_password_encrypted != password
        
        # Проверяем что можем расшифровать
        decrypted = server.get_password()
        assert decrypted == password
    
    def test_server_without_password(self, db_session):
        """Тест сервера без пароля (только SSH ключ)"""
        server = Server(
            name="Test Server",
            host="192.168.1.1",
            port=22,
            ssh_user="root",
            ssh_key_path="/path/to/key"
        )
        
        assert server.get_password() is None
    
    def test_server_update_password(self, db_session):
        """Тест обновления пароля сервера"""
        server = Server(
            name="Test Server",
            host="192.168.1.1",
            port=22,
            ssh_user="root"
        )
        
        password1 = "password1"
        server.set_password(password1)
        encrypted1 = server.ssh_password_encrypted
        
        password2 = "password2"
        server.set_password(password2)
        encrypted2 = server.ssh_password_encrypted
        
        assert encrypted1 != encrypted2
        assert server.get_password() == password2


@pytest.mark.unit
class TestUserModel:
    """Тесты модели User"""
    
    def test_user_password_hashing(self, db_session):
        """Тест хеширования пароля пользователя"""
        password = "TestPass123!"
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=get_password_hash(password)
        )
        
        assert user.password_hash != password
        assert verify_password(password, user.password_hash)
