"""
获取当前用户（需要 JWT 鉴权）
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.schemas.user import ChangePasswordRequest, UpdateUsernameRequest, UserResponse
from src.services.auth_service import (
    change_password,
    get_cached_user,
    update_avatar,
    update_username,
)
from src.utils.security import decode_access_token

router = APIRouter(prefix="/api/users", tags=["用户"])

# OAuth2 密码流：告诉 FastAPI 从请求头 Authorization: Bearer xxx 中提取 Token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 可选认证：无 token 时返回 None 而非 401（用于公共图库等可选登录场景）
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# 之后所有需要登录的接口，加current_user = Depends(get_current_user) 就可以鉴权
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """从JWTToken 解析当前用户(可复用的依赖)"""
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

async def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> User | None:
    """可选认证：无 token 或 token 无效时返回 None，不报 401"""
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    user_id = int(payload.get("sub"))
    user = await get_cached_user(db, user_id)
    return user

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    req: UpdateUsernameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改用户名"""
    return update_username(db, current_user, req.username)


@router.post("/me/password")
async def change_my_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改密码"""
    change_password(db, current_user, req.old_password, req.new_password)
    return {"message": "密码已更新"}


@router.post("/me/avatar")
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传头像"""
    avatar_url = update_avatar(db, current_user, file)
    return {"avatar_url": avatar_url}
