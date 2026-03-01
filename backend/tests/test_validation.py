"""
Тесты валидации схем данных
"""
import pytest
from pydantic import ValidationError
from app.api.schemas import UserCreate, ServerCreate, ServerBase


@pytest.mark.unit
class TestUserValidation:
    """Тесты валидации пользователей"""
    
    def test_valid_user_creation(self):
        """Валидный пользователь"""
        user = UserCreate(
            username="validuser",
            email="valid@example.com",
            password="SecurePass123!"
        )
        
        assert user.username == "validuser"
        assert user.email == "valid@example.com"
    
    def test_short_username(self):
        """Username слишком короткий"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="ab",  # Менее 3 символов
                email="test@example.com",
                password="SecurePass123!"
            )
        
        assert "username" in str(exc_info.value)
    
    def test_invalid_username_characters(self):
        """Username с недопустимыми символами"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="invalid user!",  # Пробелы и спецсимволы
                email="test@example.com",
                password="SecurePass123!"
            )
        
        assert "username" in str(exc_info.value)
    
    def test_weak_password_no_uppercase(self):
        """Пароль без заглавных букв"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="lowercase123"
            )
        
        errors = str(exc_info.value)
        assert "заглавн" in errors.lower() or "uppercase" in errors.lower()
    
    def test_weak_password_no_digit(self):
        """Пароль без цифр"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="NoDigitsHere"
            )
        
        errors = str(exc_info.value)
        assert "цифр" in errors.lower() or "digit" in errors.lower()
    
    def test_weak_password_too_short(self):
        """Слишком короткий пароль"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="Short1"
            )
        
        errors = str(exc_info.value)
        assert "8" in errors or "символ" in errors.lower()
    
    def test_invalid_email(self):
        """Невалидный email"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="testuser",
                email="invalid-email",
                password="SecurePass123!"
            )
        
        assert "email" in str(exc_info.value)


@pytest.mark.unit
class TestServerValidation:
    """Тесты валидации серверов"""
    
    def test_valid_server(self):
        """Валидный сервер"""
        server = ServerBase(
            name="Valid Server",
            host="192.168.1.1",
            port=22,
            ssh_user="root"
        )
        
        assert server.name == "Valid Server"
        assert server.host == "192.168.1.1"
    
    def test_invalid_port_too_high(self):
        """Port выше допустимого"""
        with pytest.raises(ValidationError) as exc_info:
            ServerBase(
                name="Test Server",
                host="192.168.1.1",
                port=99999,
                ssh_user="root"
            )
        
        assert "port" in str(exc_info.value)
    
    def test_invalid_port_too_low(self):
        """Port ниже допустимого"""
        with pytest.raises(ValidationError) as exc_info:
            ServerBase(
                name="Test Server",
                host="192.168.1.1",
                port=0,
                ssh_user="root"
            )
        
        assert "port" in str(exc_info.value)
    
    def test_empty_name(self):
        """Пустое имя сервера"""
        with pytest.raises(ValidationError) as exc_info:
            ServerBase(
                name="",
                host="192.168.1.1",
                port=22,
                ssh_user="root"
            )
        
        assert "name" in str(exc_info.value)
    
    def test_invalid_host_characters(self):
        """Host с недопустимыми символами"""
        with pytest.raises(ValidationError) as exc_info:
            ServerBase(
                name="Test Server",
                host="invalid host with spaces",
                port=22,
                ssh_user="root"
            )
        
        errors = str(exc_info.value)
        assert "host" in errors.lower()
    
    def test_valid_hostname(self):
        """Валидный hostname"""
        server = ServerBase(
            name="Test Server",
            host="example.com",
            port=22,
            ssh_user="root"
        )
        
        assert server.host == "example.com"
    
    def test_valid_hostname_with_subdomain(self):
        """Валидный hostname с поддоменом"""
        server = ServerBase(
            name="Test Server",
            host="vpn.example.com",
            port=22,
            ssh_user="root"
        )
        
        assert server.host == "vpn.example.com"
