"""
主应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.database import engine, Base
from src.routers import auth, users

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

#注册路由
app.include_router(auth.router)
app.include_router(users.router)

@app.get("/health")
def health_check():
    return {"status":"ok", "message":"maoliao is running"}
