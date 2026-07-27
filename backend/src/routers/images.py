"""
图片路由
(CRUD /images/*)
"""

import os

from fastapi import APIRouter, Depends, UploadFile, File, Query
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

@router.post("/upload", response_model=ImageUploadResponse)
async def upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传文件"""
    image = image_service.upload_file(db, file, current_user)
    return _build_upload_response(image)

@router.post("/upload_url", response_model=ImageUploadResponse)
async def upload_url(
    req: URLUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传URL图片"""
    image = await image_service.upload_from_url(db, req.url, current_user)
    return _build_upload_response(image)

@router.get("", response_model=ImageListResponse)
def list_images(
    skip: int = Query(0,ge = 0),    # 跳过前 N 条记录，ge=0 表示最小值为 0
    limit: int = Query(20, ge = 1, le = 100),    # 最多返回 N 条记录，最小 1，最大 100
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取图片列表"""
    return image_service.get_user_image(db, current_user, skip, limit)

@router.get("/{image_id}", response_model=ImageResponse)
def get_image(
    image_id : int,
    db : Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
):
    """获取图片详情"""
    return image_service.get_image_detail(db, image_id, current_user)

@router.delete("/{image_id}")
def delete_image(
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
        "file_size": image.file_size,
        "width": image.width,
        "height": image.height,
        "image_url": f"/static/uploads/{image.filename}",
        "thumbnail_url": f"/static/uploads/{os.path.basename(image.thumbnail_path)}",
    }    