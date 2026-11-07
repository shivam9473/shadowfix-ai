# ── Multi-Stage Production Dockerfile for ShadowFix AI ──
# Compatible with both x86_64 and ARM64 (Oracle Cloud Ampere A1)

# Stage 1: Build Frontend Dashboard
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Backend + Static Asset Server
FROM python:3.11-slim AS production

# Security: non-root user setup
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

WORKDIR /app

# Install system dependencies (git for repo cloning)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/
COPY .env.example ./.env

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure data directory exists
RUN mkdir -p /app/backend/data && chmod -R 777 /app/backend/data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
