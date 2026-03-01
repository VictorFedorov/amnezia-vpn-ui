from typing import Dict, List, Optional
from app.services.ssh_manager import SSHManager
from app.utils.security import validate_wg_public_key, validate_cidr
import re
import time
import logging

logger = logging.getLogger(__name__)


class WireGuardManager:
    """Менеджер для работы со стандартным WireGuard через Docker контейнер"""

    def __init__(self, ssh_manager: SSHManager, container_name: str = "amnezia-wireguard", interface: str = "wg0"):
        self.ssh = ssh_manager
        self.container_name = container_name
        self.interface = interface

    def get_peers(self) -> List[Dict]:
        """
        Получить список всех пиров из WireGuard

        Returns:
            List of dicts with peer info:
            [
                {
                    'public_key': 'abc123...',
                    'endpoint': '1.2.3.4:5678',
                    'allowed_ips': '10.8.0.2/32',
                    'latest_handshake': 1234567890,
                    'transfer_rx': 123456,
                    'transfer_tx': 654321
                },
                ...
            ]
        """
        try:
            command = f"docker exec {self.container_name} wg show {self.interface}"
            exit_code, stdout, stderr = self.ssh.execute_command(command)

            if exit_code != 0:
                logger.error(f"Failed to get WireGuard peers: {stderr}")
                return []

            peers = self._parse_wg_show_output(stdout)
            logger.info(f"Retrieved {len(peers)} peers from WireGuard")
            return peers

        except Exception as e:
            logger.error(f"Error getting WireGuard peers: {str(e)}")
            return []

    def _parse_wg_show_output(self, output: str) -> List[Dict]:
        """Парсинг вывода команды 'wg show'"""
        peers = []
        current_peer = None

        for line in output.split('\n'):
            line = line.strip()

            if line.startswith('peer:'):
                if current_peer:
                    peers.append(current_peer)
                current_peer = {
                    'public_key': line.split('peer:')[1].strip(),
                    'endpoint': None,
                    'allowed_ips': None,
                    'latest_handshake': None,
                    'transfer_rx': 0,
                    'transfer_tx': 0
                }
            elif current_peer:
                if 'endpoint:' in line:
                    current_peer['endpoint'] = line.split('endpoint:')[1].strip()
                elif 'allowed ips:' in line:
                    current_peer['allowed_ips'] = line.split('allowed ips:')[1].strip()
                elif 'latest handshake:' in line:
                    handshake_str = line.split('latest handshake:')[1].strip()
                    current_peer['latest_handshake'] = self._parse_handshake(handshake_str)
                elif 'transfer:' in line:
                    # Формат: "transfer: 1.23 MiB received, 456.78 KiB sent"
                    transfer_match = re.search(r'([\d.]+)\s*(\w+)\s*received,\s*([\d.]+)\s*(\w+)\s*sent', line)
                    if transfer_match:
                        rx_value, rx_unit = float(transfer_match.group(1)), transfer_match.group(2)
                        tx_value, tx_unit = float(transfer_match.group(3)), transfer_match.group(4)
                        current_peer['transfer_rx'] = self._convert_to_bytes(rx_value, rx_unit)
                        current_peer['transfer_tx'] = self._convert_to_bytes(tx_value, tx_unit)

        if current_peer:
            peers.append(current_peer)

        return peers

    def _parse_handshake(self, handshake_str: str) -> int:
        """Парсинг строки handshake в Unix timestamp"""
        if not handshake_str:
            return 0
        try:
            return int(handshake_str)
        except ValueError:
            pass
        total_seconds = 0
        patterns = [
            (r'(\d+)\s*year', 365 * 24 * 3600),
            (r'(\d+)\s*month', 30 * 24 * 3600),
            (r'(\d+)\s*week', 7 * 24 * 3600),
            (r'(\d+)\s*day', 24 * 3600),
            (r'(\d+)\s*hour', 3600),
            (r'(\d+)\s*minute', 60),
            (r'(\d+)\s*second', 1),
        ]
        for pattern, multiplier in patterns:
            match = re.search(pattern, handshake_str)
            if match:
                total_seconds += int(match.group(1)) * multiplier
        if total_seconds > 0:
            return int(time.time()) - total_seconds
        return 0

    def _convert_to_bytes(self, value: float, unit: str) -> int:
        """Конвертация размера в байты"""
        units = {
            'B': 1,
            'KiB': 1024,
            'MiB': 1024**2,
            'GiB': 1024**3,
            'TiB': 1024**4
        }
        return int(value * units.get(unit, 1))

    def block_peer(self, public_key: str) -> bool:
        """
        Блокировка пира (удаление из runtime config)
        """
        try:
            validate_wg_public_key(public_key)
            # wg set wg0 peer <PUBKEY> remove
            command = f"docker exec {self.container_name} wg set {self.interface} peer {public_key} remove"
            exit_code, stdout, stderr = self.ssh.execute_command(command)

            if exit_code != 0:
                logger.error(f"Failed to block peer {public_key}: {stderr}")
                return False

            logger.info(f"Blocked peer {public_key}")
            return True
        except Exception as e:
            logger.error(f"Error blocking peer {public_key}: {str(e)}")
            return False

    def unblock_peer(self, public_key: str, allowed_ips: str) -> bool:
        """
        Разблокировка пира (добавление обратно)
        """
        try:
            validate_wg_public_key(public_key)
            validate_cidr(allowed_ips)
            # wg set wg0 peer <PUBKEY> allowed-ips <IPS>
            command = f"docker exec {self.container_name} wg set {self.interface} peer {public_key} allowed-ips {allowed_ips}"
            exit_code, stdout, stderr = self.ssh.execute_command(command)

            if exit_code != 0:
                logger.error(f"Failed to unblock peer {public_key}: {stderr}")
                return False

            logger.info(f"Unblocked peer {public_key} with ips {allowed_ips}")
            return True
        except Exception as e:
            logger.error(f"Error unblocking peer {public_key}: {str(e)}")
            return False

    def get_peer_stats(self, public_key: str) -> Optional[Dict]:
        """
        Получить статистику конкретного пира

        Args:
            public_key: Публичный ключ пира

        Returns:
            Dict with peer stats or None
        """
        peers = self.get_peers()
        for peer in peers:
            if peer['public_key'] == public_key:
                return peer
        return None

    def add_peer(self, public_key: str, allowed_ips: str) -> bool:
        """
        Добавить нового пира (TODO: требует доступа к конфигу)

        Args:
            public_key: Публичный ключ клиента
            allowed_ips: Разрешенные IP адреса (например, "10.8.0.5/32")

        Returns:
            bool: True if successful
        """
        # TODO: Реализовать добавление пира через изменение конфига и перезагрузку
        logger.warning("add_peer not implemented yet")
        return False

    def remove_peer(self, public_key: str) -> bool:
        """
        Удалить пира (TODO: требует доступа к конфигу)

        Args:
            public_key: Публичный ключ пира для удаления

        Returns:
            bool: True if successful
        """
        # TODO: Реализовать удаление пира через изменение конфига и перезагрузку
        logger.warning("remove_peer not implemented yet")
        return False

    def generate_config(self, client_private_key: str, client_address: str,
                       server_public_key: str, server_endpoint: str) -> str:
        """
        Генерация конфигурации клиента WireGuard

        Args:
            client_private_key: Приватный ключ клиента
            client_address: IP адрес клиента (например, "10.8.0.5/32")
            server_public_key: Публичный ключ сервера
            server_endpoint: Endpoint сервера (например, "1.2.3.4:51820")

        Returns:
            str: Конфигурация в формате WireGuard INI
        """
        config = f"""[Interface]
PrivateKey = {client_private_key}
Address = {client_address}
DNS = 1.1.1.1

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
        return config

    def check_container_status(self) -> bool:
        """Проверить статус Docker контейнера"""
        try:
            command = f"docker ps --filter name={self.container_name} --format '{{{{.Status}}}}'"
            exit_code, stdout, stderr = self.ssh.execute_command(command)

            if exit_code == 0 and stdout.strip():
                logger.info(f"Container {self.container_name} is running")
                return True
            else:
                logger.warning(f"Container {self.container_name} is not running")
                return False

        except Exception as e:
            logger.error(f"Error checking container status: {str(e)}")
            return False