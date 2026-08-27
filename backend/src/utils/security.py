"""
JWT 和密码工具函数
"""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=10)

def hash_password(password: str):
    """明文密码->bcrypt哈希"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    """验证明文密码是否匹配哈希密码"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    """生成 JWT token"""
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp":expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> dict | None:
    """解码JWTToken，失败返回None，成功返回payload数据"""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None

