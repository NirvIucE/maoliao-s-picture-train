"""
公共图库提交记录表模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey

from src.database import Base


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
