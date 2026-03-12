from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime
import logging
import time

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


def _build_response_from_db(server_id: int, server_name: str, db: Session) -> dict:
    """Формирует ответ fetch-users из БД (используется как fallback при SSH-ошибке)."""
    configs = (
        db.query(ClientConfig)
        .options(joinedload(ClientConfig.user), joinedload(ClientConfig.client))
        .filter(ClientConfig.server_id == server_id)
        .all()
    )
    awg_peers, wireguard_peers, xray_clients = [], [], []
    for config in configs:
        base = {
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
            "config_content": config.config_content,
        }
        if config.protocol == ProtocolType.AWG:
            awg_peers.append({**base, "public_key": config.peer_public_key, "endpoint": config.endpoint, "allowed_ips": config.allowed_ips})
        elif config.protocol == ProtocolType.WIREGUARD:
            wireguard_peers.append({**base, "public_key": config.peer_public_key, "endpoint": config.endpoint, "allowed_ips": config.allowed_ips})
        elif config.protocol in (ProtocolType.VLESS, ProtocolType.VMESS, ProtocolType.TROJAN, ProtocolType.SHADOWSOCKS):
            xray_clients.append({**base, "uuid": config.client_uuid, "protocol": config.protocol.value})
    return {
        "server_id": server_id,
        "server_name": server_name,
        "awg_peers": awg_peers,
        "wireguard_peers": wireguard_peers,
        "xray_clients": xray_clients,
        "awg_status": "active" if awg_peers else "inactive",
        "wireguard_status": "active" if wireguard_peers else "inactive",
        "xray_status": "active" if xray_clients else "inactive",
    }


@router.get("/{server_id}/fetch-users")
async def fetch_server_users(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Получить список пользователей сервера с сервера (через SSH)"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    try:
        ssh_manager = create_ssh_manager(
            server_host=server.host,
            server_port=server.port,
            server_user=server.ssh_user,
            server_password=server.get_password(),
            server_key=server.ssh_key_path,
        )
        if not ssh_manager.connect():
            raise Exception("SSH connection failed")
    except Exception as e:
        logger.error(f"SSH connection error: {str(e)}")
        return _build_response_from_db(server_id, server.name, db)

    awg_peers, wireguard_peers, xray_clients = [], [], []
    try:
        # Предзагружаем все конфиги одним батч-запросом на протокол (3 запроса вместо N)
        awg_map = {
            c.peer_public_key: c
            for c in db.query(ClientConfig)
            .options(joinedload(ClientConfig.user), joinedload(ClientConfig.client))
            .filter(ClientConfig.server_id == server_id, ClientConfig.protocol == ProtocolType.AWG)
            .all()
        }
        wg_map = {
            c.peer_public_key: c
            for c in db.query(ClientConfig)
            .options(joinedload(ClientConfig.user), joinedload(ClientConfig.client))
            .filter(ClientConfig.server_id == server_id, ClientConfig.protocol == ProtocolType.WIREGUARD)
            .all()
        }
        xray_map = {
            c.client_uuid: c
            for c in db.query(ClientConfig)
            .options(joinedload(ClientConfig.user), joinedload(ClientConfig.client))
            .filter(
                ClientConfig.server_id == server_id,
                ClientConfig.protocol.in_([ProtocolType.VLESS, ProtocolType.VMESS, ProtocolType.TROJAN, ProtocolType.SHADOWSOCKS]),
            )
            .all()
        }

        # AWG
        for peer in AWGManager(ssh_manager).get_peers():
            latest_handshake = peer.get("latest_handshake") or 0
            is_online = latest_handshake > 0 and (time.time() - latest_handshake) < 180
            c = awg_map.get(peer.get("public_key"))
            awg_peers.append({
                "public_key": peer.get("public_key"),
                "endpoint": peer.get("endpoint"),
                "allowed_ips": peer.get("allowed_ips"),
                "latest_handshake": latest_handshake,
                "transfer_rx": peer.get("transfer_rx", 0),
                "transfer_tx": peer.get("transfer_tx", 0),
                "is_online": is_online,
                "is_active": c.is_active if c else True,
                "config_id": c.id if c else None,
                "client_id": c.client_id if c else None,
                "user_id": c.user_id if c else None,
                "username": c.user.username if c and c.user else None,
                "client_name": c.client.name if c and c.client else None,
                "device_name": c.device_name if c else None,
                "config_content": c.config_content if c else None,
            })

        # WireGuard
        for peer in WireGuardManager(ssh_manager).get_peers():
            latest_handshake = peer.get("latest_handshake") or 0
            is_online = latest_handshake > 0 and (time.time() - latest_handshake) < 180
            c = wg_map.get(peer.get("public_key"))
            wireguard_peers.append({
                "public_key": peer.get("public_key"),
                "endpoint": peer.get("endpoint"),
                "allowed_ips": peer.get("allowed_ips"),
                "latest_handshake": latest_handshake,
                "transfer_rx": peer.get("transfer_rx", 0),
                "transfer_tx": peer.get("transfer_tx", 0),
                "is_online": is_online,
                "is_active": c.is_active if c else True,
                "config_id": c.id if c else None,
                "client_id": c.client_id if c else None,
                "user_id": c.user_id if c else None,
                "username": c.user.username if c and c.user else None,
                "client_name": c.client.name if c and c.client else None,
                "device_name": c.device_name if c else None,
                "config_content": c.config_content if c else None,
            })

        # XRay
        xray_manager = XRayManager(ssh_manager)
        xray_stats = xray_manager.get_stats()
        for client in xray_manager.get_clients():
            uuid = client.get("uuid")
            email = client.get("email", "")
            c = xray_map.get(uuid)
            client_stats = xray_stats.get(email) or xray_stats.get(uuid, {})
            xray_clients.append({
                "uuid": uuid,
                "email": email,
                "flow": client.get("flow"),
                "protocol": client.get("protocol"),
                "config_id": c.id if c else None,
                "client_id": c.client_id if c else None,
                "user_id": c.user_id if c else None,
                "username": c.user.username if c and c.user else None,
                "client_name": c.client.name if c and c.client else None,
                "device_name": c.device_name if c else None,
                "is_active": c.is_active if c else True,
                "transfer_tx": client_stats.get("uplink", 0),
                "transfer_rx": client_stats.get("downlink", 0),
            })

    except Exception as e:
        logger.error(f"Error fetching users from server: {str(e)}")
        awg_peers, wireguard_peers, xray_clients = [], [], []
        return _build_response_from_db(server_id, server.name, db)
    finally:
        ssh_manager.disconnect()

    return {
        "server_id": server_id,
        "server_name": server.name,
        "awg_peers": awg_peers,
        "wireguard_peers": wireguard_peers,
        "xray_clients": xray_clients,
        "awg_status": "active" if awg_peers else "inactive",
        "wireguard_status": "active" if wireguard_peers else "inactive",
        "xray_status": "active" if xray_clients else "inactive",
    }


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
