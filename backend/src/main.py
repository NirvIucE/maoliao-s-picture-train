"""
主应用入口
"""

import os
import mimetypes
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.database import engine, Base
from src.routers import auth, users, images, agent, public_images


# 注册 .webp 的 MIME 类型（Windows 上默认不识别）
mimetypes.add_type("image/webp", ".webp")

# 创建所有 ORM 表（学习阶段用，生产环境应使用 Alembic 迁移）
Base.metadata.create_all(bind=engine)

app = FastAPI(title = "猫里奥云图库", version = "1.0.0")

#CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_for_images(request: Request, call_next):
    response = await call_next(request)
    # 图片覆盖后会变但 URL 不变，禁用缓存避免主页显示旧图
    if request.url.path.startswith("/static/uploads"):
        response.headers["Cache-Control"] = "no-cache"
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
        app.mount("/background-removal", 
        StaticFiles(directory=background_removal_dir), 
        name="background_removal")

#注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(images.router)
app.include_router(agent.router)
app.include_router(public_images.router)

@app.get("/health")
def health_check():
    return {"status":"ok", "message":"maoliao is running"}

# SPA 回退：必须在所有 API 路由之后注册，否则会拦截 API 请求
if os.path.isdir(frontend_assets):
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not Found"}, status_code=404)
