from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.core.database import get_db
from app.models import VpnClient, ClientConfig, Subscription, User
from app.api.routes.auth import get_current_active_user

router = APIRouter()

class VpnClientBase(BaseModel):
    name: str
    email: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True

class VpnClientCreate(VpnClientBase):
    pass

class VpnClientUpdate(VpnClientBase):
    pass

class VpnClientResponse(VpnClientBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[VpnClientResponse])
async def get_clients(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Получить всех VPN клиентов"""
    return db.query(VpnClient).all()

@router.post("/", response_model=VpnClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(client: VpnClientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Создать нового VPN клиента"""
    db_client = VpnClient(
        name=client.name,
        email=client.email,
        notes=client.notes,
        is_active=client.is_active
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.get("/{client_id}", response_model=VpnClientResponse)
async def get_client(client_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Получить клиента по ID"""
    client = db.query(VpnClient).filter(VpnClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.put("/{client_id}", response_model=VpnClientResponse)
async def update_client(client_id: int, client_data: VpnClientUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Обновить данные клиента"""
    client = db.query(VpnClient).filter(VpnClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    client.name = client_data.name
    client.email = client_data.email
    client.notes = client_data.notes
    client.is_active = client_data.is_active
    
    db.commit()
    db.refresh(client)
    return client

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Удалить клиента"""
    client = db.query(VpnClient).filter(VpnClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db.delete(client)
    db.commit()
    return None
