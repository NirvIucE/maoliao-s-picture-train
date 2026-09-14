"""
图片 三套 Pydantic Schema
Pydantic Schema 负责校验和序列化, 时刻分清楚每个场景该用哪个 Schema
ImageResponse、ImageUploadResponse 等
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ImageResponse(BaseModel):
    """单张图片响应"""
    id: int
    filename: str
    original_name: str
    custom_name: str | None = None
    display_name: str
    file_size: int
    mime_type: str
    width: int | None = None
    height: int | None = None
    created_at: datetime
    thumbnail_url: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}

class ImageDetailResponse(ImageResponse):
    """单张图片详情响应（阶段 19：额外带个人标签）

    阶段 21 起列表项也复用本模型：图库网格要显示标签、并支持点击标签筛选，
    因此把 tags 一并放进列表响应。随之而来的两处代价已同步处理：
    ① 标签增删路径补清 `images:user:{id}:*` 缓存；
    ② 列表查询用 `selectinload(Image.tags)` 预取，避免逐行查标签的 N+1。
    """
    tags: list[str] = []

class ImageListResponse(BaseModel):
    """图片列表响应（阶段 21：items 与详情同构，含个人标签）"""
    total: int
    items: list[ImageDetailResponse]

class ImageTagsRequest(BaseModel):
    """个人图库添加标签请求"""
    tags: list[str]

class ImageTagStat(BaseModel):
    """单个标签及其使用次数（阶段 21：图库筛选条数据源）"""
    name: str
    count: int

class ImageTagListResponse(BaseModel):
    """当前用户个人图库的标签统计（按使用次数降序）"""
    total: int
    items: list[ImageTagStat]

class ImageUploadResponse(BaseModel):
    """上传成功响应"""
    id: int
    original_name: str
    custom_name: str | None = None
    display_name: str
    file_size: int
    width: int
    height: int
    image_url: str
    thumbnail_url: str

class EditOperation(BaseModel):
    """单次编辑操作(rotate/flip/crop 三选一)"""
    type: Literal["rotate", "flip", "crop"]
    angle: int | None = None # rotate: 90 / 180 / 270
    direction: str | None = None # flip: "horizontal" / "vertical"
    left: int | None = None # crop
    top: int | None = None
    right: int | None = None
    bottom: int | None = None

class EditImageRequest(BaseModel):
    """编辑图片请求"""
    operations: list[EditOperation]
    save_mode: Literal["overwrite", "new"]
    custom_name: str | None = None

class AIEditRequest(BaseModel):
    """AI编辑图片请求"""
    prompt: str # 用户编辑指令，如“换成星空”
    image_base64: str # 提示图（原图+涂鸦标记）的 base64 data URL
    color_name: str = "红色"   # 涂鸦标记色，用于拼接 prompt

class UpdateImageNameRequest(BaseModel):
    """修改图片名称请求"""
    custom_name: str = Field(..., max_length=255, description="新名称，空字符串表示恢复原文件名")
