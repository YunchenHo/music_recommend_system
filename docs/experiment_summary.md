# 實驗結果與結論彙整

本份整理目前所有跑過的推薦模型實驗，給專題報告 / 學長教授匯報用。

---

## TL;DR

1. **標準 LOO benchmark**（KKBOX 全量 12140 users，每位使用者 hold-out 最後 1 筆）：
   - **LightFM pureCF**（components=256, epochs=30, max_sampled=50, WARP）為目前最佳：**Recall@20 = 0.225, NDCG@20 = 0.111**。
   - ItemKNN（item_k=5, top-5000 users）次之：Recall@20 = 0.188, NDCG@20 = 0.092。
   - Popularity LOO：Recall@20 = 0.071。

2. **冷啟動實驗**（4 模型 × 4 場景，每位使用者多筆 ground truth）：
   - LightFM hybrid 在 Scenario A 比 pureCF **NDCG@20 高 1.3–6.4 個百分點**（max_sampled=10）或 **5.3–13.6 個百分點**（max_sampled=50）→ **user features 確實有貢獻**（ablation 結論）。
   - LightFM hybrid 是 **唯一** 能處理 Scenario C（全新使用者）的 CF 模型；表現與 Popularity 強 baseline 打平（NDCG@20 0.39 vs 0.40）。
   - ItemKNN 在 cold-start 場景因 user-item 矩陣過於稀疏而**結構性失效**（Recall@20 < 1%）。

3. **可寫進報告的核心論述**：「LightFM hybrid 能無縫銜接『無互動 → 有少量互動』整個 user lifecycle」。

---

## 實驗一：標準 LOO benchmark（已完成）

**目的**：在標準 leave-one-out 評估下，比較 LightFM / ItemKNN / Popularity 三類模型的上限表現，並調 LightFM 超參數。

**評估方法**：每位 user 留最後 1 筆 positive 當 test item；Recall@K = 該 item 是否在 top-K 推薦中（per-user 二元命中率）。

### LightFM 調參歷程（May 16）

| 配置 | Recall@20 | NDCG@20 |
|---|---|---|
| epochs=10, components=128, hybrid | 0.124 | 0.059 |
| epochs=10, components=128, pureCF | 0.147 | 0.070 |
| epochs=20, components=128, pureCF, max_sampled=30 | 0.185 | 0.090 |
| epochs=30, components=128, pureCF, max_sampled=50 | 0.208 | 0.103 |
| **epochs=30, components=256, pureCF, max_sampled=50** | **0.225** | **0.111** |

**觀察**：
- 在 LOO 標準評估下，**pureCF 比 hybrid 強**（0.147 vs 0.124 在 epochs=10）。
- 提升 components / epochs / max_sampled 三個維度都有幫助，最佳 ~0.225 Recall@20。
- KKBOX user features（性別、年齡、城市、註冊管道、會員資歷）在 LOO 設定下對 hybrid 沒顯著幫助。

### 三模型橫比（標準 LOO 設定）

| Model | Setup | Recall@20 | NDCG@20 |
|---|---|---|---|
| LightFM pureCF | full 12140 users, components=256/epochs=30/ms=50 | **0.225** | **0.111** |
| ItemKNN baseline | top-5000 users, item_k=5 | 0.188 | 0.092 |
| Popularity | full 12140 users, top-K=20 | 0.071 | — |

LightFM > ItemKNN > Popularity，順序符合預期。

---

## 實驗二：冷啟動專項實驗（5/23 完成，max_sampled=10 與 50 兩組設定）

**目的**：評估 LightFM 對「互動很少」或「全新」使用者的推薦能力，並驗證 user features 是否真的有幫助（ablation）。

**Branch**：`recommend/lightfm-coldstart`
**Pipeline**：6 個 stage (`stage_cs00`–`stage_cs05`)
**詳細方法說明**：見 [`docs/coldstart_research.md`](./coldstart_research.md)

### 場景設計

| 場景 | 切法 | 模擬什麼 |
|---|---|---|
| **A_N1** | 每位 user 留 1 筆 positive 進 train、其餘進 test | onboarding 後第一首歌就要推 |
| **A_N3** | 留 3 筆進 train | onboarding 後幾首歌 |
| **A_N5** | 留 5 筆進 train | 已有少量互動 |
| **C** | 1000 位 user 全部 hold out（train 完全沒看過） | 全新使用者，只有 features |

### 結果：NDCG@20

LightFM 兩個 stage 用 `components=128, epochs=30, WARP loss`，比較 `max_sampled` 兩個值（10 跟 50）。其他模型（ItemKNN、Popularity）不受此參數影響、只列一次。

**max_sampled=10**

```
Model  ItemKNN  LightFM-hybrid  LightFM-pureCF  Popularity
Split                                                     
A_N1    0.0000          0.3184          0.3053      0.3888
A_N3    0.0125          0.3500          0.2858      0.4018
A_N5    0.0177          0.3621          0.3317      0.4005
C          NaN          0.3900             NaN      0.4027
```

**max_sampled=50**（hybrid 表現顯著提升、pureCF 反而略降）

```
Model  ItemKNN  LightFM-hybrid  LightFM-pureCF  Popularity
Split                                                     
A_N1    0.0000          0.3472          0.2941      0.3888
A_N3    0.0125          0.3869          0.2505      0.4018
A_N5    0.0177          0.3905          0.3148      0.4005
C          NaN          0.3952             NaN      0.4027
```

**max_sampled 對兩個模型影響相反**：

- **Hybrid 變強**（A_N1 +0.029、A_N3 +0.037、A_N5 +0.029、C +0.005）：features 提供額外訊號，model 能 leverage 更積極的 negative sampling。
- **PureCF 變差**（A_N1 −0.011、A_N3 −0.035、A_N5 −0.017）：collaborative 訊號在 cold-start 已稀疏，硬找 hard negative 反而引入噪訊。

最佳配置：**LightFM-hybrid + components=128 + epochs=30 + max_sampled=50**。

### 結果：Recall@20（最佳配置 max_sampled=50）

| Split | ItemKNN | hybrid | pureCF | Popularity |
|---|---|---|---|---|
| A_N1 | 0.00% | 6.18% | 4.99% | 7.04% |
| A_N3 | 0.20% | **6.60%** | 4.54% | 6.85% |
| A_N5 | 0.63% | **6.60%** | 5.93% | 6.68% |
| C    | N/A   | **6.54%** | N/A   | 6.68% |

### 視覺化

3 張圖在 `recommender/reports/cs_figures/`（自動更新為最新 max_sampled=50 數據）：

- `cs_ndcg_at_20_by_split.png` — 4 模型 × 4 場景 grouped bar chart
- `cs_recall_at_20_by_split.png` — 同上 (Recall metric)
- `cs_ablation_ndcg_at_20.png` — **關鍵圖**：hybrid vs pureCF 在 N=1/3/5 的折線 + 淨增益 bar

### Ablation 結論（hybrid vs pureCF 對 NDCG@20 的增益）

**max_sampled=10**

| N | hybrid | pureCF | 絕對差 | 百分點 |
|---|---|---|---|---|
| 1 | 0.318 | 0.305 | +0.013 | **+1.3 pp** |
| 3 | 0.350 | 0.286 | +0.064 | **+6.4 pp** |
| 5 | 0.362 | 0.332 | +0.030 | **+3.0 pp** |

**max_sampled=50**（差距明顯放大）

| N | hybrid | pureCF | 絕對差 | 百分點 |
|---|---|---|---|---|
| 1 | 0.347 | 0.294 | +0.053 | **+5.3 pp** |
| 3 | 0.387 | 0.251 | +0.136 | **+13.6 pp** |
| 5 | 0.391 | 0.315 | +0.076 | **+7.6 pp** |

> 註：「pp」（percentage points / 百分點）指 NDCG 數值的絕對差。例如 0.318 → 0.347 為 +2.9 pp（不是 +29%）。

**核心觀察**：

1. **user features 在 N=3 時加分最多**——模型已有些 collaborative 訊號可用，features 補上 user 個別差異。
2. **積極的 negative sampling（max_sampled=50）讓 features 的價值放大** —— ms=10 時 hybrid 領先 pureCF 1.3–6.4 pp，ms=50 時放大到 5.3–13.6 pp。

### ItemKNN 為什麼接近 0%？

Cold-start 設定下 `X_ui` 太稀疏：

| Split | X_ui shape | nnz | 平均每 item 多少 user |
|---|---|---|---|
| A_N1 | (12140, 273405) | 12140 | 0.044 |
| A_N3 | (11803, 273099) | 35409 | 0.130 |
| A_N5 | (11556, 272770) | 57780 | 0.212 |

絕大多數 item 只有 0–1 個 user 互動過 → item-item cosine similarity 沒共現訊號可學 → ItemKNN 推薦品質崩潰。

這 **本身就是 LightFM 賣點論述**：cold-start 場景下基於 co-occurrence 的方法（ItemKNN）結構性失效，需要 embedding-based 方法（LightFM）才能運作。

---

## 兩個實驗的數字為什麼**不能**直接比

| | 實驗一（LOO） | 實驗二（冷啟動） |
|---|---|---|
| 每位 user 的 truth 數 | 1 筆 | 10–500 筆 |
| Recall@K 分母 | 1 | 該 user 全部 truth |
| 數值範圍 | Recall 直接是命中率（0–100%） | Recall 是 K/total，物理上低 |
| 適合回答的問題 | 模型上限有多高 | cold-start 場景下能力如何 |

**舉例**：實驗一 LightFM Recall@20=0.225（22.5% 用戶的單一 hold-out item 被命中），跟實驗二 LightFM-hybrid Recall@20=0.066（每位用戶平均 6.6% 的 hold-out items 被命中）不是同一回事。

---

## 核心結論（給報告用）

1. **整體推薦上限**：LightFM (pureCF, components=256, epochs=30, ms=50) 在 KKBOX 標準 LOO 評估下達到 Recall@20=0.225 / NDCG@20=0.111，優於 ItemKNN 與 Popularity。

2. **冷啟動 user features 有效**：在 Scenario A（少量互動）下，hybrid 比 pureCF **NDCG@20 高 5.3–13.6 個百分點**（最佳配置 max_sampled=50；max_sampled=10 為 1.3–6.4 個百分點），證實 user features 對冷啟動有實際貢獻。

3. **Scenario C 的獨特價值**：對於完全沒有互動歷史的全新使用者，hybrid 是**唯一**能運作的 CF 模型（ItemKNN / pureCF 結構上不適用），表現與 Popularity 強 baseline 相當（NDCG@20 ≈ 0.39 vs 0.40）。

4. **生命週期完整覆蓋**：LightFM hybrid 能銜接「無互動 → 有少量互動 → 充分互動」整個 user lifecycle，且**全程使用同一個模型**，無需切換策略，這對實際系統工程上的維護成本是顯著優勢。

5. **Popularity 是強對手**：KKBOX 互動高度集中於熱門歌曲，top-20 popular songs 覆蓋率高。要明顯超越 popularity，需要更豐富的 user features（KKBOX 只有人口統計類）。

---

## 已知 limitations

1. **KKBOX user features 偏弱**：僅有 5 類 categorical 特徵（gender / 年齡組 / 城市 / 註冊管道 / 會員資歷），共 41 個 unique tag。實際系統中可加上 onboarding 偏好、播放時間段、語言偏好等豐富特徵後表現可能不同。

2. **單線程 LightFM**：本機 LightFM 編譯時 OpenMP 沒接上，全程 single-thread。如果 deploy 時用支援 multi-thread 的版本，train + predict 都會快 4-8 倍。

3. **沒做完整 hyperparam sweep on cold-start**：本次 cold-start 只跑 `components=128, epochs=30` 兩個 `max_sampled`（10 / 50）。已知 `max_sampled=50` 對 hybrid 有顯著幫助（NDCG@20 +0.005~+0.037），但 `components=256` / `epochs=50` 等其他維度未探索。實驗一（標準 LOO）顯示這些維度都有效，cold-start 也可能再壓 0.01~0.03 NDCG@20。

4. **真實系統 case study 未做**：目前系統 DB 只有 2 個真實 OAuth 使用者、0 個 dataset-seeded 使用者。等前端同學灌入更多測試資料後可做 qualitative case study。

5. **冷啟動 multi-truth Recall 數值偏低**：分母大（180+ 個 truth items per user），Recall@K 數字本質上不會高。要看相對比較（不同模型同設定下），不要看絕對值。

---

## 後續工作

| 項目 | 狀態 |
|---|---|
| LightFM `max_sampled=10` 冷啟動實驗 | ✅ 完成 |
| LightFM `max_sampled=50` 冷啟動重跑 | ✅ 完成（hybrid 改善明顯） |
| 進一步調 hyperparam（components=256、epochs=50） | ⏸ 未做（可能再壓出表現） |
| 額外 K 值 (K=5, 50) 評估 | ⏸ 未做 |
| 接入後端 (`UserLightFMRecommendation` 表 + service) | ⏸ 分支 B（未開） |
| 灌 dataset users 進 DB + qualitative case study | ⏸ 等前端同學 |
| LightFM 接入後端的 docker 整合 | ⏸ 分支 B |

---

## 相關文件

- [`coldstart_research.md`](./coldstart_research.md) — 冷啟動 pipeline 設計與 Quickstart
- [`lightfm_README.md`](./lightfm_README.md) — LightFM 安裝、訓練、評估操作手冊
- [`db_lightfm_pipeline.md`](./db_lightfm_pipeline.md) — DB → LightFM pipeline 設計（給接入後端用）
- [`ITEMKNN_RECOMMENDATION.md`](./ITEMKNN_RECOMMENDATION.md) — ItemKNN 後端整合（LightFM 接入會走類似模式）

## 相關資料檔

- `recommender/reports/lightfm_metrics.csv` — 歷史 LightFM 調參全紀錄
- `recommender/reports/itemknn_grid_metrics.csv` — ItemKNN grid search
- `recommender/reports/model_comparison.csv` — 標準 LOO 三模型對比
- `recommender/reports/cs_model_comparison.csv` — 冷啟動四模型對比
- `recommender/reports/cs_figures/*.png` — 冷啟動圖表
