"""
主应用入口
"""

import os
import mimetypes
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

import logging
import time
from contextlib import asynccontextmanager

from src.database import engine, Base
from src.routers import auth, users, images, agent, public_images
from src.logger import setup_logging, stop_logging

# ① 初始化日志（必须在创建 app 之前，让后续启动过程也有日志）
setup_logging()
logger = logging.getLogger(__name__)

# 注册 .webp 的 MIME 类型（Windows 上默认不识别）
mimetypes.add_type("image/webp", ".webp")

# 创建所有 ORM 表（学习阶段用，生产环境应使用 Alembic 迁移）
Base.metadata.create_all(bind=engine)

# ② lifespan：app 启动/关闭钩子，关闭时排空日志队列
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动")
    yield
    logger.info("应用关闭，排空日志队列")
    stop_logging()

# 创建 FastAPI 应用（绑定 lifespan，让启动/关闭钩子生效）
app = FastAPI(title="猫里奥云图库", version="1.0.0", lifespan=lifespan)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ③ 请求日志 + 静态资源禁缓存（合并到一个中间件，减少嵌套层）
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """
    - 记录每个 API 请求的 method/path/status/耗时（静态文件不打日志，避免噪音）
    - /static/uploads 路径禁用缓存（图片覆盖后 URL 不变，避免主页显示旧图）
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    if request.url.path.startswith("/static/uploads"):
        response.headers["Cache-Control"] = "no-cache"

    if not request.url.path.startswith("/static"):
        logger.info(
            "%s %s -> %d  %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response


# 静态文件服务(提供图片访问)
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# ── 生产模式：托管前端构建产物 ──
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
frontend_assets = os.path.join(frontend_dist, "assets")
if os.path.isdir(frontend_assets):
    app.mount("/assets", StaticFiles(directory=frontend_assets), name="frontend_assets")
    background_removal_dir = os.path.join(frontend_dist, "background-removal")
    if os.path.isdir(background_removal_dir):
        app.mount("/background-removal", StaticFiles(directory=background_removal_dir), name="background_removal")

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(images.router)
app.include_router(agent.router)
app.include_router(public_images.router)

# ④ 全局异常处理器：兜底所有非 HTTPException 的未捕获异常
# - HTTPException（401/403/404 等）走 FastAPI 默认 handler，不进这里
# - 其他 Exception（ValueError/NoneError/数据库异常等）进这里
# - logger.exception() 记完整 traceback 到 error.log，不向客户端泄露内部细节
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "未捕获异常 %s %s -> 500",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code = 500,
        content = {"detail": "服务器内部错误"}
    )

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "maoliao is running"}

# SPA 回退：必须在所有 API 路由之后注册，否则会拦截 API 请求
if os.path.isdir(frontend_assets):
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not Found"}, status_code=404)
