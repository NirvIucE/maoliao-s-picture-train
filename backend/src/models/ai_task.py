"""
AI 任务表模型（阶段 16：长任务异步化 + 状态持久化）

用 MySQL 持久化任务状态，替代参考项目（DiTing）的内存字典方案：
- 进程重启后残留任务可被回收（不会永久卡在"处理中"）
- 任务状态可查询、可追溯

状态机：pending → processing → completed / failed / cancelled

注：本模型用 SQLAlchemy 2.0 的 Mapped[] 注解（本项目 mypy 的 sqlalchemy 插件
不解析旧式 Column(...)，用 Mapped[] 才能让 task_service / routers 通过类型检查）。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base

# 任务状态常量
TASK_PENDING = "pending"
TASK_PROCESSING = "processing"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"
TASK_CANCELLED = "cancelled"

# 未结束状态（用于启动时回收僵尸任务）
TASK_ACTIVE_STATUSES = (TASK_PENDING, TASK_PROCESSING)


class AITask(Base):
    __tablename__ = "ai_tasks"
    # 复合索引：用户按时间查自己的任务；状态索引：启动回收扫描
    __table_args__ = (
        Index("ix_ai_tasks_user_created", "user_id", "created_at"),
        Index("ix_ai_tasks_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ai_edit", comment="任务类型"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TASK_PENDING,
        comment="pending/processing/completed/failed/cancelled",
    )
    progress: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="阶段式进度 0-100"
    )
    message: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="阶段文案")
    payload: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="任务参数 JSON（输入图路径/指令/标记色）"
    )
    result_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="结果图文件路径"
    )
    error: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="失败原因")
    # 时间戳与项目其它表保持一致（nullable=True，由 Python 侧 default 赋值）
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
