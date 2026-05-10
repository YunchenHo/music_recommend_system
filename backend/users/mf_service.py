"""
MF Fold-in 推薦服務：載入離線 artifacts，即時計算 user embedding 並推薦。

不依賴 recommender 套件；fold-in 邏輯自包含。
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Artifact loading (lazy, cached)
# ---------------------------------------------------------------------------

MF_MIN_INTERACTIONS = 15
MF_LAMBDA_REG = 0.1
MF_NEGATIVE_RATIO = 1  # 負樣本 : 正樣本 = 1:1


@lru_cache(maxsize=1)
def _load_mf_bundle() -> tuple[np.ndarray, np.ndarray, dict[int, int], dict[int, int]]:
    """
    載入 MF artifacts，回傳:
      - song_embeddings: (num_items, dim)
      - song_bias: (num_items,)
      - item_mapping: {song_id -> embedding_index}
      - reverse_mapping: {embedding_index -> song_id}
    """
    artifact_dir = Path(getattr(settings, "MF_ARTIFACT_DIR", "/app/recommender_artifacts"))

    emb_path = artifact_dir / "mf_song_embeddings.npy"
    bias_path = artifact_dir / "mf_song_bias.npy"
    mapping_path = artifact_dir / "mf_item_mapping.json"

    if not emb_path.is_file():
        raise FileNotFoundError(f"MF song embeddings not found: {emb_path}")
    if not mapping_path.is_file():
        raise FileNotFoundError(f"MF item mapping not found: {mapping_path}")

    song_embeddings = np.load(emb_path).astype("float32")
    song_bias = np.load(bias_path).astype("float32") if bias_path.is_file() else np.zeros(
        song_embeddings.shape[0], dtype="float32"
    )

    with open(mapping_path, "r", encoding="utf-8") as f:
        raw_mapping = json.load(f)
    item_mapping = {int(k): int(v) for k, v in raw_mapping.items()}
    reverse_mapping = {v: k for k, v in item_mapping.items()}

    logger.info(
        "[MF] Loaded artifacts: embeddings %s, items %d",
        song_embeddings.shape,
        len(item_mapping),
    )
    return song_embeddings, song_bias, item_mapping, reverse_mapping


def clear_mf_cache() -> None:
    """測試或重新載入時清除快取。"""
    _load_mf_bundle.cache_clear()


# ---------------------------------------------------------------------------
# Fold-in core
# ---------------------------------------------------------------------------


def fold_in_user(
    interactions: list[dict],
    lambda_reg: float = MF_LAMBDA_REG,
) -> np.ndarray | None:
    """
    根據使用者互動計算 user embedding (fold-in)。

    Parameters
    ----------
    interactions : list of {"song_id": int, "target": 0 or 1}
    lambda_reg : L2 正則化參數

    Returns
    -------
    user_embedding (dim,) 或 None（互動不足時）
    """
    song_embeddings, song_bias, item_mapping, _ = _load_mf_bundle()
    dim = song_embeddings.shape[1]

    # 篩選 item_mapping 中存在的互動
    valid_indices = []
    valid_targets = []
    for interaction in interactions:
        idx = item_mapping.get(int(interaction["song_id"]))
        if idx is not None:
            valid_indices.append(idx)
            valid_targets.append(float(interaction["target"]))

    if len(valid_indices) < MF_MIN_INTERACTIONS:
        return None

    indices = np.array(valid_indices, dtype=np.int32)
    y = np.array(valid_targets, dtype=np.float32)

    # 取出對應的 song embedding 子矩陣
    V_s = song_embeddings[indices]  # (n, dim)

    # 減去 song bias
    y_adjusted = y - song_bias[indices]

    # Ridge regression: u = (V_s^T V_s + λI)^{-1} V_s^T y_adjusted
    VtV = V_s.T @ V_s  # (dim, dim)
    VtY = V_s.T @ y_adjusted  # (dim,)
    A = VtV + lambda_reg * np.eye(dim, dtype=np.float32)
    user_embedding = np.linalg.solve(A, VtY)

    return user_embedding.astype("float32")


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


def recommend_song_ids_for_user(
    interactions: list[dict],
    top_n: int = 30,
    lambda_reg: float = MF_LAMBDA_REG,
) -> tuple[list[int], list[float]] | None:
    """
    對使用者執行 fold-in 並回傳推薦 song_ids。

    Parameters
    ----------
    interactions : list of {"song_id": int, "target": 0 or 1}
        包含正樣本、明確負樣本、和隨機負樣本。
    top_n : 回傳數量
    lambda_reg : 正則化參數

    Returns
    -------
    (song_ids, scores) 或 None（互動不足）
    """
    user_embedding = fold_in_user(interactions, lambda_reg=lambda_reg)
    if user_embedding is None:
        return None

    song_embeddings, song_bias, item_mapping, reverse_mapping = _load_mf_bundle()

    # 計算 user embedding 與所有 song embeddings 的內積 + song bias
    scores = song_embeddings @ user_embedding + song_bias  # (num_items,)

    # 排除已互動過的歌
    interacted_indices = set()
    for interaction in interactions:
        idx = item_mapping.get(int(interaction["song_id"]))
        if idx is not None:
            interacted_indices.add(idx)

    # 將已互動的設為 -inf
    scores_filtered = scores.copy()
    for idx in interacted_indices:
        scores_filtered[idx] = -np.inf

    # 取 Top-N
    search_n = min(top_n * 3, len(scores_filtered))
    top_indices = np.argpartition(-scores_filtered, search_n - 1)[:search_n]
    top_indices = top_indices[np.argsort(-scores_filtered[top_indices])][:top_n]

    # 轉回 song_id
    song_ids = []
    song_scores = []
    for idx in top_indices:
        sid = reverse_mapping.get(int(idx))
        if sid is not None:
            song_ids.append(sid)
            song_scores.append(float(scores_filtered[idx]))

    return song_ids, song_scores


def generate_negative_samples(
    positive_song_ids: set[int],
    all_interacted_song_ids: set[int],
    ratio: int = MF_NEGATIVE_RATIO,
    seed: int | None = None,
) -> list[dict]:
    """
    從 item_mapping 中隨機抽取負樣本（使用者未互動過的歌）。

    Parameters
    ----------
    positive_song_ids : 正樣本的 song_id 集合
    all_interacted_song_ids : 所有互動過的 song_id（正 + 明確負）
    ratio : 負樣本數量 = len(positive_song_ids) * ratio
    seed : random seed（可用 user_id 以保持穩定）

    Returns
    -------
    list of {"song_id": int, "target": 0}
    """
    _, _, item_mapping, _ = _load_mf_bundle()

    # 所有可抽的 song_id（在 mapping 中且使用者未互動過）
    all_mapped_songs = set(item_mapping.keys())
    candidates = list(all_mapped_songs - all_interacted_song_ids)

    if not candidates:
        return []

    n_samples = min(len(positive_song_ids) * ratio, len(candidates))
    rng = np.random.default_rng(seed)
    sampled = rng.choice(candidates, size=n_samples, replace=False)

    return [{"song_id": int(sid), "target": 0} for sid in sampled]
