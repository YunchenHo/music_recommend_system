FROM python:3.12-slim

# 系統設定 (不寫 pyc 檔、不緩衝輸出)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 安裝系統必備工具與 uv
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# 利用 Docker 快取，先安裝 Python 套件
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# 複製專案原始碼
COPY . .

# 預設啟動指令 (設定為 bash 讓我們可以進去下指令)
CMD ["bash"]