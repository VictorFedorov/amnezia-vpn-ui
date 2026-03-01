from typing import Dict, List, Optional
from app.services.ssh_manager import SSHManager
import json
import logging

logger = logging.getLogger(__name__)


class XRayManager:
    """Менеджер для работы с XRay через Docker контейнер"""

    def __init__(self, ssh_manager: SSHManager, container_name: str = "amnezia-xray"):
        self.ssh = ssh_manager
        self.container_name = container_name

    def get_clients(self) -> List[Dict]:
        """
        Получить список всех клиентов XRay из конфигурации сервера
        
        Returns:
            List of dicts with client info
        """
        try:
            # Читаем конфигурацию Xray с сервера
            config_cmd = "docker exec amnezia-xray cat /opt/amnezia/xray/server.json"
            exit_code, stdout, stderr = self.ssh.execute_command(config_cmd)
            
            if exit_code != 0:
                logger.error(f"Failed to read XRay config: {stderr}")
                return []
            
            import json
            config = json.loads(stdout)
            
            clients = []
            if "inbounds" in config:
                for inbound in config["inbounds"]:
                    protocol = inbound.get("protocol", "")
                    if protocol in ("vless", "vmess", "trojan", "shadowsocks") and "settings" in inbound:
                        for client in inbound["settings"].get("clients", []):
                            client_info = {
                                "uuid": client.get("id"),
                                "email": client.get("email", ""),
                                "flow": client.get("flow", ""),
                                "protocol": protocol
                            }
                            clients.append(client_info)
            
            logger.info(f"Found {len(clients)} XRay clients in config")
            return clients

        except Exception as e:
            logger.error(f"Error getting XRay clients: {str(e)}")
            return []

    def get_stats(self) -> Dict[str, Dict]:
        """
        Получить статистику трафика всех клиентов через XRay API
        
        Returns:
            Dict with format:
            {
                'user_email_or_uuid': {
                    'uplink': 123456,
                    'downlink': 654321
                },
                ...
            }
        """
        try:
            command = f"docker exec {self.container_name} xray api statsquery --server=127.0.0.1:10085"
            exit_code, stdout, stderr = self.ssh.execute_command(command)

            if exit_code != 0:
                logger.error(f"Failed to get XRay stats: {stderr}")
                return {}

            stats = self._parse_stats_output(stdout)
            logger.info(f"Retrieved stats for {len(stats)} XRay clients")
            return stats

        except Exception as e:
            logger.error(f"Error getting XRay stats: {str(e)}")
            return {}

    def _parse_stats_output(self, output: str) -> Dict[str, Dict]:
        """
        Парсинг вывода команды 'xray api statsquery'.
        Поддерживает JSON-формат (новый XRay) и текстовый (старый).

        JSON формат:
        {
            "stat": [
                {"name": "user>>>uuid>>>traffic>>>uplink", "value": 1234},
                ...
            ]
        }

        Текстовый формат:
        stat: <
          name: "user>>>email>>>traffic>>>uplink"
          value: 1234567
        >
        """
        stats: Dict[str, Dict] = {}

        # --- JSON формат ---
        try:
            data = json.loads(output)
            for entry in data.get("stat", []):
                name = entry.get("name", "")
                value = entry.get("value", 0)
                parts = name.split(">>>")
                if len(parts) >= 4 and parts[0] == "user" and parts[2] == "traffic":
                    user_id = parts[1]
                    direction = parts[3]  # uplink / downlink
                    stats.setdefault(user_id, {"uplink": 0, "downlink": 0})
                    stats[user_id][direction] = value
            return stats
        except (json.JSONDecodeError, AttributeError):
            pass

        # --- Текстовый формат (fallback) ---
        current_name = None
        for line in output.split("\n"):
            line = line.strip()
            if "name:" in line:
                current_name = line.split("name:")[1].strip().strip('"')
            elif "value:" in line and current_name:
                try:
                    value = int(line.split("value:")[1].strip())
                except ValueError:
                    current_name = None
                    continue
                parts = current_name.split(">>>")
                if len(parts) >= 4 and parts[0] == "user" and parts[2] == "traffic":
                    user_id = parts[1]
                    direction = parts[3]
                    stats.setdefault(user_id, {"uplink": 0, "downlink": 0})
                    stats[user_id][direction] = value
                current_name = None

        return stats

    def get_client_stats(self, client_id: str) -> Optional[Dict]:
        """
        Получить статистику конкретного клиента
        
        Args:
            client_id: Email или UUID клиента
            
        Returns:
            Dict with stats or None
        """
        all_stats = self.get_stats()
        return all_stats.get(client_id)

    def enable_stats_api(self) -> Dict:
        """
        Добавляет API статистики в конфиг XRay:
        - inbound dokodemo-door на 127.0.0.1:10085
        - секции api, stats, policy, routing
        - поле email (= UUID) каждому клиенту для идентификации в stats

        Returns:
            Dict: {"success": bool, "message": str, "clients_updated": int}
        """
        try:
            # Читаем текущий конфиг
            code, out, err = self.ssh.execute_command(
                f"docker exec {self.container_name} cat /opt/amnezia/xray/server.json"
            )
            if code != 0:
                return {"success": False, "message": f"Failed to read config: {err}"}

            config = json.loads(out)

            # --- 1. Добавляем email каждому клиенту ---
            clients_updated = 0
            for inbound in config.get("inbounds", []):
                protocol = inbound.get("protocol", "")
                if protocol in ("vless", "vmess", "trojan", "shadowsocks"):
                    for client in inbound.get("settings", {}).get("clients", []):
                        if not client.get("email"):
                            client["email"] = client.get("id", "")
                            clients_updated += 1

            # --- 2. Добавляем api inbound (dokodemo-door 127.0.0.1:10085) ---
            api_inbound_exists = any(
                ib.get("tag") == "api" for ib in config.get("inbounds", [])
            )
            if not api_inbound_exists:
                config.setdefault("inbounds", []).append({
                    "listen": "127.0.0.1",
                    "port": 10085,
                    "protocol": "dokodemo-door",
                    "settings": {"address": "127.0.0.1"},
                    "tag": "api"
                })

            # --- 3. Добавляем секции api, stats, policy ---
            config.setdefault("api", {
                "services": ["HandlerService", "LoggerService", "StatsService"],
                "tag": "api"
            })
            config.setdefault("stats", {})
            config.setdefault("policy", {
                "levels": {"0": {"statsUserUplink": True, "statsUserDownlink": True}},
                "system": {"statsOutboundUplink": True, "statsOutboundDownlink": True}
            })

            # --- 4. Добавляем routing для api ---
            config.setdefault("routing", {"rules": []})
            api_rule_exists = any(
                "api" in r.get("inboundTag", [])
                for r in config["routing"].get("rules", [])
            )
            if not api_rule_exists:
                config["routing"].setdefault("rules", []).insert(0, {
                    "inboundTag": ["api"],
                    "outboundTag": "api"
                })

            # --- 5. Добавляем tag к outbound freedom ---
            for ob in config.get("outbounds", []):
                if ob.get("protocol") == "freedom" and not ob.get("tag"):
                    ob["tag"] = "freedom"

            # --- 6. Записываем обновлённый конфиг обратно ---
            new_config_json = json.dumps(config, indent=2, ensure_ascii=False)
            escaped = new_config_json.replace("'", "'\\''")
            write_cmd = (
                f"echo '{escaped}' | "
                f"docker exec -i {self.container_name} tee /opt/amnezia/xray/server.json > /dev/null"
            )
            code, out, err = self.ssh.execute_command(write_cmd)
            if code != 0:
                return {"success": False, "message": f"Failed to write config: {err}"}

            # --- 7. Перезапускаем контейнер ---
            code, out, err = self.ssh.execute_command(
                f"docker restart {self.container_name}"
            )
            if code != 0:
                return {"success": False, "message": f"Failed to restart container: {err}"}

            logger.info(
                f"XRay stats API enabled, {clients_updated} clients updated with email"
            )
            return {
                "success": True,
                "message": "Stats API enabled, container restarted",
                "clients_updated": clients_updated
            }

        except Exception as e:
            logger.error(f"Error enabling XRay stats API: {e}")
            return {"success": False, "message": str(e)}

    def add_client(self, client_id: str, protocol: str = "vless") -> bool:
        """
        Добавить нового клиента (TODO: требует API управления или изменения конфига)
        
        Args:
            client_id: UUID или email клиента
            protocol: Протокол (vless, vmess, trojan, shadowsocks)
            
        Returns:
            bool: True if successful
        """
        # TODO: Реализовать через XRay Management API или изменение config.json
        logger.warning(f"add_client for protocol {protocol} not implemented yet")
        return False

    def remove_client(self, client_id: str) -> bool:
        """
        Удалить клиента (TODO: требует API управления или изменения конфига)
        
        Args:
            client_id: UUID или email клиента
            
        Returns:
            bool: True if successful
        """
        # TODO: Реализовать через XRay Management API или изменение config.json
        logger.warning("remove_client not implemented yet")
        return False

    def generate_vless_config(self, uuid: str, server_address: str, 
                              server_port: int = 443) -> str:
        """
        Генерация конфигурации клиента для VLESS
        
        Args:
            uuid: UUID клиента
            server_address: Адрес сервера
            server_port: Порт сервера
            
        Returns:
            str: URL в формате vless://
        """
        config_url = (
            f"vless://{uuid}@{server_address}:{server_port}"
            f"?type=tcp&security=tls#AmneziaVPN"
        )
        return config_url

    def generate_vmess_config(self, uuid: str, server_address: str,
                             server_port: int = 443) -> Dict:
        """
        Генерация конфигурации клиента для VMess
        
        Args:
            uuid: UUID клиента
            server_address: Адрес сервера
            server_port: Порт сервера
            
        Returns:
            Dict: Конфигурация VMess в JSON формате
        """
        config = {
            "v": "2",
            "ps": "AmneziaVPN",
            "add": server_address,
            "port": str(server_port),
            "id": uuid,
            "aid": "0",
            "net": "tcp",
            "type": "none",
            "host": "",
            "path": "",
            "tls": "tls"
        }
        return config

    def generate_trojan_config(self, password: str, server_address: str,
                              server_port: int = 443) -> str:
        """
        Генерация конфигурации клиента для Trojan
        
        Args:
            password: Пароль клиента
            server_address: Адрес сервера
            server_port: Порт сервера
            
        Returns:
            str: URL в формате trojan://
        """
        config_url = (
            f"trojan://{password}@{server_address}:{server_port}"
            f"?security=tls#AmneziaVPN"
        )
        return config_url

    def generate_shadowsocks_config(self, password: str, server_address: str,
                                   server_port: int = 8388, method: str = "chacha20-ietf-poly1305") -> str:
        """
        Генерация конфигурации клиента для Shadowsocks
        
        Args:
            password: Пароль клиента
            server_address: Адрес сервера
            server_port: Порт сервера
            method: Метод шифрования
            
        Returns:
            str: URL в формате ss://
        """
        import base64
        
        # Формат: method:password
        auth_string = f"{method}:{password}"
        encoded_auth = base64.urlsafe_b64encode(auth_string.encode()).decode().rstrip('=')
        
        config_url = f"ss://{encoded_auth}@{server_address}:{server_port}#AmneziaVPN"
        return config_url

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

    def get_api_stats_json(self) -> Dict:
        """
        Получить полную статистику в JSON формате
        
        Returns:
            Dict: Полная статистика XRay
        """
        try:
            # Используем опцию --json для получения JSON вывода
            command = f"docker exec {self.container_name} xray api statsquery --server=127.0.0.1:10085 --json"
            exit_code, stdout, stderr = self.ssh.execute_command(command)

            if exit_code != 0:
                logger.error(f"Failed to get XRay stats JSON: {stderr}")
                return {}

            try:
                stats_json = json.loads(stdout)
                return stats_json
            except json.JSONDecodeError:
                logger.error(f"Failed to parse XRay stats JSON")
                return {}

        except Exception as e:
            logger.error(f"Error getting XRay stats JSON: {str(e)}")
            return {}
