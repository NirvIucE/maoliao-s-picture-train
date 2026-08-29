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


# ── 便利 fixtures：减少接口测试样板代码（见计划 3.3 步骤 3）──
from io import BytesIO  # noqa: E402

from PIL import Image as PILImage  # noqa: E402


@pytest.fixture
def registered_user(client):
    """注册一个普通用户 alice，返回 {username, email, password, uid, id}"""
    payload = {"username": "alice", "email": "alice@test.com", "password": "pass1234"}
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, f"注册失败: {r.text}"
    data = r.json()
    return {
        "username": payload["username"],
        "email": payload["email"],
        "password": payload["password"],
        "uid": data["uid"],
        "id": data["id"],
    }


@pytest.fixture
def auth_headers(client, registered_user):
    """登录 registered_user，返回 Authorization headers"""
    r = client.post(
        "/api/auth/login",
        data={
            "username": registered_user["username"],
            "password": registered_user["password"],
        },
    )
    assert r.status_code == 200, f"登录失败: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_user(client, db_session):
    """注册并提权一个 admin，返回 {username, password, uid, id}"""
    payload = {"username": "admin", "email": "admin@test.com", "password": "admin1234"}
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, f"admin 注册失败: {r.text}"
    # 提权（get_cached_user 即使命中也会重查 DB，role 永远最新，无缓存陈旧）
    from src.models.user import User

    admin = db_session.query(User).filter_by(username="admin").first()
    assert admin is not None
    admin.role = "admin"
    db_session.commit()
    data = r.json()
    return {
        "username": payload["username"],
        "password": payload["password"],
        "uid": data["uid"],
        "id": data["id"],
    }


@pytest.fixture
def admin_headers(client, admin_user):
    """登录 admin，返回 Authorization headers"""
    r = client.post(
        "/api/auth/login",
        data={
            "username": admin_user["username"],
            "password": admin_user["password"],
        },
    )
    assert r.status_code == 200, f"admin 登录失败: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def test_image(client, auth_headers):
    """上传一张 PNG，返回 image_id"""
    buf = BytesIO()
    PILImage.new("RGB", (10, 10), (255, 0, 0)).save(buf, format="PNG")
    buf.seek(0)
    r = client.post(
        "/api/images/upload",
        headers=auth_headers,
        files={"file": ("test.png", buf, "image/png")},
        data={"custom_name": "fixture 图"},
    )
    assert r.status_code == 200, f"上传失败: {r.text}"
    return r.json()["id"]


@pytest.fixture
def mock_models(monkeypatch):
    """注入 mock 模型注册表 + 厂商配置（避免依赖 .env 的 AI_MODELS）"""
    fake_registry = [
        {"id": "text-model", "name": "文本模型", "type": "text", "provider": "deepseek"},
        {"id": "vision-model", "name": "视觉模型", "type": "vision", "provider": "siliconflow"},
    ]
    fake_providers = {
        "deepseek": {"api_key": "fake-key", "base_url": "https://api.deepseek.com/v1"},
        "siliconflow": {"api_key": "fake-key", "base_url": "https://api.siliconflow.cn/v1"},
    }
    from src.routers import agent as agent_router
    from src.services import agent_service, public_service

    monkeypatch.setattr(agent_router, "MODEL_REGISTRY", fake_registry)
    monkeypatch.setattr(agent_service, "MODEL_REGISTRY", fake_registry)
    monkeypatch.setattr(agent_service, "PROVIDER_CONFIG", fake_providers)
    # ai_search 从 public_service 命名空间读 MODEL_REGISTRY
    monkeypatch.setattr(public_service, "MODEL_REGISTRY", fake_registry)
    return fake_registry
