"""
业务逻辑
上传、压缩、查询、删除
"""
import asyncio
import base64
import io
import os
import uuid

import httpx
from fastapi import HTTPException, UploadFile, status
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from src.cache import cache_delete_pattern, cache_get, cache_set
from src.config import AI_EDIT_TIMEOUT, PROVIDER_CONFIG, UPLOAD_ROOT
from src.models.image import Image
from src.models.public_image import PublicImage
from src.models.user import User
from src.schemas.image import ImageResponse
from src.utils.image_utils import (
    generate_thumbnail,
    get_date_upload_dir,
    get_image_dimensions,
    validate_image_format,
)

UPLOAD_DIR = UPLOAD_ROOT

# Content-Type -> 扩展名映射表
CONTENT_TYPE_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
}

# 扩展名 -> 标准 MIME 映射表（上传时统一存标准 MIME，避免 image/jpg 等非标准值）
EXTENSION_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
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
        "mime_type": EXTENSION_TO_MIME.get(original_ext, f"image/{original_ext[1:]}"),
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
    # 级联删除公共图库引用记录（原图删除后，公共库对应条目失效）
    db.query(PublicImage).filter(PublicImage.image_id == image.id).delete()
    #delete db record
    db.delete(image)
    db.commit()

    # 清除后删缓存
    asyncio.create_task(cache_delete_pattern(f"images:user:{user.id}:*"))

def edit_image(db: Session,
    image_id: int,
    operations: list,
    save_mode: str,
    custom_name: str | None,
    user: User,
) -> Image:
    """编辑图片：按顺序执行裁剪/旋转/翻转，支持覆盖或另存"""
    image = get_image_detail(db, image_id, user)
    img = PILImage.open(image.file_path)

    # 按顺序应用所有编辑操作
    for op in operations:
        if op.type == "rotate":
            # Pillow 默认逆时针，取反转为顺时针
            img = img.rotate(-op.angle, expand=True)
        elif op.type == "flip":
            if op.direction == "horizontal":
                img = img.transpose(PILImage.Transpose.FLIP_LEFT_RIGHT)
            elif op.direction == "vertical":
                img = img.transpose(PILImage.Transpose.FLIP_TOP_BOTTOM)
        elif op.type == "crop":
            img = img.crop((op.left, op.top, op.right, op.bottom))

    if save_mode == "overwrite":
        # 覆盖原图 + 重生成缩略图
        img.save(image.file_path)
        image.width, image.height = img.size
        image.file_size = os.path.getsize(image.file_path)
        generate_thumbnail(image.file_path, image.thumbnail_path)
        db.commit()
        db.refresh(image)
        asyncio.create_task(cache_delete_pattern(f"images:user:{user.id}:*"))
        return image
    else:
        # 另存为新图片
        date_dir = get_date_upload_dir()
        upload_subdir = os.path.join(UPLOAD_DIR, date_dir)
        os.makedirs(upload_subdir, exist_ok=True)

        ext = os.path.splitext(image.filename)[1] or ".jpg"
        new_filename = f"{uuid.uuid4().hex}{ext}"
        new_path = os.path.join(upload_subdir, new_filename)
        img.save(new_path)

        thumb_name = f"{uuid.uuid4().hex}_thumb.webp"
        thumb_path = os.path.join(upload_subdir, thumb_name)
        generate_thumbnail(new_path, thumb_path)

        new_image = Image(
            user_id=user.id,
            filename=new_filename,
            original_name=image.original_name,
            custom_name=custom_name or f"{image.display_name}(编辑)",
            date_dir=date_dir,
            file_path=new_path,
            thumbnail_path=thumb_path,
            file_size=os.path.getsize(new_path),
            mime_type=image.mime_type,
            width=img.size[0],
            height=img.size[1],
        )

        db.add(new_image)
        db.commit()
        db.refresh(new_image)
        asyncio.create_task(cache_delete_pattern(f"images:user:{user.id}:*"))
        return new_image

def replace_image(db: Session, image_id: int, file: UploadFile, user: User) -> Image:
    """用新图片文件覆盖原图（保留原记录，更新文件+缩略图+尺寸）"""

    image = get_image_detail(db, image_id, user)

    # 校验新文件格式
    try:
        validate_image_format(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    contents = file.file.read()
    width, height = get_image_dimensions(contents)

    new_ext = os.path.splitext(file.filename)[1].lower()
    old_ext = os.path.splitext(image.file_path)[1].lower()

    if new_ext != old_ext:
        # 扩展名变了（如 JPG → PNG 抠图），删除旧文件，用新路径
        if os.path.exists(image.file_path):
            os.remove(image.file_path)
        new_filename = f"{uuid.uuid4().hex}{new_ext}"
        new_path = os.path.join(os.path.dirname(image.file_path), new_filename)
        image.filename = new_filename
        image.mime_type = EXTENSION_TO_MIME.get(new_ext, f"image/{new_ext[1:]}")
        image.file_path = new_path
    else:
        new_path = image.file_path

    # 写入新文件
    with open(new_path, "wb") as f:
        f.write(contents)

    # 重生成缩略图（覆盖原缩略图路径）
    generate_thumbnail(new_path, image.thumbnail_path)

    image.width = width
    image.height = height
    image.file_size = os.path.getsize(new_path)

    db.commit()
    db.refresh(image)
    asyncio.create_task(cache_delete_pattern(f"images:user:{user.id}:*"))
    return image

def update_image_name(db: Session, image_id: int, custom_name: str, user: User) -> Image:
    """修改图片自定义名称（仅更新 custom_name，空串恢复原文件名）"""
    image = get_image_detail(db, image_id, user)
    name = custom_name.strip()
    image.custom_name = name or None
    db.commit()
    db.refresh(image)
    # 改名后清除该用户的图片列表缓存，避免图库显示旧名
    asyncio.create_task(cache_delete_pattern(f"images:user:{user.id}:*"))
    return image

IMAGE_EDIT_MODEL = "Qwen/Qwen-Image-Edit-2509"
def _extract_result_image(payload: dict) -> str | None:
    """
    从图生图接口响应中解析结果图（兼容多种厂商返回形状）：
    images[0].url → images[0].b64_json → data[0].b64_json → data[0].url
    → data_url → 顶层 url → 顶层 b64_json；全部失败返回 None
    （参考 ai-image-edit 示例项目的多形态解析思路）
    """
    if not isinstance(payload, dict):
        return None

    def _first(items: object, key: str) -> str | None:
        if isinstance(items, list) and items and isinstance(items[0], dict):
            value = items[0].get(key)
            return value if isinstance(value, str) and value else None
        return None

    for candidate in (
        _first(payload.get("images"), "url"),
        _first(payload.get("images"), "b64_json"),
        _first(payload.get("data"), "b64_json"),
        _first(payload.get("data"), "url"),
        payload.get("data_url"),
        payload.get("url"),
        payload.get("b64_json"),
    ):
        if candidate:
            return candidate
    return None

async def call_image_edit(prompt: str, image_base64: str, color_name: str = "红色") -> str:
    """调用硅基流动图生图执行区域编辑，返回结果图 base64 data URL

    阶段 16：本函数由 task_service 的后台协程调用，是纯调用（不做 DB 校验）——
    图片存在性与归属校验已在「任务创建」时完成，避免长任务期间占用 DB 连接。
    """
    provider = PROVIDER_CONFIG.get("siliconflow")
    if not provider or not provider.get("api_key"):
        raise HTTPException(status_code=500, detail="siliconflow 未配置")

    # 组合指令：目标区域限定 + 区域外保护 + 边缘融合 + 冲突优先（黑区保护约束）
    full_prompt = (
        f"图中被{color_name}半透明标记覆盖的区域是唯一可修改的目标区域。"
        f"请仅对该区域执行以下编辑：{prompt}。\n"
        f"必须严格遵守：\n"
        f"1) 标记区域外的所有内容必须保持完全不变，包括但不限于构图、背景、"
        f"物体位置/轮廓/大小、颜色、光照、阴影、清晰度、对比度、风格、文字水印。\n"
        f"2) 标记区域的边缘要自然融合，避免改动溢出到区域外。\n"
        f"3) 如果编辑指令与区域外保持不变冲突，优先保证区域外完全不变。"
    )

    async with httpx.AsyncClient(timeout=AI_EDIT_TIMEOUT) as client:
        resp = await client.post(
            f"{provider['base_url']}/images/generations",
            headers={
                "Authorization": f"Bearer {provider['api_key']}",
                "Content-Type": "application/json",
            },
            json = {
                "model": IMAGE_EDIT_MODEL,
                "prompt": full_prompt,
                "image": image_base64,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI 编辑失败: {resp.status_code} - {resp.text[:200]}",
            )

        data = resp.json()
        result = _extract_result_image(data)
        if not result:
            raise HTTPException(status_code=502, detail="AI 编辑失败：响应中未解析到图片")

        if result.startswith("data:image/"):
            # 已是 data URL，直接返回
            return result
        if "://" in result:
            # 是 URL：下载临时结果并转 base64（URL 会过期，必须立即转存）
            dl = await client.get(result, follow_redirects=True)
            if dl.status_code != 200:
                raise HTTPException(status_code=502, detail="下载 AI 结果失败")
            result_base64 = base64.b64encode(dl.content).decode("utf-8")
            return f"data:image/png;base64,{result_base64}"
        # 裸 base64（b64_json 形状）
        return f"data:image/png;base64,{result}"
