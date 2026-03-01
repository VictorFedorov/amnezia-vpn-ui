"""
Unit тесты для SSH Manager
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.ssh_manager import SSHManager
import paramiko


@pytest.mark.unit
class TestSSHManager:
    """Тесты SSH Manager"""
    
    @patch('paramiko.SSHClient')
    def test_connect_with_password(self, mock_ssh_client_class):
        """Тест подключения с паролем"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        ssh = SSHManager(
            host="192.168.1.1",
            port=22,
            username="root",
            password="password123"
        )
        
        result = ssh.connect()
        
        assert result is True
        mock_client.connect.assert_called_once()
        
        # Проверяем что set_missing_host_key_policy был вызван
        assert mock_client.set_missing_host_key_policy.called
    
    @patch('paramiko.SSHClient')
    def test_connect_with_key(self, mock_ssh_client_class):
        """Тест подключения с SSH ключом"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        ssh = SSHManager(
            host="192.168.1.1",
            port=22,
            username="root",
            key_path="/path/to/key"
        )
        
        result = ssh.connect()
        
        assert result is True
        mock_client.connect.assert_called_once()
    
    @patch('paramiko.SSHClient')
    def test_connect_failure(self, mock_ssh_client_class):
        """Тест неудачного подключения"""
        mock_client = Mock()
        mock_client.connect.side_effect = paramiko.SSHException("Connection failed")
        mock_ssh_client_class.return_value = mock_client
        
        ssh = SSHManager(
            host="192.168.1.1",
            port=22,
            username="root",
            password="password123"
        )
        
        result = ssh.connect()
        
        assert result is False
    
    @patch('paramiko.SSHClient')
    def test_execute_command(self, mock_ssh_client_class):
        """Тест выполнения команды"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        # Мокаем вывод команды
        mock_stdout = Mock()
        mock_stdout.read.return_value = b"Command output"
        mock_stdout.channel.recv_exit_status.return_value = 0
        
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        
        mock_client.exec_command.return_value = (Mock(), mock_stdout, mock_stderr)
        
        ssh = SSHManager(
            host="192.168.1.1",
            port=22,
            username="root",
            password="password123"
        )
        ssh.client = mock_client  # Устанавливаем мокнутый клиент
        
        exit_code, stdout, stderr = ssh.execute_command("ls -la")
        
        assert exit_code == 0
        assert stdout == "Command output"
        assert stderr == ""
    
    @patch('paramiko.SSHClient')
    def test_disconnect(self, mock_ssh_client_class):
        """Тест отключения"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        ssh = SSHManager(
            host="192.168.1.1",
            port=22,
            username="root",
            password="password123"
        )
        ssh.client = mock_client
        
        ssh.disconnect()
        
        mock_client.close.assert_called_once()
    
    @patch('paramiko.SSHClient')
    def test_context_manager(self, mock_ssh_client_class):
        """Тест использования как context manager"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        with SSHManager(
            host="192.168.1.1",
            port=22,
            username="root",
            password="password123"
        ) as ssh:
            assert ssh is not None
        
        # Проверяем что disconnect был вызван
        mock_client.close.assert_called_once()
    
    @patch('paramiko.SSHClient')
    def test_strict_host_key_checking(self, mock_ssh_client_class):
        """Тест строгой проверки host keys"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        ssh = SSHManager(
            host="192.168.1.1",
            port=22,
            username="root",
            password="password123",
            strict_host_key_checking=True
        )
        
        ssh.connect()
        
        # В строгом режиме должны загружаться системные host keys
        mock_client.load_system_host_keys.assert_called_once()
