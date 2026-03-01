from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models import SubscriptionPlan, User
from app.api.routes.auth import get_current_active_user

router = APIRouter()

# Schemas
class SubscriptionPlanBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = 0.0
    duration_days: int = 30
    traffic_limit_gb: int = 0
    is_default: bool = False
    is_active: bool = True

class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass

class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    duration_days: Optional[int] = None
    traffic_limit_gb: Optional[int] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

class SubscriptionPlanResponse(SubscriptionPlanBase):
    id: int
    
    class Config:
        from_attributes = True

# Routes
@router.get("/", response_model=List[SubscriptionPlanResponse])
async def get_plans(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Получить список тарифных планов"""
    query = db.query(SubscriptionPlan)
    if active_only:
        query = query.filter(SubscriptionPlan.is_active == True)
    
    plans = query.order_by(SubscriptionPlan.price).offset(skip).limit(limit).all()
    return plans

@router.post("/", response_model=SubscriptionPlanResponse)
async def create_plan(
    plan: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Создать тарифный план"""
    # Если этот план дефолтный, снимаем галочку с других
    if plan.is_default:
        db.query(SubscriptionPlan).update({SubscriptionPlan.is_default: False})
    
    db_plan = SubscriptionPlan(**plan.dict())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

@router.put("/{plan_id}", response_model=SubscriptionPlanResponse)
async def update_plan(
    plan_id: int,
    plan_update: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Обновить тарифный план"""
    db_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    update_data = plan_update.dict(exclude_unset=True)
    
    # Если делаем этот план дефолтным
    if update_data.get('is_default'):
        db.query(SubscriptionPlan).filter(SubscriptionPlan.id != plan_id).update({SubscriptionPlan.is_default: False})
    
    for key, value in update_data.items():
        setattr(db_plan, key, value)
        
    db.commit()
    db.refresh(db_plan)
    return db_plan

@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Удалить тарифный план"""
    db_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    db.delete(db_plan)
    db.commit()
    return {"ok": True}
