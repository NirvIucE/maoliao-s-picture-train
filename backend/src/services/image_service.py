"""
业务逻辑
上传、压缩、查询、删除
"""
import os
import io
import uuid

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session

import httpx

from src.cache import cache_get, cache_set, cache_delete_pattern
import asyncio

from src.models.image import Image
from src.models.user import User
from src.schemas.image import ImageResponse
from src.utils.image_utils import (
    get_image_dimensions,
    generate_thumbnail,
    validate_image_format,
    get_date_upload_dir,
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__),"..", "uploads")

# Content-Type -> 扩展名映射表
CONTENT_TYPE_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
}

# Cache TTL 常量
IMAGE_LIST_TTL = 120 # 图片列表缓存 2 分钟

def save_upload_file(upload_file: UploadFile, custom_name: str | None = None) -> dict:
    """保存上传文件(2 文件策略：原格式 + 缩略图)，返回文件信息字典"""
    # 校验文件格式
    try:
        validate_image_format(upload_file.filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # date child directory
    date_dir = get_date_upload_dir()
    upload_subdir = os.path.join(UPLOAD_DIR, date_dir)
    os.makedirs(upload_subdir, exist_ok=True)

    # read file content
    contents = upload_file.file.read()
    width, height = get_image_dimensions(contents)

    # save original image (is display image too)
    original_ext = os.path.splitext(upload_file.filename)[1].lower()
    original_uuid_name = f"{uuid.uuid4().hex}{original_ext}"
    original_path = os.path.join(upload_subdir, original_uuid_name)
    with open(original_path, "wb") as f:
        f.write(contents)

    # generate thumbnail iamge
    thumb_name = f"{uuid.uuid4().hex}_thumb.webp"
    thumb_path = os.path.join(upload_subdir, thumb_name)
    generate_thumbnail(original_path, thumb_path)

    return{
        "filename": original_uuid_name,
        "original_name": upload_file.filename,
        "custom_name": custom_name,
        "date_dir": date_dir,
        "file_size": os.path.getsize(original_path),
        "mime_type": f"image/{original_ext[1:]}",
        "width": width,
        "height": height,
        "file_path": original_path,
        "thumbnail_path": thumb_path,
    }

def upload_file(db: Session, file : UploadFile, user: User, custom_name: str | None = None) -> Image:
    """处理文件上传"""
    file_info = save_upload_file(file, custom_name)

    image = Image(
        user_id=user.id,
        filename=file_info["filename"],
        original_name=file_info["original_name"],
        custom_name=file_info["custom_name"],
        date_dir=file_info["date_dir"],
        file_path=file_info["file_path"],
        thumbnail_path=file_info["thumbnail_path"],
        file_size=file_info["file_size"],
        mime_type=file_info["mime_type"],
        width=file_info["width"],
        height=file_info["height"],
    )
    db.add(image)
    db.commit()
    db.refresh(image)

    # 上传后删除该用户的图片列表缓存（下次访问重新加载）
    asyncio.create_task(cache_delete_pattern(f"images:user:{user.id}:*"))
    return image

async def upload_from_url(db: Session, url: str, user: User, custom_name: str | None = None) -> Image:
    """从 URL 下载图片并上传"""
    async with httpx.AsyncClient() as client:
        responses = await client.get(url, follow_redirects=True)
        if responses.status_code != 200:
            raise HTTPException(status_code=400, detail="无法下载该URL的图")

    # 从响应头获取真实图片格式，不受 URL 后缀干扰
    content_type = responses.headers.get("content-type", "").split(";")[0].strip()
    ext = CONTENT_TYPE_MAP.get(content_type)
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片类型: {content_type}",
        )

    # 构建带正确扩展名的文件名
    base_name = url.split("/")[-1].split("?")[0].split("@")[0] or "download"
    base_name = os.path.splitext(base_name)[0]  # 去掉原扩展名
    filename = f"{base_name}{ext}"

    # 打包下载内容作为类文件对象
    file_content = io.BytesIO(responses.content)
    # 创建伪 UploadFile（用 type() 避免类作用域的名字冲突）
    FakeUploadFile = type("FakeUploadFile", (), {"file": file_content, "filename": filename})
    return upload_file(db, FakeUploadFile(), user, custom_name)

async def get_user_images(db: Session, user: User, skip: int = 0, limit: int = 20, search: str | None = None) -> dict:
    """获取用户的图片列表（分页 + 搜索 + Redis缓存）"""
    # 只有无搜索、第一页才用缓存（搜索条件变化多，不缓存）
    if not search and skip == 0:
        cache_key = f"images:user:{user.id}:page0"
        cached = await cache_get(cache_key)
        if cached:
            # 缓存命中：从 dict 重建 Pydantic 模型
            cached["items"] = [ImageResponse(**item) for item in cached["items"]]
            return cached
    
    # 缓存未命中 查数据库
    query = db.query(Image).filter(Image.user_id == user.id)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Image.custom_name.ilike(pattern)) |
            (Image.original_name.ilike(pattern))
        )
    
    total = query.count()
    images = query.order_by(Image.created_at.desc()).offset(skip).limit(limit).all()
    # ORM → Pydantic（便于 JSON 序列化存入缓存）
    items = [ImageResponse.model_validate(img) for img in images]
    result = {"total": total, "items": items}
    # 缓存结果（存 model_dump 后的纯 dict）
    if not search and skip == 0:
        cache_data = {"total": total, "items": [item.model_dump() for item in items]}
        await cache_set(cache_key, cache_data, IMAGE_LIST_TTL)

    return result

def get_image_detail(db: Session, image_id: int, user: User) -> Image:
    """获取单张图片详情"""
    image = db.query(Image).filter(Image.id == image_id, Image.user_id == user.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    return image

def delete_image(db:Session, image_id: int, user: User) -> None:
    """删除图片 (数据库记录 + 物理文件 + 缓存失效)"""
    image = get_image_detail(db, image_id, user)
    #delete file
    for path in [image.file_path, image.thumbnail_path]:
        if path and os.path.exists(path):
            os.remove(path)
    #delete db record
    db.delete(image)
    db.commit()

    # 清除后删缓存
    asyncio.create_task(cache_delete_pattern(f"images:user:{user.id}:*"))

