"""
Скрипт для создания первого администратора
"""
import sys
import os

# Добавляем путь к родительской директории
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.models import User
from app.utils.security import get_password_hash
from app.core.config import settings


def create_admin():
    """Создать администратора по умолчанию"""
    db = SessionLocal()
    
    try:
        # Проверяем существует ли уже admin
        existing_admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        
        if existing_admin:
            print(f"⚠️ Admin user '{settings.ADMIN_USERNAME}' already exists. Updating password...")
            existing_admin.password_hash = get_password_hash(settings.ADMIN_PASSWORD)
            db.commit()
            print("✅ Password updated successfully!")
            print(f"   Username: {settings.ADMIN_USERNAME}")
            print(f"   Password: {settings.ADMIN_PASSWORD}")
            return
        
        # Создаем администратора
        admin = User(
            username=settings.ADMIN_USERNAME,
            email="admin@example.com",
            password_hash=get_password_hash(settings.ADMIN_PASSWORD),
            is_active=True
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print("✅ Admin user created successfully!")
        print(f"   Username: {settings.ADMIN_USERNAME}")
        print(f"   Password: {settings.ADMIN_PASSWORD}")
        print(f"   ⚠️  Please change the password after first login!")
        
    except Exception as e:
        print(f"❌ Error creating admin: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
