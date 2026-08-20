"""
公共图库 请求/响应 Schema
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class PublicImageSubmitRequest(BaseModel):
    """提交到公共图库请求（仅从自己图库选图）"""
    image_id: int


class PublicImageResponse(BaseModel):
    """公共图库条目响应（图片信息已展平）"""
    id: int
    image_id: int
    user_id: int
    username: Optional[str] = None
    status: str
    review_comment: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    display_name: str
    thumbnail_url: Optional[str] = None
    image_url: Optional[str] = None
    is_visible: bool = True


class PublicImageListResponse(BaseModel):
    """公共图库列表响应"""
    total: int
    items: list[PublicImageResponse]


class ReviewRequest(BaseModel):
    """审核请求"""
    action: Literal["approve", "reject"]
    comment: Optional[str] = None


class RemoveRequest(BaseModel):
    """下架请求"""
    comment: Optional[str] = None


class PublicImageDetailResponse(PublicImageResponse):
    """公共图库详情响应（额外含当前用户的权限判断）"""
    is_owner: bool
    is_admin: bool


class SetVisibilityRequest(BaseModel):
    """切换可见性请求"""
    visible: bool
