# ItemKNN 推薦模組說明（後端）

本文件說明離線 ItemKNN 推薦如何接到 Django、環境需求、REST API 用法、預期回傳格式，以及如何驗證與除錯。

---

## 1. 架構概覽

| 元件 | 路徑 | 說明 |
|------|------|------|
| 離線矩陣檔 | 由環境變數 `ITEMKNN_ARTIFACT_PATH` 指定之 `.npz` | 內含 `neigh_items`、`neigh_sims`、`idx2item` 等，供線上依種子歌推算鄰居與分數 |
| 載入與推薦 | `users/itemknn_service.py` | 讀取 `.npz`（行程內快取）、依種子 `song_id` 計算推薦 id 與分數；邏輯與 `recommender/src/models/itemknn` 一致 |
| 寫入 DB | `users/onboarding_itemknn_store.py` | 讀取目前使用者的 `UserOnboardingSong` 種子，呼叫 `itemknn_service`，將結果寫入 `UserItemKNNRecommendation`（含 `position`、`score`） |
| 資料表 | `users/models.py` | `UserOnboardingSong`（種子）、`UserItemKNNRecommendation`（快取推薦列） |
| HTTP | `users/views.py` | `OnboardingSubmitView` 送出 onboarding 時觸發重算；`OnboardingRecommendationsView` 讀取（可選強制重算） |

**預設儲存筆數：** `onboarding_itemknn_store.DEFAULT_STORE_TOP_N`（目前為 **30**）。實際回傳筆數可能少於 30，見「4. 資料與限制」。

---

## 2. 環境變數與部署

### 2.1 必要設定

| 變數 | 說明 |
|------|------|
| `ITEMKNN_ARTIFACT_PATH` | 後端行程可讀取的 **絕對路徑**，指向訓練／匯出之 ItemKNN `.npz` 檔。未設定或檔案不存在時，`refresh_stored_itemknn_recommendations` 會拋出 `FileNotFoundError`（submit 時僅記 log，仍回 200）。 |

`core/settings.py` 以 `os.environ.get("ITEMKNN_ARTIFACT_PATH")` 讀取。

### 2.2 Docker Compose（參考）

專案 `docker-compose.yml` 可將本機 `./recommender/artifacts` 掛載至容器內（例如 `/recommender/artifacts`）。請在 **`.env`**（供 backend 使用）中設定：

```env
ITEMKNN_ARTIFACT_PATH=/recommender/artifacts/itemknn_artifacts.npz
```

（檔名請依實際匯出結果調整。）

變更 `.env` 後需 **重建或重新建立 backend 容器**，讓新環境變數生效。

### 2.3 產生離線矩陣（recommender 端）

專案內可參考 `recommender/scripts/export_itemknn_artifacts.py` 匯出 `.npz`。訓練資料之 `song_id` 需與資料庫 `Song` 主鍵對齊策略一致，否則推薦 id 無法對應到業務資料。

---

## 3. API 一覽

**Base URL（預設開發）：** `http://localhost:8000`

**認證：** 下列 onboarding 相關端點需 **已登入**（Session；`rest_framework.authentication.SessionAuthentication`）。請先完成 Google 登入等流程取得 session cookie。

**URL 前綴：** `core/urls.py` 已掛載 `path('api/onboarding/', include('users.onboarding_urls'))`。

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/onboarding/artists` | 依語系篩選藝人（onboarding 選藝人用） |
| GET | `/api/onboarding/songs` | 依語系篩選歌曲（onboarding 選歌用） |
| POST | `/api/onboarding/submit` | 送出選取之藝人／歌曲，並觸發 ItemKNN 快取重算 |
| GET | `/api/onboarding/recommendations` | 讀取目前使用者之快取推薦 `song_ids` |

登入相關：`POST /api/auth/google-login` 等（見 `users/urls.py`）。

---

## 4. 資料與限制（為何可能少於 30 筆）

1. **`skipped_seed_ids`（種子）**  
   若種子 `song_id` 不在離線矩陣詞彙（`idx2item`）中，該 id 會列入 `skipped_seed_ids`，且不參與加總。

2. **推薦與 `Song` 表交集**  
   演算法會產生多個候選 `song_id`，但寫入 `UserItemKNNRecommendation` 前**只保留在 Django `Song` 資料表中存在的 id**（外鍵需求）。若曲庫表中僅涵蓋少數與訓練相同的 id，最終列表可能遠少於 30 筆。

3. **Submit 時 artifact 缺失**  
   `submit` 若因缺檔跳過重算，仍回成功；此時若無舊快取，之後 `recommendations` 可能為空或需帶 `refresh=1` 並確保檔案存在。

---

## 5. API 詳細與預估回傳格式

### 5.1 `GET /api/onboarding/artists`

**Query：** `languages`（必填），逗號分隔，例如 `Chinese,English`。

**成功 200：**

```json
{
  "status": "success",
  "data": [
    {
      "id": 213320,
      "artist_name": "Jay Chou",
      "artist_image": "/artists/jaychou.jpg",
      "language": "Chinese"
    }
  ]
}
```

**錯誤範例：** 缺 `languages` → `400`，`code`: `MISSING_LANGUAGES`。

---

### 5.2 `GET /api/onboarding/songs`

**Query：** `languages`（必填）。

**成功 200：**

```json
{
  "status": "success",
  "data": [
    {
      "id": 1262202,
      "song_title": "晴天",
      "artist_name": "周杰倫",
      "song_image": "/songs-cover/1262202.png",
      "language": "Chinese"
    }
  ]
}
```

---

### 5.3 `POST /api/onboarding/submit`

**Headers：** `Content-Type: application/json`；需 session。

**Body：**

```json
{
  "artist_ids": [213320, 66286],
  "song_ids": [1262202, 1118607]
}
```

**成功 200：**

```json
{
  "status": "success",
  "message": "Onboarding complete."
}
```

**說明：** 後端會清空並重建該使用者之 `UserOnboardingArtist` / `UserOnboardingSong`，接著呼叫 `refresh_stored_itemknn_recommendations(user)`。若 `.npz` 缺失或無效，僅 **warning log**，不回錯誤。

**常見錯誤 400：**

| `code` | 情境 |
|--------|------|
| `INVALID_ARTISTS` | `artist_ids` 空或非列表 |
| `INVALID_SONGS` | `song_ids` 空或非列表 |
| `INVALID_ARTIST_IDS` | 含有不存在的 artist id |
| `INVALID_SONG_IDS` | 含有不存在的 song id |

---

### 5.4 GET Recommendations API

#### Basic Information

- **Description:**  
  根據使用者 onboarding 所選種子歌曲與離線 ItemKNN 模型，取得推薦歌曲 id 清單（讀取已快取之 `UserItemKNNRecommendation`；可選強制依種子重算）。
- **Method:** `GET`
- **Endpoint:**  
  `{BASE_URL}/api/onboarding/recommendations`  
  開發預設：`http://localhost:8000/api/onboarding/recommendations`

#### 1. Request Parameters

- **Headers:**
  - `Content-Type: application/json`（選用；GET 無 body 時可省略）
  - **認證（必填）：** Session Cookie，例如 `Cookie: sessionid=<登入後取得的 sessionid>`。需先透過 `POST /api/auth/google-login` 等完成登入。

- **Query Parameters（URL 參數 — 選擇性）:**

  | 參數 | 型別 | 預設 | 說明 |
  |------|------|------|------|
  | `top_n` | 整數 | `30` | 回傳前 N 筆推薦 id，範圍 1～200 |
  | `refresh` | 字串 | 無 | 若為 `1`、`true`、`yes`，先依目前 `UserOnboardingSong` 種子重算並覆寫快取後再回傳 |

- **Body:** 無

#### 2. Response（成功 `200 OK`）

```json
{
  "status": "success",
  "data": {
    "song_ids": [803123, 556389, 689229],
    "skipped_seed_ids": []
  }
}
```

| 欄位 | 說明 |
|------|------|
| `data.song_ids` | 依模型分數排序之推薦曲 **主鍵 id**（整數陣列），長度 ≤ `top_n` |
| `data.skipped_seed_ids` | 種子 `song_id` 不在離線矩陣詞彙內者；僅在本次有執行重算時較可能非空；僅讀快取時通常為 `[]` |

#### 3. 錯誤回應

| HTTP | `code` | 說明 |
|------|--------|------|
| 400 | `INVALID_TOP_N` | `top_n` 非整數或不在 1～200 |
| 400 | `NO_ONBOARDING_SONGS` | 尚無 onboarding 種子歌曲 |
| 503 | `ITEMKNN_ARTIFACT_MISSING` | 需重算但找不到 `.npz` 或 `ITEMKNN_ARTIFACT_PATH` 未設定 |
| 500 | `ITEMKNN_ARTIFACT_INVALID` | 離線檔格式與後端預期不符 |

錯誤本體格式範例：`{"status":"error","message":"...","code":"NO_ONBOARDING_SONGS"}`（實際以 `views.py` 為準）。

---

## 6. 測試與驗證

### 6.1 自動化測試現況

`users/tests.py` 目前為空白模板，**尚未**包含 ItemKNN 或 onboarding 的單元／整合測試。若後續要補測試，建議方向：

- 使用暫存 `.npz` fixture（小矩陣）與 `settings.override(ITEMKNN_ARTIFACT_PATH=...)`。
- 建立 `User`、`Song`、`UserOnboardingSong` 測試資料後，呼叫 `onboarding_itemknn_store.refresh_stored_itemknn_recommendations` 或透過 `APIClient` 打 `submit` / `recommendations`。
- 在 teardown 呼叫 `itemknn_service.clear_itemknn_cache()` 避免快取跨測試。

執行（於 `backend` 目錄、已安裝依賴）：

```bash
python manage.py test users
```

### 6.2 手動驗證建議流程

1. 確認 `ITEMKNN_ARTIFACT_PATH` 在執行環境可讀且檔案存在（容器內可 `test -f "$ITEMKNN_ARTIFACT_PATH"`）。
2. 瀏覽器登入後，完成 `POST /api/onboarding/submit`（或前端 onboarding）。
3. `GET /api/onboarding/recommendations`（可選 `?refresh=1`）檢查 `song_ids` 與 `skipped_seed_ids`。
4. 檢視 backend log：artifact 缺失、種子全不在詞彙、或「候選與 `Song` 表交集過少」等警告（見 `onboarding_itemknn_store` 日誌）。
5. （選）資料庫：`users_useritemknnrecommendation` 依 `user_id`、`position` 查詢列數與 `song_id`。

### 6.3 使用 curl 讀取推薦（需 session）

自瀏覽器複製 `sessionid` 後：

```bash
curl -sS 'http://localhost:8000/api/onboarding/recommendations' \
  -H 'Cookie: sessionid=<你的sessionid>'
```

強制重算：

```bash
curl -sS 'http://localhost:8000/api/onboarding/recommendations?refresh=1&top_n=30' \
  -H 'Cookie: sessionid=<你的sessionid>'
```

---

## 7. 相關檔案索引

| 檔案 | 用途 |
|------|------|
| `users/itemknn_service.py` | 載入 `.npz`、種子推薦 |
| `users/onboarding_itemknn_store.py` | 寫入 `UserItemKNNRecommendation` |
| `users/views.py` | `OnboardingSubmitView`、`OnboardingRecommendationsView` |
| `users/onboarding_urls.py` | onboarding 路由 |
| `users/models.py` | `UserOnboardingSong`、`UserItemKNNRecommendation` |
| `core/settings.py` | `ITEMKNN_ARTIFACT_PATH` |
| `users/migrations/0003_useritemknnrecommendation.py` | 推薦快取表遷移 |

---

## 8. 版本與維護

- 回傳欄位與錯誤碼以 `users/views.py` 實作為準；若程式變更請同步更新本文件。
- `.npz` 欄位格式變更時，需一併更新 `itemknn_service._load_itemknn_bundle` 與匯出腳本。
