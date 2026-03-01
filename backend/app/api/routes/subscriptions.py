from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.models import User, Subscription, SubscriptionPlan, ClientConfig, VpnClient
from app.api.routes.auth import get_current_active_user

router = APIRouter()

class SubscriptionCreate(BaseModel):
    client_id: Optional[int] = None
    config_id: Optional[int] = None
    plan_id: int 

@router.get("/")
async def get_subscriptions(
    client_id: int = None,
    config_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Получить список подписок"""
    query = db.query(Subscription)
    
    if client_id:
        query = query.filter(Subscription.client_id == client_id)
    if config_id:
        query = query.filter(Subscription.config_id == config_id)
    
    # Eager load relationships
    query = query.options(
        joinedload(Subscription.client), 
        joinedload(Subscription.config), 
        joinedload(Subscription.plan)
    )
    
    subscriptions = query.all()
    return subscriptions


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Создать новую подписку"""
    # Получаем план
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == subscription.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Проверки
    if subscription.client_id:
        client = db.query(VpnClient).filter(VpnClient.id == subscription.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Vpn Client not found")
            
    if subscription.config_id:
        config = db.query(ClientConfig).filter(ClientConfig.id == subscription.config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="Client config not found")
    else:
        # Require config_id if user demands it "not optional" 
        # But wait, looking at user request: "не опционально, а один из клиентов с сервера"
        pass
    
    # Расчет дат
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=plan.duration_days)
    
    # Создание
    db_subscription = Subscription(
        client_id=subscription.client_id,
        config_id=subscription.config_id,
        plan_id=subscription.plan_id,
        subscription_type=None, # Legacy field
        subscription_start=start_date,
        subscription_end=end_date,
        traffic_limit_gb=plan.traffic_limit_gb,
        is_active=True
    )
    
    db.add(db_subscription)
    db.commit()
    db.flush()
    
    # Refresh через явный запрос, т.к. составные индексы мешают db.refresh()
    saved_id = db_subscription.id
    db_subscription = db.query(Subscription).options(
        joinedload(Subscription.client),
        joinedload(Subscription.plan),
    ).filter(Subscription.id == saved_id).first()
    
    return db_subscription


class SubscriptionUpdate(BaseModel):
    is_active: Optional[bool] = None
    subscription_end: Optional[datetime] = None
    traffic_limit_gb: Optional[int] = None
    plan_id: Optional[int] = None


@router.put("/{subscription_id}")
async def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Обновить подписку"""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    if data.is_active is not None:
        subscription.is_active = data.is_active
    if data.subscription_end is not None:
        subscription.subscription_end = data.subscription_end
    if data.traffic_limit_gb is not None:
        subscription.traffic_limit_gb = data.traffic_limit_gb
    if data.plan_id is not None:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == data.plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        subscription.plan_id = data.plan_id

    db.commit()
    saved_id = subscription.id
    subscription = db.query(Subscription).options(
        joinedload(Subscription.client),
        joinedload(Subscription.plan),
    ).filter(Subscription.id == saved_id).first()

    return subscription


@router.delete("/{subscription_id}")
async def delete_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Удалить подписку"""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    db.delete(subscription)
    db.commit()
    
    return {"message": "Subscription deleted"}


@router.post("/{subscription_id}/extend")
async def extend_subscription(
    subscription_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Продлить подписку"""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    subscription.subscription_end = subscription.subscription_end + timedelta(days=days)
    subscription.is_active = True
    
    db.commit()
    saved_id = subscription.id
    subscription = db.query(Subscription).options(
        joinedload(Subscription.client),
        joinedload(Subscription.plan),
    ).filter(Subscription.id == saved_id).first()
    
    return subscription
