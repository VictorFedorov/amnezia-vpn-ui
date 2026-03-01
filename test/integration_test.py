#!/usr/bin/env python3
"""
Тестовый скрипт для проверки консистентности данных между приложением и серверами.

Этот скрипт:
1. Получает данные клиента через API приложения
2. Получает данные напрямую с сервера через SSH
3. Сравнивает данные на консистентность

Использование:
python test/integration_test.py --client-id <ID> --server-id <ID> --token <API_TOKEN>
"""

import argparse
import requests
import json
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime

# Добавляем путь к backend для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.ssh_manager import create_ssh_manager
from app.services.awg_manager import AWGManager
from app.services.wireguard_manager import WireGuardManager
from app.services.xray_manager import XRayManager


class DataConsistencyTester:
    """Класс для тестирования консистентности данных"""

    def __init__(self, api_base_url: str = "http://localhost:8000/api", api_token: str = None):
        self.api_base_url = api_base_url.rstrip('/')
        self.api_token = api_token
        self.session = requests.Session()
        if api_token:
            self.session.headers.update({"Authorization": f"Bearer {api_token}"})

    def get_client_from_api(self, client_id: int) -> Optional[Dict]:
        """Получить данные клиента через API"""
        try:
            response = self.session.get(f"{self.api_base_url}/vpn-clients/{client_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Ошибка получения клиента через API: {e}")
            return None

    def get_client_configs_from_api(self, client_id: int) -> List[Dict]:
        """Получить конфигурации клиента через API"""
        try:
            response = self.session.get(f"{self.api_base_url}/configs/", params={"client_id": client_id})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Ошибка получения конфигураций через API: {e}")
            return []

    def get_server_users_from_api(self, server_id: int) -> Optional[Dict]:
        """Получить пользователей сервера через API"""
        try:
            response = self.session.get(f"{self.api_base_url}/servers/{server_id}/fetch-users")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Ошибка получения пользователей сервера через API: {e}")
            return None

    def get_server_from_db(self, server_id: int) -> Optional[Dict]:
        """Получить данные сервера из БД через API"""
        try:
            response = self.session.get(f"{self.api_base_url}/servers/{server_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Ошибка получения сервера через API: {e}")
            return None

    def get_peers_from_server(self, server_data: Dict, protocol: str) -> List[Dict]:
        """Получить пиров напрямую с сервера"""
        try:
            # Создаем SSH подключение
            ssh = create_ssh_manager(
                server_host=server_data['host'],
                server_port=server_data['port'],
                server_user=server_data['ssh_user'],
                server_password=server_data.get('ssh_password'),
                server_key=server_data.get('ssh_key_path')
            )

            if not ssh.connect():
                print("❌ Не удалось подключиться к серверу по SSH")
                return []

            # Получаем данные в зависимости от протокола
            if protocol == 'awg':
                manager = AWGManager(ssh)
            elif protocol == 'wireguard':
                manager = WireGuardManager(ssh)
            else:
                print(f"❌ Неподдерживаемый протокол: {protocol}")
                return []

            peers = manager.get_peers()
            ssh.disconnect()
            return peers

        except Exception as e:
            print(f"❌ Ошибка получения данных с сервера: {e}")
            return []

    def compare_peer_data(self, api_peer: Dict, server_peer: Dict, protocol: str) -> bool:
        """Сравнить данные пира из API и с сервера"""
        issues = []

        # Проверяем public key
        api_key = api_peer.get('peer_public_key') or api_peer.get('public_key')
        server_key = server_peer.get('public_key')

        if api_key != server_key:
            issues.append(f"Public key не совпадает: API='{api_key}' vs Server='{server_key}'")

        # Проверяем endpoint (если есть)
        api_endpoint = api_peer.get('endpoint')
        server_endpoint = server_peer.get('endpoint')

        if api_endpoint and server_endpoint and api_endpoint != server_endpoint:
            issues.append(f"Endpoint не совпадает: API='{api_endpoint}' vs Server='{server_endpoint}'")

        # Проверяем allowed_ips (если есть)
        api_allowed = api_peer.get('allowed_ips')
        server_allowed = server_peer.get('allowed_ips')

        if api_allowed and server_allowed and api_allowed != server_allowed:
            issues.append(f"Allowed IPs не совпадают: API='{api_allowed}' vs Server='{server_allowed}'")

        # Проверяем transfer данные (примерные)
        api_rx = api_peer.get('bytes_received', 0)
        server_rx = server_peer.get('transfer_rx', 0)

        # Допускаем небольшую разницу в transfer (могут быть несинхронизированы)
        if abs(api_rx - server_rx) > 1000:  # больше 1KB разницы
            issues.append(f"Transfer RX отличается значительно: API={api_rx} vs Server={server_rx}")

        if issues:
            print(f"⚠️  Найдены несоответствия для {protocol} пира:")
            for issue in issues:
                print(f"   - {issue}")
            return False
        else:
            print(f"✅ Данные {protocol} пира консистентны")
            return True

    def test_client_consistency(self, client_id: int, server_id: int):
        """Основная функция тестирования"""
        print(f"🚀 Начинаем тестирование клиента ID={client_id} на сервере ID={server_id}")
        print("=" * 60)

        # 1. Получаем данные клиента через API
        print("1️⃣ Получаем данные через API...")
        client_data = self.get_client_from_api(client_id)
        if not client_data:
            return False

        print(f"   Клиент: {client_data.get('name')} (ID: {client_data.get('id')})")

        # 2. Получаем конфигурации клиента
        configs = self.get_client_configs_from_api(client_id)
        print(f"   Найдено конфигураций: {len(configs)}")

        # 3. Получаем данные сервера
        server_data = self.get_server_from_db(server_id)
        if not server_data:
            return False

        print(f"   Сервер: {server_data.get('name')} ({server_data.get('host')}:{server_data.get('port')})")

        # 4. Получаем пользователей сервера через API
        server_users = self.get_server_users_from_api(server_id)
        if not server_users:
            return False

        print("2️⃣ Получаем данные напрямую с сервера...")

        all_consistent = True

        # 5. Для каждой конфигурации клиента проверяем консистентность
        for config in configs:
            if config['server_id'] != server_id:
                continue  # Пропускаем конфигурации с других серверов

            protocol = config['protocol']
            print(f"\n🔍 Проверяем конфигурацию {protocol} (ID: {config['id']})")

            # Находим соответствующего пира в данных сервера
            server_peers = []
            if protocol == 'awg':
                server_peers = server_users.get('awg_peers', [])
            elif protocol == 'wireguard':
                server_peers = server_users.get('wireguard_peers', [])
            elif protocol in ['vless', 'vmess', 'trojan', 'shadowsocks']:
                server_peers = server_users.get('xray_clients', [])

            # Ищем пира по ключу
            server_peer = None
            search_key = config.get('peer_public_key') or config.get('client_uuid')

            for peer in server_peers:
                peer_key = peer.get('public_key') or peer.get('uuid')
                if peer_key == search_key:
                    server_peer = peer
                    break

            if not server_peer:
                print(f"❌ Пир не найден на сервере для ключа: {search_key}")
                all_consistent = False
                continue

            # Сравниваем данные
            if not self.compare_peer_data(config, server_peer, protocol):
                all_consistent = False

        print("\n" + "=" * 60)
        if all_consistent:
            print("🎉 ВСЕ ДАННЫЕ КОНСИСТЕНТНЫ!")
            return True
        else:
            print("⚠️  НАЙДЕНЫ НЕСОСТЫКОВКИ В ДАННЫХ!")
            return False


def main():
    parser = argparse.ArgumentParser(description="Тест консистентности данных VPN клиентов")
    parser.add_argument("--client-id", type=int, required=True, help="ID клиента для тестирования")
    parser.add_argument("--server-id", type=int, required=True, help="ID сервера для тестирования")
    parser.add_argument("--api-url", default="http://localhost:8000/api", help="Базовый URL API")
    parser.add_argument("--token", help="API токен авторизации")

    args = parser.parse_args()

    # Если токен не указан, пытаемся получить из переменных окружения
    token = args.token or os.getenv('API_TOKEN')

    if not token:
        print("❌ Необходимо указать API токен через --token или переменную API_TOKEN")
        print("   Получить токен можно через авторизацию в приложении")
        sys.exit(1)

    tester = DataConsistencyTester(args.api_url, token)
    success = tester.test_client_consistency(args.client_id, args.server_id)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()