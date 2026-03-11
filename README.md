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

## Pipeline 執行

每個 stage 都有獨立主程式，可單獨執行或串成全流程。
共用邏輯已整理到 `src/`，`pipeline/` 只負責參數與流程組裝。

## Data 還原（給 clone 之後的人）

本 repo 不上傳 `data/` 與產物檔，請依以下流程還原：

> 如果你以前不小心 commit 過資料，請先執行：  
> `git rm -r --cached data artifacts reports datasets.zip`

1) **準備資料（統一用 Google Drive 檔案 ID）**
   - 直接帶 `--gdrive-id`

2) **一鍵下載 + 前處理**
```bash
uv run python -m scripts.prepare_data --gdrive-id <YOUR_GDRIVE_ID>
# 若本機已有舊的 datasets.zip，可強制重新下載
uv run python -m scripts.prepare_data --gdrive-id <YOUR_GDRIVE_ID> --force-download
# 若 data/raw 看起來不對（很小），請強制重新解壓
uv run python -m scripts.prepare_data --gdrive-id <YOUR_GDRIVE_ID> --force-download --force
# 直接執行也可（若你偏好）
uv run python scripts/prepare_data.py --gdrive-id <YOUR_GDRIVE_ID>
```

3) **產物位置**
```
data/raw/          # 原始 CSV
data/interim/      # 合併後的中介檔
data/processed/    # 特徵/編碼後資料
artifacts/         # encoders / 其他模型中介
```

## Legacy（額外資料 / Wikidata）

Wikidata 相關流程很慢且容易被限流，目前已移到 `legacy/`，不在正式流程中。
若你真的要用，請到 `legacy/pipeline/` 與 `legacy/src/data/` 內自行執行/調整。

## 模型階段（ItemKNN / MF / FAISS / Popularity）

```bash
uv run python -m pipeline.stage_09_itemknn_baseline --item-k 5 --reco-n 20 --auto-fallback
uv run python -m pipeline.stage_10_itemknn_grid --plot --use-all-targets
uv run python -m pipeline.stage_11_mf_train --epochs 5  # 在 Colab 執行，輸出 mf_model.h5
uv run python -m pipeline.stage_12_mf_faiss_eval        # 讀取 mf_model.h5
uv run python -m pipeline.stage_13_popularity_baseline
```
（MF 訓練目前改在 Colab 進行；其餘流程可在本機執行。）

> 若 ItemKNN 出現 `LOO split is empty`，代表正例太少。  
> 請用完整 train_encoded（不要 Top-K 篩選）重建：  
> `uv run python -m pipeline.stage_04_preprocess_train --top-k 0`  
> 或：`uv run python -m pipeline.stage_04b_train_encode_lowram`

### 單獨執行某個 stage
```bash
uv run python -m pipeline.stage_00_download --zip-path datasets.zip
uv run python -m pipeline.stage_00_download --zip-path datasets.zip --gdrive-id <YOUR_GDRIVE_ID> --force-download
uv run python -m pipeline.stage_01_preprocess_members
uv run python -m pipeline.stage_02_preprocess_songs
uv run python -m pipeline.stage_03_feature_engineering_songs --current-year 2026
uv run python -m pipeline.stage_04_preprocess_train --top-k 5000
uv run python -m pipeline.stage_04b_train_encode_lowram --chunksize 2000000
uv run python -m pipeline.stage_09_itemknn_baseline --item-k 5 --reco-n 20
uv run python -m pipeline.stage_10_itemknn_grid --plot
uv run python -m pipeline.stage_11_mf_train --epochs 5  # 在 Colab 執行
uv run python -m pipeline.stage_12_mf_faiss_eval
uv run python -m pipeline.stage_13_popularity_baseline
```

### 一次跑完整 pipeline
```bash
uv run python -m pipeline.run_all --from-stage 00_download --to-stage 04_train
```
