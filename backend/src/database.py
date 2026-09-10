"""
数据库引擎 + 会话工厂 + get_db 依赖
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=20,
    # P2-1 治理：连接复用前先探活，避免 MySQL 8h 空闲断连后
    # 从池中取到已失效连接（原表现为偶发 "MySQL server has gone away"）；
    # pool_recycle 提前于 wait_timeout 回收连接，双重保险
    pool_pre_ping=True,
    pool_recycle=3600,
)
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
