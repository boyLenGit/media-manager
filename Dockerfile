# Media Manager 多阶段构建
#
# 关键优化:前端构建阶段强制使用 BUILDPLATFORM (执行 buildx 的机器原生架构,
# 通常是 amd64),而不是目标架构。前端只产出静态 HTML/JS/CSS 没有架构差异,
# 这样跨架构(amd64+arm64)构建时 arm64 不需要 QEMU 模拟跑 node,
# 速度快 10x、内存压力小,避免 'npm Exit handler never called' OOM 问题。

# Stage 1: 构建前端 (始终在 buildx 主机原生架构下执行)
# 用 node:20-slim,与 corepack 启用 pnpm 配合更稳定 (npm 的 'Exit handler never called'
# 在 Docker 沙盒里时有发生,pnpm 用全局 store + 内容寻址,稳定性显著更好)
FROM --platform=$BUILDPLATFORM node:20-slim AS frontend-build

ARG NPM_REGISTRY=https://registry.npmjs.org
ENV NODE_OPTIONS=--max-old-space-size=4096

WORKDIR /app/frontend

# 启用 pnpm (corepack 自带)
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

# 设镜像源 + 装依赖 (用 lockfile 模式,但 pnpm 没 lockfile 时会用 package-lock.json 转换)
COPY frontend/package.json frontend/package-lock.json ./
RUN pnpm config set registry "$NPM_REGISTRY" && \
    pnpm config set fetch-timeout 600000 && \
    pnpm import && \
    pnpm install --frozen-lockfile --prefer-offline

COPY frontend/ ./
RUN pnpm run build

# Stage 2: Python 运行时 (按目标架构构建)
FROM python:3.11-slim AS runtime

# 构建参数(由 CI 注入,本地构建可不传)
ARG BUILD_VERSION=dev
ARG BUILD_COMMIT=unknown
# pip 源,默认官方;国内本地传 --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple 加速
ARG PIP_INDEX=https://pypi.org/simple

# 系统依赖:ffmpeg(可选,用于媒体探测和缩略图)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖
COPY backend/pyproject.toml ./backend/
RUN pip install --no-cache-dir -i "$PIP_INDEX" \
    fastapi \
    'uvicorn[standard]' \
    sqlmodel \
    pydantic-settings \
    apscheduler \
    httpx \
    python-multipart \
    aiofiles \
    'argon2-cffi>=23.1.0' \
    'pyjwt>=2.10.0' \
    'charset-normalizer>=3.4.0'

# 复制后端代码
COPY backend/app/ ./backend/app/

# 从前端构建阶段复制 dist
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# 写入版本信息(运行时可读取)
RUN echo "$BUILD_VERSION" > /app/VERSION && \
    echo "$BUILD_COMMIT" > /app/COMMIT

# 数据卷
RUN mkdir -p /app/backend/data
VOLUME ["/app/backend/data"]

# 配置环境变量默认值
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    APP_DEBUG=false \
    DATA_DIR=/app/backend/data \
    DATABASE_URL=sqlite:////app/backend/data/media_manager.db \
    STATIC_DIR=/app/frontend/dist \
    BUILD_VERSION=${BUILD_VERSION} \
    BUILD_COMMIT=${BUILD_COMMIT} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# OCI 标签 (CI 也会通过 metadata-action 覆盖,本地构建时也有兜底)
LABEL org.opencontainers.image.title="Media Manager" \
      org.opencontainers.image.description="NAS 资源库与视频管理系统" \
      org.opencontainers.image.source="https://github.com/boyLenGit/media-manager" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.revision="${BUILD_COMMIT}"

EXPOSE 8000

WORKDIR /app/backend

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
