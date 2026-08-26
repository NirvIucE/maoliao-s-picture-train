"""
日志模块 —— 异步日志 + 多目标输出 + 按大小滚动

架构：QueueHandler（业务线程 enqueue）→ QueueListener（监听线程）
      → 真正的 handler（控制台 / app.log / error.log）

- 业务线程不阻塞，文件 IO 与轮转在监听线程
- 进程退出时 atexit + lifespan 排空队列，避免日志丢失
- 配置全部从 .env 读取，文件大小 / 份数 / 级别 / 格式均可调
"""

import atexit
import logging
import logging.handlers
import os
import queue

from dotenv import load_dotenv

load_dotenv()

# ── 从 .env 读取配置 ──
LOG_LEVEL_CONSOLE = os.getenv("LOG_LEVEL_CONSOLE", "INFO").upper()
LOG_LEVEL_FILE = os.getenv("LOG_LEVEL_FILE", "DEBUG").upper()
LOG_LEVEL_ERROR_FILE = os.getenv("LOG_LEVEL_ERROR_FILE", "WARNING").upper()
LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))
LOG_ERROR_MAX_BYTES = int(os.getenv("LOG_ERROR_MAX_BYTES", str(5 * 1024 * 1024)))
LOG_ERROR_BACKUP_COUNT = int(os.getenv("LOG_ERROR_BACKUP_COUNT", "5"))
# 项目根目录（logger.py 在 backend/src/logger.py，上三级即项目根）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOG_DIR_ENV = os.getenv("LOG_DIR", "logs")
# 相对路径基于项目根解析，避免依赖启动 cwd 导致路径错位
LOG_DIR = _LOG_DIR_ENV if os.path.isabs(_LOG_DIR_ENV) else os.path.join(_PROJECT_ROOT, _LOG_DIR_ENV)

# 详细格式：时间 + 进程ID + 级别 + 模块 + 行号 + 消息
LOG_FORMAT = os.getenv(
    "LOG_FORMAT",
    "[%(asctime)s] [%(process)d] [%(levelname)s] [%(name)s] [%(lineno)d] [%(message)s]",
)
LOG_DATE_FORMAT = os.getenv("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S")

# 全局监听器引用，供 shutdown 调用 stop()
_listener: logging.handlers.QueueListener | None = None

def setup_logging() -> None:
    """
    初始化全局日志：QueueHandler + QueueListener + 三个 handler。

    调用时机：app 启动最开始（在创建 FastAPI app 之前）。
    """
    global _listener

    # 避免重复初始化（uvicorn --reload 可能多次导入）
    if _listener is not None:
        return

    os.makedirs(LOG_DIR, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # ── 三个真正的 handler（由 QueueListener 调用） ──
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL_CONSOLE)
    console_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "app.log"),
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )

    file_handler.setLevel(LOG_LEVEL_FILE)
    file_handler.setFormatter(formatter)

    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "error.log"),
        maxBytes=LOG_ERROR_MAX_BYTES,
        backupCount=LOG_ERROR_BACKUP_COUNT,
        encoding="utf-8",
    )

    error_handler.setLevel(LOG_LEVEL_ERROR_FILE)
    error_handler.setFormatter(formatter)

    handlers = [console_handler, file_handler, error_handler]

    # ── 异步：Queue + QueueListener ──
    log_queue: queue.Queue = queue.Queue()
    _listener = logging.handlers.QueueListener(
        log_queue,
        *handlers,
        respect_handler_level=True,  # 尊重各 handler 的 level，DEBUG 不会进 error.log
    )
    _listener.start()

    # 业务 logger 用 QueueHandler（enqueue，不阻塞）
    queue_handler = logging.handlers.QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)

    # 配置 root logger：所有模块的 getLogger() 都走这里
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # root 放最宽，由各 handler 的 level 过滤
    root_logger.handlers.clear()           # 清掉 uvicorn/默认加的 handler，避免重复输出
    root_logger.addHandler(queue_handler)

    # 进程退出时排空队列，避免日志丢失
    atexit.register(stop_logging)

    root_logger.info("日志模块初始化完成（异步，输出到控制台 + %s）", LOG_DIR)

def stop_logging() -> None:
    """停止监听线程并排空队列（进程退出 / app shutdown 调用）"""
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None
