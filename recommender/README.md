# recommender

KKBOX 音樂推薦系統的**離線 ML pipeline**：資料前處理、特徵工程、模型訓練 / 評估 / 比較。
本層是獨立的 Python 子專案（自帶 `pyproject.toml` / `uv.lock` / `.venv` / `Dockerfile`）。

> 這份 README 只做導覽。完整的環境設定與 pipeline 操作見**專案最上層 `README.md`**；
> LightFM 的安裝 / 訓練 / 調參 / 比較細節見 [`../docs/lightfm_README.md`](../docs/lightfm_README.md)。

---

## 快速開始

```bash
# 在專案最上層啟用共用 venv（ItemKNN / MF / Popularity / LightFM 都跑這個）
cd ..
source .venv/bin/activate

# 回到本層，單獨跑某個 stage（皆為 python -m 模組）
cd recommender
PYTHONPATH=. python -m pipeline.stage_14_lightfm_train --help
```

`python main.py` 等同 `pipeline.run_all`（依序跑完整 pipeline）。

---

## 目錄結構

```
pipeline/      # 各 stage 進入點（CLI），config.py / io.py / run_all.py 為共用基礎
src/
├── preprocess/   # members / songs / train 前處理
├── features/     # 特徵工程
├── models/       # itemknn / mf / popularity / lightfm_model 核心邏輯
├── coldstart/    # 冷啟動情境的資料切分、評估、helper
└── data/         # 資料載入
data/          # processed/ 等執行時產物（.gitignore 排除）
artifacts/     # 訓練好的模型 / dataset payload（.gitignore 排除）
reports/       # 評估指標 CSV、log、比較表
```

---

## Pipeline stage 地圖

| 階段 | Stage | 說明 |
|---|---|---|
| 前處理 | `stage_00_download` → `01_members` / `02_songs` / `03_feature_eng` / `04_preprocess_train` | 下載與清理、特徵工程、訓練資料編碼 |
| | `stage_04b_train_encode_lowram` | 低記憶體版 train 編碼（本機建議用這個） |
| | `stage_04c_export_db_subset` | 匯出給後端 DB 用的子集 CSV |
| ItemKNN | `stage_09_itemknn_baseline` / `stage_10_itemknn_grid` | baseline 評估 / grid search |
| MF + FAISS | `stage_11_mf_train`（Colab）/ `stage_12_mf_faiss_eval` | TensorFlow MF 訓練放 Colab，FAISS top-K 評估 |
| Popularity | `stage_13_popularity_baseline` | 熱門度 baseline |
| LightFM | `stage_14_lightfm_train` / `stage_15_lightfm_eval` | 訓練 / 評估（二切 LOO） |
| | `stage_17_lightfm_greedy` | greedy 調參（三切 train/val/test，見 lightfm 手冊 §5） |
| 比較 | `stage_16_model_comparison` | 匯總各模型成單一比較表 |
| 冷啟動 | `stage_cs00_make_splits` → `cs01`~`cs04` → `stage_cs05_compare` | 情境切分、各模型冷啟動評估、比較 |
| DB | `stage_db00_load_from_db` | 從資料庫載入（prod 整合用） |

每個 stage 都吃 `--help`，輸出統一寫進 `reports/`。

---

## 注意事項

- **本機可全量跑**：ItemKNN / Popularity / **LightFM**（純 Python）。
- **本機不要跑**：MF / TensorFlow 訓練（`stage_11`）—— 放 Colab / 雲端。
- LightFM 本機請帶 `--num-threads 1`（no-OpenMP build）。
</content>
