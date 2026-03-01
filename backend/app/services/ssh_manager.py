import paramiko
from typing import Optional, Tuple
from app.core.config import Settings
import logging

logger = logging.getLogger(__name__)


class SSHManager:
    """Менеджер SSH соединений для управления VPN серверами"""

    def __init__(self, host: str, port: int, username: str, 
                 password: Optional[str] = None, key_path: Optional[str] = None,
                 strict_host_key_checking: bool = False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path
        self.strict_host_key_checking = strict_host_key_checking
        self.client: Optional[paramiko.SSHClient] = None

    def connect(self) -> bool:
        """Установить SSH соединение"""
        try:
            self.client = paramiko.SSHClient()
            
            # SECURITY: Настройка проверки host keys
            if self.strict_host_key_checking:
                # Production mode: строгая проверка host keys
                self.client.load_system_host_keys()
                self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
                logger.info("SSH: Strict host key checking enabled")
            else:
                # Development mode: предупреждение, но соединение разрешено
                self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
                logger.warning("SSH: Host key checking disabled - not recommended for production")

            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
            }

            if self.key_path:
                connect_kwargs['key_filename'] = self.key_path
            elif self.password:
                connect_kwargs['password'] = self.password
            else:
                raise ValueError("Either password or key_path must be provided")

            self.client.connect(**connect_kwargs, timeout=10)
            logger.info(f"SSH connection established to {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to {self.host}:{self.port}: {str(e)}")
            return False

    def disconnect(self):
        """Закрыть SSH соединение"""
        if self.client:
            self.client.close()
            logger.info(f"SSH connection closed to {self.host}:{self.port}")

    def execute_command(self, command: str) -> Tuple[int, str, str]:
        """
        Выполнить команду на удаленном сервере
        
        Returns:
            Tuple[exit_code, stdout, stderr]
        """
        if not self.client:
            raise RuntimeError("SSH connection not established. Call connect() first.")

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=30)
            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode('utf-8')
            stderr_text = stderr.read().decode('utf-8')

            logger.debug(f"Command executed: {command}")
            logger.debug(f"Exit code: {exit_code}")
            
            return exit_code, stdout_text, stderr_text

        except Exception as e:
            logger.error(f"Failed to execute command '{command}': {str(e)}")
            raise

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def create_ssh_manager(server_host: str, server_port: int, server_user: str,
                       server_password: Optional[str] = None, 
                       server_key: Optional[str] = None) -> SSHManager:
    """
    Фабричная функция для создания SSH менеджера
    
    Args:
        server_host: Хост сервера
        server_port: Порт SSH
        server_user: Имя пользователя
        server_password: Пароль (опционально)
        server_key: Путь к SSH ключу (опционально)
    
    Returns:
        SSHManager instance
    """
    return SSHManager(
        host=server_host,
        port=server_port,
        username=server_user,
        password=server_password,
        key_path=server_key
    )
