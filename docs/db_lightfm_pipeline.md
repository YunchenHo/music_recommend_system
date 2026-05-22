# DB → LightFM Pipeline 設計

> 把系統 MySQL 的資料轉成 LightFM 能吃的格式。這份文件給之後要做冷啟動研究、或把 LightFM 接進後端推薦服務的人看。

## TL;DR

- 之前的 LightFM pipeline（`stage_14_lightfm_train.py`）吃的是 KKBOX 公開資料集，跟我們系統 DB 沒有接起來。
- 這個分支加了一層「把系統 DB 讀出來、轉成 LightFM 標準輸入」的共同骨幹，**冷啟動研究**跟**正式接入後端**兩條路線的第一段都會用到這層。
- 只想跑起來看看？跳到 [Quickstart](#quickstart)。

---

## 為什麼有這個 pipeline？

我們專題現在面臨兩個下游需求：

| 需求 | 目的 |
|---|---|
| 🔬 **冷啟動研究** | 評估 LightFM 在「新使用者只有少量互動」情境下的推薦效果，產出能跟學長 / 教授匯報的指標（Recall@K、NDCG@K 等） |
| 🚀 **正式接入後端** | 跑離線訓練、產出 model，讓 Django 後端能呼叫 LightFM 做即時推薦 |

兩條路線**第一段一模一樣**：都要把系統 MySQL 的資料讀出來、整理成 LightFM `Dataset` API 吃得下的格式。如果各自實作，研究跟正式環境就會分歧（schema 漂移、評估資料對不上 prod 資料等）。所以這個分支只做共同的第一段，下游各自開新分支延伸。

---

## 整體流程

```
┌─────────────────────┐   Django command   ┌──────────────────────┐
│   MySQL (backend)   │ ─────────────────▶ │  data/db_processed/  │
│  users_user         │                    │   users.csv          │
│  users_song         │                    │   songs.csv          │
│  users_history      │                    │   interactions.csv   │
│  users_usersong*    │                    │   onboarding.csv     │
│  users_onboarding*  │                    └──────────┬───────────┘
└─────────────────────┘                               │
                                                      │ db_loader.py
                                                      ▼
                                          ┌────────────────────────┐
                                          │  DBData (pandas)       │
                                          │  .users  .songs        │
                                          │  .interactions         │
                                          │  .onboarding           │
                                          └──────────┬─────────────┘
                                                     │
                            ┌────────────────────────┴─────────────────────────┐
                            ▼                                                  ▼
                  🔬 冷啟動研究分支                                  🚀 正式接入分支
                  - ID encoding                                       - ID encoding
                  - cold-start train/test split                        - 全資料訓練
                  - LightFM 訓練 + 評估                                 - 存 model → backend 載入
```

中間那層（CSV）刻意做成檔案而不是直接 import Django model：

1. **Backend venv（Py 3.13）** 跟 **recommender venv（Py 3.11.13）** 是分開的 —— LightFM 1.17 還停在 Py 3.11，Django 6.0 要 Py 3.12+。
2. CSV 當交換格式，兩邊環境完全解耦、誰也不依賴誰。
3. 對 backend 不增加 pyarrow / pandas 依賴（CSV 是 Python 內建）。

---

## Quickstart

### 一、把資料從 DB 匯出（透過 music_django container）

`music_django` container 沒掛 host 的 `data/`，所以先寫到 container `/tmp/`，再用 `docker cp` 拉到 host：

```bash
# 確認容器跑著
docker ps | grep music_django

# 匯出到 container /tmp/db_processed/
docker exec music_django uv run python manage.py export_for_lightfm \
  --output-dir /tmp/db_processed/

# 拉到 host repo root
mkdir -p data/db_processed
docker cp music_django:/tmp/db_processed/. data/db_processed/
```

實際跑過的輸出範例（2 個真實 OAuth 使用者、35.9 萬首歌的當下狀態）：

```
  users:        seeded=0, real=2 (prefix='dev_')
Wrote to /tmp/db_processed:
  users.csv                2 rows
  songs.csv           359755 rows
  interactions.csv        16 rows
  onboarding.csv          14 rows
```

### 二、在 recommender 端讀回來做 sanity check

從 repo root 跑（root `.venv` 是 Py 3.11.13，跟 LightFM 共用）：

```bash
cd recommender
PYTHONPATH=. ../.venv/bin/python pipeline/stage_db00_load_from_db.py
```

這個 stage 只印出資料統計、做 schema 檢查，**不**訓練任何模型。實際輸出：

```
[stage_db00] Loaded from /Users/.../data/db_processed
  users                2 rows  (cols: [...])
  songs           359755 rows  (cols: [...])
  interactions        16 rows  (cols: [...])
  onboarding          14 rows  (cols: [...])

  users by source_tag: {'real': 2}
  NOTE: no 'seeded' users yet — this is expected until dataset users get
  imported into the DB. [...]
  interactions: 2 unique users, 2 rows w/ like signal, 14 rows w/ affinity score
```

### 三、之後在自己的分支寫實際邏輯

```python
from src.data.db_loader import load_db_data

db = load_db_data()        # DBData(users, songs, interactions, onboarding)
print(db.interactions.head())
```

---

## 各檔案產出說明

匯出後在 `data/db_processed/` 下有 4 個 CSV：

### `users.csv`

| 欄位 | 來源 / 說明 |
|---|---|
| `user_id` | `users_user.id` |
| `google_id` | OAuth sub；測試用戶會是 `dev_xxx` |
| `email`, `nickname`, `age`, `gender`, `preferred_languages` | 使用者基本資料 |
| `profile_completed` | `0/1`；是否走完 onboarding |
| `google_name` | Google 帳戶顯示名稱 |
| `source_tag` | `'seeded'` 或 `'real'`（見下面「`source_tag` 欄位」段落；目前一律是 `'real'`） |
| `created_at` | ISO8601 |

### `songs.csv`

| 欄位 | 來源 / 說明 |
|---|---|
| `song_id` | `users_song.id` |
| `song_title`, `album_name`, `language` | 歌曲屬性 |
| `artist_id`, `artist_name` | 透過 `users_artist` JOIN |
| `release_date` | ISO date 或空 |

### `interactions.csv`

每播放一次（每筆 `users_history`）就是一列，並把 `UserSongLike` / `UserSongAffinity` 的訊號 LEFT JOIN 進來（沒紀錄就空白）。

| 欄位 | 來源 / 說明 |
|---|---|
| `user_id`, `song_id` | FK |
| `source` | `RECOMMENDATION` / `SEARCH` / `PLAYLIST` / `ONBOARDING` / `FRIEND` |
| `watch_seconds` | 該次播放秒數 |
| `played_at` | ISO8601 |
| `is_liked` | `1` 喜歡、`0` 不喜歡、空白為未表態 |
| `affinity_score` | `[-1, 1]` 的偏好分數（從 `UserSongAffinity.score`） |

⚠️ 因為 `UserSongLike` 跟 `UserSongAffinity` 是 unique(user, song)，所以同一首歌的多次播放會把 like / affinity 重複貼上去 —— 這是刻意的，方便離線分析直接用。

### `onboarding.csv`

把 `UserOnboardingArtist` 跟 `UserOnboardingSong` 合併。冷啟動研究會用這份當「新使用者的初始偏好特徵」。

| 欄位 | 說明 |
|---|---|
| `user_id` | FK |
| `kind` | `'artist'` 或 `'song'` |
| `entity_id` | 對應 `artist_id` 或 `song_id` |
| `created_at` | ISO8601 |

---

## 這層**沒有**做的事（下游分支再做）

| 項目 | 為什麼留到下游 |
|---|---|
| ID encoding（LabelEncoders） | 不同任務鎖定的 user / item 群可能不一樣（研究只看 seeded、prod 看全部），共同層硬編碼會綁手綁腳 |
| LightFM `Dataset.fit` / `build_interactions` | `recommender/src/models/lightfm_model.py::prepare_lightfm_dataset` 已經有實作了，下游分支直接把 `DBData` 餵進去即可 |
| 冷啟動 train / test split | 跟 `stage_14` 的 leave-one-out 邏輯不一樣（要保留「使用者只有 N 個互動」的條件），在研究分支設計比較有彈性 |
| 評估與訓練 | 研究分支才做；這層只負責資料準備 |

---

## `source_tag` 欄位：目前是預留 / forward-looking

`source_tag` 用來日後區分「dataset 灌入的用戶」（`seeded`）跟「真實 OAuth 用戶」（`real`）。

**現況（2026-05-22）**：DB 裡**還沒有**任何 dataset 灌入的用戶，全部都是真實 OAuth 用戶。所以匯出後 `source_tag` 一律會是 `'real'`，`stage_db00` 也會印出 NOTE 提示「沒有 seeded 是正常的」。

**規則**：

> `google_id` 以 `dev_` 開頭 → `source_tag = 'seeded'`，否則 `'real'`

這個 prefix 暫時取 `backend/users/views.py::DevLoginView` 用的 pattern。等未來真的要灌 dataset 用戶時：

1. 灌資料的腳本給每個 dataset user 用一個能跟真實 OAuth ID 區分的 `google_id`（例如 `kkbox_<msno_hash>`）
2. 跑 export 時用 `--seeded-prefix` 指定那個 prefix：

```bash
docker exec music_django uv run python manage.py export_for_lightfm \
  --output-dir /tmp/db_processed/ --seeded-prefix kkbox_
```

灌資料的時間點，再回頭調這條規則。**現在不用動**。

---

## 相關文件

- [`lightfm_README.md`](./lightfm_README.md) — LightFM 操作手冊（安裝、訓練、評估、比較流程）
- [`ITEMKNN_RECOMMENDATION.md`](./ITEMKNN_RECOMMENDATION.md) — ItemKNN 後端整合（這個 pipeline 之後也會走類似的接入模式）
- [`AFFINITY_SCORE_INTEGRATION.md`](./AFFINITY_SCORE_INTEGRATION.md) — Affinity 分數計算與 ItemKNN 重排
