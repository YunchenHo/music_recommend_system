## 🛠️ 步驟零：必備軟體安裝 (基礎環境要求)

1. **Git** (版本控制工具)
  - 用來把 GitHub 上的程式碼同步下來。
  - 下載連結：[Git 官方網站](https://git-scm.com/downloads) (預設設定一直按下一步安裝即可)
2. **Docker Desktop** (容器化引擎)
  - 這是整個專案的核心！它會自動幫你建置所有需要的 Python, Node.js 與資料庫環境，完全不用自己手動裝。
  - 下載連結：[Docker 官方網站](https://www.docker.com/products/docker-desktop/)
  - ⚠️ **Windows 用戶注意**：安裝後請務必打開 Docker Desktop 應用程式，等待左下角顯示綠色的 `Engine running` 才算啟動成功。如果遇到卡死或報錯，請嘗試在終端機輸入 `wsl --shutdown` 或直接重新開機，真的都不行再輸入`wsl --update`然後重開 Docker Desktop。

---

## 🚀 步驟一：環境變數設定 (拿取資料庫鑰匙)

為了資安考量，我們不會把含有真實密碼的環境變數檔上傳到 GitHub。請依照以下步驟設定你的本地環境：

1. 在專案的最外層目錄（跟 `docker-compose.yml` 同一層），手動新增一個檔案，並精準命名為 **`.env`** (注意最前面有一個小數點，且沒有副檔名)。
2. 將群組裡的內容全部複製，貼上到你剛建立的 `.env` 檔案中並存檔即可！

---

## 🏗️ 步驟二：一鍵建置全端系統

1. 在 VS Code 打開終端機 (Terminal)。
2. 確認 Docker Desktop 正在背景執行（亮綠燈）。
3. 輸入以下指令，讓 Docker 幫我們把四個容器蓋起來：

```bash
docker compose up -d --build
```

(第一次執行需要下載各種環境映像檔與套件，可能需要 3~5 分鐘，請耐心等候)

4. 跑完後，輸入以下指令確認容器狀態：

```bash
docker ps
```

如果有看到 4 個容器（music_react, music_django, music_mysql, music_recommender）都在運作，代表系統架構建置完畢啦！

---

## 🗄️ 步驟三：資料庫初始化 (Database Migration)

Docker 容器跑起來後，需要執行 migration 來建立資料庫的 table：

```bash
docker compose up -d
```

```bash
docker compose exec backend uv run python manage.py migrate
```

- 第一行：安裝後端 Python 依賴（因為 volume mount 的關係，容器啟動後需要執行一次）
- 第二行：根據 Django migration 檔案建立所有資料表

### ⚠️ 之後有人新增或修改資料表時

當你 pull 下來發現有新的 migration 檔案（在 `backend/*/migrations/` 底下），只需要再跑一次：

```bash
docker compose exec backend uv run python manage.py migrate
```

就會自動把新的 table 建好或更新現有的 table。

---

# 音樂推薦系統

## 環境初始化

### 前置需求

- Python >= 3.13
- [uv](https://github.com/astral-sh/uv) 套件管理器

### 安裝 uv

[https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)

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

**說明：**下列 `uv run python -m pipeline.*` 與 `scripts.*` 指令，請在 **`recommender/`** 目錄下執行（該目錄含 `pyproject.toml`）。

## Data 還原（給 clone 之後的人）

本 repo 不上傳 `data/` 與產物檔，請依以下流程還原：

> 如果你以前不小心 commit 過資料，請先執行：  
> `git rm -r --cached data artifacts reports datasets.zip`

1. **準備資料（統一用 Google Drive 檔案 ID）**
  - 直接帶 `--gdrive-id`
2. **一鍵下載 + 前處理**

```bash
uv run python -m scripts.prepare_data --gdrive-id <YOUR_GDRIVE_ID>
# 若本機已有舊的 datasets.zip，可強制重新下載
uv run python -m scripts.prepare_data --gdrive-id <YOUR_GDRIVE_ID> --force-download
# 若 data/raw 看起來不對（很小），請強制重新解壓
uv run python -m scripts.prepare_data --gdrive-id <YOUR_GDRIVE_ID> --force-download --force
# 直接執行也可（若你偏好）
uv run python scripts/prepare_data.py --gdrive-id <YOUR_GDRIVE_ID>
```

3. **產物位置**

```
data/raw/          # 原始 CSV
data/interim/      # 合併後的中介檔
data/processed/    # 特徵/編碼後資料
artifacts/         # encoders、itemknn_artifacts.npz（線上推理）等
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

### 匯出 ItemKNN 線上推理用 artifact（.npz）

與 `stage_09_itemknn_baseline` **共用同一套資料準備邏輯**，但**不執行 LOO 評估**，只訓練 ItemKNN 並寫出後端可載入的壓縮檔。適合在跑完 `stage_04_preprocess_train`（或等效產物）後使用。

**請在 `recommender/` 目錄下執行：**

```bash
cd recommender
uv run python -m scripts.export_itemknn_artifacts --item-k 5
```

- **預設輸出**：`recommender/artifacts/itemknn_artifacts.npz`
- **檔案內容**：`neigh_items`、`neigh_sims`、`idx2item`（矩陣欄位索引 → 原始 `song_id`）、`item_k`、`format_version`
- **參數對齊**：`--item-k`、`--top-n-users` 等請與實際要部署的設定一致；可用 `--out` 指定輸出路徑。
- 若資料導致 LOO 無法切分，可加 `--auto-fallback`（行為與 `stage_09` 的 `--auto-fallback` 相同）。

線上／onboarding 推薦時：依 `idx2item` 建立 `song_id → 欄位索引`，再呼叫 `recommender/src/models/itemknn.py` 的 `recommend_from_seed_item_indices`。

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
uv run python -m scripts.export_itemknn_artifacts --item-k 5   # 匯出 .npz 供後端載入（不跑評估）
uv run python -m pipeline.stage_10_itemknn_grid --plot
uv run python -m pipeline.stage_11_mf_train --epochs 5  # 在 Colab 執行
uv run python -m pipeline.stage_12_mf_faiss_eval
uv run python -m pipeline.stage_13_popularity_baseline
```

### 一次跑完整 pipeline

```bash
uv run python -m pipeline.run_all --from-stage 00_download --to-stage 04_train
```

---

## 📚 文件

技術說明文件統一放在 [`docs/`](./docs/)：

- [`lightfm_README.md`](./docs/lightfm_README.md) — LightFM 操作手冊（安裝、訓練、評估、比較流程）
- [`db_lightfm_pipeline.md`](./docs/db_lightfm_pipeline.md) — DB → LightFM pipeline 共同骨幹設計
- [`ITEMKNN_RECOMMENDATION.md`](./docs/ITEMKNN_RECOMMENDATION.md) — ItemKNN 後端整合
- [`HISTORY_AND_LIKE_INTEGRATION.md`](./docs/HISTORY_AND_LIKE_INTEGRATION.md) — 歷史紀錄 / Like API 串接
- [`AFFINITY_SCORE_INTEGRATION.md`](./docs/AFFINITY_SCORE_INTEGRATION.md) — Affinity 分數計算與權重整合
- [`DIFF_FROM_MAIN.md`](./docs/DIFF_FROM_MAIN.md) — 分支差異紀錄

