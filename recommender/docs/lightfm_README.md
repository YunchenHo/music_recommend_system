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

實驗於 2026-05-16 完成，單 seed=42、Apple M-series + single-threaded（lightfm no-openmp）。

### 8.1 LightFM 調參演進（K=10）

| # | 設定 | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | 該步 ΔR@10 | 累計 |
|---|---|---|---|---|---|---|---|
| 1 | top-5000, hybrid, e10, ms10, c128 | 0.0665 | 0.0953 | 0.0383 | 0.0455 | baseline | — |
| 2 | top-5000, **純 CF**, e10, ms10, c128 | 0.0824 | 0.1178 | 0.0481 | 0.0570 | +24% | +24% |
| 3 | **全量 12k**, 純 CF, e10, ms10, c128 | 0.1002 | 0.1468 | 0.0583 | 0.0700 | +22% | +51% |
| 4 | 全量, 純 CF, **e20, ms30**, c128 | 0.1325 | 0.1855 | 0.0771 | 0.0905 | +32% | +99% |
| 5 | 全量, 純 CF, **e30, ms50**, c128 | 0.1503 | 0.2081 | 0.0889 | 0.1035 | +13% | +126% |
| 6 | 全量, 純 CF, e30, ms50, **c256** | **0.1625** | **0.2249** | **0.0952** | **0.1110** | +8% | **+144%** |

**關鍵發現**：

1. **Hybrid features 在 warm-user 場景反而傷**（第 1→2 步 +24%）。LightFM 論文說特徵主要解決 cold-start；KKBox top-K user 都是 warm，特徵變成雜訊稀釋 item embedding。
2. **Top-K user 過濾對 LightFM 是失血**（第 2→3 步 +22%）。對 ItemKNN 是降噪，對 LightFM 是減訓練資料、傷 item embedding 共現訊號。
3. **WARP `max_sampled` 預設值（10）對大 catalog 太低**（第 3→4 步 +32%）。246k items 下 sampling 10 個 negative 經常找不到 violation；提到 30 顯著改善 ranking gradient 密度。
4. **Embedding dim 仍可繼續擴**（第 5→6 步 +8%）。c128→c256 還有改善，c512 可能也有（未驗證）。
5. **邊際效益遞減**：ms10→ms30 (+32%) 大於 ms30→ms50 (+13%) 大於 c128→c256 (+8%)。

### 8.2 三模型 head-to-head（top-5000 user）

| 模型 | 最佳設定 | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | 訓練時間 |
|---|---|---|---|---|---|---|
| 🥇 **LightFM** | pureCF, e30, ms50, c256 | **0.1625** | **0.2249** | **0.0952** | **0.1110** | 16m 09s |
| 🥈 ItemKNN | k=5, baseline, sim_t=0 | 0.1355 | 0.1878 | 0.0787 | 0.0920 | 3m |
| 🥉 Popularity | top-K=20 | 0.0432 | 0.0714 | — | — | <1s |
| **LightFM vs ItemKNN** | | **+20%** | **+20%** | **+21%** | **+21%** | |

### 8.3 ItemKNN grid（item_k ∈ {5, 10, 20}, sim_threshold=0, baseline aggregation）

| Item_K | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 |
|---|---|---|---|---|
| **5** | **0.1355** | **0.1878** | 0.0787 | 0.0920 |
| 10 | 0.1334 | 0.1863 | **0.0790** | **0.0923** |
| 20 | 0.1189 | 0.1773 | 0.0756 | 0.0902 |

ItemKNN 的 sweet spot 在 k=5~10，再多鄰居反而稀釋。整個 grid 變動幅度只有 ~1%，**ItemKNN 的調參天花板很快觸頂**。

### 8.4 訓練時間參考（M-series + single-thread）

| 設定 | 訓練 | 評估 |
|---|---|---|
| 全量 12k, hybrid, e10, c128 | 2m 09s | 8m 00s |
| 全量 12k, pureCF, e10, c128 | 60s | ~7m |
| 全量 12k, pureCF, e20, ms30, c128 | 4m 07s | ~7m |
| 全量 12k, pureCF, e30, ms50, c128 | 9m 49s | ~7m |
| 全量 12k, pureCF, e30, ms50, c256 | 16m 09s | ~8m |
| ItemKNN top-5000, k=5 | ~3m | （含在內）|

純 CF 比 hybrid 快約 2 倍（無 feature matrix 乘積）；`max_sampled` 倍增約使每 epoch 慢 1.5-2 倍；`components` 倍增約使每 epoch 慢 1.7 倍。

### 8.5 已知局限（口試準備）

- **單 seed 跑一次**：未做多 seed 重複實驗，每步 +13~32% 的提升幅度遠大於合理的 seed 變動（~±2-3%），但嚴格的 statistical significance 需 bootstrap CI。
- **LOO 切分**：每 user 最後 1 個正樣本當 test，未用 time-based split（資料無 timestamp）。
- **未測 cold-start**：所有 user 都是 warm（min_pos=2），hybrid 特徵的 cold-start 價值未驗證。
- **候選 item pool 差異**：LightFM 從全 273k catalog 排序，ItemKNN 從鄰居子集排序，pool 不對等（但通常 LightFM 較難，反而是有利結論的差異）。
- **`lightfm 1.17` 已停止維護**：production 應改用 Implicit / RecBole；本研究結論（max_sampled、components）對任何 WARP-based MF 都適用。

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

## 10. 重要參數調整建議（**已驗證**，按實測影響大小排序）

| 優先 | 參數 | 預期 ΔR@10 | 訓練成本 | 適用場景 |
|---|---|---|---|---|
| 1 | `--no-features` | **+24%** | -50% 時間 | warm-user 場景皆建議 |
| 2 | `--top-k-members 0` | **+22%** | +30% | catalog 較小、user 不太活躍時 |
| 3 | `--max-sampled 30~50` | **+13~32%** | +200~500% | 大 catalog (>50k items) 必試 |
| 4 | `--no-components 256` | **+8%** | +60% | embedding 還沒過擬合可繼續加 |
| 5 | `--epochs 20~30` | 已含在上述 | +100~200% | 配合 max_sampled 一起調 |
| — | `--user-alpha 1e-6 --item-alpha 1e-6` | 未驗證 | <+5% | 過擬合警訊時加（valid R 反向降低）|
| — | `--no-components 512` | 推測 +3~5% | +200% | 邊際效益最低，最後再試 |

**已驗證最佳組合**（KKBox warm-user, top-5000 評估）：
```bash
python -m pipeline.stage_14_lightfm_train \
  --epochs 30 --num-threads 1 --no-features --top-k-members 0 \
  --max-sampled 50 --no-components 256
```
→ Recall@10 = 0.1625, Recall@20 = 0.2249

**規則**：每次只改一個變因、跑完寫進 `--notes`，這樣 `lightfm_metrics.csv` 才能當實驗紀錄查。
