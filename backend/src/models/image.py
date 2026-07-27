"""
图片表模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from sqlalchemy.orm import relationship
from src.database import Base
from src.models import tag  # 确保 Tag 模型和 image_tags 表被注册到 Base.metadata

class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False, comment="存储文件名（UUID）")
    original_name = Column(String(255), nullable=False, comment="用户上传的原始文件名")
    file_path = Column(String(500), nullable=False, comment="原图存储路径")
    thumbnail_path = Column(String(500), nullable=True, comment="缩略图存储路径")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    mime_type = Column(String(50), nullable=False, comment="MIME 类型")
    width = Column(Integer, nullable=True, comment="图片宽度")
    height = Column(Integer, nullable=True, comment="图片高度")
    created_at = Column(DateTime, default=datetime.now)

    # ORM 关系
    user = relationship("User", back_populates="images")
    tags = relationship("Tag", secondary="image_tags", back_populates="images")