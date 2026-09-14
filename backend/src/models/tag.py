"""
标签表模型 + image_tags / public_image_tags 多对多关联

阶段 19：标签关系拆成两层
- image_tags        → 个人图库标签（用户自己的归类）
- public_image_tags → 公共图库标签（对外展示）
两者共用 tags 字典（标签名不重复存储），但关系互相独立：
个人标签不会因为提交而外泄，改个人标签也不会影响已公开记录。
"""
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from src.database import Base

#多对多中间表（个人图库标签）
image_tags = Table(
    "image_tags",
    Base.metadata,
    Column("image_id", Integer, ForeignKey("images.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
)

#多对多中间表（公共图库标签）
public_image_tags = Table(
    "public_image_tags",
    Base.metadata,
    Column(
        "public_image_id",
        Integer,
        ForeignKey("public_images.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    images = relationship("Image", secondary=image_tags, back_populates="tags")
    public_images = relationship("PublicImage", secondary=public_image_tags, back_populates="tags")
