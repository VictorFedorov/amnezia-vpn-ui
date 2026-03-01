from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging

from app.core.database import get_db
from app.models import User, Server, ClientConfig, ProtocolType
from app.api.schemas import ServerCreate, ServerUpdate, ServerResponse, ClientConfigResponse
from app.api.routes.auth import get_current_active_user
from app.services.ssh_manager import create_ssh_manager
from app.services.awg_manager import AWGManager
from app.services.xray_manager import XRayManager
from app.services.wireguard_manager import WireGuardManager

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/", response_model=List[ServerResponse])
async def get_servers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Получить список всех серверов"""
    servers = db.query(Server).offset(skip).limit(limit).all()
    return servers


@router.post("/", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
async def add_server(
    server: ServerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Добавить новый сервер"""
    # Проверка на существующий сервер с таким именем
    db_server = db.query(Server).filter(Server.name == server.name).first()
    if db_server:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server with this name already exists"
        )
    
    # Проверка SSH подключения
    try:
        ssh = create_ssh_manager(
            server_host=server.host,
            server_port=server.port,
            server_user=server.ssh_user,
            server_password=server.ssh_password,
            server_key=server.ssh_key_path
        )
        
        if not ssh.connect():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to connect to server via SSH"
            )
        ssh.disconnect()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSH connection error: {str(e)}"
        )
    
    # Создание сервера
    db_server = Server(
        name=server.name,
        host=server.host,
        port=server.port,
        ssh_user=server.ssh_user,
        ssh_key_path=server.ssh_key_path,
        status="active"
    )
    
    # Установить зашифрованный пароль
    if server.ssh_password:
        db_server.set_password(server.ssh_password)
    
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    
    return db_server


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Получить информацию о сервере"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    return server


@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: int,
    server_update: ServerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Обновить сервер"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Обновление полей
    update_data = server_update.model_dump(exclude_unset=True)
    
    # Сохраняем пароль отдельно, так как нужно его зашифровать
    new_password = update_data.pop('ssh_password', None)
    
    # Если обновляются данные подключения, проверяем SSH
    if any(k in update_data for k in ['host', 'port', 'ssh_user', 'ssh_key_path']) or new_password:
        try:
            ssh = create_ssh_manager(
                server_host=update_data.get('host', server.host),
                server_port=update_data.get('port', server.port),
                server_user=update_data.get('ssh_user', server.ssh_user),
                server_password=new_password if new_password else server.get_password(),
                server_key=update_data.get('ssh_key_path', server.ssh_key_path)
            )
            
            if not ssh.connect():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to connect to server via SSH"
                )
            ssh.disconnect()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SSH connection error: {str(e)}"
            )
    
    # Обновляем обычные поля
    for field, value in update_data.items():
        setattr(server, field, value)
    
    # Обновляем пароль, если он был передан
    if new_password:
        server.set_password(new_password)
    
    db.commit()
    db.refresh(server)
    
    return server


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Удалить сервер"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    db.delete(server)
    db.commit()
    
    return None


@router.get("/{server_id}/configs", response_model=List[ClientConfigResponse])
async def get_server_configs(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Получить все конфигурации (устройства) на сервере, 
    сгруппированные по пользователям и протоколам
    """
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Получаем все конфигурации для этого сервера
    configs = db.query(ClientConfig).filter(
        ClientConfig.server_id == server_id
    ).all()
    
    return configs


@router.get("/{server_id}/fetch-users")
async def fetch_server_users(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Получить список пользователей сервера с сервера (через SSH)
    """
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Создаем SSH менеджер
    try:
        ssh_manager = create_ssh_manager(
            server_host=server.host,
            server_port=server.port,
            server_user=server.ssh_user,
            server_password=server.get_password(),
            server_key=server.ssh_key_path
        )
        if not ssh_manager.connect():
            raise Exception("SSH connection failed")
    except Exception as e:
        logger.error(f"SSH connection error: {str(e)}")
        # В случае ошибки возвращаем данные из БД
        db_configs = db.query(ClientConfig).filter(
            ClientConfig.server_id == server_id
        ).all()

        # Группируем по протоколам
        awg_peers = []
        wireguard_peers = []
        xray_clients = []

        for config in db_configs:
            base_data = {
                "config_id": config.id,
                "client_id": config.client_id,
                "user_id": config.user_id,
                "username": config.user.username if config.user else None,
                "device_name": config.device_name,
                "client_name": config.client.name if config.client else None,
                "is_active": config.is_active,
                "is_online": config.is_online,
                "transfer_rx": config.bytes_received or 0,
                "transfer_tx": config.bytes_sent or 0,
                "last_seen": config.last_seen.isoformat() if config.last_seen else None,
                "config_content": config.config_content
            }

            if config.protocol.value == "awg":
                awg_peers.append({
                    **base_data,
                    "public_key": config.peer_public_key,
                    "endpoint": config.endpoint,
                    "allowed_ips": config.allowed_ips
                })
            elif config.protocol.value == "wireguard":
                wireguard_peers.append({
                    **base_data,
                    "public_key": config.peer_public_key,
                    "endpoint": config.endpoint,
                    "allowed_ips": config.allowed_ips
                })
            elif config.protocol.value in ["vless", "vmess", "trojan", "shadowsocks"]:
                xray_clients.append({
                    **base_data,
                    "uuid": config.client_uuid,
                    "protocol": config.protocol.value
                })

        result = {
            "server_id": server_id,
            "server_name": server.name,
            "awg_peers": awg_peers,
            "wireguard_peers": wireguard_peers,
            "xray_clients": xray_clients,
            "awg_status": "active" if awg_peers else "inactive",
            "wireguard_status": "active" if wireguard_peers else "inactive",
            "xray_status": "active" if xray_clients else "inactive"
        }

        return result

    # Получаем клиентов с сервера
    awg_peers = []
    wireguard_peers = []
    xray_clients = []

    try:
        # AWG
        awg_manager = AWGManager(ssh_manager)
        awg_peers_data = awg_manager.get_peers()
        import time
        for peer in awg_peers_data:
            # Определяем online статус (если handshake был меньше 3 минут назад)
            latest_handshake = peer.get("latest_handshake") or 0
            is_online = False
            if latest_handshake > 0:
                time_since_handshake = time.time() - latest_handshake
                is_online = time_since_handshake < 180  # 3 минуты
            
            # Проверяем есть ли этот пир в БД
            db_config = db.query(ClientConfig).filter(
                ClientConfig.server_id == server_id,
                ClientConfig.protocol == ProtocolType.AWG,
                ClientConfig.peer_public_key == peer.get("public_key")
            ).first()
            
            awg_peers.append({
                "public_key": peer.get("public_key"),
                "endpoint": peer.get("endpoint"),
                "allowed_ips": peer.get("allowed_ips"),
                "latest_handshake": latest_handshake,
                "transfer_rx": peer.get("transfer_rx", 0),
                "transfer_tx": peer.get("transfer_tx", 0),
                "is_online": is_online,
                "is_active": db_config.is_active if db_config else True,
                "config_id": db_config.id if db_config else None,
                "client_id": db_config.client_id if db_config else None,
                "user_id": db_config.user_id if db_config else None,
                "username": db_config.user.username if db_config and db_config.user else None,
                "client_name": db_config.client.name if db_config and db_config.client else None,
                "device_name": db_config.device_name if db_config else None,
                "config_content": db_config.config_content if db_config else None,
            })

        # WireGuard
        wg_manager = WireGuardManager(ssh_manager)
        wg_peers_data = wg_manager.get_peers()
        for peer in wg_peers_data:
            # Определяем online статус (если handshake был меньше 3 минут назад)
            latest_handshake = peer.get("latest_handshake") or 0
            is_online = False
            if latest_handshake > 0:
                time_since_handshake = time.time() - latest_handshake
                is_online = time_since_handshake < 180  # 3 минуты
            
            # Проверяем есть ли этот пир в БД
            db_config = db.query(ClientConfig).filter(
                ClientConfig.server_id == server_id,
                ClientConfig.protocol == ProtocolType.WIREGUARD,
                ClientConfig.peer_public_key == peer.get("public_key")
            ).first()
            
            wireguard_peers.append({
                "public_key": peer.get("public_key"),
                "endpoint": peer.get("endpoint"),
                "allowed_ips": peer.get("allowed_ips"),
                "latest_handshake": latest_handshake,
                "transfer_rx": peer.get("transfer_rx", 0),
                "transfer_tx": peer.get("transfer_tx", 0),
                "is_online": is_online,
                "is_active": db_config.is_active if db_config else True,
                "config_id": db_config.id if db_config else None,
                "client_id": db_config.client_id if db_config else None,
                "user_id": db_config.user_id if db_config else None,
                "username": db_config.user.username if db_config and db_config.user else None,
                "client_name": db_config.client.name if db_config and db_config.client else None,
                "device_name": db_config.device_name if db_config else None,
                "config_content": db_config.config_content if db_config else None,
            })

        # XRay
        xray_manager = XRayManager(ssh_manager)
        xray_clients_data = xray_manager.get_clients()
        xray_stats = xray_manager.get_stats()

        for client in xray_clients_data:
            uuid = client.get("uuid")
            email = client.get("email", "")

            # Ищем конфиг в БД по UUID
            db_config = db.query(ClientConfig).filter(
                ClientConfig.server_id == server_id,
                ClientConfig.client_uuid == uuid
            ).first()

            # Получаем статистику трафика — сначала по email, затем по UUID
            client_stats = xray_stats.get(email) or xray_stats.get(uuid, {})

            xray_clients.append({
                "uuid": uuid,
                "email": email,
                "flow": client.get("flow"),
                "protocol": client.get("protocol"),
                "config_id": db_config.id if db_config else None,
                "client_id": db_config.client_id if db_config else None,
                "user_id": db_config.user_id if db_config else None,
                "username": db_config.user.username if db_config and db_config.user else None,
                "client_name": db_config.client.name if db_config and db_config.client else None,
                "device_name": db_config.device_name if db_config else None,
                "is_active": db_config.is_active if db_config else True,
                "transfer_tx": client_stats.get("uplink", 0),
                "transfer_rx": client_stats.get("downlink", 0),
            })

    except Exception as e:
        logger.error(f"Error fetching users from server: {str(e)}")
        # В случае ошибки возвращаем данные из БД
        db_configs = db.query(ClientConfig).filter(
            ClientConfig.server_id == server_id
        ).all()

        # Группируем по протоколам
        awg_peers = []
        wireguard_peers = []
        xray_clients = []

        for config in db_configs:
            base_data = {
                "config_id": config.id,
                "client_id": config.client_id,
                "user_id": config.user_id,
                "username": config.user.username if config.user else None,
                "device_name": config.device_name,
                "client_name": config.client.name if config.client else None,
                "is_active": config.is_active,
                "is_online": config.is_online,
                "transfer_rx": config.bytes_received or 0,
                "transfer_tx": config.bytes_sent or 0,
                "last_seen": config.last_seen.isoformat() if config.last_seen else None,
                "config_content": config.config_content
            }

            if config.protocol.value == "awg":
                awg_peers.append({
                    **base_data,
                    "public_key": config.peer_public_key,
                    "endpoint": config.endpoint,
                    "allowed_ips": config.allowed_ips
                })
            elif config.protocol.value == "wireguard":
                wireguard_peers.append({
                    **base_data,
                    "public_key": config.peer_public_key,
                    "endpoint": config.endpoint,
                    "allowed_ips": config.allowed_ips
                })
            elif config.protocol.value in ["vless", "vmess", "trojan", "shadowsocks"]:
                xray_clients.append({
                    **base_data,
                    "uuid": config.client_uuid,
                    "protocol": config.protocol.value
                })
    finally:
        ssh_manager.disconnect()

    result = {
        "server_id": server_id,
        "server_name": server.name,
        "awg_peers": awg_peers,
        "wireguard_peers": wireguard_peers,
        "xray_clients": xray_clients,
        "awg_status": "active" if awg_peers else "inactive",
        "wireguard_status": "active" if wireguard_peers else "inactive",
        "xray_status": "active" if xray_clients else "inactive"
    }

    return result


@router.post("/{server_id}/enable-xray-stats")
def enable_xray_stats(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Включить Stats API в конфиге XRay на сервере:
    - Добавляет inbound dokodemo-door на 127.0.0.1:10085
    - Добавляет секции api, stats, policy, routing
    - Добавляет email (= UUID) каждому клиенту для идентификации в статистике
    - Перезапускает контейнер amnezia-xray
    """
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    ssh_manager = create_ssh_manager(
        server_host=server.host,
        server_port=server.port,
        server_user=server.ssh_user,
        server_password=server.get_password(),
        server_key=server.ssh_key_path
    )

    if not ssh_manager.connect():
        raise HTTPException(status_code=503, detail="Failed to connect to server via SSH")

    try:
        xray_manager = XRayManager(ssh_manager)
        result = xray_manager.enable_stats_api()
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])
        return result
    finally:
        ssh_manager.disconnect()
