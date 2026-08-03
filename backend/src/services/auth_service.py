
"""
注册和登录的业务逻辑：
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.models.user import User
from src.schemas.user import UserCreate
from src.utils.security import hash_password, verify_password, create_access_token

from src.cache import cache_get, cache_set, cache_delete

USER_INFO_TTL = 600 # 用户信息缓存10分钟

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
        hashed_password = hash_password(user_data.password) 
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