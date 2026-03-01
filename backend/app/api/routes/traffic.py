from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models import ClientConfig, Server, VpnClient, User
from app.api.routes.auth import get_current_active_user
from typing import Optional, List
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/realtime")
async def get_realtime_traffic(
    server_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Получить текущие суммарные счетчики трафика.
    Агрегирует данные из таблицы ClientConfig.
    """
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
        "total": (result.total_download or 0) + (result.total_upload or 0)
    }


@router.get("/top-users")
async def get_top_users_traffic(
    limit: int = 10,
    server_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Топ клиентов по потреблению трафика"""
    query = db.query(
        VpnClient.name,
        func.sum(ClientConfig.bytes_received + ClientConfig.bytes_sent).label("total_traffic")
    ).join(ClientConfig)
    
    if server_id:
        query = query.filter(ClientConfig.server_id == server_id)
        
    query = query.group_by(VpnClient.name).order_by(func.sum(ClientConfig.bytes_received + ClientConfig.bytes_sent).desc()).limit(limit)
    
    results = query.all()
    
    return [
        {"username": r[0], "total_traffic": r[1] or 0} for r in results 
    ]



@router.get("/by-server")
async def get_traffic_by_server(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Распределение трафика по серверам"""
    results = db.query(
        Server.name,
        func.sum(ClientConfig.bytes_received + ClientConfig.bytes_sent).label("total_traffic")
    ).join(ClientConfig, Server.id == ClientConfig.server_id)\
    .group_by(Server.id)\
    .all()
    
    return [
        {"server_name": r.name, "total_traffic": r.total_traffic or 0}
        for r in results
    ]
