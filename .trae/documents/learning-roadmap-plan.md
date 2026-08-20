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
   - [阶段 8：图片详情与 AI 编辑](#阶段-8图片详情与-ai-编辑)
   - [阶段 9：公共图库与角色权限（审核流）](#阶段-9公共图库与角色权限审核流)
   - [阶段 10：公共图库详情页与可见性控制](#阶段-10公共图库详情页与可见性控制)
   - [阶段 11：个人资料编辑](#阶段-11个人资料编辑)
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
            image.py： (图片表模型: filename, original_name, custom_name, date_dir, file_path, thumbnail_path)
            tag.py： (标签表模型 + image_tags 多对多关联)
            conversation.py： (对话 & 消息模型，阶段6引入)
         }
         schemas/： (Pydantic 请求/响应校验模型){
            __init__.py
            user.py： (UserCreate、UserLogin、UserResponse、TokenResponse)
            image.py： (ImageResponse, ImageUploadResponse, ImageListResponse；含 display_name 计算字段)
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
            image_utils.py： (格式校验、尺寸获取、缩略图生成、日期目录)
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
┌─────────────┐       ┌────────────────────────┐       ┌─────────────┐
│   users     │       │        images          │       │    tags     │
├─────────────┤       ├────────────────────────┤       ├─────────────┤
│ id (PK)     │──1:N──│ id (PK)                │       │ id (PK)     │
│ username    │       │ user_id (FK)           │──N:M──│ name        │
│ email       │       │ filename               │       └─────────────┘
│ password    │       │ original_name (源文件)  │              │
│ created_at  │       │ custom_name  (用户取名) │       ┌──────┴──────┐
│ updated_at  │       │ date_dir     (日期子目录)│       │ image_tags  │
└─────────────┘       │ file_path    (原格式文件)│       ├─────────────┤
                      │ thumbnail_path(缩略图)  │       │ image_id(FK)│
                      │ file_size               │       │ tag_id (FK) │
                      │ mime_type               │       └─────────────┘
                      │ width                   │
                      │ height                  │
                      │ created_at              │
                      └────────────────────────┘
```
> **当前存储策略**：每张图存 2 个物理文件 — 原格式文件（兼展示+下载）+ 缩略图 WebP。无中间 WebP 副本。

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
- 上传图片后保留原格式文件 + 生成缩略图 WebP（2 文件策略）
- URL 上传也能正常工作
- 图片列表按创建时间倒序返回
- 删除图片同时删除物理文件

**已完成增强功能（突发需求实战）**：

| 功能 | 涉及改动 |
|------|---------|
| 原图保留 + 下载 | `image.py` 用 `file_path` 存原格式（兼展示），`routers/images.py` 新增 `GET /{id}/download` |
| 自定义图片名称 | `image.py` 加 `custom_name` 字段 + `display_name` 计算属性，上传时通过 `Form` 传入 |
| 按日期目录存储 | `image_utils.py` 加 `get_date_upload_dir()`，`image.py` 加 `date_dir` 列 |
| 图片搜索 | `image_service.py` 加 `search` 参数支持 `ilike` 模糊匹配，前端 `Gallery.vue` 加 500ms 防抖搜索框 |
| `href`→`Axios blob` 下载 | `ImageCard.vue` 的 `<a>` 标签绕过 Axios 拦截器→401；改用 `downloadOriginalImage()` + `blob` 下载 |
| 上传 MIME 类型规范化 | `image_service.py` 加 `EXTENSION_TO_MIME` 映射，`.jpg` 统一存为标准 `image/jpeg`，避免视觉模型误判图片格式 |

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

**已完成增强功能（多厂商模型注册表）**：

| 功能 | 涉及改动 |
|------|---------|
| 多厂商灵活切换 | `config.py` 新增 `PROVIDER_CONFIG` + `MODEL_REGISTRY`（从 `.env` 的 `AI_MODELS` 解析），`agent_service.py` 根据模型 ID 路由到对应厂商 |
| 通用 OpenAI 兼容调用 | `stream_llm()` — DeepSeek / SiliconFlow 走同一套 `/v1/chat/completions`，只换 `base_url` + `api_key` |
| 模型列表动态获取 | `GET /api/agent/models` — 前端下拉框从后端动态加载，`.env` 加一行新模型即自动出现 |
| AgentDialog 模型选择 | 弹窗打开时过滤 `type: "vision"` 的模型供用户选择，不再硬编码模型 ID |
| 图片 base64 编码 | `analyze_image()` 读取 `image_path` → base64 → `data:image/xxx;base64,...` 嵌入多模态请求 |

> **后续调整**：图库卡片（`ImageCard.vue`）上的「AI 分析」按钮已移除——因与 AI 助手的图片分析功能（AgentChat 选图/上传分析）冗余。`AgentDialog.vue` 组件保留备用，不再由 `Gallery.vue` 引用。

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
| 7.4 | `frontend/` | 构建生产版本 (`npm run build`) + FastAPI 托管 SPA |

**验收标准**：
- ✅ Redis 缓存生效，二次查询明显快于首次
- ✅ 删除图片后缓存同步失效
- ✅ 前端能构建生产版本，FastAPI 单端口托管（`http://localhost:8000`）

**已完成增强功能**：

| 功能 | 涉及改动 |
|------|---------|
| Redis 异步连接池 | `cache.py` — `redis.asyncio` 懒加载 + JSON 序列化 + 通配符删除 |
| 图片列表 Redis 缓存 | `image_service.py` — Cache-Aside 模式，ORM → Pydantic.model_dump 后存入，命中时从 dict 重建 |
| 用户信息缓存 | `auth_service.py` — JWT 鉴权时优先读 Redis，TTL 10 分钟 |
| 前端生产构建 | `npm run build` → `frontend/dist/`，`main.py` 中 SPA fallback 路由托管 |
| 构建问题修复 | `tsconfig.json` 弃用警告、`env.d.ts` Vue 类型声明、`router/index.ts` 未使用变量 |
| Redis 降级策略 | `cache.py` — PING 健康检查 + 30s 重试间隔，Redis 挂了零开销降级纯 DB，恢复自动切回 |
| 清除 pycache 缓存 | 后端 `__pycache__/` 需定期清理，否则旧 `.pyc` 可能导致修改不生效 |

---

### 阶段 8：图片详情与 AI 编辑

**学习目标**：Fabric.js 画布操作、AI 区域编辑（遮罩+提示词）、浏览器端 AI 抠图、基础图片编辑。

**我会讲解的内容**：
- Fabric.js 在 Vue3 中的集成方式（`onMounted` 初始化 canvas）
- 图层与遮罩的概念：如何用画笔/矩形生成遮罩 → AI 只修改遮罩区域
- `@imgly/background-removal` 浏览器端 AI 抠图的原理与使用
- 编辑操作的序列化（前端累积操作 → 一次性提交后端）
- 保存策略：覆盖原图 vs 另存为新图的取舍

**实战任务**（由你编码）：
| 步骤 | 文件 | 内容 |
|------|------|------|
| 8.1 | `backend/src/schemas/agent.py` | `ChatRequest` 加 `image_id` 字段（`int \| None = None`） |
| 8.2 | `backend/src/services/agent_service.py` | `chat()` 支持多模态：有 `image_id` 时查图片 → base64 → 追加多模态 message |
| 8.3 | `backend/src/routers/agent.py` | `/chat` 端点前置校验：图片存在性 + 模型类型（text 模型拒绝带图请求） |
| 8.4 | `frontend/src/views/AgentChat.vue` | 本地上传按钮 + 附件预览 + 自动切视觉模型 |
| 8.5 | `frontend/src/api/agent.ts` | `chatStream` 加 `imageId` 参数，发送时拼入 `body.image_id` |
| 8.6 | `frontend/src/views/GalleryPicker.vue` | 图库选图弹窗（新建）：遮罩 + 图片网格 + 搜索防抖，选中 emit |
| 8.7 | `frontend/src/views/AgentChat.vue` | 输入区「选图」按钮 → 打开弹窗 → 走统一 attachedImage 流程 |
| 8.8 | `backend/src/schemas/image.py` | `EditOperation` + `EditImageRequest`（`type: rotate/flip/crop` + 参数） |
| 8.9 | `backend/src/services/image_service.py` | `edit_image()`：Pillow 按序执行 旋转→翻转→裁剪；覆盖=重写原文件+缩略图，另存=新文件+新记录 |
| 8.10 | `backend/src/services/image_service.py` | `replace_image()`：接收新图片，覆盖原 `file_path` + 重生成缩略图 + 更新尺寸，保留原记录 |
| 8.11 | `backend/src/routers/images.py` | `POST /{id}/edit`（操作列表 + `save_mode`）、`POST /{id}/replace`（multipart 图片） |
| 8.12 | `frontend/src/router/index.ts` | 新增路由 `/detail/:id` → Detail 组件 |
| 8.13 | `frontend/src/components/ImageCard.vue` | `@dblclick` → `router.push("/detail/" + id)` |
| 8.14 | `frontend/src/api/images.ts` | `editImage(id, operations, saveMode, customName?)` + `replaceImage(id, blob)` |
| 8.15 | `frontend/src/views/Detail.vue` | 详情编辑页（新建）：原生 Canvas + 操作序列 + AI 抠图/区域编辑 |
| 8.16 | `frontend/` | `npm install @imgly/background-removal`（未用 Fabric.js，改用原生 Canvas） |
| 8.17 | `backend/src/schemas/image.py` | `UpdateImageNameRequest`（`custom_name: str`） |
| 8.18 | `backend/src/services/image_service.py` | `update_image_name()`：校验归属 → 更新 `custom_name` → 清图库缓存 |
| 8.19 | `backend/src/routers/images.py` | `PATCH /{id}/name` 改名端点（`async def`） |
| 8.20 | `frontend/src/api/images.ts` | `updateImageName()` 封装 |
| 8.21 | `frontend/src/api/client.ts` | Axios 包装层新增 `patch` 方法 |
| 8.22 | `frontend/src/views/Detail.vue` | 图片信息区「名称」加「改名」按钮 |

**验收标准**：
- ✅ 双击图库图片进入详情页，能看到原图
- ✅ 能在画布上涂鸦/画矩形标记区域
- ✅ 点击"AI 区域编辑"后 AI 能修改选中区域（如"把背景变成蓝天"）
- ✅ AI 抠图能正确移除背景（透明 PNG）
- ✅ 基础旋转/翻转/裁剪操作正常
- ✅ 覆盖保存后原图被替换，另存后图库多一张新图
- ✅ 从详情页返回到图库，列表正确刷新

**已完成增强功能**：

| 功能 | 涉及改动 |
|------|---------|
| 混合架构分工 | 基础编辑走后端 Pillow（传 `operations` 参数非整图），AI 抠图纯前端 `@imgly/background-removal`，AI 区域编辑后端调视觉模型（API Key 不外泄） |
| 统一保存策略 | 所有编辑场景提供 [覆盖保存] + [另存新图]；新增 `POST /{id}/replace` 接口（保留 id/名称/标签/关联，仅重写文件+缩略图+尺寸） |
| AgentChat 多模态选图 | `chat()` 支持 `image_id` + 前端本地上传/图库选图（GalleryPicker） |
| AI 抠图模型本地化 | @imgly 模型（271MB）本地化到 `frontend/public/background-removal/`，`publicPath` 指向本地 |
| AI 区域编辑（涂鸦标记） | 原「遮罩图」方案弃用（SiliconFlow 无 mask 参数），改用红色涂鸦标记图 + `Qwen-Image-Edit-2509` 指令式编辑 |
| 画笔体验优化 | 画笔粗细三档 / 六色可调 / 30% 不透明度 |
| 图片改名 | `PATCH /{id}/name` 仅更新 `custom_name`（保留 `original_name`） |

---

**架构分工决策**：

混合架构：轻操作走后端参数化接口，重操作走前端处理，AI 区域编辑因密钥约束走后端。

| 功能 | 处理位置 | 数据流向 | 保存方式 |
|------|---------|---------|---------|
| 基础编辑（旋转/翻转/裁剪） | 前端 Canvas 预览 + 后端 Pillow 执行 | 前端传 `operations` 参数（非图片） | `POST /{id}/edit` 覆盖/另存 |
| AI 抠图 | 纯前端 `@imgly/background-removal` | 浏览器端推理，输出透明 PNG blob | 上传 blob 保存 |
| AI 区域编辑 | 前端生成遮罩 + 后端调视觉模型 | 前端传遮罩+原图+指令，后端流式返回结果图 | 后端保存结果 |

**为什么这样分工**：
- 基础编辑用 Pillow 毫秒级，并发无压力，传参数比传整图更高效
- AI 抠图是重量级模型推理，放前端省后端算力 + 免去 rembg 模型下载
- AI 区域编辑必须后端：大模型 API Key 不能暴露在前端

**保存策略（已确定）**：所有编辑场景统一提供 `[覆盖保存]` + `[另存新图]`。

| 场景 | 覆盖原图 | 另存新图 |
|------|---------|---------|
| 基础编辑 | `POST /{id}/edit` `save_mode=overwrite` | `POST /{id}/edit` `save_mode=new` |
| AI 抠图（前端 blob） | `POST /{id}/replace`（新增） | `POST /images/upload`（复用） |
| AI 区域编辑（后端结果图） | `POST /{id}/replace`（新增） | 后端直接存新记录 |

---

**实际实现与踩坑记录**

**踩坑**：

| 踩坑 | 根因 | 解决 |
|------|------|------|
| `Invalid base URL` | `publicPath` 传相对路径 `/background-removal/`，库内部 `new URL(rel, base)` 要求 base 为绝对 URL | 改为 `window.location.origin + "/background-removal/"` |
| 生产模式返回 HTML | `/background-removal` 未挂载静态目录，请求落到 SPA fallback 返回 index.html | `main.py` 挂载 `StaticFiles`（必须放在 SPA fallback 之前） |
| 覆盖保存 400「不支持的图片格式」 | `replaceImage` 传裸 `Blob`，`FormData.append` 后文件名是 `"blob"` 无扩展名，后端 `splitext` 得到空串 | 包成 `new File([blob], "result.png", { type: "image/png" })` |
| 原「遮罩图」方案走不通 | 调研发现 SiliconFlow `images/generations` 无 mask 参数 | 改用「涂鸦标记图」：前端把红色涂鸦叠到原图上作为 `image`，`prompt` 说明"仅改红色标记区域"；模型用 `Qwen/Qwen-Image-Edit-2509`（指令式编辑） |
| 前端 10s 超时 | AI 推理约 60s，远超 axios 全局 `timeout: 10000` | `aiEditImage` 单独设 `timeout: 300000` |
| 改名接口报 `RuntimeError: no running event loop` | `rename_image` 写成同步 `def` 被 FastAPI 丢进线程池执行，线程池无事件循环，`asyncio.create_task` 清缓存报错 | 改成 `async def`（与 `upload`/`delete_image` 一致），让端点在事件循环里跑 |

**画笔体验优化**：

| 优化 | 说明 |
|------|------|
| 画笔粗细可调 | `brushSize` 三档（细/中/粗），对应线宽 `max(宽,高)/80 /40 /15` |
| 画笔颜色可调 | `brushColors` 六色（红/蓝/绿/黄/黑/白），涂鸦标记色经 `color_name` 传入后端动态拼接 prompt |
| 降低不透明度 | `brushOpacity = 0.3`，让涂鸦下方的原图透出，避免误涂不想改的区域 |

---

### 阶段 9：公共图库与角色权限（审核流）

**学习目标**：数据库迁移（Alembic）、RBAC 角色权限、审核流状态机、公共资源引用与删除保护。

**我会讲解的内容**：
- Alembic 迁移：如何给「已有数据库」引入迁移机制（基线 stamp + 增量迁移），做到加列/建表不丢数据
- RBAC 角色模型：`role` 字段 + `require_admin` 依赖注入
- 审核流状态机：pending → approved / rejected，以及撤回、下架
- 「引用原图」vs「复制文件」的取舍，及引用关系下的删除保护

> **本阶段已完成并验证通过（提交 → 审核 → 级联删除闭环已跑通）。**

**数据层（Alembic 迁移）**：

`users` 表加列：

```python
role = Column(String(20), nullable=False, default="user", comment="角色：user/admin")
```

新增 `public_images` 表：

```python
class PublicImage(Base):
    __tablename__ = "public_images"
    id             = Column(Integer, primary_key=True, autoincrement=True, index=True)
    image_id       = Column(Integer, ForeignKey("images.id"), nullable=False, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status         = Column(String(20), nullable=False, default="pending", index=True)  # pending/approved/rejected
    review_comment = Column(String(255), nullable=True)
    reviewed_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at    = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.now)
```

**索引设计**：

| 索引 | 覆盖场景 |
|------|---------|
| `(status, created_at)` 复合索引 | 公共库浏览（approved 倒序）+ 待审核列表（pending 倒序） |
| `(user_id, created_at)` 复合索引 | 「我的提交」列表 |
| `image_id` 单列索引 | 删除图片时查「是否被公共库引用」 |

**接口设计**：

| 方法 & 路径 | 权限 | 说明 |
|------------|------|------|
| `POST /api/public/images` | 登录用户 | 提交到公共库（仅 `image_id`，从自己图库选图）；校验归属 + 防重复提交 |
| `GET /api/public/images` | 登录用户 | 浏览公共库，只返回 `approved`，分页 + 可选搜索 |
| `GET /api/public/images/my` | 登录用户 | 我的提交记录（含各状态） |
| `GET /api/public/images/pending` | 管理员 | 待审核列表 |
| `POST /api/public/images/{id}/review` | 管理员 | 审核：`{ action: "approve"\|"reject", comment }` |
| `POST /api/public/images/{id}/remove` | 管理员 | 下架（approved → rejected，附下架意见） |
| `DELETE /api/public/images/{id}` | 提交者本人 | 作者删除自己的公共库记录（`pending` 撤回 / `approved` 主动删除 / `rejected` 清理记录） |

**审核状态机**：

```
pending ──approve──▶ approved
pending ──reject ──▶ rejected
pending ──(作者撤回)──▶ 删除记录
approved ──(作者主动删除)──▶ 删除记录
rejected ──(作者清理)──▶ 删除记录
approved ──(管理员下架)──▶ rejected（附下架意见）
任意状态 ──(原图被删)──▶ 级联删除记录
```

**删除行为（引用原图方案）**：

| 操作 | 结果 |
|------|------|
| 作者删除个人图库原图 | 级联删除该图片对应的所有 `public_images` 记录（任意状态） |
| 作者删除公共库记录（`pending`/`approved`/`rejected`） | 仅删公共库记录，原图保留在个人图库 |

**管理员产生方式**：脚本 `backend/scripts/promote_admin.py`，把指定 `username` 提升为 admin（贴近 Django `createsuperuser`，不手写 SQL、不丢数据）。

**实战任务（已完成）**：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 9.1 | `backend/pyproject.toml` | `uv add alembic` |
| 9.2 | `backend/alembic/` | `alembic init` + 配置 `env.py`（`target_metadata = Base.metadata`）+ 基线 `stamp head` |
| 9.3 | `backend/src/models/user.py` | `User` 加 `role` 字段 |
| 9.4 | `backend/src/models/public_image.py` | 新增 `PublicImage` 模型 |
| 9.5 | `backend/src/schemas/public_image.py` | 提交/审核请求 + 响应模型 |
| 9.6 | `backend/src/services/public_service.py` | 提交/浏览/我的/待审/审核/下架/作者删除 业务逻辑 |
| 9.7 | `backend/src/routers/public_images.py` | 上述 7 个端点 + `require_admin` 依赖 |
| 9.8 | `backend/src/routers/public_images.py` | `require_admin` 依赖注入（定义在公共图库路由内：先鉴权，再校验 `role == "admin"`） |
| 9.9 | `backend/scripts/promote_admin.py` | 管理员提升脚本 |
| 9.10 | `frontend/src/views/PublicGallery.vue` | 公共图库浏览页 |
| 9.11 | `frontend/src/views/AdminReview.vue` | 管理员审核页 |
| 9.12 | `frontend/src/components/NavBar.vue` | 加「公共图库」（全员）+「审核」（仅 admin）入口 |
| 9.13 | 图库/详情页 | 加「提交到公共图库」按钮 |
| 9.14 | `frontend/src/views/Profile.vue` | 个人主页：我的提交进度 + 撤回/删除；配套 `/profile` 路由 + NavBar 用户名可点击进入 |

**验收标准**：
- ✅ Alembic 迁移后旧数据完整（用户/图片/标签不丢）
- ✅ 普通用户能提交图片到公共库（只能从自己图库已有图片中选图）
- ✅ 提交后状态为 `pending`，公共库不展示
- ✅ 管理员审核通过后，公共库对所有人可见
- ✅ 管理员可拒绝/下架，下架后公共库不再展示
- ✅ 作者删除个人图库原图时，对应公共库记录级联删除
- ✅ 用户可撤回自己的 `pending` 提交
- ✅ 个人主页可查看提交进度，`pending` 撤回 / `approved`·`rejected` 删除记录

**补漏与踩坑记录**：

| 项目 | 说明 |
|------|------|
| 撤回前端入口补漏 | 阶段 9 初版只做了后端 `DELETE /{id}`，漏前端入口；补 `Profile.vue`（个人主页）+ `/profile` 路由 + NavBar 用户名可点击进入 |
| 记录删除扩展 | `DELETE /{id}` 本身不限制状态，前端顺势给 `approved`/`rejected` 也加「删除」按钮（清理记录、降维护成本），复用同一接口 |
| 上传 `NameError: EXTENSION_TO_MIME` | 并行编辑竞态导致 `image_service.py` 的 `EXTENSION_TO_MIME` 常量丢失，本地/URL 上传均 500；补回映射后恢复 |

---

### 阶段 10：公共图库详情页与可见性控制

**学习目标**：公共图库独立详情页、三种角色权限矩阵、可切换的「可见性」字段与角色感知的列表过滤。

**我会讲解的内容**：
- 独立详情页 vs 复用个人详情页的取舍（职责分离 vs 代码复用）
- 权限矩阵：管理员 / 上传者 / 其他普通用户 三种角色如何差异化展示操作按钮
- `is_visible`（可见性）与 `status`（审核状态）两个维度的语义分离
- 列表查询的「角色感知」过滤：同一接口按当前用户角色返回不同结果集

> **本阶段为规划设计稿，代码待确认后实施。**

**需求背景**：
公共图库图片目前只能看缩略图，无法进入详情查看大图与完整信息。现要求：
1. 公共图库双击图片进入详情页（与个人图库体验一致）。
2. 管理员 / 上传者可对该图「从公共图库删除」+「切换普通用户可见性」。
3. 其他普通用户进入详情页看不到任何操作按钮。

**权限矩阵**：

| 角色 | 是否上传者 | 删除公共库图片 | 切换可见性 |
|------|-----------|--------------|-----------|
| 管理员 | 任意 | ✅ | ✅ |
| 普通用户 | 是 | ✅ | ✅ |
| 普通用户 | 否 | ❌ | ❌ |

**可见性语义**：
- `is_visible` 独立于审核状态，仅对 `approved` 图片生效。
- 设为「不可见」后：其他普通用户在公共库列表看不到该图；**上传者自己与管理员始终可见**。
- 可反复切换，不影响审核状态。

**数据层（Alembic 迁移）**：

`public_images` 表加列：

```python
is_visible = Column(Boolean, nullable=False, default=True, server_default="1", comment="普通用户是否可见")
```

**接口设计（新增/变更）**：

| 方法 & 路径 | 权限 | 说明 |
|------------|------|------|
| `GET /api/public/images`（变更） | 登录用户 | 角色感知过滤：普通用户返回 `approved + is_visible`；管理员返回全部 `approved`（含隐藏） |
| `GET /api/public/images/{id}`（新增） | 登录用户 | 公共图片详情：返回图片信息 + 上传者 + `is_visible` + `is_owner`/`is_admin` 判断 |
| `POST /api/public/images/{id}/visibility`（新增） | 管理员/上传者 | 切换可见性，body `{ visible: bool }` |
| `DELETE /api/public/images/{id}`（变更） | 管理员/上传者 | 删除公共记录（原仅上传者本人，现扩展为管理员或上传者均可） |

> 说明：`DELETE` 只删 `public_images` 记录、**不动原图**；原图删除仍走个人图库，由阶段 9 的级联逻辑同步清理公共记录。

**前端路由与页面**：

| 页面/组件 | 说明 |
|-----------|------|
| `/public` → `PublicGallery.vue` | 公共图库列表（现有，卡片双击改为跳详情） |
| `/public/:id` → `PublicDetail.vue`（新建） | 公共图片详情页，`:id` 为公共记录 id |
| 按钮显隐逻辑 | 按权限矩阵：管理员/上传者显示「删除」+「切换可见性」，其他普通用户隐藏 |

**实战任务（待实施）**：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 10.1 | `backend/src/models/public_image.py` | `PublicImage` 加 `is_visible` 字段 |
| 10.2 | `backend/alembic/` | `autogenerate` 增量迁移加 `is_visible` 列 |
| 10.3 | `backend/src/schemas/public_image.py` | 详情响应模型 + 可见性请求模型 |
| 10.4 | `backend/src/services/public_service.py` | `get_public_detail()`、`set_visibility()`、浏览过滤改为角色感知、`delete_public_image()` 扩展管理员权限 |
| 10.5 | `backend/src/routers/public_images.py` | 新增 `GET /{id}`、`POST /{id}/visibility`；`DELETE /{id}` 放开管理员 |
| 10.6 | `frontend/src/api/public.ts` | `getPublicDetail()`、`setPublicVisibility()` 封装 |
| 10.7 | `frontend/src/views/PublicDetail.vue` | 新建公共详情页，按矩阵渲染按钮 |
| 10.8 | `frontend/src/router/index.ts` | 新增 `/public/:id` 路由 |
| 10.9 | `frontend/src/views/PublicGallery.vue` | 卡片 `@dblclick` → 跳 `/public/:id` |

**验收标准**：
- 公共图库双击图片进入独立详情页，能看到大图与上传者信息
- 管理员在详情页可见「删除」+「切换可见性」两个按钮
- 上传者本人可见「删除」+「切换可见性」两个按钮
- 其他普通用户进入详情页看不到任何操作按钮
- 设为不可见后，其他普通用户列表看不到该图，上传者/管理员仍可见
- 删除只删公共记录，原图保留在个人图库

---

### 阶段 11：个人资料编辑

**学习目标**：用户资料编辑（改名/改密码），表单校验、用户名唯一性、旧密码校验与密码哈希更新。

**我会讲解的内容**：
- 用户名唯一性校验（数据库唯一约束 + 服务层查重）
- 改密码的正确姿势：先校验旧密码，再用 `hash_password` 存新哈希
- JWT `sub` 存 `user_id` 而非 `username` 的好处：改名不使登录态失效
- 前端表单与确认交互

> **本阶段为规划设计稿，代码待确认后实施。**

**需求背景**：
个人主页已展示用户名与提交进度，但还无法编辑个人资料。补充两项能力：
1. 修改账号名称（`username`）
2. 修改密码（需校验旧密码）

**数据层**：无需迁移——`users` 表已有 `username` 与 `hashed_password` 字段。

**关键设计点**：
- JWT `sub` 存的是 `user_id`（见 `get_current_user` 里 `int(payload.get("sub"))`），所以**改名不影响已登录状态**，无需重新登录。
- 改名需查重，避免与他人冲突（服务层 `filter(User.username == ...)`）。
- 改密码需 `verify_password(旧密码)` 通过后才允许更新，新密码用 `hash_password` 入库。

**接口设计（新增）**：

| 方法 & 路径 | 权限 | 说明 |
|------------|------|------|
| `PATCH /api/users/me` | 登录用户 | 修改 `username`，校验非空 + 唯一 |
| `POST /api/users/me/password` | 登录用户 | 修改密码，校验旧密码 + 新密码 |

**前端改动**：
- `Profile.vue` 增加「资料编辑」区：改名表单 + 改密码表单。

**实战任务（待实施）**：

| 步骤 | 文件 | 内容 |
|------|------|------|
| 11.1 | `backend/src/schemas/user.py` | `UpdateUsernameRequest`、`ChangePasswordRequest` |
| 11.2 | `backend/src/services/auth_service.py` | `update_username()`（查重 + 更新）、`change_password()`（验旧密码 + 哈希新密码） |
| 11.3 | `backend/src/routers/users.py` | `PATCH /me`、`POST /me/password` |
| 11.4 | `frontend/src/api/auth.ts` | `updateUsername()`、`changePassword()` 封装 |
| 11.5 | `frontend/src/views/Profile.vue` | 资料编辑区（改名 + 改密码表单） |

**验收标准**：
- 改名成功后用户名立即生效，且无需重新登录
- 改名为已存在的用户名时被拒绝
- 改密码需正确旧密码；成功后可用新密码登录

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
