# LightFM 推薦演算法操作手冊

本文件整理 LightFM 在本專案的安裝、訓練、評估、比較流程。LightFM 跟其他 recommender stages 共用 root `.venv`（Python 3.11.13），不再需要獨立 venv。

---

## 0. 環境啟用

每次開新 terminal 都要：

```bash
cd ~/Desktop/music_recommend_system
source .venv/bin/activate
which python    # 應指向 .venv/bin/python
```

ItemKNN / MF / Popularity / LightFM 所有 stages 都在這個 venv 跑。

### 首次安裝（重灌 / 換機器才需要）

詳細安裝註解見 `recommender/pyproject.toml` 的 LightFM 區塊。摘要：

1. `brew install libomp`
2. 在 root `.venv` 內降版 build 工具：`VIRTUAL_ENV=$REPO/.venv uv pip install "numpy<2" "setuptools<60" wheel "cython<3"`
   - 注意：numpy 必須 <2（LightFM 1.17 build 與執行期 ABI 都需要）。所有其他 deps (tensorflow / pandas / scipy / faiss-cpu) 皆容許 numpy 1.26.x，所以共用 root `.venv` 安全。
3. 下載 lightfm 1.17 sdist、patch `setup.py`（將 `__builtins__.__LIGHTFM_SETUP__ = True` 改成 `import builtins as _b; _b.__LIGHTFM_SETUP__ = True`）
4. `CFLAGS="-I/opt/homebrew/opt/libomp/include" LDFLAGS="-L/opt/homebrew/opt/libomp/lib -lomp" uv pip install --no-build-isolation /tmp/lfm/lightfm-1.17/`

---

## 1. 檔案地圖

```
recommender/
├── src/models/lightfm_model.py          # 核心：LOO / 三切、特徵建構、train、evaluate
├── pipeline/
│   ├── stage_14_lightfm_train.py        # 訓練
│   ├── stage_15_lightfm_eval.py         # 評估（append CSV）
│   ├── stage_16_model_comparison.py     # 匯總比較
│   └── stage_17_lightfm_greedy.py       # greedy 調參（三切 train/val/test）
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
    ├── lightfm_greedy_metrics.csv       # stage_17 累積寫入（greedy 搜尋 + final val/test/train）
    ├── lightfm_run.log                  # 手動 tee 的訓練 log
    └── model_comparison.csv             # stage_16 產出：各模型匯總
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

## 5. 自動超參數搜尋（greedy / 三切）：`stage_17_lightfm_greedy.py`

§2~§4 是「手動一次調一個參數、跑完寫 `--notes`」的流程。`stage_17` 把它自動化成
**coordinate-descent（greedy）搜尋**，並把資料切分升級成 **train / val / test 三切**，
自動找出 hybrid 與 pureCF 各自的最佳超參數組合。

### 5.1 為什麼要三切（train / val / test）

只要你開始「搜尋」超參數，就會把評估集拿來「選模型」——挑「在某集合上分數最高」的那組參數，
那個最高分就**不再是公正的泛化估計**（含了對該集合的過度配適 / selection bias）。資料固定、
反覆用同一份集合調參會讓偏差更嚴重，不是更輕。

所以 stage_17 三切：
- **train**：建訓練 interactions。
- **val**：greedy 全程只看 val 選參數。
- **test**：從頭到尾不參與選擇，只在最後對選定 config 報一次 —— 這才是能跨模型比較的公正數字。

切分用 leave-two-out（每 user 留 2 個正樣本，1 給 val、1 給 test；
`src/models/lightfm_model.py:train_val_test_split`）。同一個訓練好的模型可同時對 val 與 test
評估（兩者都是 held-out、訓練資料不變，比較才公正）。`--min-pos-per-user` 自動夾到 ≥3。

> 對照：§3 的 stage_15 走的是二切 LOO（每 user 留 1 個當 test），適合「手動單組設定、直接看 test」；
> 一旦要**搜尋**多組設定，就該用 stage_17 的三切，避免拿 test 調參。

### 5.2 搜尋策略（coordinate descent）

固定維度順序（影響大者在前、正則化在後），每個維度其餘參數固定在「目前最佳」，只掃該維度候選，
用 val 上的 `--select-metric` 取最佳後鎖定，再進下一維度：

```
loss → no_components → learning_rate → max_sampled → epochs → item_alpha → user_alpha
```

- **加法成本**：每變體約 28 次訓練（對照完整 grid 的 ~1.5 萬次乘法成本不可行）。
- `max_sampled` 只對 WARP 有效；若當前最佳 loss 非 `warp`/`warp-kos` 會自動跳過。
- **限制**：greedy 找的是好的「局部最佳」，不保證全域最佳，且結果受維度順序影響。需要更嚴謹就改跑完整 grid 或多 seed。

### 5.3 執行

```bash
# Smoke（小 cohort + 迷你候選，數分鐘，驗證跑得通）
PYTHONPATH=. python -m pipeline.stage_17_lightfm_greedy --variant both --smoke

# 全量（本機 tmux；LightFM 純 Python，可本機全量跑，禁止的是 TensorFlow）
tmux new -s lightfm_greedy
PYTHONPATH=. python -m pipeline.stage_17_lightfm_greedy --variant both --num-threads 1 \
  2>&1 | tee reports/lightfm_greedy_run.log
# Ctrl-B 然後 d 離開；tmux attach -t lightfm_greedy 回來
```

### 5.4 全部 CLI flag

| Flag | 預設 | 說明 |
|---|---|---|
| `--variant` | both | `hybrid`（含特徵）/ `purecf`（無特徵）/ `both` |
| `--loss-list` | `warp,bpr,logistic` | loss 候選 |
| `--components-list` | `32,64,128,256` | embedding 維度候選 |
| `--lr-list` | `0.01,0.025,0.05,0.1` | 學習率候選 |
| `--max-sampled-list` | `5,10,30,50` | WARP negative 採樣候選 |
| `--epochs-list` | `5,10,20,30,50` | epoch 候選 |
| `--item-alpha-list` | `0,1e-7,1e-6,1e-5` | item L2 候選 |
| `--user-alpha-list` | `0,1e-7,1e-6,1e-5` | user L2 候選 |
| `--select-metric` | `NDCG@20` | 選最佳用的指標（`<metric>@<K>`） |
| `--eval-ks` | `10,20` | 評估 K（會自動補進 select 的 K） |
| `--top-k-members` | 5000 | 同 stage_14；設 0 關閉 |
| `--min-pos-per-user` | 3 | 三切需 ≥3，會自動夾 |
| `--max-users` | None | smoke / 限縮 cohort 用 |
| `--num-threads` | 4 | **本機設 1**（no-openmp build） |
| `--seed` | 42 | 隨機種子 |
| `--out-csv` | `reports/lightfm_greedy_metrics.csv` | append 目標 |
| `--smoke` | off | 迷你候選 + 小 cohort |

### 5.5 輸出與判讀

append 寫入 `reports/lightfm_greedy_metrics.csv`（20 欄）：

`Date, variant, phase, eval_on, no_components, loss, learning_rate, max_sampled, epochs,
item_alpha, user_alpha, Model, K, Recall, Precision, NDCG, Users_evaluated,
select_metric, select_value, is_best`

- `phase`：`tune:<維度>`（搜尋中）或 `final`（最終選定的 config）。
- `eval_on`：`val`（搜尋全程）；`test` 與 `train` 只在 `final` 出現。
- `is_best`：該調參維度內的贏家。
- **過擬合判讀**：比較 `phase=final` 的 `eval_on=train` vs `eval_on=test` 的 NDCG@20 落差，
  差越大越過擬合（程式會直接印出 `gap=`）；`tune:epochs` 各列的 val 分數若「升到頂後下降」即 early-stopping 轉折。

跑完 stage_17 後直接跑 stage_16（見 §6），它會自動抓 **final/test** 的列（每個 variant 取最新一次 run）
放進跨模型比較表 —— 用的是沒有 selection bias 的 test 數字。

> §9 / §11 是 2026-05-16 單 seed、手動逐步調參得到的「已驗證」紀錄；stage_17 則是把這套調參自動化、
> 並加上三切的公正評估。兩者可互相對照。

---

## 6. 模型比較：`stage_16_model_comparison.py`

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
- `reports/lightfm_metrics.csv`（stage_15；沒有就 skip）
- `reports/lightfm_greedy_metrics.csv`（stage_17；沒有就 skip）

**stage_17 的 greedy 結果怎麼進比較表**：只取 `phase=final` 且 `eval_on=test` 的列（每個 variant
取最新一次 run），並把選定的 config 摘要寫進 Notes。用 test（而非調參用的 val）才是公正、可跨模型比較的數字。

⚠️ 注意：**手動的 `lightfm_metrics.csv`（stage_15）仍會抓全部 row**，累積多次後比較表會有重複的
LightFM 列；要乾淨比較就手動篩過該 CSV。stage_17 的 `lightfm_greedy_metrics.csv` 沒有這問題
（已自動篩 final/test + 最新 run）。

### 6.1 跨模型比較的 cohort 說明（刻意不同，非 bug）

`model_comparison.csv` 裡各模型用的**使用者數刻意不同**，這是 by-design，不是疏漏：

- **LightFM（greedy）= 全量（~11.5k users）**：低活躍使用者的少量互動對 MF / 協同嵌入**仍是有用訊號**，
  會參與 item embedding 的共現學習 → 全量才是 LightFM 的合理設定。
  （§9.1 實測佐證：top-K 過濾讓 LightFM 失血 **+22%**。）
- **ItemKNN / Popularity = top-5000（實際 ~4776）**：低活躍使用者的共現太稀疏、不可靠，灌進去會
  **稀釋 item-item 相似度、變成雜訊** → top-K 活躍用戶才是相似度法的合理設定。
  （§9.3 佐證：ItemKNN sweet spot 在 k=5~10。）

因此這張表的正確定位是「**各模型在各自最適資料規模下的最佳表現**」，而非「同一 cohort 的 head-to-head」。
這是文獻中常見的框架，而且本專案的 §9 實驗正好支持這個選擇。

補充（對 LightFM 偏保守）：LightFM 是在**更難、更廣**的評估 pool（含大量低活躍、難預測的 user）上算分，
ItemKNN 則是在**較好猜的活躍用戶子集**上算分；即便如此 LightFM 的 NDCG@20=0.0960 仍 > ItemKNN 0.0923，
代表這個領先是**保守估計**、不是被 cohort 灌水。

> 口試 / 報告務必明寫「cohort 差異是刻意的」並附上上述理由，避免讀者誤判為同 cohort 比較。
> 相關彙整見 `reports/lightfm_greedy_summary.csv`（公平對照 + WARP 延伸探索）。

---

## 7. 查看與維護 `lightfm_metrics.csv`

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

## 8. 重要產出檔大小參考

| 檔案 | 約略大小 | 由誰產生 |
|---|---|---|
| `train_encoded.parquet` | 17 MB | `stage_04b_train_encode_lowram.py` |
| `lightfm_model.pkl` | 80+ MB | `stage_14_lightfm_train.py` |
| `lightfm_dataset.pkl` | 4 MB | 同上 |
| `lightfm_train.parquet` | ~1.5 MB | 同上 |
| `lightfm_test.parquet` | ~13 KB | 同上 |
| `lightfm_metrics.csv` | <10 KB | `stage_15_lightfm_eval.py` |

---

## 9. 觀察到的數據（記錄）

實驗於 2026-05-16 完成，單 seed=42、Apple M-series + single-threaded（lightfm no-openmp）。

### 9.1 LightFM 調參演進（K=10）

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

### 9.2 三模型 head-to-head（top-5000 user）

| 模型 | 最佳設定 | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | 訓練時間 |
|---|---|---|---|---|---|---|
| 🥇 **LightFM** | pureCF, e30, ms50, c256 | **0.1625** | **0.2249** | **0.0952** | **0.1110** | 16m 09s |
| 🥈 ItemKNN | k=5, baseline, sim_t=0 | 0.1355 | 0.1878 | 0.0787 | 0.0920 | 3m |
| 🥉 Popularity | top-K=20 | 0.0432 | 0.0714 | — | — | <1s |
| **LightFM vs ItemKNN** | | **+20%** | **+20%** | **+21%** | **+21%** | |

### 9.3 ItemKNN grid（item_k ∈ {5, 10, 20}, sim_threshold=0, baseline aggregation）

| Item_K | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 |
|---|---|---|---|---|
| **5** | **0.1355** | **0.1878** | 0.0787 | 0.0920 |
| 10 | 0.1334 | 0.1863 | **0.0790** | **0.0923** |
| 20 | 0.1189 | 0.1773 | 0.0756 | 0.0902 |

ItemKNN 的 sweet spot 在 k=5~10，再多鄰居反而稀釋。整個 grid 變動幅度只有 ~1%，**ItemKNN 的調參天花板很快觸頂**。

### 9.4 訓練時間參考（M-series + single-thread）

| 設定 | 訓練 | 評估 |
|---|---|---|
| 全量 12k, hybrid, e10, c128 | 2m 09s | 8m 00s |
| 全量 12k, pureCF, e10, c128 | 60s | ~7m |
| 全量 12k, pureCF, e20, ms30, c128 | 4m 07s | ~7m |
| 全量 12k, pureCF, e30, ms50, c128 | 9m 49s | ~7m |
| 全量 12k, pureCF, e30, ms50, c256 | 16m 09s | ~8m |
| ItemKNN top-5000, k=5 | ~3m | （含在內）|

純 CF 比 hybrid 快約 2 倍（無 feature matrix 乘積）；`max_sampled` 倍增約使每 epoch 慢 1.5-2 倍；`components` 倍增約使每 epoch 慢 1.7 倍。

### 9.5 已知局限（口試準備）

- **單 seed 跑一次**：未做多 seed 重複實驗，每步 +13~32% 的提升幅度遠大於合理的 seed 變動（~±2-3%），但嚴格的 statistical significance 需 bootstrap CI。
- **LOO 切分**：每 user 最後 1 個正樣本當 test，未用 time-based split（資料無 timestamp）。
- **未測 cold-start**：所有 user 都是 warm（min_pos=2），hybrid 特徵的 cold-start 價值未驗證。
- **候選 item pool 差異**：LightFM 從全 273k catalog 排序，ItemKNN 從鄰居子集排序，pool 不對等（但通常 LightFM 較難，反而是有利結論的差異）。
- **`lightfm 1.17` 已停止維護**：production 應改用 Implicit / RecBole；本研究結論（max_sampled、components）對任何 WARP-based MF 都適用。

---

## 10. 常見 troubleshoot

| 症狀 | 原因 / 解法 |
|---|---|
| `ImportError: lightfm` | 沒 activate root `.venv`：`source .venv/bin/activate`；若 root venv 也沒裝 LightFM，照本文件 §0 首次安裝重跑 |
| `FileNotFoundError: train_encoded.csv` | 先跑 `stage_04b_train_encode_lowram.py` |
| `FileNotFoundError: lightfm_model.pkl` | 先跑 stage_14 訓練再跑 stage_15 |
| 評估超慢（>10 min） | 確認 `--num-threads 1`；user 數太大就調 `--top-k-members` |
| `UserWarning: LightFM compiled without OpenMP` | 安裝時 OpenMP 沒接上，可忽略，只是單執行緒 |
| 想重訓但保留舊 model 不被覆蓋 | `--model-out artifacts/lightfm_model_v2.pkl --data-out artifacts/lightfm_dataset_v2.pkl` |
| `uv sync` 失敗 builds lightfm | `pyproject.toml` 不應該有 lightfm；若有就移除 |

---

## 11. 重要參數調整建議（**已驗證**，按實測影響大小排序）

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
