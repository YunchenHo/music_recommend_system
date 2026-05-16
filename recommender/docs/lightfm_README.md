# LightFM 推薦演算法操作手冊

本文件整理 LightFM 在本專案的安裝、訓練、評估、比較流程。LightFM 因相依套件限制必須跑在獨立的 Python 3.11 venv（`.venv-lightfm`），與主環境（Python 3.12 / TensorFlow 等）分離。

---

## 0. 環境啟用

每次開新 terminal 都要：

```bash
cd ~/Desktop/music_recommend_system/recommender
source .venv-lightfm/bin/activate
which python    # 應指向 .venv-lightfm/bin/python
```

要離開（回主 `.venv` 跑 ItemKNN/MF 等其他 stage）：`deactivate`

### 首次安裝（重灌 / 換機器才需要）

詳細指令見 `/Users/chiwenhsu/.claude/projects/-Users-chiwenhsu-Desktop-music-recommend-system/memory/lightfm_install_py312.md`。摘要：

1. `brew install libomp`
2. `uv venv --python 3.11 .venv-lightfm`
3. 在 venv 內裝舊版 build 工具：`uv pip install "setuptools<60" wheel "cython<3" "numpy<2"`
4. 下載 lightfm 1.17 sdist、patch `setup.py`（將 `__builtins__.__LIGHTFM_SETUP__ = True` 改成 `import builtins as _b; _b.__LIGHTFM_SETUP__ = True`）
5. `uv pip install --no-build-isolation /tmp/lightfm-1.17/`
6. 再裝 `pandas tqdm pyarrow`

---

## 1. 檔案地圖

```
recommender/
├── src/models/lightfm_model.py          # 核心：LOO split、特徵建構、train、evaluate
├── pipeline/
│   ├── stage_14_lightfm_train.py        # 訓練
│   ├── stage_15_lightfm_eval.py         # 評估（append CSV）
│   └── stage_16_model_comparison.py     # 匯總比較
├── data/processed/
│   ├── train_encoded.parquet            # 【輸入】互動資料 (msno_id, song_id, target)
│   ├── complete_members.parquet         # 【輸入】user 特徵
│   ├── song_features.parquet            # 【輸入】item 特徵
│   ├── lightfm_train.parquet            # stage_14 產出：訓練切分
│   └── lightfm_test.parquet             # stage_14 產出：測試切分
├── artifacts/
│   ├── lightfm_model.pkl                # stage_14 產出：訓練好的 LightFM 物件
│   └── lightfm_dataset.pkl              # stage_14 產出：Dataset + features 矩陣
└── reports/
    ├── lightfm_metrics.csv              # stage_15 累積寫入（Date/Model/K/Recall/.../Notes）
    ├── lightfm_run.log                  # 手動 tee 的訓練 log
    └── model_comparison.csv             # stage_16 產出：四模型匯總
```

### 輸入資料前置條件

`stage_14` 跑之前要先有 `train_encoded.parquet`。本機記憶體有限就用 chunked 版：

```bash
python -m pipeline.stage_04b_train_encode_lowram \
  --train-path data/raw/kkbox_datasets/train.csv
```

---

## 2. 訓練：`stage_14_lightfm_train.py`

### 2.1 常用組合

```bash
# A. 全量（不對 user 做 top-K 過濾）
python -m pipeline.stage_14_lightfm_train \
  --epochs 10 --num-threads 1 \
  --top-k-members 0

# B. 對齊 ItemKNN 的 top-5000 user
python -m pipeline.stage_14_lightfm_train \
  --epochs 10 --num-threads 1
  # （預設 --top-k-members 5000）

# C. 純 CF 對照（驗證特徵價值）
python -m pipeline.stage_14_lightfm_train \
  --epochs 10 --num-threads 1 --no-features

# D. Smoke test（500 users, 2 epochs，~1 分鐘）
python -m pipeline.stage_14_lightfm_train \
  --epochs 2 --max-users 500 --num-threads 1
```

### 2.2 全部 CLI flag

| Flag | 預設 | 說明 |
|---|---|---|
| `--epochs` | 10 | 訓練 epoch 數 |
| `--no-components` | 128 | embedding 維度 |
| `--loss` | warp | `warp` / `bpr` / `logistic` / `warp-kos` |
| `--learning-rate` | 0.05 | adagrad 初始學習率 |
| `--max-sampled` | 10 | WARP 每次更新最多採樣幾個 negative。**值得試 30~100**，對大 catalog 改善 ranking 顯著（訓練約 3-10x 慢） |
| `--item-alpha` | 0.0 | item embedding L2 正則。過擬合時設 1e-6 |
| `--user-alpha` | 0.0 | user embedding L2 正則。同上 |
| `--num-threads` | 4 | **本機必須設 1**（no-openmp build） |
| `--top-k-members` | 5000 | 對齊 ItemKNN 的 top-K user 過濾；設 0 關閉 |
| `--min-membership-days` | 30 | top-K 過濾的會員天數門檻 |
| `--max-users` | None | 在 top-K 之後再限第一 N 個 user（smoke 用） |
| `--sample-rate` | None | 隨機抽 N% 互動（OOM 救急用） |
| `--min-pos-per-user` | 2 | 用戶要至少 N 個正樣本才納入 |
| `--top-k-artists` | 5000 | item 特徵 artist 截斷 |
| `--top-k-cities` | 30 | user 特徵 city 截斷 |
| `--no-features` | off | 關掉所有 user/item 特徵走純 CF |
| `--seed` | 42 | 隨機種子（與 MF 一致才能對比） |
| `--train-path` | `data/processed/train_encoded.parquet` | 互動資料 |
| `--members-path` | `data/processed/complete_members.parquet` | user 特徵 |
| `--songs-path` | `data/processed/song_features.parquet` | item 特徵 |
| `--model-out` | `artifacts/lightfm_model.pkl` | 模型檔輸出 |
| `--data-out` | `artifacts/lightfm_dataset.pkl` | Dataset payload 輸出 |
| `--train-out` | `data/processed/lightfm_train.parquet` | 訓練切分輸出 |
| `--test-out` | `data/processed/lightfm_test.parquet` | 測試切分輸出 |

### 2.3 特徵設計

Hybrid 模式下使用的 user / item feature tag（離散 categorical）：

**User features**（來自 `complete_members.parquet`）
- `bd_{0..6}`：年齡分群（7 bin）
- `gender_{female,male,unknown}`：性別
- `ms_{0..6}`：會員天數分群（7 bin）
- `reg_{N}`：註冊管道
- `city_{N}` / `city_other`：城市 top-K + other

**Item features**（來自 `song_features.parquet`）
- `artist_{name}` / `artist_other`：歌手 top-K + other
- `lang_{N}`：語言代碼
- `len_{0..4}`：歌曲長度分位數（5 bucket）
- `genre_{N}`：multi-label（每首歌可多個）

`--no-features` 會跳過所有特徵，走純 CF（只用 user-item 互動矩陣）。

---

## 3. 評估：`stage_15_lightfm_eval.py`

評估**最近一次訓練的模型**（讀取 `artifacts/lightfm_model.pkl`），結果以 **append** 模式寫入 `reports/lightfm_metrics.csv`，不會覆蓋舊紀錄。

### 3.1 基本

```bash
python -m pipeline.stage_15_lightfm_eval \
  --num-threads 1 \
  --notes "top-5000 對齊 ItemKNN, hybrid, epochs=10, components=128, WARP"
```

**`--notes` 一定要寫**，否則 Notes 欄位空白，未來看不出來哪行是哪次的設定。

### 3.2 全部 CLI flag

| Flag | 預設 | 說明 |
|---|---|---|
| `--notes` | `""` | 自由文字，會寫進 Notes 欄 |
| `--run-date` | `now` | 覆寫日期（補歷史紀錄時用） |
| `--eval-ks` | `"10,20"` | 用逗號分隔多個 K |
| `--num-threads` | 4 | **設 1** |
| `--batch-size` | 500 | 不影響結果，只影響速度 |
| `--model-path` | `artifacts/lightfm_model.pkl` | 要評估哪個模型 |
| `--data-path` | `artifacts/lightfm_dataset.pkl` | 對應的 dataset payload |
| `--train-path` | `data/processed/lightfm_train.parquet` | 訓練切分 |
| `--test-path` | `data/processed/lightfm_test.parquet` | 測試切分 |
| `--out-path` | `reports/lightfm_metrics.csv` | append 目標 CSV |

### 3.3 補歷史紀錄

```bash
python -m pipeline.stage_15_lightfm_eval --num-threads 1 \
  --run-date "2026-05-15 23:30:00" \
  --notes "舊版實驗：xxx"
```

---

## 4. 訓練 + 評估一條龍（建議 tmux 內跑）

```bash
NOTES="top-5000, hybrid, epochs=10, components=128, WARP"

{ time python -m pipeline.stage_14_lightfm_train --epochs 10 --num-threads 1; \
  time python -m pipeline.stage_15_lightfm_eval --num-threads 1 --notes "$NOTES"; } \
  2>&1 | tee reports/lightfm_run_$(date +%Y%m%d_%H%M).log
```

### tmux 使用

```bash
brew install tmux                # 第一次裝
tmux new -s lightfm              # 開 session
# Ctrl-B 然後 d：離開但不中斷
tmux attach -t lightfm           # 回來看
tmux ls                          # 列現有 session
```

---

## 5. 模型比較：`stage_16_model_comparison.py`

讀取所有 `reports/*_metrics.csv` 匯總成單一比較表：

```bash
# 預設輸入 / 輸出
python -m pipeline.stage_16_model_comparison

# 客製輸出位置
python -m pipeline.stage_16_model_comparison \
  --out-path reports/comparison_$(date +%Y%m%d).csv
```

**預設讀取**：
- `reports/itemknn_grid_metrics.csv`（沒有就 skip）
- `reports/mf_faiss_metrics.csv`（沒有就 skip）
- `reports/popularity_baseline.csv`（沒有就 skip）
- `reports/lightfm_metrics.csv`（沒有就 skip）

⚠️ 目前會抓 LightFM CSV 的**全部 row**，累積多次後比較表會有重複的 LightFM 列。要乾淨比較的話手動篩過 CSV，或之後加 `--lightfm-date` flag 來指定某次紀錄。

---

## 6. 查看與維護 `lightfm_metrics.csv`

```bash
# 表格化檢視
column -s, -t < reports/lightfm_metrics.csv | less -S

# 只看 K=10 的紀錄
awk -F, 'NR==1 || $3==10' reports/lightfm_metrics.csv | column -s, -t

# 按 Recall@10 排序找最佳
awk -F, 'NR==1 || $3==10' reports/lightfm_metrics.csv | sort -t, -k4 -rn -g | head

# 備份（每次重大實驗前）
cp reports/lightfm_metrics.csv reports/lightfm_metrics_backup_$(date +%Y%m%d).csv
```

CSV 欄位：`Date, Model, K, Recall, Precision, NDCG, Users_evaluated, Notes`

Excel / Numbers / VSCode 開 CSV 也可以直接編輯刪行。

---

## 7. 重要產出檔大小參考

| 檔案 | 約略大小 | 由誰產生 |
|---|---|---|
| `train_encoded.parquet` | 17 MB | `stage_04b_train_encode_lowram.py` |
| `lightfm_model.pkl` | 80+ MB | `stage_14_lightfm_train.py` |
| `lightfm_dataset.pkl` | 4 MB | 同上 |
| `lightfm_train.parquet` | ~1.5 MB | 同上 |
| `lightfm_test.parquet` | ~13 KB | 同上 |
| `lightfm_metrics.csv` | <10 KB | `stage_15_lightfm_eval.py` |

---

## 8. 觀察到的數據（記錄）

### Top-5000 vs 全量（同 epochs=10, hybrid, WARP, components=128）

| 設定 | Users 訓練 | Items | Train interactions | Recall@10 | Recall@20 | 訓練時間 | 評估時間 |
|---|---|---|---|---|---|---|---|
| 全量（top-K=0） | 12,140 | 273,405 | 2,172,109 | 0.0872 | 0.1239 | 2m 09s | 8m 00s |
| top-5000 | 5,000 | 246,708 | 1,675,830 | 0.0665 | 0.0953 | 1m 42s | 2m 51s |

**觀察**：top-K 過濾在 LightFM 反而降低指標。原因：LightFM WARP 訓練是 per-positive-pair 採樣，砍 user 等於砍訓練資料，連被保留 user 的 embedding 品質都受影響。對 ItemKNN 而言 top-K 是降噪，對 LightFM 則是失血。

公平比較 ItemKNN 的話建議跑兩組（全量 + top-5000），報告中並列。

---

## 9. 常見 troubleshoot

| 症狀 | 原因 / 解法 |
|---|---|
| `ImportError: lightfm` | 沒 activate `.venv-lightfm`：`source .venv-lightfm/bin/activate` |
| `FileNotFoundError: train_encoded.csv` | 先跑 `stage_04b_train_encode_lowram.py` |
| `FileNotFoundError: lightfm_model.pkl` | 先跑 stage_14 訓練再跑 stage_15 |
| 評估超慢（>10 min） | 確認 `--num-threads 1`；user 數太大就調 `--top-k-members` |
| `UserWarning: LightFM compiled without OpenMP` | 安裝時 OpenMP 沒接上，可忽略，只是單執行緒 |
| 想重訓但保留舊 model 不被覆蓋 | `--model-out artifacts/lightfm_model_v2.pkl --data-out artifacts/lightfm_dataset_v2.pkl` |
| `uv sync` 失敗 builds lightfm | `pyproject.toml` 不應該有 lightfm；若有就移除 |

---

## 10. 重要參數調整建議（從影響大到小）

1. `--top-k-members 0`（用全量訓練資料，最直接的指標提升手段）
2. `--epochs 15` 或 `20`（給更多時間收斂，搭配 loss 曲線觀察）
3. `max_sampled=30`（WARP 採樣負樣本上限，目前寫死在 `lightfm_model.py:train_lightfm_model`；改大可顯著改善 ranking）
4. `--no-features`（純 CF 對照組，驗證特徵是否真有幫助）
5. `item_alpha=1e-6, user_alpha=1e-6`（L2 正則；過擬合時加）
6. `--no-components 64` 或 `256`（embedding 維度）
7. `--top-k-artists 1000`（item 特徵截斷較緊，減過擬合）

每次只改一個變因、跑完寫進 `--notes`，這樣 `lightfm_metrics.csv` 才能當實驗紀錄查。
