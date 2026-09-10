"""
图片路由
(CRUD /images/*)
"""

import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.routers.users import get_current_user
from src.schemas.ai_task import AITaskSubmitResponse
from src.schemas.image import (
    AIEditRequest,
    EditImageRequest,
    ImageListResponse,
    ImageResponse,
    ImageUploadResponse,
    UpdateImageNameRequest,
)
from src.services import image_service, task_service

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
    image = await image_service.upload_file(db, file, current_user, custom_name)
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


@router.patch("/{image_id}/name", response_model=ImageResponse)
async def rename_image(
    image_id: int,
    req: UpdateImageNameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改图片名称"""
    return image_service.update_image_name(db, image_id, req.custom_name, current_user)


@router.post("/{image_id}/edit", response_model=ImageUploadResponse)
async def edit_image(
    image_id: int,
    req: EditImageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑图片（裁剪/旋转/翻转），支持覆盖或另存"""
    image = await image_service.edit_image(
        db, image_id, req.operations, req.save_mode, req.custom_name, current_user
    )
    return _build_upload_response(image)


@router.post("/{image_id}/replace", response_model=ImageUploadResponse)
async def replace_image(
    image_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用新图片文件覆盖原图（AI 抠图/区域编辑结果）"""
    image = await image_service.replace_image(db, image_id, file, current_user)
    return _build_upload_response(image)

@router.post("/{image_id}/ai-edit", response_model=AITaskSubmitResponse)
async def ai_edit_image(
    image_id: int,
    req: AIEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 区域编辑（涂鸦 + 指令）：提交即返回 task_id，前端轮询 /api/tasks/{task_id} 取状态与结果"""
    task = task_service.create_ai_edit_task(
        db, image_id, req.prompt, req.image_base64, current_user, req.color_name
    )
    task_service.schedule_ai_edit_task(task.id)
    return AITaskSubmitResponse(task_id=task.id, status=task.status)

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
