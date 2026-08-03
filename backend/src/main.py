'''
Author: NirvIucE 1750682685@qq.com
Date: 2026-07-23 21:11:40
LastEditors: NirvIucE 1750682685@qq.com
LastEditTime: 2026-07-31 01:16:36
FilePath: \new-picture-train\backend\src\main.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''

"""
主应用入口
"""
import os
import mimetypes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.database import engine, Base
from src.routers import auth, users, images, agent


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

# 静态文件服务(提供图片访问)
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# ── 生产模式：托管前端构建产物 ──
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
frontend_assets = os.path.join(frontend_dist, "assets")
if os.path.isdir(frontend_assets):
    app.mount("/assets", StaticFiles(directory=frontend_assets), name="frontend_assets")

#注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(images.router)
app.include_router(agent.router)

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
