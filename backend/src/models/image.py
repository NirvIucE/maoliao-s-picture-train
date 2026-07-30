
"""
图片表模型
"""
import os
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
    custom_name = Column(String(255), nullable=True, comment="用户自定义名称（可选）")
    date_dir = Column(String(8), nullable=False, comment="日期子目录")
    file_path = Column(String(500), nullable=False, comment="原图（原格式）存储路径")
    thumbnail_path = Column(String(500), nullable=True, comment="缩略图存储路径")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    mime_type = Column(String(50), nullable=False, comment="MIME 类型")
    width = Column(Integer, nullable=True, comment="图片宽度")
    height = Column(Integer, nullable=True, comment="图片高度")
    created_at = Column(DateTime, default=datetime.now)

    # ORM 关系
    user = relationship("User", back_populates="images")
    tags = relationship("Tag", secondary="image_tags", back_populates="images")

    # 计算属性：Pydantic from_attributes 可读取 @property
    @property
    def display_name(self) -> str:
        """显示名称：自定义名称 > 原始文件名"""
        return self.custom_name or self.original_name

    @property
    def image_url(self) -> str | None:
        if self.file_path:
            return f"/static/uploads/{self.date_dir}/{self.filename}"
        return None        

    @property
    def thumbnail_url(self) -> str | None:
        if self.thumbnail_path:
            return f"/static/uploads/{self.date_dir}/{os.path.basename(self.thumbnail_path)}"
        return None