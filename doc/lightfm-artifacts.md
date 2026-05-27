# LightFM Artifacts

以下 artifact 不納入版本控制（檔案過大），需要自行在本地產生：

- `recommender/artifacts/lightfm_purecf.npz` — Pure CF 模式的 item embeddings
- `recommender/artifacts/lightfm_hybrid.npz` — Hybrid 模式，含 user feature embeddings

## 前置條件

- 需要在 recommender container 內執行（已安裝 `lightfm` 套件）
- 資料庫中需有足夠的使用者互動資料

## 產生步驟

### Step 1: 從 Backend 匯出訓練資料

```bash
cd backend
python manage.py export_for_lightfm --output-dir ../data/db_processed
```

### Step 2: 訓練 LightFM 模型

在 recommender container 內執行：

```bash
cd recommender
python pipeline/stage_db01_lightfm_train.py
```

預設讀取 `../data/db_processed`，可用 `--dir` 指定其他路徑。

### Step 3: 匯出 Serving Artifacts

```bash
cd recommender

# Pure CF
python scripts/export_lightfm_artifacts.py \
    --model artifacts/lightfm_model.pkl \
    --dataset artifacts/lightfm_dataset.pkl \
    --output artifacts/lightfm_purecf.npz

# Hybrid
python scripts/export_lightfm_artifacts.py --hybrid \
    --model artifacts/lightfm_hybrid_model.pkl \
    --dataset artifacts/lightfm_hybrid_dataset.pkl \
    --output artifacts/lightfm_hybrid.npz
```

完成後 backend 即可載入這兩個 `.npz` 進行線上推理。
