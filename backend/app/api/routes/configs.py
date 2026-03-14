import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64

from app.core.database import get_db
from app.models import User, Server, ClientConfig, ProtocolType, VpnClient, EndpointLog
from app.api.schemas import (
    ClientConfigCreate, ClientConfigUpdate, ClientConfigResponse,
    EndpointLogResponse, SharingStatusResponse, SharingAlertItem,
    SharingAlertIpDetail, BulkConfigCreate,
)
from app.api.routes.auth import get_current_active_user
from app.services.ssh_manager import SSHManager
from app.services.awg_manager import AWGManager
from app.services.ssh_manager import create_ssh_manager
import shlex

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Helper for sharing score ---
def _compute_sharing_score(distinct_ips: int) -> int:
    """0=ok, 1=suspicious (2 IPs), 2=sharing (3+ IPs)"""
    if distinct_ips >= 3:
        return 2
    if distinct_ips >= 2:
        return 1
    return 0


# ============================================================
# Static-path endpoints MUST be defined BEFORE /{config_id}
# ============================================================


@router.get("/sharing-alerts", response_model=List[SharingAlertItem])
async def get_sharing_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all configs with 2+ distinct IPs in last 24h (sharing suspects)."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    rows = (
        db.query(
            EndpointLog.config_id,
            func.count(func.distinct(EndpointLog.endpoint_ip)).label("distinct_ips"),
        )
        .filter(EndpointLog.seen_at >= cutoff)
        .group_by(EndpointLog.config_id)
        .having(func.count(func.distinct(EndpointLog.endpoint_ip)) >= 2)
        .all()
    )

    result = []
    for row in rows:
        config = db.query(ClientConfig).options(joinedload(ClientConfig.client)).filter(ClientConfig.id == row.config_id).first()
        if not config:
            continue

        # Get per-IP details for this config
        ip_rows = (
            db.query(
                EndpointLog.endpoint_ip,
                func.min(EndpointLog.seen_at).label("first_seen"),
                func.max(EndpointLog.seen_at).label("last_seen"),
                func.count(EndpointLog.id).label("times_seen"),
            )
            .filter(EndpointLog.config_id == config.id, EndpointLog.seen_at >= cutoff)
            .group_by(EndpointLog.endpoint_ip)
            .order_by(func.max(EndpointLog.seen_at).desc())
            .all()
        )

        ips = [
            SharingAlertIpDetail(
                ip=ip_row.endpoint_ip,
                first_seen=ip_row.first_seen,
                last_seen=ip_row.last_seen,
                times_seen=ip_row.times_seen,
            )
            for ip_row in ip_rows
        ]

        result.append(SharingAlertItem(
            config_id=config.id,
            device_name=config.device_name,
            client_name=config.client.name if config.client else None,
            protocol=config.protocol.value if config.protocol else None,
            is_online=config.is_online or False,
            is_active=config.is_active if config.is_active is not None else True,
            distinct_ips_24h=row.distinct_ips,
            sharing_score=_compute_sharing_score(row.distinct_ips),
            ips=ips,
        ))
    return result


@router.post("/bulk", response_model=List[ClientConfigResponse], status_code=status.HTTP_201_CREATED)
async def bulk_create_configs(
    data: BulkConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create multiple configs at once."""
    client = db.query(VpnClient).filter(VpnClient.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    server = db.query(Server).filter(Server.id == data.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    created = []
    for i in range(data.count):
        db_config = ClientConfig(
            user_id=current_user.id,
            client_id=data.client_id,
            server_id=data.server_id,
            device_name=f"{data.device_name_prefix} {i + 1}",
            protocol=data.protocol,
            config_content=data.config_content_template or "",
        )
        db.add(db_config)
        created.append(db_config)

    db.commit()
    for c in created:
        db.refresh(c)

    return created


@router.get("/", response_model=List[ClientConfigResponse])
async def get_configs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    server_id: int = None,
    client_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Получить список конфигураций с фильтрацией"""
    query = db.query(ClientConfig).options(joinedload(ClientConfig.client))

    if server_id:
        query = query.filter(ClientConfig.server_id == server_id)
    if client_id:
        query = query.filter(ClientConfig.client_id == client_id)

    configs = query.offset(skip).limit(limit).all()

    # Batch-compute sharing scores for all returned configs
    config_ids = [c.id for c in configs]
    sharing_map: dict[int, int] = {}
    if config_ids:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        rows = (
            db.query(
                EndpointLog.config_id,
                func.count(func.distinct(EndpointLog.endpoint_ip)).label("cnt"),
            )
            .filter(EndpointLog.config_id.in_(config_ids), EndpointLog.seen_at >= cutoff)
            .group_by(EndpointLog.config_id)
            .all()
        )
        for row in rows:
            sharing_map[row.config_id] = _compute_sharing_score(row.cnt)

    # Attach sharing_score to each config as a transient attribute
    result = []
    for c in configs:
        resp = ClientConfigResponse.model_validate(c)
        resp.sharing_score = sharing_map.get(c.id, 0)
        result.append(resp)

    return result


@router.post("/", response_model=ClientConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    config: ClientConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Создать новую конфигурацию клиента"""
    # Проверка на существование клиента (VpnClient)
    client = db.query(VpnClient).filter(VpnClient.id == config.client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Проверка на существование сервера
    server = db.query(Server).filter(Server.id == config.server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Проверка на уникальность peer_public_key (если указан)
    if config.peer_public_key:
        existing_config = db.query(ClientConfig).filter(
            ClientConfig.peer_public_key == config.peer_public_key
        ).first()
        if existing_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Peer public key already exists (config ID: {existing_config.id})"
            )

    # Проверка на уникальность client_uuid (если указан)
    if config.client_uuid:
        existing_config = db.query(ClientConfig).filter(
            ClientConfig.client_uuid == config.client_uuid
        ).first()
        if existing_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Client UUID already exists (config ID: {existing_config.id})"
            )

    # Создание конфигурации
    db_config = ClientConfig(
        user_id=current_user.id,
        client_id=config.client_id,
        server_id=config.server_id,
        device_name=config.device_name,
        protocol=config.protocol,
        config_content=config.config_content,
        peer_public_key=config.peer_public_key,
        client_uuid=config.client_uuid,
        client_email=config.client_email,
        endpoint=config.endpoint,
        allowed_ips=config.allowed_ips,
    )

    db.add(db_config)
    db.commit()
    db.refresh(db_config)

    return db_config


@router.get("/{config_id}/endpoint-history", response_model=List[EndpointLogResponse])
async def get_endpoint_history(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get last 50 endpoint log entries for a config."""
    config = db.query(ClientConfig).filter(ClientConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    logs = (
        db.query(EndpointLog)
        .filter(EndpointLog.config_id == config_id)
        .order_by(EndpointLog.seen_at.desc())
        .limit(50)
        .all()
    )
    return logs


@router.get("/{config_id}/sharing-status", response_model=SharingStatusResponse)
async def get_sharing_status(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get sharing status for a config (distinct IPs in last 24h)."""
    config = db.query(ClientConfig).filter(ClientConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    cutoff = datetime.utcnow() - timedelta(hours=24)
    distinct_ips = (
        db.query(func.count(func.distinct(EndpointLog.endpoint_ip)))
        .filter(EndpointLog.config_id == config_id, EndpointLog.seen_at >= cutoff)
        .scalar()
    ) or 0

    return SharingStatusResponse(
        config_id=config_id,
        distinct_ips_24h=distinct_ips,
        sharing_score=_compute_sharing_score(distinct_ips),
    )


@router.get("/{config_id}", response_model=ClientConfigResponse)
async def get_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Получить конфигурацию по ID"""
    config = db.query(ClientConfig).filter(ClientConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Config not found"
        )
    return config


@router.put("/{config_id}", response_model=ClientConfigResponse)
async def update_config(
    config_id: int,
    config_update: ClientConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Обновить конфигурацию"""
    config = db.query(ClientConfig).filter(ClientConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Config not found"
        )

    # Обновление полей
    update_data = config_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)

    return config


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Удалить конфигурацию"""
    config = db.query(ClientConfig).filter(ClientConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Config not found"
        )

    db.delete(config)
    db.commit()

    return None


@router.post("/{config_id}/toggle-active", response_model=ClientConfigResponse)
async def toggle_config_active(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Переключить активность конфигурации (блокировка/разблокировка)"""
    config = db.query(ClientConfig).filter(ClientConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Config not found"
        )

    server = db.query(Server).filter(Server.id == config.server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Попытка применить изменения на сервере
    try:
        ssh = SSHManager(
            host=server.host,
            port=server.port,
            username=server.ssh_user,
            password=server.get_password(),
            key_path=server.ssh_key_path
        )
        ssh.connect()

        if config.protocol in [ProtocolType.AWG, ProtocolType.WIREGUARD]:
            awg = AWGManager(ssh)
            if config.is_active: # Was active, now blocking
                success = awg.block_peer(config.peer_public_key)
            else: # Was inactive, now unblocking
                success = awg.unblock_peer(config.peer_public_key, config.allowed_ips)

            if not success:
                raise Exception("Failed to update peer on server")

        # TODO: Implement XRay blocking

        ssh.disconnect()

    except Exception as e:
        logger.error(f"Error updating peer status on server: {e}")

    config.is_active = not config.is_active

    db.commit()
    db.refresh(config)

    return config


@router.get("/{config_id}/qrcode")
async def get_config_qrcode(
    config_id: int,
    format: str = 'standard',
    remote: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Сгенерировать QR код для конфигурации"""
    config = db.query(ClientConfig).filter(ClientConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Config not found"
        )

    content_to_encode = config.config_content
    logger.debug(f"QR generation for config {config_id}: protocol={config.protocol.value}, content_length={len(content_to_encode) if content_to_encode else 0}")

    if not content_to_encode:
        try:
            server = db.query(Server).filter(Server.id == config.server_id).first()
            if server:
                logger.debug(f"Remote QR: connecting to server {server.host}:{server.port} as {server.ssh_user}")
                ssh = create_ssh_manager(server.host, server.port, server.ssh_user, server.get_password(), server.ssh_key_path)
                if ssh.connect():
                    search_key = None
                    container = None
                    if config.protocol.value == 'awg' and config.peer_public_key:
                        search_key = config.peer_public_key
                        container = 'amnezia-awg'
                    elif config.protocol.value in ['vless', 'vmess', 'trojan', 'shadowsocks'] and config.client_uuid:
                        search_key = config.client_uuid
                        container = 'amnezia-xray'
                    else:
                        logger.debug(f"Remote QR: no search key for protocol {config.protocol.value}")

                    if search_key and container:
                        escaped_key = shlex.quote(search_key)
                        remote_cmd = (
                            f'sh -c \'f=$(grep -r -F {escaped_key} /etc /data /config /etc/wireguard /opt/amnezia /var/lib/amnezia 2>/dev/null | head -n1 | cut -d: -f1); '
                            'if [ -n "$f" ]; then echo "FOUND: $f"; cat "$f"; else echo "NOT_FOUND"; fi\'')
                        cmd = f"docker exec {container} {remote_cmd}"
                        exit_code, stdout_text, stderr_text = ssh.execute_command(cmd)
                        logger.debug(f"Remote QR exit={exit_code} stdout_len={len(stdout_text or '')} stderr_len={len(stderr_text or '')}")

                        if exit_code == 0 and stdout_text and stdout_text.strip() and not stdout_text.strip().startswith('NOT_FOUND'):
                            if stdout_text.startswith('FOUND:'):
                                lines = stdout_text.split('\n', 1)
                                if len(lines) >= 2:
                                    file_path = lines[0].replace('FOUND:', '').strip()
                                    content_to_encode = lines[1]
                                    logger.debug(f"Remote QR: found config at {file_path}, length={len(content_to_encode)}")
                                else:
                                    content_to_encode = stdout_text
                            else:
                                content_to_encode = stdout_text
                        else:
                            logger.debug("Remote QR: config not found in container")

                    ssh.disconnect()
                else:
                    logger.warning(f"Remote QR: SSH connect failed to {server.host}")
        except Exception as e:
            logger.error(f"Remote QR generation error: {e}")

    if not content_to_encode:
         raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Config content is empty"
        )

    # Генерируем QR код из config_content
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(content_to_encode)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return Response(content=buf.getvalue(), media_type="image/png")
