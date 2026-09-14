"""
公共图库 请求/响应 Schema
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from src.schemas.image import ImageTagStat


class PublicImageSubmitRequest(BaseModel):
    """提交到公共图库请求（仅从自己图库选图，可选标签）"""
    image_id: int
    tags: list[str] = []


class PublicImageResponse(BaseModel):
    """公共图库条目响应（图片信息已展平）"""
    id: int
    image_id: int
    user_id: int
    username: str | None = None
    status: str
    review_comment: str | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    display_name: str
    thumbnail_url: str | None = None
    image_url: str | None = None
    is_visible: bool = True
    tags: list[str] = []


class PublicImageListResponse(BaseModel):
    """公共图库列表响应"""
    total: int
    items: list[PublicImageResponse]


class PublicImageTagListResponse(BaseModel):
    """公共图库标签统计响应（阶段 22：筛选条数据源）

    复用个人图库的 ImageTagStat（{name, count}）避免同构模型重复定义；
    统计口径随请求者角色变化（详见 public_service.get_public_tag_stats）。
    """
    total: int
    items: list[ImageTagStat]


class ReviewRequest(BaseModel):
    """审核请求"""
    action: Literal["approve", "reject"]
    comment: str | None = None


class RemoveRequest(BaseModel):
    """下架请求"""
    comment: str | None = None


class PublicImageDetailResponse(PublicImageResponse):
    """公共图库详情响应（额外含当前用户的权限判断）"""
    is_owner: bool
    is_admin: bool


class SetVisibilityRequest(BaseModel):
    """切换可见性请求"""
    visible: bool


class AddTagsRequest(BaseModel):
    """添加标签请求"""
    tags: list[str]


class AISearchRequest(BaseModel):
    """AI 搜索请求"""
    query: str
    mode: Literal["semantic", "vision"] = "semantic"
