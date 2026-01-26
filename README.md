# 音樂推薦系統

## 環境初始化

### 前置需求
- Python >= 3.13
- [uv](https://github.com/astral-sh/uv) 套件管理器

### 安裝 uv

https://docs.astral.sh/uv/getting-started/installation/

### 初始化專案環境

1. **同步依賴套件**（安裝 pyproject.toml 中定義的所有依賴）：
```bash
uv sync
```

2. **啟動虛擬環境**：
```bash
source .venv/bin/activate  # macOS / Linux
# 或
.venv\Scripts\activate  # Windows
```

或者直接使用 uv 執行命令（無需手動啟動虛擬環境）：
```bash
uv run python main.py
```

3. **在 Jupyter Notebook 中使用虛擬環境**：

   若要在 Jupyter Notebook（`.ipynb`）中使用此專案的虛擬環境，請在 notebook 的 kernel 選擇器中選擇 `.venv` 環境。

   - 在 Jupyter Notebook 中，點擊右上角的 kernel 名稱
   - 選擇「Change Kernel」或「選擇核心」
   - 選擇 `.venv` 或 `Python 3 (music_recommend_system/.venv)` 相關選項