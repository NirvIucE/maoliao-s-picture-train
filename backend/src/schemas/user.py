"""
三套 Pydantic Schema
Pydantic Schema 负责校验和序列化, 时刻分清楚每个场景该用哪个 Schema
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

# EmailStr 来自 pydantic[email-validator] ，会自动校验邮箱格式。
# 如果前端传了 "not-an-email" ，FastAPI 会直接返回 422 验证错误。 
# model_config = {"from_attributes": True} 是 Pydantic v2 的写法，
# 之前的 class Config: orm_mode = True 已经废弃。

class UserCreate(BaseModel):
    """注册请求"""
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    """登录请求"""
    username: str
    password: str

class UserResponse(BaseModel):
    """返回给前端的用户信息(不包含密码)"""
    id : int
    username : str
    email : str
    role : str
    uid : str
    avatar_url : Optional[str] = None
    created_at : datetime
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """登陆成功返回的token"""
    access_token: str
    token_type: str = "bearer"


class UpdateUsernameRequest(BaseModel):
    """修改用户名请求"""
    username: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str
