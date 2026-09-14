"""
公共图库提交记录表模型
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.database import Base
from src.models.tag import public_image_tags


class PublicImage(Base):
    __tablename__ = "public_images"

    id             = Column(Integer, primary_key=True, autoincrement=True, index=True)
    image_id       = Column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status         = Column(String(20), nullable=False, default="pending", server_default="pending", index=True)  # pending/approved/rejected
    review_comment = Column(String(255), nullable=True)
    reviewed_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at    = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.now)
    is_visible     = Column(Boolean, nullable=False, default=True, server_default="1", comment="普通用户是否可见")

    # ORM 关系：公开标签（阶段 19 起与 Image.tags 个人标签分离）
    tags = relationship("Tag", secondary=public_image_tags, back_populates="public_images")
