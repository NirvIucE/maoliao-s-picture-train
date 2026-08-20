"""
图片 三套 Pydantic Schema
Pydantic Schema 负责校验和序列化, 时刻分清楚每个场景该用哪个 Schema
ImageResponse、ImageUploadResponse 等
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

class ImageResponse(BaseModel):
    """单张图片响应"""
    id: int
    filename: str
    original_name: str
    custom_name: Optional[str] = None
    display_name: str
    file_size: int
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime
    thumbnail_url: Optional[str] = None
    image_url: Optional[str] = None

    model_config = {"from_attributes": True}

class ImageListResponse(BaseModel):
    """图片列表响应"""
    total: int
    items: list[ImageResponse]

class ImageUploadResponse(BaseModel):
    """上传成功响应"""
    id: int
    original_name: str
    custom_name: Optional[str] = None
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

class AIEditResponse(BaseModel):
    """AI 区域编辑响应"""
    image_base64: str    # 结果图的 base64 data URL

class UpdateImageNameRequest(BaseModel):
    """修改图片名称请求"""
    custom_name: str = Field(..., max_length=255, description="新名称，空字符串表示恢复原文件名")