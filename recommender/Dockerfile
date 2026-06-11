FROM python:3.11-slim

# 系統設定 (不寫 pyc 檔、不緩衝輸出)python --version
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

# 安裝 LightFM（需要 patch setup.py，因為 lightfm 1.17 跟新版 setuptools 不相容）
RUN pip install "pip<24" "numpy==1.26.4" "scipy==1.11.4" "pandas==2.2.3" "pyarrow==17.0.0" "requests<3" "scikit-learn==1.3.2" "setuptools>=65,<70" "cython<3" wheel && \
    curl -fsSL -o /tmp/lightfm-1.17.tar.gz \
      https://files.pythonhosted.org/packages/1f/96/5ec230f5c27811534af0faaa8525f11c1000ee1c24c8a82c0546d0724aea/lightfm-1.17.tar.gz && \
    tar xzf /tmp/lightfm-1.17.tar.gz -C /tmp && \
    sed -i 's/__builtins__.__LIGHTFM_SETUP__ = True/import builtins as _builtins; _builtins.__LIGHTFM_SETUP__ = True/' /tmp/lightfm-1.17/setup.py && \
    cd /tmp/lightfm-1.17 && pip install . --no-deps && \
    rm -rf /tmp/lightfm*

# 利用 Docker 快取，先安裝 Python 套件
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# 複製專案原始碼
COPY . .

# 預設啟動指令 (設定為 bash 讓我們可以進去下指令)
CMD ["bash"]