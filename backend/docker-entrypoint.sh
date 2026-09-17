#!/bin/sh
# 容器启动流程（阶段 23）
#
#   1. 等待 MySQL 可连接（compose 的 service_healthy 已兜底，这里再防一层，
#      让镜像在非 compose 环境直连时也不会抢跑）
#   2. 建库（若不存在）并执行 Alembic 迁移 —— schema 一律由迁移管理，应用不建表
#   3. 启动 uvicorn，监听 0.0.0.0（否则容器外访问不到）
set -e

echo "[entrypoint] 等待 MySQL 就绪..."
python - <<'PY'
import os
import sys
import time

import pymysql

host = os.getenv("DB_HOST", "localhost")
port = int(os.getenv("DB_PORT", "3306"))
user = os.getenv("DB_USER", "root")
password = os.getenv("DB_PASSWORD", "")
database = os.getenv("DB_NAME", "cat_pic")

last_error: Exception | None = None
for attempt in range(1, 61):
    try:
        # 先不指定库连，确认服务端已接受连接
        conn = pymysql.connect(host=host, port=port, user=user, password=password)
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        conn.close()
        print(f"[entrypoint] MySQL 就绪（{host}:{port}/{database}）")
        sys.exit(0)
    except Exception as exc:  # 启动期任何异常都视为"未就绪"，继续重试
        last_error = exc
        print(f"[entrypoint] MySQL 未就绪（{attempt}/60）：{exc}")
        time.sleep(2)

print(f"[entrypoint] 等待 MySQL 超时，放弃启动：{last_error}")
sys.exit(1)
PY

echo "[entrypoint] 执行数据库迁移（alembic upgrade head）..."
alembic upgrade head

echo "[entrypoint] 启动服务..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
