# Affinity Score 與 ItemKNN 推薦整合說明

本文件說明使用者偏好分數（affinity score）的計算規則、儲存設計，以及如何作為權重接入 ItemKNN 推薦的重排與過濾流程。

---

## 1. 架構概覽

| 元件 | 路徑 | 說明 |
|------|------|------|
| 計算模組 | `users/affinity_score.py` | 訊號聚合與分數計算；模組常數區集中所有可調權重 |
| 資料表 | `users/models.py:UserSongAffinity` | 儲存每位使用者對每首歌的原始訊號聚合與最終分數 |
| 批次入口 | `users/management/commands/refresh_affinity_scores.py` | `python manage.py refresh_affinity_scores [--user <id>]` |
| 推薦整合 | `users/views.py:RecommendationsView` | 在 ItemKNN 結果上套用 affinity 重排與過濾 |
| Migration | `users/migrations/0009_alter_usersonglike_is_liked_usersongaffinity.py` | 建立 `users_usersongaffinity` 表 |

---

## 2. 訊號與分數計算

### 2.1 訊號來源

| 訊號 | 計算方式 | 加分 |
|------|---------|------|
| 聽歌總秒數（排除 skip 行） | `SUM(History.watch_seconds)` 且 `watch_seconds >= SKIP_THRESHOLD_SECONDS` | bucket，見下表 |
| Skip 次數 | `COUNT(History)` 且 `watch_seconds < SKIP_THRESHOLD_SECONDS` | `-0.1 × min(skip_count, 5)`，下限 `-0.5` |
| 收藏 | 是否在 `Playlist(playlist_name='archive')` 中 | `+0.5` |
| Like / Dislike | `UserSongLike.is_liked` | like → `+0.5`；dislike → `-1.0`；無紀錄 → `0` |

### 2.2 聽歌秒數分桶

| 範圍（秒） | 加分 |
|---|---|
| 0–10 | 0.0 |
| 10–30 | +0.1 |
| 30–60 | +0.3 |
| 60–180 | +0.5 |
| 180+ | +0.7 |

### 2.3 最終分數

```
score = bucket(total_watch_seconds)
      + max(SKIP_PENALTY_PER_EVENT × skip_count, SKIP_PENALTY_FLOOR)
      + (FAVORITE_WEIGHT  if is_favorited           else 0)
      + (LIKE_WEIGHT      if like_state == 1        else 0)
      + (DISLIKE_WEIGHT   if like_state == -1       else 0)
score = clip(score, SCORE_MIN, SCORE_MAX)   # → [-1.0, 1.0]
```

### 2.4 範例驗證

| 行為 | watch_total | skip | bucket | skip_pen | like/fav | 最終 |
|---|---|---|---|---|---|---|
| 喜歡 + 收藏 + 聽完整首 | 200 | 0 | +0.7 | 0 | +1.0 | **+1.0**（clip） |
| 跳過 5 次無其他訊號 | 0 | 5 | 0.0 | −0.5 | 0 | **−0.5** |
| 跳過 3 次但後來聽 200s | 200 | 3 | +0.7 | −0.3 | 0 | **+0.4** |
| Explicit dislike | 0 | 0 | 0.0 | 0 | −1.0 | **−1.0** |
| 沒互動 | 0 | 0 | 0.0 | 0 | 0 | **0.0** |

---

## 3. 資料表 `users_usersongaffinity`

| 欄位 | 型別 | 說明 |
|------|------|------|
| `user` | FK → User | 使用者 |
| `song` | FK → Song | 歌曲 |
| `total_watch_seconds` | Integer | 排除 skip 後的累計播放秒數 |
| `skip_count` | Integer | 單次 watch_seconds < `SKIP_THRESHOLD_SECONDS` 的次數 |
| `is_favorited` | Boolean | 是否在 archive playlist |
| `like_state` | SmallInt | `1` = like，`-1` = dislike，`0` = 無紀錄 |
| `score` | Float | 最終分數，clip 到 [-1.0, 1.0] |
| `computed_at` | DateTime | 最後計算時間（auto_now） |
| `created_at` | DateTime | 建立時間（auto_now_add） |

**約束與索引：**
- `UniqueConstraint(user, song)`：每位使用者對每首歌至多一筆。
- `Index(user, -score)`：方便取使用者 top-K affinity 歌曲。

保留原始訊號欄位的目的：未來調權重時不需重跑 aggregation；除錯方便；MF 訓練可直接使用 raw signal。

---

## 4. 批次更新

### 4.1 用法

```bash
# 重算所有使用者
docker compose exec backend uv run python manage.py refresh_affinity_scores

# 只重算單一使用者
docker compose exec backend uv run python manage.py refresh_affinity_scores --user 123
```

### 4.2 行為

- `compute_affinity_for_user(user)` 會**先刪除**該使用者所有舊 `UserSongAffinity`，再 `bulk_create` 新資料。整段包在 `@transaction.atomic` 內，避免中途失敗造成不一致。
- 沒有任何訊號的使用者（History/Like/Favorite 都空）→ 寫入 0 筆，舊資料同樣會被清空。

### 4.3 觸發策略（目前）

**目前僅手動 / 排程觸發**，未串接 like/收藏/播放等事件即時更新。原因：

- MVP 簡單原則：先確認分數本身合理，再考慮即時同步成本。
- 即時觸發會與多個 view 耦合（`HistoryView`、`UserSongLikeView`、`FavoritesView`），改動面大。

未來若要排程定期重算，從本 management command 接 cron / Celery 即可，不須改變模組介面。

---

## 5. 與 ItemKNN 推薦的整合

### 5.1 公式

`RecommendationsView.get`（`users/views.py`）在讀取 ItemKNN 候選之後套用：

```
final_score = itemknn_score × (1 + affinity)
```

| 條件 | 行為 |
|------|------|
| `affinity = 0`（無紀錄） | `final = itemknn_score`，順序不變 |
| `affinity > 0` | 推上去（最多翻倍：`affinity = +1` → final 為 itemknn_score 的 2 倍） |
| `0 > affinity ≥ AFFINITY_FILTER_THRESHOLD` | 微幅扣分但仍保留在候選中 |
| `affinity < AFFINITY_FILTER_THRESHOLD` | **直接過濾掉**，不出現在推薦結果 |

`AFFINITY_FILTER_THRESHOLD = -0.5`（定義於 `users/affinity_score.py`）。

### 5.2 流程

1. 載入該使用者最新批次 `RecommendationBatch` 內**所有**候選 `RecommendationItem`（不再只取前 9，因為要重排）。
2. 一次查詢取得這些候選歌的 `UserSongAffinity.score`（沒紀錄者預設 `0`）。
3. 套公式計算 `final_score`，過濾 `affinity < AFFINITY_FILTER_THRESHOLD`。
4. 依 `final_score` 降冪排序，取前 9 回傳。
5. 回傳的 `rank` 為**重排後的新名次**（1..9）。

### 5.3 為何選 [-1, 1] 範圍與此公式

- **語意對齊**：`(1 + affinity)` 把 [-1, 1] 對應到乘數 [0, 2]，affinity = 0 自然不影響原排序。
- **過濾簡潔**：負分本身就是「不喜歡」訊號，閾值 `-0.5` 排除明顯有負面互動的候選。
- **無互動歌曲不受懲罰**：候選清單中大多數歌都是使用者沒聽過的（affinity = 0），公式對它們是 no-op。
- **強訊號可凌駕**：affinity = +1（強烈喜歡）讓相似度本來中等的歌也能擠進前段。

### 5.4 範例（user_id=4 實測）

候選 20 首中，使用者對 6 首已有偏好：

| 原 rank | song_id | knn_score | affinity | final | 重排後 |
|---|---|---|---|---|---|
| 1 | 1996987 | 0.8475 | +0.30 | 1.1018 | **2** |
| 5 | 1305934 | 0.7841 | +0.70 | 1.3330 | **1** ↑ |
| 6 | 625737 | 0.5477 | +1.00 | 1.0954 | **3** ↑ |
| 2 | 645952 | 0.8292 | +0.00 | 0.8292 | 5 ↓ |

兩首高 affinity 的歌成功擠掉純 ItemKNN 排名靠前但使用者沒互動過的歌。

---

## 6. 驗證流程

### 6.1 端到端驗證

```bash
# 1. Migration
docker compose exec backend uv run python manage.py migrate

# 2. 製造資料：歷史播放、like、收藏（用既有 API）
# POST /api/auth/dev-login          → 取得 session
# POST /api/history                 → 製造 watch_seconds
# POST /api/auth/like               → 標 like / dislike
# POST /api/songs/favorites         → 加到 archive

# 3. 批次計算 affinity
docker compose exec backend uv run python manage.py refresh_affinity_scores --user <id>

# 4. 取推薦結果（會自動套重排）
# GET /api/songs/recommendations
```

### 6.2 SQL / shell 直接驗證 affinity

```python
from users.models import UserSongAffinity
for a in UserSongAffinity.objects.filter(user_id=<id>).order_by('-score'):
    print(a.song_id, a.score, a.total_watch_seconds, a.skip_count, a.like_state, a.is_favorited)
```

### 6.3 邊界檢查

- 使用者沒有 affinity 紀錄 → `RecommendationsView` 回傳結果與舊版本（純 ItemKNN）相同。
- 候選歌中有 dislike（affinity = −1.0）→ 被過濾，不出現在回傳列表。
- 候選歌數小於 9 → 回傳實際筆數，不補空。

---

## 7. 後續工作（不在本次範圍）

- **MF 整合**：`UserSongAffinity` 已保留所有 raw signal 欄位，可作為未來 MF 訓練的 implicit feedback weight 來源。
- **API 端點**：未提供「直接讀取 user affinity 列表」的 API；前端目前不需要，未來如要做「我的喜好歌單」可新增 view。
- **權重調整實驗**：所有權重集中在 `affinity_score.py` 模組常數區，建議搭配實際使用者行為資料做 grid search。
- **即時同步**：可考慮在 `UserSongLikeView.post`、`FavoritesView.post`、`HistoryView.post` 中對該 (user, song) 增量更新 `UserSongAffinity`，但需評估事件量與 race condition。
