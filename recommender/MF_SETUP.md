# MF Fold-in 推薦系統設定

## 簡介

MF Fold-in 是系統中的第二種推薦演算法。它使用離線訓練好的歌曲 embedding（GMF 模型），透過 ridge regression 即時計算新用戶的 embedding，產生個人化推薦。

系統會**自動判斷**使用哪種演算法：

- 用戶正樣本 **≥ 15 筆** → 使用 MF Fold-in
- 用戶正樣本 **< 15 筆** → 使用 ItemKNN（fallback）
- 已有 MF 推薦的用戶，累積 **30+ 筆新互動**後，下次請求會自動重算

> 正樣本 = liked 的歌 + 聽超過 10 秒的歷史紀錄（不重複）

## 需要的 Artifact 檔案

MF 推薦需要以下 3 個檔案，放在 `recommender/artifacts/` 下：

| 檔案 | 大小 | 說明 |
|---|---|---|
| `mf_song_embeddings.npy` | ~121 MB | 歌曲 embedding 矩陣 (246708 × 128) |
| `mf_song_bias.npy` | ~964 KB | 歌曲 bias 向量 |
| `mf_item_mapping.json` | ~4.3 MB | song_id → embedding index 對應表 |

這些檔案不在 git 裡（太大），需要自己在本地產生。

## 產生 Artifacts

Docker 可以先跑起來

### 前提

`recommender/data/processed/train_encoded.parquet` 必須存在。如果沒有，先跑前處理：

```bash
docker exec music_recommender python -m pipeline.stage_04_preprocess_train
```

### 訓練 MF 模型 + 匯出 Artifacts

```bash
docker exec music_recommender python -m pipeline.stage_11_mf_train
```

訓練時間約 **5-15 分鐘**（CPU），完成後會自動匯出 artifacts 到 `recommender/artifacts/`。

> 注意：每次訓練的結果會因為隨機初始化而不同，但不影響功能正確性。

## 驗證

確認檔案已產生：

應該在 artifacts 看到 `mf_song_embeddings.npy`、`mf_song_bias.npy`、`mf_item_mapping.json` 三個檔案。

產生完成後，重啟 backend 即可自動啟用 MF 推薦：

```bash
docker-compose restart backend
```
