# 與 `main` 分支差異說明（feature/itemknn-mf-pipeline）

本文件整理目前分支（`feature/itemknn-mf-pipeline`）相對 `main` 的主要差異，方便在 GitHub 上 review / 開 PR。

## 重點變更摘要

- **ItemKNN（Stage 09 / 10）**
  - **Stage 09 的評估 aggregation 對齊 notebook 最佳組合**：將評估用的 aggregation 改為 `baseline`（過去是 `normalize_seed`）。
  - **Stage 10 的預設 grid search 縮到單一最佳組合**：預設只跑 `Item_K=5`、`aggregation=baseline`、`sim_threshold=0.0`（避免一次跑 100 組造成耗時/需要手動中斷）。

- **MF + FAISS（Stage 11 / 12）**
  - 新增 MF 訓練與 FAISS 評估流程的 stage 腳本與模型函式（供 notebook/Colab 或本機環境可用時使用）。
  - README 補充：MF 訓練目前建議在 Colab 進行（避免本機 TensorFlow/Metal 相容性問題）。

- **Popularity baseline（Stage 13）**
  - 新增 popularity baseline 的 stage 與模型實作。

## 變更的檔案（相對 `main`）

以下為主要程式碼與文件變更（不含資料產物；資料夾已在 `.gitignore` 排除）：

- **文件**
  - `README.md`：更新模型階段指令與 MF/Colab 說明。

- **Pipeline（新增/更新）**
  - `pipeline/stage_10_itemknn_grid.py`：預設超參數改為只跑最佳組合。
  - `pipeline/stage_11_mf_train.py`：新增 MF 訓練 stage（輸出 `mf_model.h5` 與 train/test split）。
  - `pipeline/stage_12_mf_faiss_eval.py`：新增 MF + FAISS top‑K 評估 stage。
  - `pipeline/stage_13_popularity_baseline.py`：新增 popularity baseline stage。

- **Models（新增/更新）**
  - `src/models/itemknn.py`：Stage 09 baseline 評估 aggregation 對齊 `baseline`。
  - `src/models/mf.py`：新增 MF 資料準備、模型訓練與 FAISS 評估。
  - `src/models/popularity.py`：新增 popularity baseline 模型邏輯。

- **環境/依賴**
  - `pyproject.toml`、`uv.lock`、`.python-version`：依賴與 Python 版本設定更新（配合新增 MF/FAISS 相關套件）。

- **Notebook**
  - `專題.ipynb`：結構與輸出整理（大量 cell/output 變更）。

## 行為差異（使用者會感覺到的變動）

- **`pipeline.stage_10_itemknn_grid` 預設不再跑 100 組**  
  - 以前不帶參數會跑：5（K）×4（threshold）×5（agg）= 100 組  
  - 現在預設只跑：1 組（`k=5, sim_t=0.0, agg=baseline`）  
  - 若要恢復完整 grid search，請在 CLI 明確覆寫 `--item-k-list/--sim-thresholds/--agg-list`。

- **`pipeline.stage_09_itemknn_baseline` 的指標可能與過去不同**  
  - 因為 aggregation 從 `normalize_seed` 改為 `baseline`（與 notebook 找到的最佳組合一致）。

## 產物/資料檔（不會被 commit）

`.gitignore` 已排除以下路徑（因此不會推到 GitHub）：

- `data/`、`artifacts/`、`reports/`、`datasets.zip`、`_tmp_dataset/`、`*.parquet`

例如：`data/processed/complete_members_small.csv` 是執行時產生的資料檔，不會被 commit。

## 如何重現（快速）

（以下指令以 README 的流程為準）

```bash
uv run python -m pipeline.stage_09_itemknn_baseline --item-k 5 --reco-n 20 --auto-fallback
uv run python -m pipeline.stage_10_itemknn_grid --plot --use-all-targets
```

MF/FAISS 若本機 TensorFlow 環境不相容，請依 README 建議改在 Colab 執行 Stage 11，再將 `mf_model.h5` 帶回本機跑 Stage 12。

