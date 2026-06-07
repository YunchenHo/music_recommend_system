# 冷啟動 Pipeline 實作 Walkthrough

這份文件解釋冷啟動實驗的 **程式邏輯與資料流**——給看過 [`experiment_summary.md`](./experiment_summary.md) 結果、但想理解「code 怎麼跑出來的」的人看。

- 想知道**結果**：看 [`experiment_summary.md`](./experiment_summary.md)
- 想知道**研究方法 / Quickstart**：看 [`coldstart_research.md`](./coldstart_research.md)
- 想知道**程式如何實作**：就是本檔

---

## 1. 整體資料流

```
recommender/data/processed/train_encoded.parquet  (KKBOX 4.2M rows)
                    │
                    ▼
       pipeline/stage_cs00_make_splits.py
                    │
   ┌────────────┬────┴────────┬───────────────┐
   ▼            ▼             ▼               ▼
A_N1 split   A_N3 split   A_N5 split      C split
(留 1 筆     (留 3 筆     (留 5 筆        (1000 個 user
 進 train)    進 train)    進 train)       完全 hold out)

每組 split 輸出：cs_<split>_train.parquet
              cs_<split>_test.parquet
              cs_<split>_useridx.json   ← {raw_msno: encoded_idx}
              cs_<split>_itemidx.json   ← {raw_song: encoded_idx}
（C 額外多一個 cs_C_test_users.json）

                    │
   ┌────────────────┼────────────────┬──────────────┐
   ▼                ▼                ▼              ▼
stage_cs01      stage_cs02       stage_cs03    stage_cs04
LightFM-hybrid  LightFM-pureCF   ItemKNN       Popularity
(A + C)         (A only)         (A only)      (A + C)

每個 stage 輸出 cs_<model>_metrics.csv（long format，append 模式）
schema: Date, Model, K, Recall, Precision, NDCG, Users_evaluated, Notes

   └────────────────┴────────────────┴──────────────┘
                    │
                    ▼
            pipeline/stage_cs05_compare.py
                    │
                    ▼
       reports/cs_model_comparison.csv  (dedup → 最新一筆每 model+K+split)
                    │
                    ▼
            scripts/plot_coldstart.py
                    │
                    ▼
       reports/cs_figures/{ndcg, recall, ablation}_at_K.png
```

設計重點：
- **stage 之間透過 parquet / CSV 接力**，stage 自己獨立可重跑
- **id 編碼 (useridx/itemidx) 用 JSON 持久化**，下游 stage 直接 load 即可（不需重新 encode）
- **metrics CSV 用 append + dedup**，保留歷史 run 比較用

---

## 2. 工具層模組（`recommender/src/coldstart/`）

### 2.1 `split.py` — 切分邏輯

兩個函數負責產出 cold-start 訓練 / 測試集：

```python
make_split_a(train_encoded, n_seed)        # Scenario A：留前 N 筆當 train
make_split_c(train_encoded, n_test_users)  # Scenario C：整批 user hold out
```

**為什麼 useridx / itemidx 要分別產出？**

下游 stage（特別是 LightFM）需要把 raw msno_id / song_id 對應到 0-based 整數 index 才能塞進 sparse matrix。把這個 mapping 跟 split 一起產出，所有下游 stage 看到同樣的 mapping → 結果可重現。

**為什麼 Scenario C 的 `df_test` 用 raw msno_id（不 encode）？**

C 場景的 test users 故意**不在 train**——他們沒有對應的 encoded idx。LightFM 預測時會臨時建 cold user 的 feature row，預測完才匹配回 raw msno_id 算 metric。

### 2.2 `eval_metrics.py` — 共用 metric 計算

唯一的 public function：

```python
compute_topk_metrics(
    user_topk: dict[int, list[int]],   # {user_id: [top-K item ids]}
    user_truth: dict[int, list[int]],  # {user_id: [ground-truth item ids]}
    eval_ks: tuple[int, ...] = (10, 20),
    model_name: str,
) -> pd.DataFrame  # long-format: Date, Model, K, Recall, Precision, NDCG, ...
```

**設計重點：所有 4 個模型共用這個函數**

- LightFM-hybrid / LightFM-pureCF / ItemKNN / Popularity 各自負責產出 `{user → top-K 預測}`
- 接著統一餵進 `compute_topk_metrics()` 算指標 → 確保所有模型用**完全一樣的計算邏輯**算同樣的東西，公平比較

**跟既有 `evaluate_lightfm`（LOO）的差別**

既有的 LOO 版本（`recommender/src/models/lightfm_model.py:310-392`）只看「test 那 1 個 item 是否在 top-K」（per-user 二元命中）。我們的 multi-truth 版本：

- `Recall@K(u) = hits_in_topK / total_relevant`（per-user 比例）
- `NDCG@K(u) = DCG(u) / IDCG(u)`，IDCG 用 `min(n_truth, K)` 做 truncation
- 再對所有 user average

### 2.3 `lightfm_helpers.py` — LightFM 專屬包裝

三個 function：

```python
build_lightfm_data_from_split(df_train, df_test, useridx, itemidx, members, songs, use_features)
    → LightFMData (含 Dataset + interactions + features matrices)

predict_topk_known_users(model, data, user_truth, max_k)
    → {user_idx: [top-K item idx]}  # 給 Scenario A 用

predict_topk_unseen_users(model, data, members, useridx, test_user_ids, user_truth, max_k)
    → {raw_msno: [top-K item idx]}  # 給 Scenario C 用（最 tricky）
```

**為什麼自己寫 `build_lightfm_data_from_split`？**

既有 `prepare_lightfm_dataset`（`src/models/lightfm_model.py:174-271`）內部會呼叫 `loo_split`，沒辦法直接餵 pre-split。所以我們抄它的下半部（Dataset.fit + build_interactions + build_user/item_features），但跳過 split 那段。

---

## 3. 三個 Key Algorithm 詳解

### 3.1 翻轉 LOO（`make_split_a`）

**目標**：模擬「新使用者只有 N 筆互動」的訓練場景。

**思路**：把既有 `loo_split` 倒過來——既有版「每 user 留最後 1 筆當 test、其餘 train」，我們改成「每 user 留前 N 筆當 train、其餘 test」。

**關鍵 code essence**（`src/coldstart/split.py:74-91`）：

```python
df_positives = (
    df_filtered[df_filtered["target"] == 1]
    .sample(frac=1, random_state=seed)      # 先 shuffle
    .sort_values("msno_idx")                # 再按 user 排
    .reset_index()
)

seed_indices = (
    df_positives.groupby("msno_idx").head(n_seed)["index"].tolist()   # 每 user 取前 N 筆
)
seed_set = set(seed_indices)
test_indices = df_positives[~df_positives["index"].isin(seed_set)]["index"].tolist()

df_test = df_filtered.loc[test_indices].copy()
df_train = df_filtered.drop(test_indices).copy()  # train = 全部 - test
```

**為什麼這樣做**：
- `sample(frac=1)` 確保「前 N 筆」是隨機的、不是依時間排序的前 N 筆——避開「使用者一開始聽什麼」這種 bias
- `seed=42` 固定隨機性，重跑可重現
- df_train 包含 N 筆 positive **跟所有 negative**——negative 仍然有訊號可學

### 3.2 Multi-truth Recall@K / NDCG@K（`compute_topk_metrics`）

**目標**：每位 test user 可能有「很多」要被推薦的 ground truth item（A_N3 中每 user 平均約 180 筆 test positive），需要 multi-truth 版本。

**關鍵 code essence**（`src/coldstart/eval_metrics.py:53-75`）：

```python
for uid, truth_items in user_truth.items():
    topk = user_topk.get(uid)
    truth_set = set(truth_items)
    n_truth = len(truth_set)

    for k in eval_ks:
        top_k = topk[:k]
        hits = sum(1 for item in top_k if item in truth_set)
        sums[k]["recall"] += hits / n_truth          # ← 分母是 user 的 truth 數，不是 1
        sums[k]["precision"] += hits / k

        # NDCG with truncated ideal DCG
        dcg = sum(1.0 / math.log2(rank + 2)
                  for rank, item in enumerate(top_k) if item in truth_set)
        ideal_hits = min(n_truth, k)
        idcg = sum(1.0 / math.log2(r + 2) for r in range(ideal_hits))
        sums[k]["ndcg"] += (dcg / idcg) if idcg > 0 else 0.0

# 之後對 n_eval users 取平均
```

**為什麼 NDCG 要 truncated**：當 truth 數 < K（少數情況），ideal DCG 也要 truncate 在 truth 數，否則 NDCG 上限不是 1。

**為什麼這份計算 vs LOO 版的數字不能直接比**：分母不同（180 vs 1）→ Recall 物理上低很多。詳見 `experiment_summary.md` 的對照段落。

### 3.3 Scenario C 手動 vstack（`predict_topk_unseen_users`）— **最 tricky**

**目標**：對 train 中**完全沒看過**的 user 做預測。LightFM 模型支援這個——理論上拿 user 的 feature vector 餵 `model.predict()` 即可——但實作上踩了幾個坑。

**踩過的 3 個版本**：

**版本 1（失敗）**：用 `dataset.fit_partial(users=cold_users)` 加 cold users → 再 `build_user_features` 重建 feature matrix
```
❌ build_user_features 預設 add_identity_features=True
   → cold users 也被加進 identity 欄位
   → 矩陣 column 數 +50（新加的 cold users）
   → 跟 trained model 的 feature embedding 表（13208 cols）對不上
   → ValueError: The user feature matrix specifies more features than there are estimated feature embeddings: 13208 vs 13258
```

**版本 2（失敗）**：改 `Dataset(user_identity_features=False)` 訓練時就關 identity
```
❌ hybrid 模型退化
   → 12140 個 user 被擠進 41-dim tag 空間（city / gender / 年齡組...）
   → 平均每 ~300 users 共用一個 embedding
   → per-user 區辨力沒了
   → A 場景 NDCG@20 從 0.31 跌到 0.025
   → ablation 結果完全錯
```

**版本 3（成功）**：保持 identity ON 訓練，預測時**手動建一個 (n_cold, n_total_cols) 的 sparse row**：

```python
# 從 trained dataset 拿 feature 對應表
_, user_feature_mapping, _, _ = dataset.mapping()
# user_feature_mapping 同時包含 identity 條目（user_id）跟 tag 條目（"city_5" 等）

# 為每個 cold user 建 sparse row
rows, cols, vals = [], [], []
for i, raw_msno in enumerate(test_user_ids):
    tags = cold_user_tags_raw.get(raw_msno, [])    # 從 members.parquet 抽 tag
    valid_cols = [user_feature_mapping[t] for t in tags if t in user_feature_mapping]
    if not valid_cols:
        continue
    weight = 1.0 / len(valid_cols)                  # normalize
    for col in valid_cols:
        rows.append(i)
        cols.append(col)                            # 都是 tag column，不碰 identity column
        vals.append(weight)
    cold_row_idx[raw_msno] = n_train + i            # 新 user 的 row index 接在 train 之後

cold_user_features = csr_matrix(
    (vals, (rows, cols)),
    shape=(len(test_user_ids), n_total_cols),       # 跟訓練時 user_features 同寬
    dtype=data.user_features.dtype,
)
# vstack 到原 user_features 後面 → shape (n_train + n_cold, n_total_cols)
extended_user_features = sparse_vstack([data.user_features, cold_user_features], format="csr")

# predict 對 user_id = n_train + i
scores = model.predict(
    ext_idx,                                        # n_train + i
    all_items,
    user_features=extended_user_features,
    item_features=data.item_features,
)
```

**為什麼這樣可以**：
- model 的 feature embedding 表是訓練時定形的 → 預測時的 user_features 必須 column 數一致
- cold user 的 row 在 identity columns 填 0 → 等於告訴 model「這個 user 沒有任何訓練過的 identity」
- tag columns 填 normalized 值 → model 用 tag 對應的 embedding 算出 user embedding
- 整個 user embedding = 0 · identity_embeddings + tag_weights · tag_embeddings = 純 feature-driven prediction

完整實作見 `recommender/src/coldstart/lightfm_helpers.py:159-250`。

---

## 4. 跟著一個 user 走完整個 pipeline

假設 user msno_id=104，他在 KKBOX 有 50 筆 positive interaction（target=1）。

**Step 1**：原始資料

```
recommender/data/processed/train_encoded.parquet
  msno_id=104, song_id=8721, target=1, source_*=...
  msno_id=104, song_id=44102, target=1, source_*=...
  ... (50 rows for msno=104)
  msno_id=104, song_id=99213, target=0, source_*=...  # also negatives
  ...
```

**Step 2**：`stage_cs00 --scenarios A_N3` 切分

```python
# split.py::make_split_a(n_seed=3)
# 1. 篩 ≥4 個 positive 的 user（msno=104 符合，50≥4）
# 2. assign msno_idx: msno=104 → msno_idx=42（假設）
# 3. shuffle msno=104 的 50 個 positive、取前 3 個當 seed
#    seed_indices: [<idx of 3 random positives>]
# 4. train = seed (3 rows) + 所有 negative
#    test = 其餘 47 個 positive
```

輸出：
- `cs_A_N3_train.parquet` 含 msno_idx=42 的 3 筆 positive + 全部 negative
- `cs_A_N3_test.parquet` 含 msno_idx=42 的 47 筆 positive
- `cs_A_N3_useridx.json` 含 `{"104": 42, ...}`

**Step 3**：`stage_cs01 --splits A_N3` 訓練 LightFM hybrid

```python
# lightfm_helpers.py::build_lightfm_data_from_split
# - Dataset.fit(users=[0..12139], items=[0..273404], user_tags, item_tags)
# - interactions = sparse matrix from train positives → shape (12140, 273405)
# - user_features = (12140, 12140+41)  # identity + 41 tags
# - item_features = (273405, 273405+5180)
#
# train_lightfm_model:
# - LightFM(no_components=128, loss='warp', max_sampled=50)
# - .fit(interactions, user_features, item_features, epochs=30)
# - 學出 user_embedding 表 (12181, 128) 跟 item_embedding 表 (278585, 128)
```

**Step 4**：`stage_cs01` 預測

```python
# predict_topk_known_users (Scenario A, user 在 training matrix 裡)
all_items = np.arange(273405)
scores = model.predict(42, all_items, user_features=..., item_features=...)
# scores shape (273405,) — user 42 對每首歌的分數

# Mask 掉 train 看過的歌（避免推薦已聽過的）
seen = {<msno_idx=42 在 train 的 3 個 song_idx>}
scores[seen] = -np.inf

top_idx = np.argpartition(-scores, 20)[:20]
top_idx = top_idx[np.argsort(-scores[top_idx])]   # top-20 by score
user_topk[42] = top_idx.tolist()
```

**Step 5**：`eval_metrics.py` 算指標

```python
# user_topk[42] = [預測的 20 個 song_idx]
# user_truth[42] = [47 個 ground truth song_idx]
truth_set = set(user_truth[42])
hits = sum(1 for item in user_topk[42] if item in truth_set)   # 假設 7 hits
recall_at_20 = 7 / 47  ≈ 0.149                                  # ← per-user recall
# 加進 sums["recall"]，最後對 12140 users 平均
```

**Step 6**：`stage_cs05` 匯總

`reports/cs_lightfm_hybrid_metrics.csv` 新增一行：
```
2026-05-23 14:37:44, LightFM-hybrid, 20, 0.0660, 0.3637, 0.3869, 11803, "split=A_N3, components=128, epochs=30, loss=warp, max_sampled=50"
```

stage_cs05 從所有 4 個 metrics CSV 抽最新、合進 `cs_model_comparison.csv`。

**Step 7**：`plot_coldstart.py` 畫圖

`cs_ablation_ndcg_at_20.png` 上 hybrid 線在 N=3 點 = 0.387。

---

## 5. 修改指南（Reading Guide）

| 想做的事 | 先看 / 改哪個檔 |
|---|---|
| **加新場景**（e.g. Scenario B：依互動數排序取最少的） | `src/coldstart/split.py` 加 `make_split_b()`；`pipeline/stage_cs00_make_splits.py` 的 `ALL_SCENARIOS` list 加新名字 |
| **換指標**（e.g. MRR / Hit@K） | `src/coldstart/eval_metrics.py::compute_topk_metrics()` 加新欄位 |
| **加新模型**（e.g. MF baseline） | 仿 `pipeline/stage_cs04_popularity.py` 模式：load split → 產出 `{user: top-K}` dict → 餵 `compute_topk_metrics` → append CSV |
| **調 LightFM 超參** | `stage_cs01/02` 的 CLI 已開：`--no-components`, `--epochs`, `--loss`, `--max-sampled`, `--learning-rate` |
| **改 cold-start C 預測邏輯** | `src/coldstart/lightfm_helpers.py::predict_topk_unseen_users()` — 注意「為什麼不用 fit_partial」的設計理由（見本檔 §3.3） |
| **加 K 值**（e.g. K=5, K=50） | 所有 stage 都有 `--eval-ks` 通用 flag，e.g. `--eval-ks 5 10 20 50` |
| **換圖風格** | `recommender/scripts/plot_coldstart.py` — `MODEL_COLORS` 改顏色、`_bar_by_split` / `_ablation_plot` 改 layout |
| **加新比較表** | `pipeline/stage_cs05_compare.py` — 加新 metric source 或 dedup 邏輯 |

---

## 相關文件

- [`coldstart_research.md`](./coldstart_research.md) — 研究方法、場景定義、Quickstart
- [`experiment_summary.md`](./experiment_summary.md) — 全部實驗結果與結論
- [`lightfm_README.md`](./lightfm_README.md) — LightFM 安裝、訓練、評估操作手冊
- [`db_lightfm_pipeline.md`](./db_lightfm_pipeline.md) — DB → LightFM pipeline 設計（給未來接入後端用）
