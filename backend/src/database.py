"""
数据库引擎 + 会话工厂 + get_db 依赖
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from src.config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    """FastAPI 依赖注入:每个请求获取独立的数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()