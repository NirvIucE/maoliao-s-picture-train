"""
测试脚手架：测试库注入 + 事务隔离 + fakeredis + get_db override（见计划 3.3 节）

机制：
1. 导入 src 前设 DB_NAME=cat_pic_test，让 config 生成测试库 URL
2. 自动 CREATE DATABASE cat_pic_test
3. echo=False 测试引擎 + savepoint 事务隔离（每测回滚，零残留）
4. fakeredis 注入 cache 模块（零 Docker 依赖）
5. override get_db 返回隔离 session
6. 测试 app factory：只注册 routers，跳过 main.py 的日志/静态/SPA/全局异常副作用
"""

import os

import fakeredis.aioredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# ── ① 环境注入：必须在 import src.* 之前 ──
os.environ["DB_NAME"] = "cat_pic_test"
from src.config import DB_HOST, DB_PASSWORD, DB_PORT, DB_USER  # noqa: E402

# ── ② 自动建测试库（连服务器，不指定 db）──
_SERVER_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
_admin_engine = create_engine(_SERVER_URL, echo=False)
with _admin_engine.connect() as _conn:
    _conn.execute(text("CREATE DATABASE IF NOT EXISTS cat_pic_test CHARACTER SET utf8mb4"))
    _conn.commit()
_admin_engine.dispose()

# ── ③ 测试引擎（echo=False 避免 SQL 刷屏）──
TEST_DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/cat_pic_test?charset=utf8mb4"
)
test_engine = create_engine(TEST_DATABASE_URL, echo=False)

# ── ④ 建表：先 import routers 触发模型注册，再 create_all（幂等）──
from src.database import Base, get_db  # noqa: E402
from src.routers import agent, auth, images, public_images, users  # noqa: E402,F401

Base.metadata.create_all(test_engine)

# ── ⑤ 测试 app factory（不导入 src.main，避免日志线程/静态/SPA/全局异常副作用）──
app = FastAPI()
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(images.router)
app.include_router(agent.router)
app.include_router(public_images.router)

@app.get("/health")
def health():
    return {"status": "ok", "message": "maoliao is running"}

# ── ⑥ fixtures ──
import src.cache as cache  # noqa: E402


@pytest.fixture
def fake_redis():
    """注入 fakeredis，避免连真实 Redis；每测结束重置保证隔离"""
    cache._redis_pool = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache._redis_available = True
    yield
    cache._redis_pool = None
    cache._redis_available = None
    cache._last_ping_time = 0


@pytest.fixture
def db_session():
    """savepoint 事务隔离：app 的 commit 变成 savepoint 释放，测试结束整体回滚"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield session
    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session, fake_redis):
    """TestClient，已注入隔离 session + fakeredis"""
    yield TestClient(app)