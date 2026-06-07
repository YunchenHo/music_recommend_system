# LightFM Artifacts

以下 artifact 不納入版本控制（檔案過大），pull 下來後需自行在本地產生：

- `recommender/artifacts/lightfm_purecf.npz` — Pure CF 模式的 item embeddings（給歷史 ≥10 首的用戶）
- `recommender/artifacts/lightfm_hybrid.npz` — Hybrid 模式，含 user feature embeddings（給冷啟動用戶）

---

## 1. 建立環境

> **Windows 額外需求：** 安裝 [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)，勾選「使用 C++ 的桌面開發」。
> 這是因為 LightFM 底層是 C/Cython 寫的，安裝時需要編譯，Windows 預設沒有 C 編譯器。

```bash
cd recommender

# 建立 .venv
uv venv .venv --python 3.11

# 安裝專案依賴
uv pip install -e . --python .venv/bin/python

# 安裝 LightFM（需 patch，不能直接 pip install）
VIRTUAL_ENV=.venv uv pip install "numpy<2" "setuptools<60" wheel "cython<3"

mkdir -p /tmp/lfm && cd /tmp/lfm
curl -fsSL -o lightfm-1.17.tar.gz \
  https://files.pythonhosted.org/packages/1f/96/5ec230f5c27811534af0faaa8525f11c1000ee1c24c8a82c0546d0724aea/lightfm-1.17.tar.gz
tar xzf lightfm-1.17.tar.gz

sed -i 's/__builtins__.__LIGHTFM_SETUP__ = True/import builtins as _builtins; _builtins.__LIGHTFM_SETUP__ = True/' \
  /tmp/lfm/lightfm-1.17/setup.py

cd /path/to/repo/recommender
VIRTUAL_ENV=.venv uv pip install --no-build-isolation /tmp/lfm/lightfm-1.17

# macOS 若要多執行緒，需額外裝 libomp：
# brew install libomp
# CFLAGS="-I/opt/homebrew/opt/libomp/include" \
# LDFLAGS="-L/opt/homebrew/opt/libomp/lib -lomp" \
# VIRTUAL_ENV=.venv uv pip install --no-build-isolation /tmp/lfm/lightfm-1.17
```

### 驗證安裝

```bash
.venv/bin/python -c "import lightfm; print('LightFM OK')"
```

---

## 2. 產生 Artifacts

```bash
cd recommender
.venv/bin/python -m pipeline.stage_db02_lightfm_from_kkbox
```

這會一次完成：
1. 讀取 KKBOX 資料集互動資料（5000 用戶、15 萬首歌）
2. 篩選正向互動（target=1）並去重
3. 分別訓練 Pure CF 和 Hybrid 兩個 LightFM 模型（WARP loss, 128 維, 30 epochs）
4. 輸出 `artifacts/lightfm_purecf.npz` 和 `artifacts/lightfm_hybrid.npz`

預計耗時約 3-5 分鐘（Windows 無 OpenMP 時可加 `--num-threads 1`，會稍慢）。

### 可選參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `--mode` | `both` | 可選 `purecf`、`hybrid`、`both` |
| `--epochs` | 30 | 訓練輪數 |
| `--no-components` | 128 | Embedding 維度 |
| `--num-threads` | 4 | 平行執行緒數 |

---

## 3. 啟動系統

```bash
docker compose up
```

`docker-compose.yml` 已設定將 `recommender/artifacts/` 掛載到後端容器的 `/app/recommender_artifacts`，後端會自動載入 `.npz` 進行推薦。

---

## 舊流程（已棄用）

之前的流程需要先從 Django DB 匯出資料再訓練（`export_for_lightfm` → `stage_db01`），
現已改為直接使用 KKBOX 資料集訓練，品質更好且不依賴系統內的種子用戶資料。
