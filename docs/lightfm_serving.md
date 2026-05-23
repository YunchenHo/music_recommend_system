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

這就是我們之前說「按 ItemKNN 模式接入」的具體流程：

```
[離線、週期性] (例如每週跑一次)
  ┌─ stage_lightfm_train_for_prod.py
  │   1. 讀 system DB（用 db_loader.py）
  │   2. 跑 LightFM fit
  │   3. 存到 backend/artifacts/lightfm_model.pkl
  └─

[線上、即時]
  ┌─ Django backend: GET /api/recommendations/?user_id=7
  │   1. lightfm_service.py 載入 .pkl（行程內快取，一次就好）
  │   2. 從 DB 撈 user 7 的 features（用 db_loader）
  │   3. 手動建 sparse row → predict() → top-K
  │   4. 寫進 UserLightFMRecommendation 表 + 回傳 JSON
  └─
```

幾乎跟 `docs/ITEMKNN_RECOMMENDATION.md` 講的一樣，只是把 ItemKNN 的「找相似 item」換成 LightFM 的「user features + predict」。
