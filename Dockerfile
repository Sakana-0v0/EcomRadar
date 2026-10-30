# EcomRadar Docker 镜像 (多阶段构建)
#
# Stage 1: node    —— 构建前端静态资源
# Stage 2: builder —— 安装 Python 依赖
# Stage 3: runtime —— 最小运行时镜像

# ============ Stage 1: 前端构建 ============
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# ============ Stage 2: Python 依赖 ============
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ============ Stage 3: 运行时 ============
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖 (从 builder 复制)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/python /usr/local/bin/python

# 应用代码
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/ ./data/

# 前端构建产物
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
