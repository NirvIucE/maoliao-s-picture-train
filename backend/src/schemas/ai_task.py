"""
AI 任务 三套 Pydantic Schema（阶段 16）

提交 → 轮询状态（轻量，不含图片）→ 完成后单独取结果
"""
from pydantic import BaseModel


class AITaskSubmitResponse(BaseModel):
    """提交任务响应（立即返回，不等待执行）"""
    task_id: int
    status: str


class AITaskStatusResponse(BaseModel):
    """任务状态响应（轮询用，不含图片，保证轮询轻量）"""
    task_id: int
    status: str
    progress: int
    message: str | None = None
    error: str | None = None


class AITaskResultResponse(BaseModel):
    """任务结果响应（仅 completed 可取）"""
    task_id: int
    status: str
    image_base64: str
