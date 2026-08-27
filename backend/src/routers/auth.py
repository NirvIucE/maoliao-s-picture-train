"""
注册和登录接口
"""
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.user import TokenResponse, UserCreate, UserResponse
from src.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    return await auth_service.register_user(db, user_data)


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """用户登录（OAuth2 密码模式，支持 Swagger Authorize 按钮和前端表单提交）"""
    return await auth_service.authenticate_user(db, form_data.username, form_data.password)
