"""
注册和登录的业务逻辑：
"""

import os
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.cache import cache_get, cache_set
from src.models.user import User
from src.schemas.user import UserCreate
from src.utils.security import create_access_token, hash_password, verify_password

USER_INFO_TTL = 600 # 用户信息缓存10分钟

# 头像存储目录（位于 uploads 下，通过 /static/uploads/avatars/... 访问）
AVATAR_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "avatars")
# 允许的头像扩展名
ALLOWED_AVATAR_EXT = {".jpg", ".jpeg", ".png", ".webp"}

def register_user(db: Session, user_data :UserCreate) -> User:
    """注册新用户"""
    existing = db.query(User).filter(
       (User.username == user_data.username)|
       (User.email == user_data.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = "用户名或邮箱已存在"
        )
    new_user = User(
        username = user_data.username,
        email = user_data.email,
        hashed_password = hash_password(user_data.password),
        uid = str(uuid.uuid4()),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user) #session刷新，获取最新数据
    #"sub" 是 JWT 标准字段（subject），习惯上存用户 ID
    # db.add() 后对象虽然有值，但 id 和 created_at 是数据库自动生成的，
    # 需要 refresh 才能取到。
    return new_user

def authenticate_user(db: Session, username: str, password: str) -> dict:
    """验证用户登录,成功返回Token"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "用户名或密码错误"
        )
    token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer"
    }

async def get_cached_user(db:Session, user_id: int) -> User | None:
    """从缓存或数据库获取用户（用于 JWT 鉴权）"""
    cache_key = f"user:{user_id}"
    cached = await cache_get(cache_key)
    if cached:
        # 缓存命中：从字典重建 User 对象
        return db.query(User).filter(User.id == user_id).first()

    # 缓存未命中：查数据库 → 写入缓存
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        await cache_set(cache_key, {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }, USER_INFO_TTL)
    return user


def update_username(db: Session, user: User, new_username: str) -> User:
    """修改用户名（校验非空 + 唯一）"""
    new_username = new_username.strip()
    if not new_username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    existing = db.query(User).filter(User.username == new_username).first()
    if existing and existing.id != user.id:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user.username = new_username
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    """修改密码（校验旧密码 + 新密码哈希）"""
    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码错误")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    user.hashed_password = hash_password(new_password)
    db.commit()


def update_avatar(db: Session, user: User, file: UploadFile) -> str:
    """上传/更换头像（覆盖式存储），返回头像 URL"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_AVATAR_EXT:
        raise HTTPException(status_code=400, detail="头像仅支持 jpg/png/webp")
    contents = file.file.read()
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像大小不能超过 2MB")
    os.makedirs(AVATAR_DIR, exist_ok=True)
    filename = f"avatar_{user.id}{ext}"
    path = os.path.join(AVATAR_DIR, filename)
    with open(path, "wb") as f:
        f.write(contents)
    url = f"/static/uploads/avatars/{filename}"
    # 删除旧头像文件（覆盖式，处理扩展名变化）
    if user.avatar_url and user.avatar_url != url:
        old_path = os.path.join(AVATAR_DIR, os.path.basename(user.avatar_url))
        if os.path.exists(old_path):
            os.remove(old_path)
    user.avatar_url = url
    db.commit()
    return url
