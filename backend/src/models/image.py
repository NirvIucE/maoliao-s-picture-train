'''
Author: NirvIucE 1750682685@qq.com
Date: 2026-07-24 21:21:41
LastEditors: NirvIucE 1750682685@qq.com
LastEditTime: 2026-07-29 16:00:35
FilePath: \new-picture-train\backend\src\models\image.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
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

    # 计算属性：Pydantic from_attributes 可读取 @property
    @property
    def image_url(self) -> str:
        return f"/static/uploads/{self.filename}"

    @property
    def thumbnail_url(self) -> str | None:
        if self.thumbnail_path:
            return f"/static/uploads/{os.path.basename(self.thumbnail_path)}"
        return None