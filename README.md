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

## 测试

完整测试计划与各阶段结论见 `.trae/documents/learning_test_plan.md`。测试分 4 层 + 独立冒烟层：

| 层 | 工具 | 位置 | 覆盖 |
|----|------|------|------|
| 冒烟测试 | pytest | `backend/tests/test_smoke.py` | 注册→登录→上传→列表→提交公共库→审核→可见（9 步主链路） |
| 接口测试 | pytest（独立测试库 `cat_pic_test` + 事务回滚） | `backend/tests/` | 全部模块端点（108 用例） |
| AI 应用测试 | pytest（respx mock + 真实冒烟） | `backend/tests/test_ai_flow.py` | SSE 流式、AI 错误降级、payload 校验 |
| 前端 E2E | Playwright | `frontend/e2e/` | 4 条用户流（注册上传 / 提交审核 / 详情编辑 / AI 对话） |
| 压力测试 | Locust | `tests/perf/locustfile.py` | 5 场景，50 并发 30s 约 700 请求 0 失败 |

### 运行接口测试

```powershell
cd backend
uv run pytest tests/ -q
```

### 运行 E2E 测试

需保证 8000/5173 端口空闲（Playwright 会自动拉起前后端，使用专用库 `cat_pic_e2e`，不污染开发数据）：

```powershell
cd frontend
npm run test:e2e
```

### 运行压测

```powershell
# 1. 启动后端
cd backend && uv run uvicorn src.main:app --port 8000
# 2. 启动 Locust（另开终端）
cd tests/perf
locust -f locustfile.py --headless -u 50 -r 10 -t 30s --host http://localhost:8000 --only-summary
```

### 性能优化记录（7.1 节）

- bcrypt rounds 降至 10（注册 552→138ms）+ `asyncio.to_thread` 异步化（不再阻塞事件循环）
- Redis 连接池预热（lifespan `init_redis`）+ `socket_keepalive` + `health_check_interval`
- `user_id + custom_name` 复合索引（个人图库搜索）；公共图库搜索只按 `custom_name`
- 公共图库匿名可浏览（Optional auth）

## 常见问题

- **E2E 运行报端口占用**：`reuseExistingServer: false` 要求 8000/5173 空闲，先停掉手动启动的后端/前端再跑。
- **浏览器下载慢**：`npx playwright install chromium` 失败时用 `PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright`。
