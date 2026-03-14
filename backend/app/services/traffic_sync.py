"""
Фоновая синхронизация трафика с VPN-серверов в БД.
Запускается по расписанию через APScheduler.
"""
import asyncio
import logging
import re
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import SessionLocal
from app.models import Server, ClientConfig, ProtocolType, EndpointLog, Subscription, TrafficHistory
from app.services.ssh_manager import SSHManager, create_ssh_manager
from app.services.awg_manager import AWGManager
from app.services.wireguard_manager import WireGuardManager
from app.services.xray_manager import XRayManager

logger = logging.getLogger(__name__)


def _extract_ip_from_endpoint(endpoint_str: str) -> str | None:
    """Extract IP address from WireGuard endpoint string like '1.2.3.4:51820'."""
    if not endpoint_str:
        return None
    # Handle IPv6 [::1]:port and IPv4 1.2.3.4:port
    match = re.match(r'^\[?([^\]]+)\]?:\d+$', endpoint_str)
    if match:
        return match.group(1)
    # Fallback: return as-is if it looks like an IP
    stripped = endpoint_str.split(':')[0] if ':' in endpoint_str else endpoint_str
    return stripped if stripped else None


def _track_endpoint(db: Session, config_id: int, endpoint_str: str) -> None:
    """Log endpoint IP if it differs from the last known one for this config."""
    ip = _extract_ip_from_endpoint(endpoint_str)
    if not ip or ip == '(none)':
        return

    last_log = (
        db.query(EndpointLog)
        .filter(EndpointLog.config_id == config_id)
        .order_by(EndpointLog.seen_at.desc())
        .first()
    )

    if not last_log or last_log.endpoint_ip != ip:
        now = datetime.utcnow()
        db.add(EndpointLog(config_id=config_id, endpoint_ip=ip, seen_at=now, created_at=now))


def _save_traffic_delta(db: Session, config_id: int, old_rx: int, old_tx: int, new_rx: int, new_tx: int) -> None:
    """Write a TrafficHistory delta record if traffic has increased since last sync."""
    delta_rx = max(0, new_rx - old_rx)
    delta_tx = max(0, new_tx - old_tx)
    if delta_rx > 0 or delta_tx > 0:
        db.add(TrafficHistory(config_id=config_id, bytes_received=delta_rx, bytes_sent=delta_tx))


def _update_online_status(db_config: ClientConfig, handshake_ts: int | None) -> None:
    """Update is_online, last_handshake, last_seen from WireGuard handshake timestamp."""
    now = time.time()
    if handshake_ts and handshake_ts > 0:
        db_config.last_handshake = datetime.utcfromtimestamp(handshake_ts)
        db_config.last_seen = datetime.utcfromtimestamp(handshake_ts)
        # Online if handshake was within last 3 minutes
        db_config.is_online = (now - handshake_ts) < 180
    else:
        db_config.is_online = False


def block_peer_on_server(config: ClientConfig, server: Server, db: Session) -> bool:
    """Block a peer on the VPN server via SSH. Returns True on success."""
    try:
        ssh = create_ssh_manager(
            server_host=server.host,
            server_port=server.port,
            server_user=server.ssh_user,
            server_password=server.get_password(),
            server_key=server.ssh_key_path,
        )
        if not ssh.connect():
            logger.error(f"[block_peer] SSH connection failed to {server.host}")
            return False

        try:
            if config.protocol in (ProtocolType.AWG, ProtocolType.WIREGUARD):
                if config.protocol == ProtocolType.AWG:
                    manager = AWGManager(ssh)
                else:
                    manager = WireGuardManager(ssh)
                success = manager.block_peer(config.peer_public_key)
                if not success:
                    logger.warning(f"[block_peer] Failed to block peer {config.peer_public_key}")
                return success
            # XRay blocking not yet implemented
            return True
        finally:
            ssh.disconnect()
    except Exception as e:
        logger.error(f"[block_peer] Error blocking config {config.id}: {e}")
        return False


def check_expired_subscriptions(db: Session) -> int:
    """Deactivate expired subscriptions and block their peers. Returns count of deactivated."""
    now = datetime.utcnow()
    expired_subs = (
        db.query(Subscription)
        .filter(
            Subscription.is_active == True,
            Subscription.subscription_end < now,
        )
        .all()
    )

    blocked_count = 0
    for sub in expired_subs:
        sub.is_active = False
        logger.info(f"[expiry] Subscription {sub.id} expired (end={sub.subscription_end})")

        if sub.config_id:
            config = db.query(ClientConfig).filter(ClientConfig.id == sub.config_id).first()
            if config and config.is_active:
                server = db.query(Server).filter(Server.id == config.server_id).first()
                if server:
                    block_peer_on_server(config, server, db)
                config.is_active = False
                blocked_count += 1
                logger.info(f"[expiry] Config {config.id} blocked due to expired subscription {sub.id}")

                _try_broadcast({
                    "type": "config_blocked",
                    "config_id": config.id,
                    "reason": "subscription_expired",
                    "subscription_id": sub.id,
                })

    if blocked_count > 0:
        db.commit()
    return blocked_count


def check_traffic_limit(config: ClientConfig, db: Session) -> bool:
    """Check if config exceeded traffic limit. Block if so. Returns True if blocked."""
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.config_id == config.id,
            Subscription.is_active == True,
        )
        .first()
    )
    if not sub or not sub.traffic_limit_gb or sub.traffic_limit_gb <= 0:
        return False

    total_gb = ((config.bytes_received or 0) + (config.bytes_sent or 0)) / (1024 ** 3)
    sub.traffic_used_gb = round(total_gb, 2)

    if total_gb >= sub.traffic_limit_gb:
        sub.is_active = False
        config.is_active = False

        server = db.query(Server).filter(Server.id == config.server_id).first()
        if server:
            block_peer_on_server(config, server, db)

        logger.info(
            f"[traffic_limit] Config {config.id} blocked: "
            f"{total_gb:.2f}GB >= {sub.traffic_limit_gb}GB limit"
        )

        _try_broadcast({
            "type": "config_blocked",
            "config_id": config.id,
            "reason": "traffic_limit_exceeded",
            "traffic_used_gb": round(total_gb, 2),
            "traffic_limit_gb": sub.traffic_limit_gb,
        })
        return True
    return False


def _try_broadcast(data: dict) -> None:
    """Attempt to broadcast a message via WebSocket ConnectionManager."""
    try:
        from app.api.routes.ws import manager as ws_manager
        loop = ws_manager._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(data), loop)
    except Exception as e:
        logger.debug(f"[broadcast] WS not available or no clients connected: {e}")


def sync_server_traffic(server: Server, db: Session) -> dict:
    """
    Синхронизирует трафик одного сервера.
    Возвращает статистику: сколько записей обновлено.
    """
    updated = 0
    errors = []

    ssh_manager = create_ssh_manager(
        server_host=server.host,
        server_port=server.port,
        server_user=server.ssh_user,
        server_password=server.get_password(),
        server_key=server.ssh_key_path,
    )

    if not ssh_manager.connect():
        raise ConnectionError(f"SSH connection failed to {server.host}")

    try:
        # --- AWG ---
        try:
            awg_manager = AWGManager(ssh_manager)
            for peer in awg_manager.get_peers():
                public_key = peer.get("public_key")
                if not public_key:
                    continue
                db_config = db.query(ClientConfig).filter(
                    ClientConfig.server_id == server.id,
                    ClientConfig.protocol == ProtocolType.AWG,
                    ClientConfig.peer_public_key == public_key,
                ).first()
                if db_config:
                    new_rx = peer.get("transfer_rx", 0)
                    new_tx = peer.get("transfer_tx", 0)
                    _save_traffic_delta(db, db_config.id, db_config.bytes_received or 0, db_config.bytes_sent or 0, new_rx, new_tx)
                    db_config.bytes_received = new_rx
                    db_config.bytes_sent = new_tx
                    endpoint = peer.get("endpoint", "")
                    if endpoint and endpoint != '(none)':
                        db_config.endpoint = endpoint
                        _track_endpoint(db, db_config.id, endpoint)
                    _update_online_status(db_config, peer.get("latest_handshake"))
                    check_traffic_limit(db_config, db)
                    updated += 1
        except Exception as e:
            errors.append(f"AWG: {e}")
            logger.warning(f"[traffic_sync] AWG error on server {server.id}: {e}")

        # --- WireGuard ---
        try:
            wg_manager = WireGuardManager(ssh_manager)
            for peer in wg_manager.get_peers():
                public_key = peer.get("public_key")
                if not public_key:
                    continue
                db_config = db.query(ClientConfig).filter(
                    ClientConfig.server_id == server.id,
                    ClientConfig.protocol == ProtocolType.WIREGUARD,
                    ClientConfig.peer_public_key == public_key,
                ).first()
                if db_config:
                    new_rx = peer.get("transfer_rx", 0)
                    new_tx = peer.get("transfer_tx", 0)
                    _save_traffic_delta(db, db_config.id, db_config.bytes_received or 0, db_config.bytes_sent or 0, new_rx, new_tx)
                    db_config.bytes_received = new_rx
                    db_config.bytes_sent = new_tx
                    endpoint = peer.get("endpoint", "")
                    if endpoint and endpoint != '(none)':
                        db_config.endpoint = endpoint
                        _track_endpoint(db, db_config.id, endpoint)
                    _update_online_status(db_config, peer.get("latest_handshake"))
                    check_traffic_limit(db_config, db)
                    updated += 1
        except Exception as e:
            errors.append(f"WireGuard: {e}")
            logger.warning(f"[traffic_sync] WireGuard error on server {server.id}: {e}")

        # --- XRay ---
        try:
            xray_manager = XRayManager(ssh_manager)
            xray_stats = xray_manager.get_stats()  # {email_or_uuid: {uplink, downlink}}
            for client in xray_manager.get_clients():
                uuid = client.get("uuid")
                email = client.get("email", "")
                if not uuid:
                    continue
                client_stats = xray_stats.get(email) or xray_stats.get(uuid, {})
                if not client_stats:
                    continue
                db_config = db.query(ClientConfig).filter(
                    ClientConfig.server_id == server.id,
                    ClientConfig.client_uuid == uuid,
                ).first()
                if db_config:
                    new_rx = client_stats.get("downlink", 0)
                    new_tx = client_stats.get("uplink", 0)
                    traffic_changed = (new_rx != db_config.bytes_received or new_tx != db_config.bytes_sent)
                    _save_traffic_delta(db, db_config.id, db_config.bytes_received or 0, db_config.bytes_sent or 0, new_rx, new_tx)
                    db_config.bytes_received = new_rx
                    db_config.bytes_sent = new_tx
                    if traffic_changed:
                        db_config.is_online = True
                        db_config.last_seen = datetime.utcnow()
                    else:
                        db_config.is_online = False
                    check_traffic_limit(db_config, db)
                    updated += 1
        except Exception as e:
            errors.append(f"XRay: {e}")
            logger.warning(f"[traffic_sync] XRay error on server {server.id}: {e}")

        db.commit()

    finally:
        ssh_manager.disconnect()

    return {"updated": updated, "errors": errors}


def sync_all_traffic():
    """
    Точка входа для APScheduler.
    Обходит все серверы и синхронизирует трафик.
    """
    db: Session = SessionLocal()
    try:
        servers = db.query(Server).filter(Server.status == "active").all()
        logger.info(f"[traffic_sync] Starting traffic sync for {len(servers)} server(s)")

        total_updated = 0
        for server in servers:
            try:
                result = sync_server_traffic(server, db)
                total_updated += result["updated"]
                if result["errors"]:
                    logger.warning(
                        f"[traffic_sync] Server {server.name} ({server.host}): "
                        f"{result['updated']} updated, errors: {result['errors']}"
                    )
                else:
                    logger.info(
                        f"[traffic_sync] Server {server.name} ({server.host}): "
                        f"{result['updated']} records updated"
                    )
            except Exception as e:
                logger.error(f"[traffic_sync] Failed to sync server {server.name}: {e}")

        # Check expired subscriptions after all servers synced
        expired_count = check_expired_subscriptions(db)
        if expired_count > 0:
            logger.info(f"[traffic_sync] Blocked {expired_count} config(s) due to expired subscriptions")

        logger.info(f"[traffic_sync] Done. Total records updated: {total_updated}")

        # Broadcast traffic update to WebSocket clients
        _try_broadcast({
            "type": "traffic_update",
            "updated": total_updated,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.error(f"[traffic_sync] Unexpected error: {e}")
    finally:
        db.close()
