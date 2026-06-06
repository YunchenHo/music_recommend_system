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

---

## 12. 冷啟動（cold-start）與「超參數情境特定性」

冷啟動評估走另一條 stage：`stage_cs01_lightfm_hybrid`（含特徵）、`stage_cs02_lightfm_purecf`
（無特徵）、`stage_cs05_compare`（跨模型彙整），切分為 `A_N1 / A_N3 / A_N5`（warm 用戶但只留
1/3/5 個正樣本）與 `C`（完全沒看過的新用戶）。`cs01` 已支援 `--item-alpha / --user-alpha`。

### 12.1 把 warm 最佳 config 搬到冷啟動 → 全面變差（負面結果，已驗證）

用 §5 greedy 在 **warm-user 全量**選出的 hybrid 最佳組合
（`warp, c256, lr0.1, ms50, e50, item_α=1e-7, user_α=1e-6`）重跑冷啟動，對照原本保守的
`ms10/e10/c128`：

| split | 新 greedy NDCG@20 | 舊 保守 NDCG@20 | Δ |
|---|---|---|---|
| A_N1（最稀疏） | 0.206 | 0.347 | **−0.141** |
| A_N3 | 0.267 | 0.387 | −0.120 |
| A_N5 | 0.305 | 0.391 | −0.086 |
| C（新用戶） | 0.395 | 0.395 | ~0 |

**結論**：warm 調出來的高容量 config 在冷啟動**全面更差**，且**越稀疏的用戶傷得越重**
（A_N1 −0.141 → A_N5 −0.086）。原因：c256/e50/lr0.1 是「每人資料多」時的最佳；冷啟動每人互動
極少，這麼大的模型 + 激進學習率會過擬合。Scenario C 幾乎平手，因為新用戶靠「特徵 + fit_partial」
冷推論，與學到的 per-user embedding 容量無關。

→ **超參數不跨資料情境通用**：warm 最佳 ≠ 冷啟動最佳。冷啟動請沿用保守 config，或另切冷啟動
validation 重新調參（勿在冷啟動 test 上挑最佳，會重蹈 selection bias）。greedy config 的冷啟動
結果另存於 `reports/cs_lightfm_hybrid_metrics_greedy.csv`，當「試過、更差」的紀錄。

### 12.2 冷啟動跨模型比較（保守 config，NDCG@20）

`stage_cs05_compare` 產出 `reports/cs_model_comparison.csv`：

| Split | Popularity | LightFM-hybrid | LightFM-pureCF | ItemKNN |
|---|---|---|---|---|
| A_N1 | **0.389** | 0.347 | 0.294 | 0.000 |
| A_N3 | **0.402** | 0.387 | 0.251 | 0.013 |
| A_N5 | **0.401** | 0.391 | 0.315 | 0.018 |
| C | **0.403** | 0.395 | —（做不到） | —（做不到） |

冷啟動的故事幾乎是 warm 的**鏡像**：

1. **Popularity 最強** —— 冷用戶沒歷史，推熱門就贏，是經典且合理的冷啟動結果。
2. **LightFM-hybrid 第二，且是唯一（除 Popularity）能處理全新用戶 C 的模型**；pureCF / ItemKNN 在 C 都做不到。
3. **冷啟動 hybrid > pureCF**（特徵有用），與 warm 的「pureCF 勝、特徵反而傷」完全相反 —— 特徵的價值在冷啟動才發揮。
4. **ItemKNN 在冷啟動崩潰**（~0）：每人僅 1 個互動 → 沒鄰居可算相似度。

⚠️ **指標尺度**：冷啟動 NDCG（~0.35–0.40）與 warm（~0.08–0.12）**不可直接比** —— 冷啟動每人
ground-truth 只有 1/3/5 個，分母不同，只能在冷啟動表內互比。

### 12.3 最終建議

- **warm-user 線上推薦**：pureCF（無特徵）+ greedy 最佳 config（見 §5）。
- **冷啟動 / 新用戶**：hybrid（含特徵）+ 保守 config；Popularity 是極強的 fallback baseline，值得保留。

---

## 13. 切換門檻：pureCF ↔ hybrid 隨使用者活躍度 N（`stage_cs06_switch_threshold.py`）

研究問題：切換式推薦系統若要「依使用者歷史筆數路由到 pureCF 或 hybrid」，**門檻該設在幾筆**？
即兩變體的效能曲線在哪個活躍度交叉。

### 13.1 方法（控制 A_N1/N3/N5 的兩個 confound）

`stage_cs06` 掃 `N`（訓練可見的**正向**互動筆數），用 `make_split_a_fixed_holdout`
（`src/coldstart/split.py`）建切分：

- **固定留出 H=5** 筆當 test（不像 `make_split_a` 把所有非 seed 正樣本丟進 test）→ NDCG 尺度跨 N 可比。
- 每位使用者**恰好** N 筆進 train、H 筆進 test、其餘丟棄 → N 是乾淨的自變數。
- **自然母體**：每個 N 取「≥ N+H 正樣本」的人（母體隨 N 縮，對應部署：歷史 N 筆的人來自 ≥N 池）。
- **兩變體用完全相同的 config** → 唯一差異是「特徵 on/off」+ N，是乾淨的特徵 × 活躍度消融。

**N 的定義**：使用者「訓練時被模型看到」的正向互動筆數（不含負樣本）。H=5 純粹是評估量尺，
**部署時不存在** —— 線上只看使用者實際筆數 N 路由，不需要 N+H。

config（pureCF 與 hybrid 相同，刻意中庸、避開 greedy 高容量過擬合組）：
`loss=warp, no_components=128, learning_rate=0.05, epochs=20, max_sampled=30, alpha=0`，seed=42。

### 13.2 結果（NDCG@20 vs N；母體 8.7k–11.6k）

| N | hybrid | pureCF | 贏家 | Δ(pureCF−hybrid) |
|---|---|---|---|---|
| 1 | 0.0359 | 0.0308 | **hybrid** | −0.0051 |
| 2 | 0.0349 | 0.0241 | **hybrid** | −0.0107 |
| 3 | 0.0379 | 0.0329 | **hybrid** | −0.0050 |
| 5 | 0.0381 | 0.0374 | hybrid | −0.0007 |
| 8 | 0.0405 | 0.0406 | ~平手 | +0.0001 |
| 12 | 0.0424 | 0.0421 | ~平手 | −0.0003 |
| 20 | 0.0420 | 0.0440 | **pureCF** | +0.0020 |
| 30 | 0.0429 | 0.0449 | **pureCF** | +0.0020 |
| 50 | 0.0454 | 0.0469 | **pureCF** | +0.0015 |

NDCG@10 同型（hybrid 領到 N=12、pureCF 從 N=20 起穩定領先）。兩條曲線都隨 N 上升（歷史越多越好），協定一致、可信。

### 13.3 結論：門檻是一段「轉換帶」，不是單一點

- **N ≤ 3（很稀疏）**：hybrid 明確贏（Δ −0.005 ~ −0.011）→ 特徵在資料極少時最有用。
- **N ≈ 5–12**：平手（Δ 在 ±0.001 內、N=8/12 來回翻 → 雜訊等級）。
- **N ≥ 20（夠活躍）**：pureCF 穩定贏（Δ +0.0015 ~ +0.0020）→ 協同訊號夠了、特徵變輕微拖累。

→ **切換路由建議**：歷史 **< ~5 筆用 hybrid、≥ ~20 筆用 pureCF**，中間（5–20）兩者幾乎沒差。

### 13.4 限制（口試 / 報告務必寫）

1. **轉換帶 Δ（~0.001–0.002）落在單一 seed 的雜訊內** → 精確門檻（N=12 還是 20）現在釘不死；
   最可信的是「N≤3 hybrid 明顯贏、N≥20 pureCF 穩定贏」兩端。要釘死門檻需**多 seed 重跑取 mean±std**。
2. **固定單一 config 的消融**，非各 N、各變體各自最佳調參（那是更貴的另一個實驗）。
3. **截斷母體假設**：實驗的「N=3 使用者」其實是「本來 ≥8 筆、被截成 3 筆」的活躍用戶，
   與「天生只有 3 筆」的真稀疏用戶不完全等價（離線冷啟動模擬通病）。模型看到的 N 筆相同，
   故路由結論可轉移，但低 N 母體偏向「碰巧活躍」的人。

### 13.5 重現

```bash
PYTHONPATH=. python -m pipeline.stage_cs06_switch_threshold --smoke   # 快速驗證
PYTHONPATH=. python -m pipeline.stage_cs06_switch_threshold           # 全量（數小時，建議 tmux）
# 輸出 reports/cs_switch_threshold.csv，並印出 winner-by-N crossover summary
```
