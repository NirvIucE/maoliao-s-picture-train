
"""
User 表的ORM模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime


from src.database import Base
from src.models.image import Image

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)
    # ORM 关系
    from sqlalchemy.orm import relationship
    images = relationship("Image", back_populates="user")
