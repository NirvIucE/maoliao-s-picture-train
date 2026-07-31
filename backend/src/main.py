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

#注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(images.router)
app.include_router(agent.router)

@app.get("/health")
def health_check():
    return {"status":"ok", "message":"maoliao is running"}
