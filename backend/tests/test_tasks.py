"""tasks 模块测试（阶段 16：AI 编辑任务异步化 + 状态持久化）

覆盖：
- 提交即返回 task_id（不等待模型）
- 状态轮询 / 取结果 / 取消（含 404 权限隔离、409 未完成）
- 后台执行状态机（成功 / 失败 / 取消）
- 并发限流（上游同时在跑数 ≤ AI_TASK_CONCURRENCY）
- 启动僵尸任务回收

约定：后台协程按设计自建会话，测试通过 task_service.session_factory 注入隔离 session；
执行改为用例内显式驱动（schedule 被替换为记录器），避免 TestClient 每个请求新建事件循环
导致后台协程被销毁带来的不确定性。
"""

import asyncio
import base64
import json
import os
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from src.models.ai_task import (
    TASK_CANCELLED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_PENDING,
    TASK_PROCESSING,
    AITask,
)
from src.models.user import User
from src.services import image_service, task_service


# ── 辅助 ──
def _png_data_url() -> str:
    """生成一张 PNG 的 base64 data URL"""
    buf = BytesIO()
    PILImage.new("RGB", (8, 8), (0, 255, 0)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _body(prompt: str = "换成星空") -> dict:
    return {"prompt": prompt, "image_base64": _png_data_url(), "color_name": "红色"}


async def _fake_edit_ok(prompt: str, image_base64: str, color_name: str = "红色") -> str:
    """假的上游调用：直接返回结果图"""
    return _png_data_url()


async def _fake_edit_slow(prompt: str, image_base64: str, color_name: str = "红色") -> str:
    """假的上游调用：慢到足以被取消"""
    await asyncio.sleep(5)
    return _png_data_url()


async def _fake_edit_fail(prompt: str, image_base64: str, color_name: str = "红色") -> str:
    """假的上游调用：直接失败"""
    raise HTTPException(status_code=502, detail="上游模型不可用")


def _make_task(
    db: Session,
    user_id: int,
    status_: str = TASK_PENDING,
    payload: str | None = None,
) -> AITask:
    task = AITask(
        user_id=user_id,
        task_type="ai_edit",
        status=status_,
        progress=0,
        message="任务已提交",
        payload=payload,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _reload(db: Session, task_id: int) -> AITask:
    """后台协程 close() 过共享会话后重新读（同一事务内可见自身写入）"""
    task = db.get(AITask, task_id)
    assert task is not None
    return task


def _drive(task_id: int) -> None:
    """同步驱动后台协程跑完（等价于生产环境的后台执行）"""
    asyncio.run(task_service.run_ai_edit_task(task_id))


# ── fixtures ──
@pytest.fixture(autouse=True)
def task_dirs(tmp_path, monkeypatch):
    """落盘目录改到临时目录 + 重置事件循环相关模块状态，避免用例间互相影响"""
    out = tmp_path / "ai_tasks"
    monkeypatch.setattr(task_service, "TASK_UPLOAD_DIR", str(out))
    monkeypatch.setattr(task_service, "_semaphore", None)
    monkeypatch.setattr(task_service, "_semaphore_loop", None)
    monkeypatch.setattr(task_service, "_running_tasks", {})
    return out


@pytest.fixture
def isolated_task_session(db_session, monkeypatch):
    """让后台协程复用测试隔离会话（savepoint 事务，用例结束整体回滚）"""
    monkeypatch.setattr(task_service, "session_factory", lambda: db_session)
    return db_session


@pytest.fixture
def scheduled(monkeypatch) -> list[int]:
    """拦截后台调度，记录被调度的 task_id（执行由用例显式驱动）"""
    ids: list[int] = []
    monkeypatch.setattr(task_service, "schedule_ai_edit_task", ids.append)
    return ids


@pytest.fixture
def bob_headers(client):
    """第二个用户 bob 的登录态（用于任务/图片所有权隔离测试）"""
    client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@test.com", "password": "pass1234"},
    )
    r = client.post("/api/auth/login", data={"username": "bob", "password": "pass1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestSubmit:
    def test_returns_task_id_without_calling_model(
        self, client, auth_headers, test_image, isolated_task_session, scheduled, monkeypatch
    ):
        """提交立即返回 task_id + pending，且不在提交阶段调用模型"""

        async def _boom(prompt, image_base64, color_name="红色"):
            raise AssertionError("提交阶段不应调用模型")

        monkeypatch.setattr(image_service, "call_image_edit", _boom)
        r = client.post(
            f"/api/images/{test_image}/ai-edit", headers=auth_headers, json=_body()
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == TASK_PENDING
        assert body["task_id"] > 0
        assert scheduled == [body["task_id"]]  # 路由确实把任务交给了后台

        task = _reload(isolated_task_session, body["task_id"])
        assert task.status == TASK_PENDING
        # 提示图已落盘（base64 不落库，避免撑大表）
        assert os.path.exists(json.loads(task.payload)["input_path"])

    def test_unknown_image_404(self, client, auth_headers, isolated_task_session, scheduled):
        """AI 编辑不存在的图片 → 404，且不创建任务"""
        r = client.post("/api/images/9999/ai-edit", headers=auth_headers, json=_body())
        assert r.status_code == 404
        assert scheduled == []

    def test_other_users_image_404(
        self, client, bob_headers, test_image, isolated_task_session, scheduled
    ):
        """AI 编辑他人图片 → 404"""
        r = client.post(
            f"/api/images/{test_image}/ai-edit", headers=bob_headers, json=_body()
        )
        assert r.status_code == 404
        assert scheduled == []

    def test_invalid_base64_400(
        self, client, auth_headers, test_image, isolated_task_session, scheduled
    ):
        """提示图不是合法 base64 → 400"""
        r = client.post(
            f"/api/images/{test_image}/ai-edit",
            headers=auth_headers,
            json={"prompt": "换成星空", "image_base64": "a", "color_name": "红色"},
        )
        assert r.status_code == 400


class TestStatusAndResult:
    def test_status_isolated_between_users(
        self, client, auth_headers, bob_headers, test_image, isolated_task_session, scheduled
    ):
        """查询/取结果/取消他人任务 → 404（不泄露存在性）"""
        r = client.post(
            f"/api/images/{test_image}/ai-edit", headers=auth_headers, json=_body()
        )
        task_id = r.json()["task_id"]
        assert client.get(f"/api/tasks/{task_id}", headers=bob_headers).status_code == 404
        assert (
            client.get(f"/api/tasks/{task_id}/result", headers=bob_headers).status_code == 404
        )
        assert (
            client.post(f"/api/tasks/{task_id}/cancel", headers=bob_headers).status_code == 404
        )

    def test_result_before_completion_409(
        self, client, auth_headers, test_image, isolated_task_session, scheduled
    ):
        """任务未完成时取结果 → 409"""
        r = client.post(
            f"/api/images/{test_image}/ai-edit", headers=auth_headers, json=_body()
        )
        task_id = r.json()["task_id"]
        assert (
            client.get(f"/api/tasks/{task_id}/result", headers=auth_headers).status_code == 409
        )


class TestLifecycle:
    def test_success_flow(
        self, client, auth_headers, test_image, isolated_task_session, scheduled, monkeypatch
    ):
        """提交 → 后台执行 → 轮询 completed → 取结果（提示图清理、结果图落盘）"""
        monkeypatch.setattr(image_service, "call_image_edit", _fake_edit_ok)
        r = client.post(
            f"/api/images/{test_image}/ai-edit", headers=auth_headers, json=_body()
        )
        task_id = r.json()["task_id"]
        input_path = json.loads(_reload(isolated_task_session, task_id).payload)["input_path"]
        assert os.path.exists(input_path)

        _drive(task_id)

        status = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()
        assert status["status"] == TASK_COMPLETED
        assert status["progress"] == 100
        assert "image_base64" not in status  # 轮询响应保持轻量

        result = client.get(f"/api/tasks/{task_id}/result", headers=auth_headers)
        assert result.status_code == 200
        assert result.json()["image_base64"] == _png_data_url()

        done = _reload(isolated_task_session, task_id)
        assert done.result_path is not None and os.path.exists(done.result_path)
        assert not os.path.exists(input_path)  # 提示图终态后清理

    def test_model_failure_marks_failed(
        self, client, auth_headers, test_image, isolated_task_session, scheduled, monkeypatch
    ):
        """上游失败 → 任务 failed + error 落库，取结果 409"""
        monkeypatch.setattr(image_service, "call_image_edit", _fake_edit_fail)
        r = client.post(
            f"/api/images/{test_image}/ai-edit", headers=auth_headers, json=_body()
        )
        task_id = r.json()["task_id"]

        _drive(task_id)

        status = client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()
        assert status["status"] == TASK_FAILED
        assert "上游模型不可用" in status["error"]
        assert (
            client.get(f"/api/tasks/{task_id}/result", headers=auth_headers).status_code == 409
        )

    def test_cancel_queued_task_never_runs(
        self, client, auth_headers, test_image, isolated_task_session, scheduled, monkeypatch
    ):
        """排队中的任务被取消后，即使补跑也不会调用模型"""
        calls: list[int] = []

        async def _spy(prompt, image_base64, color_name="红色"):
            calls.append(1)
            return _png_data_url()

        monkeypatch.setattr(image_service, "call_image_edit", _spy)
        r = client.post(
            f"/api/images/{test_image}/ai-edit", headers=auth_headers, json=_body()
        )
        task_id = r.json()["task_id"]

        cancel = client.post(f"/api/tasks/{task_id}/cancel", headers=auth_headers)
        assert cancel.status_code == 200
        assert cancel.json()["status"] == TASK_CANCELLED

        _drive(task_id)  # 补跑：应立即返回
        assert calls == []
        assert (
            client.get(f"/api/tasks/{task_id}", headers=auth_headers).json()["status"]
            == TASK_CANCELLED
        )

    def test_cancel_finished_task_is_idempotent(
        self, client, auth_headers, test_image, isolated_task_session, scheduled, monkeypatch
    ):
        """已完成任务再取消 → 原状态返回（不倒退）"""
        monkeypatch.setattr(image_service, "call_image_edit", _fake_edit_ok)
        r = client.post(
            f"/api/images/{test_image}/ai-edit", headers=auth_headers, json=_body()
        )
        task_id = r.json()["task_id"]
        _drive(task_id)

        cancel = client.post(f"/api/tasks/{task_id}/cancel", headers=auth_headers)
        assert cancel.status_code == 200
        assert cancel.json()["status"] == TASK_COMPLETED

    def test_cancel_interrupts_running_task(
        self, db_session, registered_user, isolated_task_session, task_dirs, monkeypatch
    ):
        """运行中的任务被取消 → 中断后台协程，状态保持 cancelled"""
        monkeypatch.setattr(image_service, "call_image_edit", _fake_edit_slow)
        task_dirs.mkdir(parents=True, exist_ok=True)
        input_path = task_dirs / "input_manual.png"
        input_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        task = _make_task(
            db_session,
            registered_user["id"],
            payload=json.dumps({"prompt": "换成星空", "input_path": str(input_path)}),
        )
        operator = User(id=registered_user["id"])

        async def _scenario() -> None:
            background = task_service.schedule_ai_edit_task(task.id)
            await asyncio.sleep(0.05)  # 等协程进入上游调用
            assert not background.done()
            task_service.cancel_task(db_session, task.id, operator)
            with pytest.raises(asyncio.CancelledError):
                await background

        asyncio.run(_scenario())

        assert _reload(db_session, task.id).status == TASK_CANCELLED
        assert not input_path.exists()


class TestConcurrency:
    def test_upstream_concurrency_capped(self, tmp_path, monkeypatch):
        """并发限流：10 个任务同时执行，上游同时在跑数 ≤ AI_TASK_CONCURRENCY"""
        monkeypatch.setattr(task_service, "AI_TASK_CONCURRENCY", 2)
        active = 0
        peak = 0

        async def _fake(prompt, image_base64, color_name="红色"):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1
            return _png_data_url()

        monkeypatch.setattr(image_service, "call_image_edit", _fake)

        async def _scenario() -> None:
            backgrounds = []
            for i in range(10):
                source = tmp_path / f"in_{i}.png"
                source.write_bytes(b"png")
                # 只验限流：用桩会话喂后台协程，不碰 DB
                stub = MagicMock()
                stub.get.return_value = SimpleNamespace(
                    id=i,
                    status=TASK_PENDING,
                    progress=0,
                    message="",
                    error=None,
                    started_at=None,
                    finished_at=None,
                    result_path=None,
                    payload=json.dumps({"prompt": "换成星空", "input_path": str(source)}),
                )
                monkeypatch.setattr(task_service, "session_factory", lambda s=stub: s)
                backgrounds.append(task_service.schedule_ai_edit_task(i))
            await asyncio.gather(*backgrounds)

        asyncio.run(_scenario())
        assert peak == 2


class TestRecovery:
    def test_recover_stuck_tasks(
        self, db_session, registered_user, isolated_task_session, task_dirs
    ):
        """启动回收：pending/processing 置为 failed，completed 不受影响"""
        uid = registered_user["id"]
        pending = _make_task(db_session, uid, TASK_PENDING)
        processing = _make_task(db_session, uid, TASK_PROCESSING)
        done = _make_task(db_session, uid, TASK_COMPLETED)
        ids = (pending.id, processing.id, done.id)

        assert task_service.recover_stuck_tasks() == 2

        assert _reload(db_session, ids[0]).status == TASK_FAILED
        assert _reload(db_session, ids[1]).status == TASK_FAILED
        assert _reload(db_session, ids[2]).status == TASK_COMPLETED
