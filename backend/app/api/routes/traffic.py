from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models import ClientConfig, Server, VpnClient, User, TrafficHistory
from app.api.routes.auth import get_current_active_user
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter()

# Конфигурация периодов: (timedelta, sqlite strftime bucket)
_PERIOD_CFG = {
    "day":     (timedelta(days=1),   "%Y-%m-%d %H:00:00"),
    "week":    (timedelta(weeks=1),  "%Y-%m-%d"),
    "month":   (timedelta(days=30),  "%Y-%m-%d"),
    "quarter": (timedelta(days=90),  "%Y-%W"),
    "year":    (timedelta(days=365), "%Y-%m"),
}


@router.get("/realtime")
async def get_realtime_traffic(
    server_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Текущие суммарные счётчики трафика из ClientConfig."""
    query = db.query(
        func.sum(ClientConfig.bytes_received).label("total_download"),
        func.sum(ClientConfig.bytes_sent).label("total_upload")
    )
    if server_id:
        query = query.filter(ClientConfig.server_id == server_id)
    if client_id:
        query = query.filter(ClientConfig.client_id == client_id)
    result = query.first()
    return {
        "total_download": result.total_download or 0,
        "total_upload": result.total_upload or 0,
        "total": (result.total_download or 0) + (result.total_upload or 0),
    }


@router.get("/summary")
async def get_traffic_summary(
    period: str = Query("week", pattern="^(day|week|month|quarter|year)$"),
    server_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Суммарный трафик за период из истории (TrafficHistory дельты)."""
    delta, _ = _PERIOD_CFG[period]
    since = datetime.utcnow() - delta

    query = (
        db.query(
            func.sum(TrafficHistory.bytes_received).label("total_download"),
            func.sum(TrafficHistory.bytes_sent).label("total_upload"),
            func.count(func.distinct(TrafficHistory.config_id)).label("active_configs"),
        )
        .join(ClientConfig, TrafficHistory.config_id == ClientConfig.id)
        .filter(TrafficHistory.timestamp >= since)
    )
    if server_id:
        query = query.filter(ClientConfig.server_id == server_id)

    result = query.first()
    total_download = result.total_download or 0
    total_upload = result.total_upload or 0
    return {
        "period": period,
        "since": since.isoformat(),
        "total_download": total_download,
        "total_upload": total_upload,
        "total": total_download + total_upload,
        "active_configs": result.active_configs or 0,
    }


@router.get("/history")
async def get_traffic_history(
    period: str = Query("week", pattern="^(day|week|month|quarter|year)$"),
    server_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Временной ряд трафика за период, сгруппированный по бакетам."""
    delta, fmt = _PERIOD_CFG[period]
    since = datetime.utcnow() - delta

    bucket_expr = func.strftime(fmt, TrafficHistory.timestamp)

    query = (
        db.query(
            bucket_expr.label("bucket"),
            func.sum(TrafficHistory.bytes_received).label("download"),
            func.sum(TrafficHistory.bytes_sent).label("upload"),
        )
        .join(ClientConfig, TrafficHistory.config_id == ClientConfig.id)
        .filter(TrafficHistory.timestamp >= since)
    )
    if server_id:
        query = query.filter(ClientConfig.server_id == server_id)

    results = query.group_by(bucket_expr).order_by(bucket_expr).all()
    return [
        {"bucket": r.bucket, "download": r.download or 0, "upload": r.upload or 0}
        for r in results
    ]


@router.get("/top-users")
async def get_top_users_traffic(
    limit: int = Query(10, ge=1, le=100),
    server_id: Optional[int] = None,
    period: Optional[str] = Query(None, pattern="^(day|week|month|quarter|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Топ клиентов по трафику. Если period задан — из истории, иначе из текущих счётчиков."""
    if period:
        delta, _ = _PERIOD_CFG[period]
        since = datetime.utcnow() - delta
        query = (
            db.query(
                VpnClient.name,
                func.sum(TrafficHistory.bytes_received + TrafficHistory.bytes_sent).label("total_traffic"),
            )
            .join(ClientConfig, TrafficHistory.config_id == ClientConfig.id)
            .join(VpnClient, ClientConfig.client_id == VpnClient.id)
            .filter(TrafficHistory.timestamp >= since)
        )
        if server_id:
            query = query.filter(ClientConfig.server_id == server_id)
        results = (
            query.group_by(VpnClient.name)
            .order_by(func.sum(TrafficHistory.bytes_received + TrafficHistory.bytes_sent).desc())
            .limit(limit)
            .all()
        )
    else:
        query = (
            db.query(
                VpnClient.name,
                func.sum(ClientConfig.bytes_received + ClientConfig.bytes_sent).label("total_traffic"),
            )
            .join(ClientConfig)
        )
        if server_id:
            query = query.filter(ClientConfig.server_id == server_id)
        results = (
            query.group_by(VpnClient.name)
            .order_by(func.sum(ClientConfig.bytes_received + ClientConfig.bytes_sent).desc())
            .limit(limit)
            .all()
        )

    return [{"username": r[0], "total_traffic": r[1] or 0} for r in results]


@router.get("/by-server")
async def get_traffic_by_server(
    period: Optional[str] = Query(None, pattern="^(day|week|month|quarter|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Трафик по серверам. Если period задан — из истории."""
    if period:
        delta, _ = _PERIOD_CFG[period]
        since = datetime.utcnow() - delta
        results = (
            db.query(
                Server.name,
                func.sum(TrafficHistory.bytes_received + TrafficHistory.bytes_sent).label("total_traffic"),
            )
            .join(ClientConfig, Server.id == ClientConfig.server_id)
            .join(TrafficHistory, TrafficHistory.config_id == ClientConfig.id)
            .filter(TrafficHistory.timestamp >= since)
            .group_by(Server.id)
            .all()
        )
    else:
        results = (
            db.query(
                Server.name,
                func.sum(ClientConfig.bytes_received + ClientConfig.bytes_sent).label("total_traffic"),
            )
            .join(ClientConfig, Server.id == ClientConfig.server_id)
            .group_by(Server.id)
            .all()
        )
    return [{"server_name": r.name, "total_traffic": r.total_traffic or 0} for r in results]
