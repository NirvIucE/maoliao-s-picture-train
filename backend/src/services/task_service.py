"""
AI 任务服务（阶段 16：长任务异步化 + 状态持久化）

对照参考项目 DiTing 的 TaskManager 做了三处改进：
1. 状态落 MySQL（DiTing 用进程内字典）→ 重启后不会残留永久"处理中"
2. 启动时 recover_stuck_tasks() 回收未结束任务（DiTing 的 processing 记录不回收）
3. 结果图/提示图落磁盘（base64 约 1-2MB，落库会撑大表且超出 TEXT 上限）

流程：提交即返回 → 后台协程执行 → 前端轮询状态 → 完成后单独取结果
    create_ai_edit_task() 建记录 + 提示图落盘，返回 task_id
    schedule_ai_edit_task() asyncio.create_task 丢后台
    run_ai_edit_task() 信号量限流 → 阶段推进 → 结果落盘 → 终态
"""

import asyncio
import base64
import binascii
import json
import logging
import os
import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.config import AI_TASK_CONCURRENCY
from src.database import SessionLocal
from src.models.ai_task import (
    TASK_ACTIVE_STATUSES,
    TASK_CANCELLED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_PENDING,
    TASK_PROCESSING,
    AITask,
)
from src.models.user import User
from src.services import image_service

logger = logging.getLogger(__name__)

# 提示图 / 结果图落盘目录（提示图在任务终态后删除，结果图保留供前端取用）
TASK_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "ai_tasks")

# 后台协程必须自建会话（请求期会话在响应返回后已关闭/被复用，不能跨请求使用）。
# 声明为模块级变量供测试注入隔离会话，避免后台写库绕过测试事务隔离。
session_factory: Callable[[], Session] = SessionLocal

# 并发信号量：同时在跑的任务上限，超出的协程在信号量上排队（排队期间不占 DB 连接）
# 按事件循环缓存：pytest 每个用例可能新建 event loop，跨 loop 复用 Semaphore 会报错
_semaphore: asyncio.Semaphore | None = None
_semaphore_loop: asyncio.AbstractEventLoop | None = None

# task_id -> 运行中的 asyncio.Task，供取消使用
_running_tasks: dict[int, "asyncio.Task[None]"] = {}


def _get_semaphore() -> asyncio.Semaphore:
    """取当前事件循环的并发信号量（跨事件循环自动重建）"""
    global _semaphore, _semaphore_loop
    loop = asyncio.get_running_loop()
    if _semaphore is None or _semaphore_loop is not loop:
        _semaphore = asyncio.Semaphore(AI_TASK_CONCURRENCY)
        _semaphore_loop = loop
    return _semaphore


def _decode_base64_image(data_url: str) -> bytes:
    """解析 base64 data URL（或裸 base64）为字节"""
    raw = data_url.split(",", 1)[1] if "," in data_url else data_url
    try:
        return base64.b64decode(raw)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="提示图 base64 解析失败") from exc


def _result_mime(path: str) -> str:
    """按扩展名推断结果图 MIME（jpg/jpeg 之外一律按 png）"""
    return "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"


def _input_path_of(task: AITask) -> str | None:
    """从 payload 中取提示图路径"""
    if not task.payload:
        return None
    try:
        value = json.loads(task.payload).get("input_path")
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, str) else None


def _remove_input_file(task: AITask) -> None:
    """删除提示图文件（任务终态后无需保留，避免磁盘孤儿）"""
    path = _input_path_of(task)
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.warning("删除提示图失败：%s", path)


def _set_progress(db: Session, task: AITask, progress: int, message: str) -> None:
    """推进阶段进度（processing 中间态）"""
    task.status = TASK_PROCESSING
    task.progress = progress
    task.message = message
    if task.started_at is None:
        task.started_at = datetime.now()
    db.commit()


def _set_finished(
    db: Session,
    task: AITask,
    task_status: str,
    message: str,
    error: str | None = None,
    result_path: str | None = None,
) -> None:
    """写终态（completed/failed）；已被取消的任务不覆盖"""
    if task.status == TASK_CANCELLED:
        return
    task.status = task_status
    task.progress = 100 if task_status == TASK_COMPLETED else task.progress
    task.message = message
    task.error = error
    if result_path is not None:
        task.result_path = result_path
    task.finished_at = datetime.now()
    db.commit()


def create_ai_edit_task(
    db: Session,
    image_id: int,
    prompt: str,
    image_base64: str,
    user: User,
    color_name: str = "红色",
) -> AITask:
    """创建 AI 编辑任务：校验图片归属 → 建记录 → 提示图落盘，立即返回（不等待执行）

    图片归属校验放在这里（提交时刻），长任务期间不再持有请求期 DB 连接。
    """
    image_service.get_image_detail(db, image_id, user)  # 非本人图片 → 404

    task = AITask(
        user_id=user.id,
        task_type="ai_edit",
        status=TASK_PENDING,
        progress=0,
        message="任务已提交",
        payload=json.dumps(
            {"image_id": image_id, "prompt": prompt, "color_name": color_name},
            ensure_ascii=False,
        ),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 提示图（原图 + 涂鸦标记）落盘：数 MB 的 base64 落库会撑大表且超出 TEXT 上限
    input_path = os.path.join(TASK_UPLOAD_DIR, f"input_{task.id}.png")
    try:
        contents = _decode_base64_image(image_base64)
        os.makedirs(TASK_UPLOAD_DIR, exist_ok=True)
        with open(input_path, "wb") as f:
            f.write(contents)
    except HTTPException as exc:
        _set_finished(db, task, TASK_FAILED, "提示图保存失败", error=str(exc.detail))
        raise
    except OSError as exc:
        _set_finished(db, task, TASK_FAILED, "提示图保存失败", error="磁盘写入失败")
        raise HTTPException(status_code=500, detail="提示图保存失败") from exc

    payload = json.loads(task.payload or "{}")
    payload["input_path"] = input_path
    task.payload = json.dumps(payload, ensure_ascii=False)
    db.commit()
    db.refresh(task)
    return task


def schedule_ai_edit_task(task_id: int) -> "asyncio.Task[None]":
    """把任务丢进后台协程执行（提交即返回，前端轮询）"""
    background = asyncio.create_task(run_ai_edit_task(task_id))
    _running_tasks[task_id] = background
    background.add_done_callback(lambda _t: _running_tasks.pop(task_id, None))
    return background


async def run_ai_edit_task(task_id: int) -> None:
    """后台执行 AI 编辑任务

    必须自建会话：请求期会话在响应返回后已关闭/被复用。
    信号量在外面：排队等待期间不占用 DB 连接。
    """
    async with _get_semaphore():
        db = session_factory()
        task = db.get(AITask, task_id)
        try:
            # 任务已被删除或已被取消：不执行（取消状态由 cancel_task 写库）
            if task is None or task.status == TASK_CANCELLED:
                return
            await _execute(db, task)
        except asyncio.CancelledError:
            # 运行中被取消：状态已由 cancel_task 写入，这里只负责清理
            logger.info("AI 任务 %d 已取消", task_id)
            raise
        finally:
            if task is not None:
                _remove_input_file(task)
            db.close()


async def _execute(db: Session, task: AITask) -> None:
    """任务主体：推进阶段 → 调模型 → 结果落盘 → 终态（task 已确保存在且未取消）"""
    try:
        payload = json.loads(task.payload or "{}")
        input_path = payload.get("input_path")
        if not input_path or not os.path.exists(input_path):
            _set_finished(db, task, TASK_FAILED, "失败", error="提示图已失效")
            return

        _set_progress(db, task, 10, "正在提交模型")
        with open(input_path, "rb") as f:
            marked = base64.b64encode(f.read()).decode("utf-8")

        _set_progress(db, task, 30, "模型生成中")
        result_data_url = await image_service.call_image_edit(
            str(payload.get("prompt", "")),
            f"data:image/png;base64,{marked}",
            str(payload.get("color_name", "红色")),
        )

        _set_progress(db, task, 80, "正在解析结果")
        contents = _decode_base64_image(result_data_url)

        _set_progress(db, task, 95, "正在保存结果")
        result_path = _write_result_image(task.id, result_data_url, contents)

        _set_finished(db, task, TASK_COMPLETED, "编辑完成", result_path=result_path)
        logger.info("AI 任务 %d 完成：%s", task.id, result_path)
    except HTTPException as exc:
        logger.warning("AI 任务 %d 失败：%s", task.id, exc.detail)
        _set_finished(db, task, TASK_FAILED, "编辑失败", error=str(exc.detail)[:500])
    except Exception as exc:
        logger.exception("AI 任务 %d 异常", task.id)
        _set_finished(db, task, TASK_FAILED, "编辑失败", error=str(exc)[:500])


def _write_result_image(task_id: int, data_url: str, contents: bytes) -> str:
    """结果图落盘并返回文件路径（URL 型结果已在 call_image_edit 内转 data URL）"""
    ext = ".jpg" if data_url.startswith("data:image/jpeg") else ".png"
    os.makedirs(TASK_UPLOAD_DIR, exist_ok=True)
    path = os.path.join(TASK_UPLOAD_DIR, f"result_{task_id}_{uuid.uuid4().hex[:8]}{ext}")
    with open(path, "wb") as f:
        f.write(contents)
    return path


def get_task(db: Session, task_id: int, user: User) -> AITask:
    """取本人任务；他人任务按 404 处理（不泄露存在性）"""
    task = db.get(AITask, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


def get_task_result(db: Session, task_id: int, user: User) -> str:
    """取任务结果图，返回 base64 data URL；任务未完成抛 409"""
    task = get_task(db, task_id, user)
    if task.status != TASK_COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"任务尚未完成：{task.status}",
        )
    if not task.result_path or not os.path.exists(task.result_path):
        raise HTTPException(status_code=404, detail="结果图已丢失")

    with open(task.result_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{_result_mime(task.result_path)};base64,{encoded}"


def cancel_task(db: Session, task_id: int, user: User) -> AITask:
    """取消任务（协作式）：终态任务直接幂等返回，运行中的中断后台协程"""
    task = get_task(db, task_id, user)
    if task.status not in TASK_ACTIVE_STATUSES:
        return task

    task.status = TASK_CANCELLED
    task.message = "已取消"
    task.finished_at = datetime.now()
    db.commit()
    db.refresh(task)

    background = _running_tasks.get(task_id)
    if background is not None and not background.done():
        background.cancel()
    return task


def recover_stuck_tasks() -> int:
    """启动时回收僵尸任务：进程重启后未结束的任务不可能再执行，统一置为失败

    DiTing 的 processing 记录不回收，前端会永久显示"处理中"；这里在 lifespan 中修正。
    """
    db = session_factory()
    try:
        stuck = db.query(AITask).filter(AITask.status.in_(TASK_ACTIVE_STATUSES)).all()
        for task in stuck:
            _remove_input_file(task)
            task.status = TASK_FAILED
            task.message = "服务重启，任务已中断"
            task.error = "服务重启，任务已中断"
            task.finished_at = datetime.now()
        if stuck:
            db.commit()
            logger.warning("回收僵尸 AI 任务 %d 个", len(stuck))
        return len(stuck)
    finally:
        db.close()
