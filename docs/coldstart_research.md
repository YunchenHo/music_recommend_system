# 冷啟動研究 pipeline

研究 LightFM 在「使用者互動很少」或「全新使用者」情境下的推薦效果，並跟 ItemKNN、Popularity 同基準比較。所有 stage 都在本機跑，KKBOX 公開資料集當資料源（不用系統 DB——原因見 `db_lightfm_pipeline.md`）。

## 研究問題

1. LightFM 對「冷啟動使用者」推薦效果如何？vs ItemKNN / Popularity
2. user / item features 對冷啟動有實際幫助嗎？（**ablation**：hybrid vs pureCF）

## 兩種冷啟動場景

| 場景 | 定義 | 模擬什麼情境 |
|---|---|---|
| **A. leave-first-N** | 對每個 user 隨機留 N (=1, 3, 5) 筆 positive 互動當 train、其餘當 test | onboarding 後幾首歌就要推薦 |
| **C. held-out users** | 隨機抽 1000 個 user 全部 hold out（連 1 筆互動都不在 train），只用他們的 user features 推薦 | 全新使用者第一次登入 |

A 用 N=1/3/5 三個值各跑一次，看不同「seed 數量」對效果的影響。

## 模型 × 場景矩陣

| 模型 | A (N=1/3/5) | C |
|---|:---:|:---:|
| **LightFM-hybrid** (帶 user/item features) | ✅ 主角 | ✅ 主角 |
| **LightFM-pureCF** (無 features) | ✅ ablation | ❌ 結構上不可行 † |
| **ItemKNN** | ✅ 對照組 | ❌ 結構上不可行 ‡ |
| **Popularity** | ✅ 下限 baseline | ✅ 下限 baseline |

† pureCF 在 fit 時固定 user embedding 表大小，cold user 沒有對應的 row，predict 會 index out-of-bounds。
‡ ItemKNN 需要 seed item 才能推薦，cold user 連 seed 都沒有。

C 場景對 pureCF / ItemKNN「故意打不過」是設計上的對照——凸顯 user features 在冷啟動的價值。

## Pipeline 結構

```
stage_cs00_make_splits        → 4 組 split parquet (A_N1/A_N3/A_N5/C)
stage_cs01_lightfm_hybrid     → LightFM 帶 features × 4 split
stage_cs02_lightfm_purecf     → LightFM 無 features × 3 A split  (ablation)
stage_cs03_itemknn            → ItemKNN × 3 A split
stage_cs04_popularity         → Popularity × 4 split
stage_cs05_compare            → 匯總 → cs_model_comparison.csv
```

各 stage 互相獨立（透過 parquet / CSV 接力），可以單獨重跑。

## Quickstart

從 repo root 跑。先 smoke test 驗證 pipeline 通：

```bash
cd recommender
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs00_make_splits.py --smoke
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs04_popularity.py
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs03_itemknn.py --smoke
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs02_lightfm_purecf.py --smoke
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs01_lightfm_hybrid.py --smoke
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs05_compare.py
```

每個 stage smoke 在 1 分鐘內結束。

正式跑（拿掉 `--smoke`）：

```bash
# 1) 全量 split（不限 user 數，C 場景 1000 cold users）
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs00_make_splits.py

# 2) 輕量 stage（分鐘級）
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs04_popularity.py
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs03_itemknn.py

# 3) LightFM 兩個 stage 是時間瓶頸（單線程，每組 split 約 30 分鐘 – 2 小時）
#    建議晚上掛機跑、或開不同 terminal session 並行
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs02_lightfm_purecf.py --epochs 30 --no-components 128
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs01_lightfm_hybrid.py --epochs 30 --no-components 128

# 4) 匯總
PYTHONPATH=. ../.venv/bin/python pipeline/stage_cs05_compare.py
```

## 輸出檔案

| 檔 | 用途 |
|---|---|
| `data/processed/cs_*_train.parquet`<br>`data/processed/cs_*_test.parquet` | 各 split 的訓練 / 測試集（msno_idx / song_idx 已 encode） |
| `data/processed/cs_*_useridx.json`<br>`data/processed/cs_*_itemidx.json` | raw ID → encoded idx 對應表 |
| `data/processed/cs_C_test_users.json` | C 場景的 cold user msno_id 清單 |
| `reports/cs_{model}_metrics.csv` | 各模型的指標長表（append-only） |
| `reports/cs_model_comparison.csv` | 最終匯總，依 Split / K / NDCG 排序 |

## 評估指標

每個 (model, split, K) 算 **Recall@K** / **Precision@K** / **NDCG@K**，K = 10 / 20。

採 per-user 計算後平均：
- Recall@K = (hits in top-K) / (total relevant items per user)
- NDCG@K 用 truncated ideal DCG normalize（多 truth aware）

跟既有 `stage_15` LOO eval **不直接可比**——LOO 每 user 一筆 truth、我們多筆 truth，Recall 分母不同。

## 設計決策

### 為什麼用 KKBOX 不用系統 DB

樣本量問題。目前系統 DB 只有 2 個真實使用者，做不出統計顯著的冷啟動指標。KKBOX 有 14k+ users / 4M+ interactions、是學界 standard benchmark。詳見 `db_lightfm_pipeline.md`。

### 為什麼用 LightFM-pureCF 取代 MF

避免維護 TensorFlow MF stage 的環境依賴。LightFM 用 `use_features=False` 跑出來就是純 CF（user × item interaction，無 features），跟 MF 等效。同時這個 run 也充當 hybrid 的 ablation 對照。

### 為什麼 hybrid 模式關掉 identity features

`Dataset(user_identity_features=False, item_identity_features=False)` 讓 user / item embeddings **完全**由 tag features 決定。原本 lightfm 預設會加 per-user / per-item 的 one-hot identity column，但這樣 cold user 沒對應的 identity 列、無法預測。關掉 identity 後，cold user 的 embedding 就由「他的 features」算出來，這才是 hybrid 模式做 cold-start 的正確設定。代價：warm users 失去個別化的 embedding 部分，但對 cold-start 研究問題是必要的取捨。

### 為什麼 Scenario A 的 cold-start user 的「前 N 筆」也進 train

兩個選擇：

1. **前 N 筆進 train**（採用）：模型還是知道這位 user 是誰、有少量訊號
2. **完全 hold out**：模型只能靠 features

選 1 因為更貼近真實 onboarding 場景（前端會把 onboarding 選擇即時餵進去），且能讓 ItemKNN 也適用（不然 A 跟 C 都變成 ItemKNN 不可行）。

## 已知 limitations

1. **smoke test 數字不可信**：500 users 的稀疏設定下 ItemKNN / LightFM 都接近隨機。要看真實效能等 full run。
2. **C 場景 pureCF 跟 ItemKNN 跳過**：不是 bug，是兩個模型結構上做不到。
3. **memory 限制**：full A 場景訓練約 30 分鐘 – 2 小時、C 場景更久（13k users），單線程 LightFM 在本機跑。如果太慢可以降 `--no-components`、`--epochs`、或對 train_encoded 做 `sample_rate`。

## 後續

跑出 `cs_model_comparison.csv` 後：

1. 畫圖：N (1/3/5) vs Recall@K 折線（hybrid vs pureCF vs ItemKNN vs Popularity）
2. 用 DB 那幾個真實 user 做 qualitative case study（feed 到訓練好的 hybrid model、看推薦的歌單）
3. 寫進專題報告

## 相關文件

- [`lightfm_README.md`](./lightfm_README.md) — LightFM 安裝、訓練、評估的操作手冊
- [`db_lightfm_pipeline.md`](./db_lightfm_pipeline.md) — DB pipeline 設計（這份研究不用 DB，但未來正式接入後端會用到）
- [`ITEMKNN_RECOMMENDATION.md`](./ITEMKNN_RECOMMENDATION.md) — ItemKNN 後端整合（LightFM 之後也會走類似的接入模式）
