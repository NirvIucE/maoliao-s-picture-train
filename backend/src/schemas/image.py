
"""
图片 三套 Pydantic Schema
Pydantic Schema 负责校验和序列化, 时刻分清楚每个场景该用哪个 Schema
ImageResponse、ImageUploadResponse 等
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

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

