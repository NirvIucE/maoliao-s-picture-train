# 猫里奥全栈云图库

一个基于 FastAPI + Vue3 的全栈云图库 Web 项目，支持图片上传与管理、AI 图片分析与编辑、公共图库与管理员审核等能力。

## 功能特性

- **用户系统**：注册、登录、JWT 鉴权、角色（普通用户/管理员）、专属 UID（UUID）、头像、个人资料编辑（改名/改密/头像）
- **图片上传与管理**：本地文件上传、URL 上传、自动 WebP 压缩与缩略图、图片列表/详情/删除/改名
- **AI 能力**：图片视觉分析、AI 对话助手、AI 图片编辑（涂鸦、抠图、旋转/翻转/裁剪、区域编辑）
- **公共图库**：提交/审核/下架/撤回、可见性控制、删除原图级联删除公共记录
- **缓存优化**：Redis 缓存用户信息与热点数据

## 技术栈

**后端**：Python · FastAPI · Uvicorn · SQLAlchemy · Alembic · MySQL · Redis

**前端**：Vue3 · TypeScript · Vite · Pinia · Vue Router · Axios

## 项目结构

```
.
├── backend/                 # FastAPI 后端
│   ├── alembic/             # 数据库迁移（Alembic）
│   ├── scripts/             # 辅助脚本（promote_admin 等）
│   └── src/
│       ├── models/          # SQLAlchemy ORM 模型
│       ├── routers/         # API 路由
│       ├── schemas/         # Pydantic 请求/响应模型
│       ├── services/        # 业务逻辑
│       ├── utils/           # 工具（安全、图片处理）
│       ├── config.py        # 从 .env 读取配置
│       ├── database.py      # 数据库引擎与会话
│       └── main.py          # 应用入口
└── frontend/                # Vue3 前端
    └── src/
        ├── api/             # Axios 封装与接口
        ├── components/      # 通用组件
        ├── router/          # 路由
        ├── stores/          # Pinia 状态管理
        └── views/           # 页面
```

## 快速开始

### 环境要求

- Python 3.x + [uv](https://docs.astral.sh/uv/)
- Node.js 22+
- MySQL 8.0
- Redis 7.0+

### 1. 配置环境变量

在 `backend/` 目录下创建 `.env` 文件，参考以下内容：

```env
# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的数据库密码
DB_NAME=cat_pic

# JWT（必填，请改成随机长字符串）
JWT_SECRET_KEY=请改成随机长字符串
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# AI（可选，按需填写）
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
AI_MODELS=
```

> `AI_MODELS` 格式：`id|名称|类型|provider`，多个模型用英文逗号分隔。

### 2. 启动 Redis

使用 Docker 启动 Redis 容器（容器名为 `redis`）：

```powershell
docker run -d --name redis -p 6379:6379 redis:7
```

### 3. 安装后端依赖并执行数据库迁移

```powershell
cd backend
uv sync
uv run alembic upgrade head
```

> 数据库迁移用于增量更新表结构，不会丢失已有数据。

### 4. 启动后端

```powershell
cd backend
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

后端运行在 `http://localhost:8000`，接口文档见 `http://localhost:8000/docs`。

### 5. 启动前端（开发模式）

```powershell
cd frontend
npm install
npm run dev
```

前端开发服务器运行在 `http://localhost:5173`。

### 6. 生产模式（单端口托管）

构建前端后，后端会自动托管 `frontend/dist`，只需运行后端即可：

```powershell
cd frontend
npm run build

cd ../backend
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### 7. 设置管理员

```powershell
cd backend
uv run python scripts/promote_admin.py <用户名>
```

## 数据库迁移

本项目使用 Alembic 管理数据库结构变更：

- 已有数据库首次引入迁移：使用空基线 + `alembic stamp head` 标记现有库。
- 后续增量变更：`uv run alembic revision --autogenerate -m "说明"` 生成迁移，再 `uv run alembic upgrade head` 应用。
