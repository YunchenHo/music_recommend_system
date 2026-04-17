FROM python:3.13-slim

# 安裝 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 複製環境設定並安裝套件
COPY pyproject.toml uv.lock* ./
RUN uv sync

COPY . .

# Django 預設跑在 8000 port
EXPOSE 8000

# 啟動 Django 開發伺服器 (注意：正式上線會改用 gunicorn)
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]