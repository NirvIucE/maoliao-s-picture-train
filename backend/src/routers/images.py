"""
图片路由
(CRUD /images/*)
"""

import os

from fastapi import APIRouter, Depends, UploadFile, File, Query, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.database import get_db
from src.models.user import User
from src.schemas.image import ImageResponse, ImageListResponse, ImageUploadResponse
from src.services import image_service
from src.routers.users import get_current_user

router = APIRouter(prefix="/api/images", tags = ["图片"])

class URLUploadRequest(BaseModel):
    url: str
    custom_name: str | None = None

@router.post("/upload", response_model=ImageUploadResponse)
async def upload(
    file: UploadFile = File(...),
    custom_name: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传文件（可选自定义名称）"""
    image = image_service.upload_file(db, file, current_user, custom_name)
    return _build_upload_response(image)

@router.post("/upload-url", response_model=ImageUploadResponse)
async def upload_url(
    req: URLUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传URL图片"""
    image = await image_service.upload_from_url(db, req.url, current_user, req.custom_name)
    return _build_upload_response(image)

@router.get("", response_model=ImageListResponse)
async def list_images(
    skip: int = Query(0,ge = 0),    # 跳过前 N 条记录，ge=0 表示最小值为 0
    limit: int = Query(20, ge = 1, le = 100),    # 最多返回 N 条记录，最小 1，最大 100
    search: str | None = Query(None, description="搜索关键词（匹配图片名称）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取图片列表（支持搜索 + Redis 缓存）"""
    return await image_service.get_user_images(db, current_user, skip, limit, search)

@router.get("/{image_id}", response_model=ImageResponse)
def get_image(
    image_id : int,
    db : Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
):
    """获取图片详情"""
    return image_service.get_image_detail(db, image_id, current_user)

@router.get("/{image_id}/download")
def download_original(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """下载原始格式图片"""
    image = image_service.get_image_detail(db, image_id, current_user)
    if not os.path.exists(image.file_path):
        raise HTTPException(status_code=404, detail="原始图片不存在")
    return FileResponse(
        image.file_path, 
        filename=image.original_name,
        media_type="application/octet-stream",
    )

@router.delete("/{image_id}")
async def delete_image(
    image_id : int,
    db : Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
):
    """删除图片"""
    image_service.delete_image(db, image_id, current_user)
    return {"message": "图片删除成功"}

def _build_upload_response(image) -> dict:
    """构建上传响应(含URL)"""
    return {
        "id": image.id,
        "original_name": image.original_name,
        "custom_name": image.custom_name,
        "display_name": image.display_name,
        "file_size": image.file_size,
        "width": image.width,
        "height": image.height,
        "image_url": image.image_url,
        "thumbnail_url": image.thumbnail_url,
    }    