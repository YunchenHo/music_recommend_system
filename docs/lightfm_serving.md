完全正確！你抓到 **production 推薦系統的標準做法**了。這就是「offline train + online serve」模式，業界主流（Netflix、Spotify、KKBOX 自家應該也是這樣）。

## 1. 離線訓練 → 存什麼

`model.fit(...)` 跑完，LightFM 物件裡有這些東西：

```python
model.user_embeddings  # shape (n_features_total, n_components)
                       # hybrid: (12140 identity + 41 tags, 128) = (12181, 128)
model.item_embeddings  # shape (n_items + n_item_tags, n_components) = (278585, 128)
model.user_biases      # shape (12181,)
model.item_biases      # shape (278585,)

dataset.mapping()      # 4 個 dict：
                       # user_id → idx, user_feature → col_idx
                       # item_id → idx, item_feature → col_idx
```

這些 pickle 起來存成 `.pkl` 檔（已存好的格式就是這樣，跑 `stage_14` 出的 `artifacts/lightfm_model.pkl`）。

## 2. Online 推薦的 3 個步驟

當網站有人要看推薦：

```
Step 1: 從 DB 拿這個 user 的 features
   user_id = 7
   features = {age=25, gender=F, city=Taipei, ...}
   → 這就是 db_loader.py 的工作

Step 2: 在 trained dataset.mapping 裡找對應 col_idx，build user feature row
   age_25_col   = user_feature_mapping["age_25"]   # 比方說是 12141
   gender_F_col = user_feature_mapping["gender_F"] # 12142
   city_TP_col  = user_feature_mapping["city_1"]   # 12148
   ...
   → 一個 sparse row (1, 12181)，identity 部分填 0、tag 部分填 normalized

Step 3: 呼叫 model.predict()
   scores = model.predict(
       user_id=新 user 的 row index,
       item_ids=np.arange(全部 item),
       user_features=這個 row,
       item_features=trained_item_features,
   )
   top_20 = np.argsort(-scores)[:20]
   → 寫進 DB 或直接 return JSON
```

整個過程**不重新訓練**，只是查表 + 一個大矩陣乘法。在我們的規模（273k items × 128 dim）大概**毫秒到秒級**。

## 3. Warm user vs Cold user 的差別

| 情境 | 怎麼 predict | 需要 retrain？ |
|---|---|---|
| **warm user**（訓練時就在資料裡） | `model.predict(user_idx)`，model 直接查 user identity embedding | ❌ 不用 |
| **cold user**（全新註冊，不在訓練資料裡） | 手動建 sparse row（identity=0、tag=normalized）餵 predict | ❌ 不用 |

兩種都**不用 retrain** —— 這就是 LightFM hybrid 的核心賣點，也是我們冷啟動實驗在驗證的東西。

## 4. 那什麼時候才需要 retrain？

**不是「有新 user 就 retrain」**，而是定期 batch retrain：

| 情況 | 處理方式 |
|---|---|
| 有 100 個新 user 加入 | 不用 retrain，hybrid 用他們的 features 直接 predict |
| 有 10,000 首新歌加進 catalog | 該 retrain（model 對新歌沒 embedding） |
| 累積了一個月的新 interaction | 該 retrain（讓 model 學新趨勢） |
| 新 user 互動了 50 次變 active | 不用立刻 retrain，下次定期 retrain 就會被併入 |

實務上常見：每天/每週 retrain 一次，把累積的新資料整批吃進去。

## 5. 對應到我們系統的「分支 B」設計

按 ItemKNN 模式接入。**現階段**訓練資料用 KKBOX dataset（系統累積資料量不足以單獨訓練）；`db_loader.py` 只負責**inference 時撈該 user 的 features**：

```
[離線、週期性] (例如每週跑一次)
  ┌─ stage_lightfm_train_for_prod.py（現階段：Phase 1）
  │   1. 讀 KKBOX 訓練資料（train_encoded.parquet + complete_members.parquet + song_features.parquet）
  │   2. 跑 LightFM fit
  │   3. 存到 backend/artifacts/lightfm_model.pkl
  └─

[線上、即時]
  ┌─ Django backend: GET /api/recommendations/?user_id=7
  │   1. lightfm_service.py 載入 .pkl（行程內快取，一次就好）
  │   2. 從系統 DB 撈 user 7 的 features（用 db_loader.py）
  │   3. 手動建 sparse row → predict() → top-K
  │   4. 寫進 UserLightFMRecommendation 表 + 回傳 JSON
  └─
```

之所以可行：song catalog 跟 KKBOX 共用（`users_song.id` 就是 KKBOX song_id），所以 KKBOX-trained model 直接能推薦系統 user 也認得的歌。

---

### 之後系統資料夠多時的演進（Phase 2 → 3）

不需要做明確的「切換」動作，而是**漸進式加入系統互動**到訓練 matrix：

**Phase 2 — joint training**（系統 ≥ 5,000 active users 或 ≥ 50,000 explicit interactions）：

```python
# 合併 interaction matrix
#   KKBOX 部分：(12,140 個 msno_hash) × 273k songs，target=1
#   系統部分：(N 個 system_user_id) × 共用 song catalog
#                來源：UserSongLike.is_liked=True / UserSongAffinity.score>threshold

interactions = vstack([kkbox_interactions, system_interactions])
sample_weights = np.concatenate([
    np.ones(kkbox_interactions.nnz),           # KKBOX 權重 1.0
    np.full(system_pos.nnz, 2.0),              # 系統 explicit positive 加倍
])

# explicit negative（is_liked=False）→ 不進 matrix，作 inference 時的 post-hoc filter

model.fit(interactions, sample_weight=sample_weights, ...)
```

system_user 跟 KKBOX msno 是不同的 user，但共用 item embedding 跟 feature 空間（年齡 / 性別 / 城市等可以 map 過去）。

**Phase 3 — 純系統資料**：實務上很少這樣切。多數 production 系統就一路 joint training、永遠不丟歷史資料。

### 何時該啟動 Phase 2 的判準

| 訊號 | 判準 |
|---|---|
| 系統活躍 user 數 | ≥ 5,000 |
| 系統累積 explicit feedback (like/dislike) | ≥ 50,000 |
| KKBOX-only model 在系統 user 上效果飽和 | 該收新訊號 |
| KKBOX 跟系統使用者品味落差變大 | 該加系統資料 |

**現在系統只有 2 個真實 user → 還早，先 Phase 1。**

---

幾乎跟 `docs/ITEMKNN_RECOMMENDATION.md` 講的一樣，只是把 ItemKNN 的「找相似 item」換成 LightFM 的「user features + predict」。
