"""
WebP 压缩、缩略图生成
"""
import io
import os
import uuid
from datetime import date

from PIL import Image


def get_date_upload_dir() -> str:
    """返回按日期组织的上传子目录名，如 20260729"""
    return date.today().strftime("%Y%m%d")

def generate_filename(original_filename:str) -> str:
    """
    生成唯一的文件名:UUID + 原扩展名
    """
    ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
    return f"{uuid.uuid4().hex}{ext}"

def get_image_dimensions(file_content: bytes) -> tuple[int, int]:
    """
    获取图片尺寸
    """
    img = Image.open(io.BytesIO(file_content))
    return img.size

def compress_to_webp(input_path: str, output_path: str, quality: int = 80) -> str:
    """将图片压缩为 WebP 格式，返回输出路径"""
    img = Image.open(input_path)
    img.save(output_path, "WEBP", quality=quality)
    return output_path

# 允许的上传图片格式
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}


def validate_image_format(filename: str) -> str:
    """校验文件名是否为允许的图片格式，通过则返回小写扩展名"""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的图片格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}")
    return ext


def generate_thumbnail(input_path: str, output_path: str, size: tuple[int, int] = (300, 300), quality: int = 70) -> str:
    """生成缩略图，返回输出路径"""
    img = Image.open(input_path)
    img.thumbnail(size)
    img.save(output_path, "WEBP", quality=quality)
    return output_path
