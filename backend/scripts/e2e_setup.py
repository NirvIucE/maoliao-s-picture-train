"""
E2E 环境准备脚本（由 Playwright webServer 在启动后端前执行）

职责：
1. 清空 E2E 上传目录（阶段 18.7：否则 e2e-uploads 会跨轮累积产物）
2. 创建专用测试库（默认 cat_pic_e2e，可被 DB_NAME 环境变量覆盖）
3. 执行 alembic upgrade head 建表（顺带验证迁移链自举）
4. 幂等种子管理员账号 e2e_admin / Admin1234!

用法（backend 目录下）：
    DB_NAME=cat_pic_e2e UPLOAD_ROOT=<backend>/e2e-uploads uv run python scripts/e2e_setup.py
"""
import os
import shutil
import sys
import uuid
from pathlib import Path

# 让脚本能找到 src 包（backend 目录加入 sys.path）
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# 必须在 import src.config 之前确定库名（config 拼接 URL 时读取）
os.environ.setdefault("DB_NAME", "cat_pic_e2e")

from sqlalchemy import create_engine, text  # noqa: E402

from src.config import (  # noqa: E402
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    UPLOAD_ROOT,
)
from src.utils.security import hash_password  # noqa: E402


def reset_upload_root() -> None:
    """清空 E2E 上传目录，让每轮 E2E 都从空目录开始

    为什么需要：E2E 库每轮由 alembic 重建，但磁盘上的 e2e-uploads 只会累积
    （实测跑一轮多 10 个文件），旧产物既无用又会掩盖「新增孤儿文件」的判断。

    安全护栏（两重，防止手滑删到真实 uploads）：
    1. 必须显式设置 UPLOAD_ROOT 环境变量（真实环境不设它，直接中止）
    2. 目录名必须是 e2e-uploads
    """
    if "UPLOAD_ROOT" not in os.environ:
        raise SystemExit("[e2e_setup] 拒绝清理：未设置 UPLOAD_ROOT（防止误删真实 uploads）")
    root = Path(UPLOAD_ROOT).resolve()
    if root.name != "e2e-uploads":
        raise SystemExit(f"[e2e_setup] 拒绝清理：目录名不是 e2e-uploads（{root}）")
    if root.exists():
        shutil.rmtree(root)
        print(f"[e2e_setup] 已清空 E2E 上传目录 {root}")
    root.mkdir(parents=True, exist_ok=True)


def create_database() -> None:
    """连接 MySQL 服务器，若目标库不存在则创建"""
    server_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
    engine = create_engine(server_url)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4"))
            conn.commit()
    finally:
        engine.dispose()
    print(f"[e2e_setup] 数据库 {DB_NAME} 就绪")


def run_migrations() -> None:
    """执行 alembic upgrade head"""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    print("[e2e_setup] alembic upgrade head 完成")


def seed_admin() -> None:
    """幂等种子管理员 e2e_admin"""
    from src.database import SessionLocal
    from src.models.user import User

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "e2e_admin").first()
        if admin:
            print("[e2e_setup] 管理员 e2e_admin 已存在，跳过")
            return
        db.add(
            User(
                username="e2e_admin",
                email="e2e_admin@test.com",
                hashed_password=hash_password("Admin1234!"),
                uid=str(uuid.uuid4()),
                role="admin",
            )
        )
        db.commit()
        print("[e2e_setup] 管理员 e2e_admin 已创建")
    finally:
        db.close()


if __name__ == "__main__":
    reset_upload_root()
    create_database()
    run_migrations()
    seed_admin()
    print("[e2e_setup] 完成")
