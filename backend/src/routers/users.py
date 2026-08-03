"""
获取当前用户（需要 JWT 鉴权）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer

from src.database import get_db
from src.models.user import User
from src.schemas.user import UserResponse
from src.utils.security import decode_access_token
from src.services.auth_service import get_cached_user

router = APIRouter(prefix="/api/users", tags=["用户"])

# OAuth2 密码流：告诉 FastAPI 从请求头 Authorization: Bearer xxx 中提取 Token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 之后所有需要登录的接口，加current_user = Depends(get_current_user) 就可以鉴权
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """从JWT Token 解析当前用户(可复用的依赖)"""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        )
    user_id = int(payload.get("sub"))
    user = await get_cached_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return current_user
    