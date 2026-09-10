"""
AI 任务路由
(/api/tasks/*)
查询状态（轮询）/ 取结果 / 取消
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.ai_task import TASK_COMPLETED
from src.models.user import User
from src.routers.users import get_current_user
from src.schemas.ai_task import AITaskResultResponse, AITaskStatusResponse
from src.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["AI 任务"])


@router.get("/{task_id}", response_model=AITaskStatusResponse)
def get_task_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询任务状态（轮询用，不含图片，保证轮询轻量）"""
    task = task_service.get_task(db, task_id, current_user)
    return AITaskStatusResponse(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        message=task.message,
        error=task.error,
    )


@router.get("/{task_id}/result", response_model=AITaskResultResponse)
def get_task_result(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取任务结果图（仅 completed 可取），返回结果图 base64 data URL"""
    image_base64 = task_service.get_task_result(db, task_id, current_user)
    return AITaskResultResponse(
        task_id=task_id,
        status=TASK_COMPLETED,
        image_base64=image_base64,
    )


@router.post("/{task_id}/cancel", response_model=AITaskStatusResponse)
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消任务（幂等：已完成/已失败/已取消的任务原样返回）"""
    task = task_service.cancel_task(db, task_id, current_user)
    return AITaskStatusResponse(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        message=task.message,
        error=task.error,
    )
