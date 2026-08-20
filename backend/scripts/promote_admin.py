"""
管理员提升脚本
用法（在 backend 目录下执行）：
    uv run python scripts/promote_admin.py <username>
"""
import sys
from pathlib import Path

# 让脚本能找到 src 包（backend 目录加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import SessionLocal
from src.models.user import User


def promote(username: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"用户不存在：{username}")
            return
        if user.role == "admin":
            print(f"用户 {username} 已是管理员")
            return
        user.role = "admin"
        db.commit()
        print(f"已将用户 {username} 提升为管理员")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：uv run python scripts/promote_admin.py <username>")
        sys.exit(1)
    promote(sys.argv[1])
