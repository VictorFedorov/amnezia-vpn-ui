"""
Unit тесты для аутентификации
"""
import pytest
from app.utils.security import verify_password, get_password_hash, create_access_token, decode_access_token
from datetime import timedelta


@pytest.mark.unit
class TestPasswordHashing:
    """Тесты хеширования паролей"""
    
    def test_password_hash_and_verify(self):
        """Тест хеширования и проверки пароля"""
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False
    
    def test_same_password_different_hashes(self):
        """Одинаковые пароли дают разные хеши (из-за соли)"""
        password = "TestPassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


@pytest.mark.unit
class TestJWTTokens:
    """Тесты JWT токенов"""
    
    def test_create_and_decode_token(self):
        """Тест создания и декодирования токена"""
        data = {"sub": "testuser"}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        
        assert token is not None
        assert isinstance(token, str)
        
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
    
    def test_decode_invalid_token(self):
        """Тест декодирования невалидного токена"""
        invalid_token = "invalid.token.here"
        payload = decode_access_token(invalid_token)
        
        assert payload is None
    
    def test_token_expiration(self):
        """Тест истечения срока токена"""
        data = {"sub": "testuser"}
        # Создаем токен с отрицательным временем жизни (уже истек)
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        # Попытка декодировать истекший токен должна вернуть None
        payload = decode_access_token(token)
        assert payload is None


@pytest.mark.unit
def test_encryption_and_decryption():
    """Тест шифрования/дешифрования паролей SSH"""
    from app.utils.encryption import encrypt_password, decrypt_password
    
    original = "my_secure_password_123"
    encrypted = encrypt_password(original)
    
    assert encrypted != original
    assert encrypted is not None
    
    decrypted = decrypt_password(encrypted)
    assert decrypted == original


@pytest.mark.unit
def test_empty_password_encryption():
    """Тест шифрования пустого пароля"""
    from app.utils.encryption import encrypt_password, decrypt_password
    
    encrypted = encrypt_password("")
    assert encrypted == ""
    
    decrypted = decrypt_password("")
    assert decrypted is None
