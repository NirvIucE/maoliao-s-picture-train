# 猫里奥全栈云图库 — 学习路线与迭代计划

> **学习模式：你主导编码，我负责指导、审查、讲解。代码在对话中输出，由你判断后自行写入项目。**

---

## 目录

1. [学习目标总览](#1-学习目标总览)
2. [技术栈学习路线](#2-技术栈学习路线)
3. [项目架构设计](#3-项目架构设计)
4. [分阶段迭代计划](#4-分阶段迭代计划)
   - [阶段 0：环境搭建与工具链](#阶段-0环境搭建与工具链)
   - [阶段 1：FastAPI 入门 + 数据库 + 用户系统（JWT）](#阶段-1fastapi-入门--数据库--用户系统jwt)
   - [阶段 2：图片上传与管理](#阶段-2图片上传与管理)
   - [阶段 3：Vue3 前端搭建](#阶段-3vue3-前端搭建)
   - [阶段 4：前后端联调与 JWT 鉴权](#阶段-4前后端联调与-jwt-鉴权)
   - [阶段 5：Agent 接入 — AI 图片分析](#阶段-5agent-接入--ai-图片分析)
   - [阶段 6：Agent 接入 — AI 对话助手](#阶段-6agent-接入--ai-对话助手)
   - [阶段 7：缓存、优化与部署](#阶段-7缓存优化与部署)
5. [每个阶段的标准流程](#5-每个阶段的标准流程)
6. [关键约定](#6-关键约定)

---

## 1. 学习目标总览

| 知识领域 | 具体目标 |
|---------|---------|
| **Python 全栈基础** | 掌握 FastAPI 路由、依赖注入、中间件、异常处理、Pydantic 数据校验 |
| **数据库** | MySQL 表设计、SQLAlchemy ORM、Alembic 迁移、查询优化 |
| **认证鉴权** | JWT 原理、Access/Refresh Token、OAuth2 Password Flow |
| **Vue3 前端** | 组件化、Composition API、Vue Router、状态管理 (Pinia)、Axios 封装 |
| **Agent 接入** | 调用大模型 API、流式响应、图片多模态分析、对话管理 |
| **工程化** | Git 分支管理、uv 包管理、环境变量、Docker 运行 Redis |

---

## 2. 技术栈学习路线

在每个阶段开始前，我会先**在对话中讲解**该阶段涉及的技术概念和工具用法，然后由你动手实现。

### 需要掌握的工具链

```
uv          → Python 包管理 & 虚拟环境（替代 pip + venv）
FastAPI     → Web 框架，异步路由，自动生成 OpenAPI 文档
Uvicorn     → ASGI 服务器，运行 FastAPI
SQLAlchemy  → Python ORM，操作 MySQL
Alembic     → 数据库迁移管理（后续引入）
Pydantic    → 数据模型校验（FastAPI 内置）
python-jose → JWT 编码/解码
passlib     → 密码哈希存储（后续引入）
Redis       → 缓存（Docker 运行）
Vite        → 前端构建工具
Vue 3       → Composition API + <script setup>
Vue Router  → 前端路由
Pinia       → 状态管理
Axios       → HTTP 请求
Pillow      → 图片处理（webp 压缩、缩略图）
```

---

## 3. 项目架构设计

### 目录结构（最终形态）

> 格式说明：`目录名/： (用途注释)` 或者 `文件名： (用途注释)`，嵌套用缩进表示层级。
> 选择键值对格式而非 ASCII 树状图的原因：每个文件/目录都能附带中文注释，学习友好，维护方便。

```
new-picture-train/： (项目根目录){
   backend/： (后端项目目录){
      .venv/： (Python 虚拟环境，gitignore)
      src/： (Python 源代码目录——所有业务代码放这里){
         main.py： (FastAPI 应用入口，创建 app + 注册路由)
         config.py： (配置管理，从 .env 读取数据库/JWT 等配置)
         database.py： (数据库引擎、SessionLocal、get_db 依赖注入)
         models/： (SQLAlchemy ORM 数据模型){
            __init__.py
            user.py： (用户表模型)
            image.py： (图片表模型)
            tag.py： (标签表模型 + image_tags 多对多关联)
            conversation.py： (对话 & 消息模型，阶段6引入)
         }
         schemas/： (Pydantic 请求/响应校验模型){
            __init__.py
            user.py： (UserCreate、UserLogin、UserResponse、TokenResponse)
            image.py： (ImageResponse、ImageUploadResponse 等)
            agent.py： (ChatRequest、AnalysisResponse 等)
         }
         routers/： (API 路由——接收请求，调用 service，返回响应){
            __init__.py
            auth.py： (POST /register, POST /login, POST /logout)
            users.py： (GET /users/me)
            images.py： (CRUD /images/*)
            agent.py： (POST /agent/analyze, POST /agent/chat)
         }
         services/： (业务逻辑层——核心逻辑，被 router 调用){
            __init__.py
            auth_service.py： (注册、登录、Token 签发)
            image_service.py： (上传、压缩、查询、删除)
            agent_service.py： (调用大模型、对话管理)
         }
         utils/： (工具函数——纯函数，无副作用){
            __init__.py
            security.py： (JWT 编解码、密码哈希)
            image_utils.py： (WebP 压缩、缩略图生成)
         }
         uploads/： (用户上传的图片 & 缩略图存储，gitignore)
      }
      tests/： (后端测试代码){
         __init__.py
         test_auth.py： (认证相关测试)
         test_images.py： (图片相关测试)
      }
      sql/： (数据库建表 SQL 脚本，便于直接查看表结构){
         init.sql： (建库建表语句)
      }
      pyproject.toml： (uv 项目配置 + 依赖声明)
      .env： (环境变量：数据库密码、JWT密钥等，不提交到 Git)
      .gitignore： (忽略 .venv、.env、uploads 等)
   }
   frontend/： (前端项目目录){
      index.html： (HTML 入口)
      package.json： (Node 依赖管理)
      vite.config.ts： (Vite 构建配置 + 代理设置)
      tsconfig.json： (TypeScript 编译配置)
      src/： (前端源代码){
         main.ts： (Vue 应用入口，挂载 App)
         App.vue： (根组件，布局 + <router-view>)
         router/： (Vue Router 路由){
            index.ts： (路由表 + 导航守卫)
         }
         stores/： (Pinia 状态管理){
            auth.ts： (用户登录状态、Token)
            images.ts： (图片列表状态)
         }
         api/： (后端 API 调用封装){
            client.ts： (Axios 实例 + JWT 拦截器)
            auth.ts： (login、register、getCurrentUser)
            images.ts： (upload、list、detail、delete)
            agent.ts： (analyze、chat)
         }
         views/： (页面级组件——每个路由对应一个){
            Login.vue： (登录页)
            Register.vue： (注册页)
            Gallery.vue： (图片画廊页)
            Upload.vue： (图片上传页)
            AgentChat.vue： (AI 对话助手页)
         }
         components/： (可复用组件){
            NavBar.vue： (顶部导航栏)
            ImageCard.vue： (图片卡片)
            AgentDialog.vue： (AI 分析结果弹窗)
         }
         assets/： (静态资源：CSS、图标等)
      }
   }
   .gitignore： (项目级忽略规则)
   plan.md： (你最初写的项目计划)
   README.md： (项目说明)
}
```

### 关于 `src/` 布局的重要说明

采用 `backend/src/` 将源码与配置分离，是 Python 工程化的主流做法。需要注意：

1. **内部 import 路径变化**：
   ```python
   # 原来（无 src/）
   from models.user import User
   from utils.security import create_access_token

   # 现在（有 src/）
   from src.models.user import User
   from src.utils.security import create_access_token
   ```

2. **启动命令需指向 `src/main.py`**：
   ```bash
   # 在 backend/ 目录下执行
   uvicorn src.main:app --reload
   ```

3. **`pyproject.toml` 配置**：uv init 生成的配置无需大改，FastAPI 会自动处理路径。

### 数据库 ER 图（核心表）

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│   users     │       │     images       │       │    tags     │
├─────────────┤       ├──────────────────┤       ├─────────────┤
│ id (PK)     │──1:N──│ id (PK)          │       │ id (PK)     │
│ username    │       │ user_id (FK)     │──N:M──│ name        │
│ email       │       │ filename         │       └─────────────┘
│ password    │       │ original_name    │              │
│ created_at  │       │ file_path        │       ┌──────┴──────┐
│ updated_at  │       │ thumbnail_path   │       │ image_tags  │
└─────────────┘       │ file_size        │       ├─────────────┤
                      │ mime_type        │       │ image_id(FK)│
                      │ width            │       │ tag_id (FK) │
                      │ height           │       └─────────────┘
                      │ created_at       │
                      └──────────────────┘
```

---

## 4. 分阶段迭代计划

### 阶段 0：环境搭建与工具链

**学习目标**：建立完整开发环境，理解 uv、FastAPI 项目结构、Git 工作流。

**我会讲解的内容**：
- `uv init` vs `uv add` vs `uv sync` 的用法
- FastAPI 最小应用的三个部分（app、router、run）
- Git 分支管理策略（main → dev → feature/xxx）

**实战任务**（由你编码）：
1. 用 `uv init` 初始化 `backend/` 项目
2. 创建 `backend/src/` 目录结构（`main.py`, `config.py`, `database.py`, `models/`, `schemas/`, `routers/`, `services/`, `utils/`, `uploads/`）
3. 编写最小的 FastAPI `backend/src/main.py`：一个 `/health` 端点返回 `{"status": "ok"}`
4. 用 `uvicorn` 启动，浏览器访问 `/docs` 查看 Swagger UI
5. 创建数据库 `cat_pic`（在 MySQL 中执行 CREATE DATABASE）
6. Git: 初始化仓库，创建 `main` 和 `dev` 分支

**验收标准**：
- `http://localhost:8000/health` 返回 200
- `http://localhost:8000/docs` 显示交互式文档
- MySQL 中存在 `cat_pic` 数据库

---

### 阶段 1：FastAPI 入门 + 数据库 + 用户系统（JWT）

**学习目标**：掌握 FastAPI 核心概念 + SQLAlchemy ORM + JWT 认证。

**我会讲解的内容**：
- FastAPI 依赖注入 (`Depends`)、路径参数、查询参数、请求体
- SQLAlchemy 声明式模型、Session 管理、`sessionmaker`
- Pydantic `BaseModel`：请求校验 vs 数据库模型 vs 响应模型的区别
- JWT 原理：Header、Payload、Signature；Access Token vs Refresh Token
- `passlib` 密码哈希（bcrypt）

**实战任务**（由你编码）：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1.1 | `backend/pyproject.toml` | 添加依赖：`fastapi`, `uvicorn`, `sqlalchemy`, `pymysql`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`, `pydantic[email-validator]` |
| 1.2 | `backend/src/database.py` | 数据库引擎 + `SessionLocal` + `get_db` 依赖 |
| 1.3 | `backend/src/config.py` | 读取 `.env` 中的数据库/JWT 配置 |
| 1.4 | `backend/src/models/user.py` | User 模型（id, username, email, hashed_password, created_at, updated_at） |
| 1.5 | `backend/src/schemas/user.py` | `UserCreate`, `UserLogin`, `UserResponse`, `TokenResponse` |
| 1.6 | `backend/src/utils/security.py` | `hash_password`, `verify_password`, `create_access_token`, `decode_token` |
| 1.7 | `backend/src/services/auth_service.py` | `register_user`, `authenticate_user` |
| 1.8 | `backend/src/routers/auth.py` | `POST /api/auth/register`, `POST /api/auth/login` |
| 1.9 | `backend/src/routers/users.py` | `GET /api/users/me`（需 JWT 鉴权） |
| 1.10 | `backend/src/main.py` | 注册路由，配置 CORS |

**验收标准**：
- 通过 `/docs` 能成功注册用户、登录获取 JWT Token
- 用 JWT Token 调用 `/api/users/me` 返回当前用户信息
- 密码在数据库中以哈希存储，不是明文

---

### 阶段 2：图片上传与管理

**学习目标**：FastAPI 文件上传、Pillow 图片处理、SQLAlchemy 关联查询。

**我会讲解的内容**：
- FastAPI `UploadFile` 处理 multipart 上传
- Pillow 基本操作：打开、resize、保存、格式转换
- WebP 格式的优势与压缩参数
- SQLAlchemy 外键关系、一对多查询
- 图片存储策略：本地文件系统 vs 对象存储的区别

**实战任务**（由你编码）：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 2.1 | `backend/src/models/image.py` | Image 模型（user_id 外键, filename, file_path, thumbnail_path, file_size, mime_type, width, height, created_at） |
| 2.2 | `backend/src/models/tag.py` | Tag 模型 + image_tags 多对多关联表 |
| 2.3 | `backend/src/utils/image_utils.py` | `compress_to_webp()`, `generate_thumbnail()`, `get_image_dimensions()` |
| 2.4 | `backend/src/schemas/image.py` | `ImageResponse`, `ImageListResponse`, `ImageUploadResponse` |
| 2.5 | `backend/src/services/image_service.py` | `upload_file()`, `upload_from_url()`, `get_user_images()`, `get_image_detail()`, `delete_image()` |
| 2.6 | `backend/src/routers/images.py` | `POST /api/images/upload`, `POST /api/images/upload-url`, `GET /api/images`, `GET /api/images/{id}`, `DELETE /api/images/{id}` |
| 2.7 | `backend/src/main.py` | 注册图片路由，配置静态文件服务 |

**验收标准**：
- 上传图片后自动生成 WebP 格式 + 缩略图
- URL 上传也能正常工作
- 图片列表按创建时间倒序返回
- 删除图片同时删除物理文件

**后续增强计划**：
- 保留用户上传的原始格式文件（如 png），提供原图下载功能。需改动：
  - `Image` 模型加 `original_path` 字段
  - `save_upload_file()` 保留原格式副本
  - `ImageResponse` 加 `original_url` 字段
  - `delete_image()` 同步清理原图文件

---

### 阶段 3：Vue3 前端搭建

**学习目标**：Vite 项目初始化、Vue3 Composition API、Vue Router、Pinia。

**我会讲解的内容**：
- `npm create vite` 初始化 Vue3 + TS 项目
- `<script setup>` 语法糖 vs Options API
- `ref`、`reactive`、`computed`、`watch` 的用法
- Vue Router 路由配置与导航守卫
- Pinia `defineStore` 的两种写法（Options Store / Setup Store）
- Axios 拦截器封装（自动携带 JWT、401 跳转登录）

**实战任务**（由你编码）：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 3.1 | `frontend/` | `npm create vite@latest frontend -- --template vue-ts` |
| 3.2 | `frontend/src/router/index.ts` | 路由：`/login`, `/register`, `/gallery`, `/upload`, `/agent` |
| 3.3 | `frontend/src/stores/auth.ts` | Pinia Store：token 存储、用户信息、登录/登出方法 |
| 3.4 | `frontend/src/api/client.ts` | Axios 实例：baseURL、请求拦截器（加 Token）、响应拦截器（401 处理） |
| 3.5 | `frontend/src/api/auth.ts` | `login()`, `register()`, `getCurrentUser()` |
| 3.6 | `frontend/src/views/Login.vue` | 登录页面：表单 + 调用 API + 存储 Token + 跳转 |
| 3.7 | `frontend/src/views/Register.vue` | 注册页面 |
| 3.8 | `frontend/src/components/NavBar.vue` | 导航栏：根据登录状态显示不同菜单 |
| 3.9 | `frontend/src/App.vue` | 布局：NavBar + `<router-view>` |

**验收标准**：
- 前端能正常启动（`npm run dev`）
- 登录/注册页面样式可用，能跳转
- 登录成功后 Token 存储在 Pinia + localStorage
- 未登录访问 `/gallery` 自动跳转 `/login`

---

### 阶段 4：前后端联调与 JWT 鉴权

**学习目标**：完整的请求链路（前端 → Axios → FastAPI → MySQL），CORS 配置，Token 刷新机制。

**我会讲解的内容**：
- CORS 跨域原理与 FastAPI CORSMiddleware 配置
- Bearer Token 在 HTTP Header 中的传递
- 前端导航守卫（`router.beforeEach`）鉴权逻辑
- Token 过期处理与静默刷新
- 前后端联调常见问题排查方法

**实战任务**（由你编码）：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 4.1 | `frontend/src/api/images.ts` | 图片相关 API 封装 |
| 4.2 | `frontend/src/stores/images.ts` | 图片列表状态管理 |
| 4.3 | `frontend/src/views/Gallery.vue` | 图片网格展示 + 分页/无限滚动 |
| 4.4 | `frontend/src/views/Upload.vue` | 上传页面：拖拽上传 + URL 输入 |
| 4.5 | `frontend/src/components/ImageCard.vue` | 图片卡片组件：缩略图、标签、删除按钮 |
| 4.6 | `backend/src/main.py` | 添加 CORSMiddleware（允许 `http://localhost:5173`） |

**验收标准**：
- 前端能完成注册 → 登录 → 上传图片 → 查看列表 → 删除图片的完整流程
- 非登录用户无法访问受保护的页面和 API
- Token 过期后自动跳转登录页

---

### 阶段 5：Agent 接入 — AI 图片分析

**学习目标**：调用大模型 API（兼容 OpenAI 格式），处理多模态请求，理解流式响应 SSE。

**我会讲解的内容**：
- OpenAI 兼容 API 的请求/响应格式
- 多模态请求：如何将图片以 base64 传给大模型
- SSE（Server-Sent Events）流式响应的原理与 FastAPI `StreamingResponse`
- 异步 HTTP 请求 (`httpx`) 的使用
- Agent 层架构：service 层的职责划分

**实战任务**（由你编码）：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 5.1 | `backend/src/schemas/agent.py` | `ImageAnalysisRequest`, `ImageAnalysisResponse`, `TagSuggestionResponse` |
| 5.2 | `backend/src/services/agent_service.py` | `analyze_image()`：读取图片 → 转 base64 → 调用大模型 → 返回描述 + 建议标签 |
| 5.3 | `backend/src/services/agent_service.py` | `suggest_tags()`：根据图片内容建议标签 |
| 5.4 | `backend/src/routers/agent.py` | `POST /api/agent/analyze-image` 流式返回分析结果 |
| 5.5 | `backend/src/routers/images.py` | 上传图片后可选调用 Agent 自动打标签 |
| 5.6 | `frontend/src/api/agent.ts` | Agent API 封装 |
| 5.7 | `frontend/src/components/AgentDialog.vue` | 图片分析结果弹窗 |

**验收标准**：
- 上传图片后，点击"AI 分析"按钮，能看到图片描述和标签建议
- 支持流式显示分析结果（逐字输出）
- 分析结果中建议的标签可以一键添加到图片

---

### 阶段 6：Agent 接入 — AI 对话助手

**学习目标**：多轮对话管理、对话历史存储、Agent 工具调用概念。

**我会讲解的内容**：
- 对话角色体系（system / user / assistant）
- 对话历史的存储策略（内存 vs 数据库）
- Agent 的 Function Calling / Tool Use 概念
- 前端聊天 UI 的实现模式（消息列表 + 输入框 + 自动滚动）

**实战任务**（由你编码）：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 6.1 | `backend/src/models/conversation.py` | Conversation + Message 模型 |
| 6.2 | `backend/src/schemas/agent.py` | `ChatRequest`, `ChatResponse`, `ConversationListResponse` |
| 6.3 | `backend/src/services/agent_service.py` | `chat()`：多轮对话 + 上下文管理 |
| 6.4 | `backend/src/routers/agent.py` | `POST /api/agent/chat`（流式）, `GET /api/agent/conversations` |
| 6.5 | `frontend/src/views/AgentChat.vue` | 聊天页面：对话列表 + 消息区 + 输入框 |

**验收标准**：
- 用户可以创建多轮对话，AI 有上下文记忆
- 对话支持流式打字效果
- 聊天助手能回答关于图库的问题（如"我有多少张图片？"）

---

### 阶段 7：缓存、优化与部署

**学习目标**：Redis 缓存策略、图片列表性能优化、生产部署基础。

**我会讲解的内容**：
- Redis 在 Docker 中的启动与管理
- 缓存策略：Cache-Aside 模式、TTL 设置
- 什么数据适合缓存（用户信息、图片列表首页）
- 缓存失效与更新策略

**实战任务**（由你编码）：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 7.1 | `backend/src/cache.py` | Redis 连接 + `get_cache`, `set_cache` 工具函数 |
| 7.2 | `backend/src/services/image_service.py` | 图片列表添加 Redis 缓存 |
| 7.3 | `backend/src/services/auth_service.py` | 用户信息缓存 |
| 7.4 | `frontend/` | 构建生产版本 (`npm run build`) + Nginx 配置 |

**验收标准**：
- Redis 缓存生效，二次查询明显快于首次
- 删除图片后缓存同步失效
- 前端能构建生产版本

---

## 5. 每个阶段的标准流程

每个阶段遵循以下节奏，确保你真正理解而不是照抄代码：

```
Step 1 [我讲]：在对话中讲解该阶段涉及的技术概念和框架用法
Step 2 [我出题]：给出该阶段的任务清单（如上表）
Step 3 [你做]：你动手写代码，遇到问题随时在对话中问我
Step 4 [我审]：你把代码贴到对话中，我审查并给出改进建议
Step 5 [你改]：根据反馈修改代码并验证通过
Step 6 [你写]：将最终代码写入项目文件中
```

---

## 6. 关键约定

1. **代码只生成在对话中**：我不会直接写文件，所有代码都在对话中输出，由你评审后自行写入项目。这能确保你理解每行代码。

2. **提问优先**：在写任何代码之前，随时打断我提问。不要怕问"蠢问题"——每个有经验的开发者都经历过这个阶段。

3. **AGENTS.md 规范**：你的项目中没有 `AGENTS.md` 文件。如果你需要我为某些模块创建自定义的 AGENTS.md 规范指导文件（比如给 AI 助手看的项目规则），可以随时告诉我。

4. **Git 小步提交**：每完成一个小功能就做一次 Git commit，方便回滚和对照。

5. **错误是最好的老师**：遇到报错不要慌，我会教你如何阅读报错信息、如何定位问题。调试能力比写代码能力更重要。

6. **环境确认**：每次开始新阶段前，先确认 MySQL 服务运行、Docker Redis 容器运行（需要缓存时）、虚拟环境激活。

---

> **下一步**：请回复"开始阶段0"或直接提出你的任何疑问，我们从环境搭建开始！
