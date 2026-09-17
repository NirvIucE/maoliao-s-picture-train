# 猫里奥全栈云图库 — 生产镜像（多阶段构建）
#
# 注：刻意不写 `# syntax=docker/dockerfile:1`。该指令会让 BuildKit 额外去 Docker Hub
# 拉取 dockerfile 前端语法镜像，在国内网络下会直接导致构建失败；本文件未使用任何
# BuildKit 专属语法，去掉后构建不依赖该镜像。
#
# 设计要点（阶段 23）：
# 1. 单镜像即可提供完整服务：后端已托管前端构建产物 + SPA 回退
#    （main.py 挂载 dist/assets 并提供 serve_spa），生产形态同源，
#    因此不需要额外的 nginx 容器。
# 2. 关键约束：main.py 用 `../../frontend/dist` 这个相对路径定位前端产物
#    （backend/src/main.py 上两级 = 仓库根），所以镜像内必须保持
#    /app/backend/src/main.py 与 /app/frontend/dist 的相对位置，勿改动布局。
# 3. 分层缓存：先 COPY 依赖清单再 COPY 源码，改业务代码不会重装依赖。
# 4. 生产镜像不装 dev 依赖（pytest/ruff/mypy 只在 CI 装）。
# 5. 非 root 用户运行；.env 不 COPY 进镜像，配置一律运行时注入。

# syntax=docker/dockerfile:1

# ── 阶段 1：构建前端 ──
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── 阶段 2：Python 运行时 ──
FROM python:3.12-slim AS runtime

# 通过 pip 装 uv（走清华源）。不用 ghcr.io 的 uv 官方镜像：国内多处网络无法访问 ghcr.io，
# 会让镜像在国内环境下无法构建。依赖版本仍由 uv.lock 锁定（下面 --frozen）。
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app/backend

# 依赖层：只依赖清单变化时才重装
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 业务代码（.dockerignore 已排除 .venv / uploads / logs / __pycache__）
COPY backend/ ./

# 前端产物：路径由 main.py 的相对寻址决定，勿改
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

# 非 root 运行；uploads 与 logs 需可写
# 注：logger.py 的相对 LOG_DIR 是相对「仓库根」解析的（backend/src/logger.py 上三级 = /app），
#     这里直接给绝对路径，避免落到意料之外的目录
RUN useradd --create-home --shell /bin/sh appuser \
    && mkdir -p /app/uploads /app/logs \
    && chmod +x /app/backend/docker-entrypoint.sh \
    && chown -R appuser:appuser /app

# 用虚拟环境里的可执行文件（alembic / uvicorn）；uploads 与 logs 指向容器内可写目录
ENV PATH="/app/backend/.venv/bin:$PATH" \
    UPLOAD_ROOT=/app/uploads \
    LOG_DIR=/app/logs

USER appuser

EXPOSE 8000

# 启动流程见脚本：等待 MySQL 就绪 → 执行迁移 → 启动服务
ENTRYPOINT ["sh", "/app/backend/docker-entrypoint.sh"]
