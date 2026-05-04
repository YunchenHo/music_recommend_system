# History & Like API 串接紀錄

把 **歷史紀錄（History）** 與 **喜歡 / 不喜歡（UserSongLike）** 兩組 API 從後端接到前端 `HomePage`，讓網頁能：

1. 使用者播放任一首歌時，自動把 `(song_id, watch_seconds, source)` 寫進後端歷史
2. 重新整理頁面 → 左側「歷史紀錄」顯示後端真實資料（含歌名 / 作者）
3. 按喜歡 / 不喜歡按鈕 → toggle 寫入後端，切歌回來時自動還原狀態

---

## 一、最終 API 規格

> ⚠️ **重要設計決策**：點歌時就會**立刻** POST 一筆 `watch_seconds=0` 的紀錄，
> 切歌 / 結束時改用 PATCH 更新該筆的 `watch_seconds`。
> 這樣即使使用者馬上重新整理也不會掉資料（保證最後一首在歷史紀錄裡）。
> 詳見〈三、(3) 為什麼「點歌就立刻 POST」〉。

### 1. `POST /api/auth/history` — 新增播放紀錄

**Body**

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `song_id` | int | ✅ | 必須是 `Song` 表中存在的 id |
| `watch_seconds` | int (≥ 0) | ✅ | 實際播放秒數 |
| `source` | str | ✅ | 限定 `RECOMMENDATION` / `SEARCH` / `PLAYLIST` / `ONBOARDING` / `FRIEND` |

**Response (201)**

```json
{
  "status": "success",
  "message": "History created.",
  "data": { "id": 123, "song_id": 7, "watch_seconds": 84, "source": "SEARCH" }
}
```

**錯誤碼**：`MISSING_SONG_ID` / `MISSING_WATCH_SECONDS` / `MISSING_SOURCE` / `INVALID_SOURCE` / `SONG_NOT_FOUND` / `INVALID_WATCH_SECONDS`

### 1.5 `PATCH /api/auth/history/<id>` — 更新某筆紀錄的 watch_seconds

僅允許更新「本人建立」的紀錄；非本人或不存在皆回 404 `HISTORY_NOT_FOUND`。

**Body**

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `watch_seconds` | int (≥ 0) | ✅ | 要更新到的播放秒數 |

**Response (200)**

```json
{
  "status": "success",
  "message": "History updated.",
  "data": { "id": 123, "song_id": 7, "watch_seconds": 84, "source": "SEARCH" }
}
```

**單調遞增保護**：傳入的 `watch_seconds` ≤ 現有值時不會覆蓋，避免「中段 PATCH 比末段 PATCH 晚到」的 race condition。

**錯誤碼**：`HISTORY_NOT_FOUND` / `MISSING_WATCH_SECONDS` / `INVALID_WATCH_SECONDS`

### 2. `GET /api/auth/history` — 取歷史紀錄（含歌曲 metadata）

**Query Params**：`limit` (預設 20、上限 50)、`offset` (預設 0)、`song_id`、`source`

**Response (200)**

```json
{
  "status": "success",
  "data": [
    {
      "id": 123,
      "song_id": 7,
      "song_title": "Lover",
      "artist_name": "Taylor Swift",
      "album_name": "Lover",
      "song_image": "...",
      "language": "English",
      "watch_seconds": 84,
      "source": "SEARCH",
      "played_at": "2026-04-26T12:00:00Z",
      "created_at": "2026-04-26T12:00:00Z"
    }
  ],
  "total": 38,
  "limit": 20,
  "offset": 0
}
```

依 `played_at` desc 排序（最新在前）。

### 3. `GET /api/auth/like?song_id=<id>` — 取單首 like 狀態

**Response**

```json
{ "status": "success", "data": { "song_id": 7, "is_liked": true } }
```

`is_liked`：`true` = 喜歡 / `false` = 不喜歡 / `null` = 尚未設定。

### 4. `POST /api/auth/like` — Toggle 喜歡 / 不喜歡

**Body**：`{ "song_id": 7, "is_like": true }`（`is_like` 必須是 boolean）

行為：

| 目前狀態 | 傳入 `is_like` | 結果 | 回傳 `is_liked` |
| --- | --- | --- | --- |
| 沒紀錄 | `true` | 新增 | `true` |
| 沒紀錄 | `false` | 新增 | `false` |
| `true` | `true` | 刪除（取消） | `null` |
| `false` | `false` | 刪除（取消） | `null` |
| `true` | `false` | 切換 | `false` |
| `false` | `true` | 切換 | `true` |

---

## 二、後端改動

### 檔案：`backend/users/views.py`

#### (1) `HistoryView.get()` — 改為一次帶出歌曲 metadata

避免 N+1 查詢，並讓前端直接拿來顯示：

```python
queryset = History.objects.filter(user=user).select_related('song')
# ... filter / order / pagination ...

results = []
for history in queryset:
    song = history.song
    results.append({
        "id": history.id,
        "song_id": history.song_id,
        "song_title": song.song_title,
        "artist_name": song.artist_name,
        "album_name": song.album_name,
        "song_image": song.song_image,
        "language": song.language,
        "watch_seconds": history.watch_seconds,
        "source": history.source,
        "played_at": history.played_at,
        "created_at": history.created_at,
    })
```

> 改動前只回傳 `song_id`，前端要再逐筆呼叫 `GET /api/songs/<id>` 取詳情。

#### (2) 新增 `HistoryDetailView` — 處理 `PATCH /api/auth/history/<pk>`

```python
class HistoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            history = History.objects.get(pk=pk)
        except History.DoesNotExist:
            return Response({...HISTORY_NOT_FOUND...}, status=404)

        # 不是本人的紀錄一律 404，避免洩漏 id 是否存在
        if history.user_id != request.user.id:
            return Response({...HISTORY_NOT_FOUND...}, status=404)

        watch_seconds = request.data.get('watch_seconds')
        # 驗證 必填 / int / >= 0 ...

        # 單調遞增保護
        if watch_seconds > history.watch_seconds:
            history.watch_seconds = watch_seconds
            history.save(update_fields=['watch_seconds'])

        return Response({"status": "success", ...}, status=200)
```

**`backend/users/urls.py`** 對應加入：

```python
path('history/<int:pk>', HistoryDetailView.as_view(), name='history-detail'),
```

#### (3) `UserSongLikeView` — 新增 `get()` 取單首 like 狀態

```python
class UserSongLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        song_id = request.query_params.get('song_id')
        if song_id is None:
            return Response({...MISSING_SONG_ID...}, status=400)
        try:
            song_id_int = int(song_id)
        except (TypeError, ValueError):
            return Response({...INVALID_SONG_ID...}, status=400)
        if not Song.objects.filter(id=song_id_int).exists():
            return Response({...SONG_NOT_FOUND...}, status=404)

        like = UserSongLike.objects.filter(user=request.user, song_id=song_id_int).first()
        is_liked = like.is_liked if like is not None else None

        return Response({
            "status": "success",
            "data": {"song_id": song_id_int, "is_liked": is_liked},
        }, status=200)

    def post(self, request):  # 既有 toggle 邏輯，未動
        ...
```

> 改動前只有 POST，所以前端切歌時無從得知這首之前是否已喜歡 → 切歌就 reset。

### 不需 migration

只動 view，未改 model，**直接重啟 Django 即可**。

---

## 三、前端改動

### (1) 新增 `frontend/src/api/history.js`

```js
import api from "./api"

export const HISTORY_SOURCE = {
  RECOMMENDATION: "RECOMMENDATION",
  SEARCH: "SEARCH",
  PLAYLIST: "PLAYLIST",
  ONBOARDING: "ONBOARDING",
  FRIEND: "FRIEND",
}

export async function getHistory(params = {}) {
  const { data } = await api.get("/api/auth/history", { params })
  return data
}

export async function createHistory({ songId, watchSeconds, source }) {
  const { data } = await api.post("/api/auth/history", {
    song_id: songId,
    watch_seconds: Math.max(0, Math.floor(watchSeconds || 0)),
    source,
  })
  return data
}

export async function updateHistory(historyId, watchSeconds) {
  const { data } = await api.patch(`/api/auth/history/${historyId}`, {
    watch_seconds: Math.max(0, Math.floor(watchSeconds || 0)),
  })
  return data
}
```

`createHistory` / `updateHistory` 都對 `watchSeconds` 做防呆（`Math.floor` + 不為負）。

### (2) 新增 `frontend/src/api/likes.js`

```js
import api from "./api"

export async function getLikeStatus(songId) {
  const { data } = await api.get("/api/auth/like", { params: { song_id: songId } })
  return data
}

export async function toggleLike(songId, intentLike) {
  const { data } = await api.post("/api/auth/like", {
    song_id: songId,
    is_like: intentLike,
  })
  return data
}
```

### (3) `frontend/src/pages/HomePage.jsx`

#### 新增 import

```js
import { getHistory, createHistory, updateHistory, HISTORY_SOURCE } from "../api/history"
import { toggleLike, getLikeStatus } from "../api/likes"
```

#### 移除寫死 mock

- `historySongs` 初始改成空陣列，由 API 載入

#### 追蹤目前播放的 ref

```js
// 切歌 / 結束 / 卸載時用來決定要把哪筆 history 的 watch_seconds PATCH 上去
// - historyId: POST 回傳的 id（POST 還沒回來時為 null）
// - createPromise: 等 POST 拿 id 用
const playbackRef = useRef({
  song: null,
  source: null,
  historyId: null,
  createPromise: null,
})
```

#### 啟動時載入歷史紀錄並去重

後端會回多筆「同一首歌」的紀錄（每次播放都新增一筆），UI 要的是「最近聽過的歌曲清單」，所以保留每首歌最近的一筆：

```js
getHistory({ limit: 20 })
  .then((resp) => {
    const items = resp?.data ?? []
    const seen = new Set()
    const deduped = []
    for (const it of items) {
      if (seen.has(it.song_id)) continue
      seen.add(it.song_id)
      deduped.push({
        id: it.song_id,
        song_title: it.song_title,
        artist_name: it.artist_name,
        song_image: it.song_image,
        album_name: it.album_name,
        language: it.language,
      })
    }
    setHistorySongs(deduped)
  })
  .catch(console.error)
```

#### 切歌前用 PATCH 更新上一首的 watch_seconds

關鍵點：
- 一進來就把 ref **snapshot** 取出並清空，避免接著的 `handlePlay` 覆寫造成競態
- 沒實際播到（< 1 秒）就不 PATCH（保留 POST 時建立的 `watch_seconds=0`）
- 等 `createPromise` 回來拿 id 再 PATCH

```js
const flushCurrentHistory = useCallback(() => {
  const snapshot = playbackRef.current
  playbackRef.current = { song: null, source: null, historyId: null, createPromise: null }

  if (!snapshot.song || !snapshot.source) return
  let seconds = 0
  try {
    seconds = playerRef.current?.getCurrentTime?.() ?? 0
  } catch { seconds = 0 }
  if (!seconds || seconds < 1) return

  ;(async () => {
    let id = snapshot.historyId
    if (!id && snapshot.createPromise) {
      try {
        const resp = await snapshot.createPromise
        id = resp?.data?.id ?? null
      } catch { id = null }
    }
    if (!id) return
    try { await updateHistory(id, seconds) }
    catch (err) { console.error("更新 history 失敗", err) }
  })()
}, [])
```

呼叫時機：
1. `handlePlay` 進來時 → flush 上一首
2. YouTube `onEnd` 觸發時 → flush 目前這首
3. 元件卸載時 → flush（清掉指針避免 leak）

#### `handlePlay(song, source)` 加入 source 參數，並在進來時立刻 POST

呼叫者要明確指定點擊來源（給後端的 enum）：

| UI 入口 | 傳入 source |
| --- | --- |
| 推薦歌曲 grid | `RECOMMENDATION` |
| 重溫舊愛（mock） | `RECOMMENDATION` |
| 搜尋結果 | `SEARCH` |
| 已收藏歌曲清單 | `PLAYLIST` |
| 歷史紀錄清單 | `PLAYLIST` |
| 自訂 playlist 清單 | `PLAYLIST` |
| 朋友也在聽（mock） | `FRIEND` |

```js
const handlePlay = async (song, source = HISTORY_SOURCE.RECOMMENDATION) => {
  flushCurrentHistory()                                      // 先 PATCH 上一首
  setCurrentSong(song)
  setIsPlaying(true)
  setLiked(false); setDisliked(false)

  // 點到歌就立刻 POST 一筆 watch_seconds=0；確保即使馬上 refresh 也不會掉
  const createPromise = createHistory({ songId: song.id, watchSeconds: 0, source })
    .then((resp) => {
      // 如果這時還在播同一首，把後端回傳的 id 寫回 ref，後續 PATCH 用
      if (
        playbackRef.current.song?.id === song.id &&
        playbackRef.current.source === source
      ) {
        playbackRef.current.historyId = resp?.data?.id ?? null
      }
      return resp
    })
    .catch((err) => { console.error("建立 history 失敗", err); return null })

  playbackRef.current = { song, source, historyId: null, createPromise }

  // 還原這首歌之前的 like 狀態
  getLikeStatus(song.id)
    .then((resp) => {
      const isLiked = resp?.data?.is_liked
      setLiked(isLiked === true)
      setDisliked(isLiked === false)
    })
    .catch((err) => console.error("取得 like 狀態失敗", err))

  // 既有的 historySongs 樂觀更新 + YouTube 搜尋邏輯（未變）
  ...
}
```

#### Like / Dislike 按鈕串接 toggleLike

```js
const handleToggleLike = async (intentLike) => {
  if (!currentSong) return
  try {
    const resp = await toggleLike(currentSong.id, intentLike)
    const isLiked = resp?.data?.is_liked   // true / false / null
    setLiked(isLiked === true)
    setDisliked(isLiked === false)
  } catch (err) {
    console.error("toggle like 失敗", err)
  }
}

// JSX
<button className={`action-btn-new ${liked ? "active" : ""}`}
        onClick={() => handleToggleLike(true)} title="喜歡">...</button>
<button className={`action-btn-new ${disliked ? "active" : ""}`}
        onClick={() => handleToggleLike(false)} title="不喜歡">...</button>
```

按相同狀態會自動取消（後端 toggle 行為），UI 一起變成不亮。

---

## 四、為什麼「點歌就立刻 POST」（Option B 設計）

### 問題

最初的設計是「切歌時才 POST」，導致一個 bug：

```
play A → ref={A}                        (還沒送)
play B → flush(A)送出A、ref={B}          (B 還沒送)
play C → flush(B)送出C、ref={C}          (C 還沒送)
play D → flush(C)送出C、ref={D}          (D 還沒送)
[使用者重新整理]
        → useEffect cleanup 觸發 flush(D)
        → 但瀏覽器在 axios POST 完成前已切斷網路 → D 沒進 DB
```

使用者實際聽 4 首，但 refresh 後歷史紀錄只剩 3 首。

### 解法：先 POST 後 PATCH

| 時機 | 動作 |
| --- | --- |
| **點歌時** | 立刻 `POST /api/auth/history`（`watch_seconds=0`），把這首歌**建檔** |
| **切歌 / 結束 / 卸載** | `PATCH /api/auth/history/<id>` 更新 `watch_seconds` 為實際秒數 |

### 為什麼不會掉資料

- **POST 是快速 fire-and-forget**：使用者點下歌曲就建檔，後端紀錄立刻存在
- **即使 PATCH 沒送出**：紀錄已存在，只是 `watch_seconds` 維持 0；refresh 後仍會出現在歷史紀錄
- **避免 race condition**：後端 PATCH 有單調遞增保護，前端 ref 用 snapshot 避免覆寫

### Trade-off

- 短按一下沒聽完整首也會留下紀錄（`watch_seconds=0`）。若推薦系統要把這視為「無效播放」過濾即可。

---

## 五、資料流總覽

```
[使用者點某首歌]
        ↓
HomePage.handlePlay(song, source)
        ↓
flushCurrentHistory()                        ──→  PATCH /api/auth/history/<上一首id>
                                                  （等上一首 POST 回來拿 id 再 PATCH）

createHistory(song, 0, source)               ──→  POST /api/auth/history
                                                  resp.data.id 存進 playbackRef.historyId

getLikeStatus(song.id)                       ──→  GET  /api/auth/like
        ↓
[YouTube 播放，progress timer 跑著]
        ↓
[使用者切下一首 / 歌結束 / 離開頁面]
        ↓
flushCurrentHistory()                        ──→  PATCH /api/auth/history/<id>
                                                  （把實際 watch_seconds 補上去）


[使用者按愛心 / 拇指向下]
        ↓
handleToggleLike(true|false)                 ──→  POST /api/auth/like
        ↓
依後端回的 is_liked 設定 UI


[頁面載入]
        ↓
getHistory({ limit: 20 })                    ──→  GET /api/auth/history
                                                  → 去重後填入左側「歷史紀錄」
```

---

## 六、已知限制 / 後續可優化

1. **`watch_seconds` 不夠精準**：目前是讀 YouTube `getCurrentTime()`，使用者拖動進度條會偏掉。若要嚴格紀錄「實際聽幾秒」，需自己累計播放時間（在 timer 裡每秒 +1）。
2. **重溫舊愛 / 朋友也在聽 是 mock**：點下去 song_id 是 2001~3008，後端 POST 會回 `SONG_NOT_FOUND`，紀錄根本建不起來。等接上真資料後就會自動恢復正常。
3. **POST 失敗的歌不會再 PATCH**：`createPromise` resolve 為 null 時 flush 會直接 skip，不會反覆嘗試。
4. **短按沒聽就切歌也會留紀錄**：`watch_seconds=0` 的紀錄推薦系統可視為無效播放過濾。
5. **`GET /api/auth/history` 沒 cursor pagination**：總筆數多時可改 cursor；目前 limit 20 / offset 範圍小尚不需要。
6. **歷史紀錄 UI 去重邏輯在前端**：若希望伺服器端就回「distinct songs」，可在後端加 `?distinct=1` 模式，用 `DISTINCT ON (song_id)` 配合 `played_at desc`。

---

## 七、變更檔案清單

| 檔案 | 動作 |
| --- | --- |
| `backend/users/views.py` | 改 `HistoryView.get()` 帶 metadata、新增 `HistoryDetailView.patch()`、新增 `UserSongLikeView.get()` |
| `backend/users/urls.py` | 新增 `path('history/<int:pk>', HistoryDetailView.as_view(), ...)` |
| `frontend/src/api/history.js` | **新增**（含 `getHistory` / `createHistory` / `updateHistory` / `HISTORY_SOURCE`） |
| `frontend/src/api/likes.js` | **新增**（含 `getLikeStatus` / `toggleLike`） |
| `frontend/src/pages/HomePage.jsx` | 串接 history / like API、點歌立刻 POST、切歌時 PATCH、追蹤 historyId、還原 like 狀態 |

未動 model，**不需要 migration**。
最後更新日氣：2026-04-26
