"""
业务逻辑
上传、压缩、查询、删除
"""
import os
import io
import uuid

from fastapi import UploadFile, HTTPException, responses, status
from sqlalchemy.orm import Session, session

import httpx

from src.models.image import Image
from src.models.user import User
from src.utils.image_utils import (
    generate_filename,
    get_image_dimensions,
    compress_to_webp,
    generate_thumbnail,
    validate_image_format,
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__),"..", "uploads")

def save_upload_file(upload_file: UploadFile) -> dict:
    """保存上传文件，返回文件信息字典"""
    # 校验文件格式
    try:
        validate_image_format(upload_file.filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # generate only filename
    filename = generate_filename(upload_file.filename)
    webp_name = f"{os.path.splitext(filename)[0]}.webp"
    thumb_name = f"{os.path.splitext(filename)[0]}.thumb.webp"

    #make sure the upload directory exits
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    #read file content
    contents = upload_file.file.read()
    width, height = get_image_dimensions(contents)
    #save original image
    original_path = os.path.join(UPLOAD_DIR, webp_name)
    with open(original_path, "wb") as f:
        f.write(contents)
    compress_to_webp(original_path, original_path)

    #generate thumbnail
    thumb_path = os.path.join(UPLOAD_DIR, thumb_name)
    generate_thumbnail(original_path, thumb_path)

    return{
        "filename": webp_name,
        "original_name": upload_file.filename,
        "file_size": os.path.getsize(original_path),
        "mime_type": "image/webp",
        "width": width,
        "height": height,
        "file_path": original_path,
        "thumbnail_path": thumb_path,
    }

def upload_file(db: session, file : UploadFile, user: User) -> Image:
    """处理文件上传"""
    file_info = save_upload_file(file)

    image = Image(
        user_id=user.id,
        filename=file_info["filename"],
        original_name=file_info["original_name"],
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
    return image


# Content-Type → 扩展名 映射表
CONTENT_TYPE_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
}


async def upload_from_url(db: Session, url: str, user: User) -> Image:
    """从 URL 下载图片并上传"""
    async with httpx.AsyncClient() as client:
        responses = await client.get(
            url,
            follow_redirects=True,
        )
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

    return upload_file(db, FakeUploadFile(), user)

def get_user_image(db: Session, user: User, skip: int = 0, limit: int = 20) -> dict:
    """获取用户的图片列表（分页）"""
    total = db.query(Image).filter(Image.user_id == user.id).count()
    images = (
        db.query(Image)
        .filter(Image.user_id == user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {"total": total, "items": images}



def get_image_detail(db: Session, image_id: int, user: User) -> Image:
    """获取单张图片详情"""
    image = db.query(Image).filter(Image.id == image_id, Image.user_id == user.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    return image

def delete_image(db:Session, image_id: int, user: User) -> None:
    """删除图片"""
    image = get_image_detail(db, image_id, user)
    #delete file
    if os.path.exists(image.file_path):
        os.remove(image.file_path)
    if image.thumbnail_path and os.path.exists(image.thumbnail_path):
        os.remove(image.thumbnail_path)
    #delete db record
    db.delete(image)
    db.commit()