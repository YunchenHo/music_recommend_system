"""LightFM 推薦服務。

提供兩種推理路徑：
1. Pure CF（暖用戶，≥10 首歷史）：歷史歌曲 embeddings 平均 → dot product
2. Hybrid（冷啟動，<10 首歷史）：user features + onboarding 歌曲 embeddings 混合

只依賴 numpy，不需要 lightfm 套件。
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache

import numpy as np
from django.conf import settings

from .feature_encoding import encode_user_features

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Artifact loading (cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_purecf_bundle():
    """載入 Pure CF npz artifact。"""
    path = settings.LIGHTFM_PURECF_ARTIFACT_PATH
    logger.info("Loading LightFM PureCF artifacts from %s", path)
    data = np.load(path)

    item_embeddings = data["item_embeddings"]  # (n_items, n_components)
    item_biases = data["item_biases"]          # (n_items,)
    song_ids = data["song_ids"]                # (n_items,)
    song_id_to_idx = {int(sid): i for i, sid in enumerate(song_ids)}

    logger.info(
        "PureCF loaded: %d songs, %d components",
        len(song_ids), item_embeddings.shape[1],
    )
    return item_embeddings, item_biases, song_ids, song_id_to_idx


@lru_cache(maxsize=1)
def _load_hybrid_bundle():
    """載入 Hybrid npz artifact（含 user feature embeddings）。"""
    path = settings.LIGHTFM_HYBRID_ARTIFACT_PATH
    logger.info("Loading LightFM Hybrid artifacts from %s", path)
    data = np.load(path, allow_pickle=True)

    item_embeddings = data["item_embeddings"]            # (n_items, n_components)
    item_biases = data["item_biases"]                    # (n_items,)
    song_ids = data["song_ids"]                          # (n_items,)
    user_feature_embeddings = data["user_feature_embeddings"]  # (n_features, n_components)
    user_feature_biases = data["user_feature_biases"]          # (n_features,)
    user_feature_names = json.loads(str(data["user_feature_names"]))  # list[str]

    song_id_to_idx = {int(sid): i for i, sid in enumerate(song_ids)}
    feature_name_to_idx = {name: i for i, name in enumerate(user_feature_names)}

    logger.info(
        "Hybrid loaded: %d songs, %d components, %d user features",
        len(song_ids), item_embeddings.shape[1], len(user_feature_names),
    )
    return (
        item_embeddings, item_biases, song_ids, song_id_to_idx,
        user_feature_embeddings, user_feature_biases, feature_name_to_idx,
    )


def clear_cache():
    """清除快取（供測試或 artifact 熱更新用）。"""
    _load_purecf_bundle.cache_clear()
    _load_hybrid_bundle.cache_clear()


# ---------------------------------------------------------------------------
# Recommendation functions
# ---------------------------------------------------------------------------

def recommend_purecf(
    history_song_ids: list[int],
    exclude_song_ids: set[int],
    affinity_map: dict[int, float] | None = None,
    top_n: int = 9,
) -> tuple[list[int], list[float]]:
    """Pure CF 推薦：Affinity 加權歷史歌曲 embeddings → dot product → top-K。

    Parameters
    ----------
    history_song_ids : list[int]
        用戶聽過的不重複歌曲 ID。
    exclude_song_ids : set[int]
        要排除的歌曲 ID（歷史 + onboarding）。
    affinity_map : dict[int, float] | None
        {song_id: affinity_score}，用於加權 user vector。
        None 時退回等權重平均。
    top_n : int
        回傳的推薦數量。

    Returns
    -------
    tuple[list[int], list[float]]
        (recommended_song_ids, scores)
    """
    from .affinity_score import AFFINITY_FILTER_THRESHOLD

    item_embeddings, item_biases, song_ids, song_id_to_idx = _load_purecf_bundle()

    default_affinity = settings.AFFINITY_DEFAULT_WEIGHT

    # 歷史歌曲 → model 內的 indices，並過濾掉 affinity 過低的歌曲
    valid_sids: list[int] = []
    for sid in history_song_ids:
        if sid not in song_id_to_idx:
            continue
        if affinity_map is not None:
            aff = affinity_map.get(sid, default_affinity)
            if aff < AFFINITY_FILTER_THRESHOLD:
                continue
        valid_sids.append(sid)

    indices = [song_id_to_idx[sid] for sid in valid_sids]

    if not indices:
        logger.warning(
            "PureCF: none of the %d history songs valid after affinity filter",
            len(history_song_ids),
        )
        return [], []

    # Affinity-weighted average → user vector
    if affinity_map is not None:
        raw_weights = np.array(
            [max(0.0, affinity_map.get(sid, default_affinity) + 0.5) for sid in valid_sids],
            dtype=np.float32,
        )
        weight_sum = raw_weights.sum()
        if weight_sum > 0:
            weights = raw_weights / weight_sum
            user_vector = (item_embeddings[indices] * weights[:, None]).sum(axis=0)
        else:
            user_vector = item_embeddings[indices].mean(axis=0)
    else:
        user_vector = item_embeddings[indices].mean(axis=0)

    # 計算所有歌曲分數（含 bias dampening）
    bias_beta = settings.LIGHTFM_BIAS_DAMPENING
    scores = user_vector @ item_embeddings.T + bias_beta * item_biases

    return _top_k_excluding(scores, song_ids, song_id_to_idx, exclude_song_ids, top_n)


def recommend_hybrid(
    user,
    onboarding_song_ids: list[int],
    exclude_song_ids: set[int],
    top_n: int = 9,
) -> tuple[list[int], list[float]]:
    """Hybrid 冷啟動推薦：user features + onboarding embeddings 混合。

    user_vector = α × feature_vector + (1-α) × taste_vector

    Parameters
    ----------
    user : User model instance
        Django User object (needs .age, .gender, .created_at)
    onboarding_song_ids : list[int]
        Onboarding 時選的歌曲 ID。
    exclude_song_ids : set[int]
        要排除的歌曲 ID。
    top_n : int
        回傳的推薦數量。

    Returns
    -------
    tuple[list[int], list[float]]
        (recommended_song_ids, scores)
    """
    (
        item_embeddings, item_biases, song_ids, song_id_to_idx,
        user_feature_embeddings, user_feature_biases, feature_name_to_idx,
    ) = _load_hybrid_bundle()

    alpha = settings.LIGHTFM_HYBRID_ALPHA
    n_components = item_embeddings.shape[1]

    # --- Feature vector ---
    tags = encode_user_features(
        user.age, user.gender, user.created_at,
        preferred_languages=getattr(user, 'preferred_languages', None),
    )
    feature_vector = np.zeros(n_components, dtype=np.float32)
    feature_bias = 0.0
    valid_count = 0

    for tag in tags:
        idx = feature_name_to_idx.get(tag)
        if idx is not None:
            feature_vector += user_feature_embeddings[idx]
            feature_bias += user_feature_biases[idx]
            valid_count += 1

    if valid_count > 0:
        feature_vector /= valid_count
        feature_bias /= valid_count

    # --- Taste vector (onboarding songs embeddings) ---
    taste_indices = [
        song_id_to_idx[sid]
        for sid in onboarding_song_ids
        if sid in song_id_to_idx
    ]

    taste_vector = np.zeros(n_components, dtype=np.float32)
    if taste_indices:
        taste_vector = item_embeddings[taste_indices].mean(axis=0)

    # --- Mix ---
    if valid_count > 0 and taste_indices:
        user_vector = alpha * feature_vector + (1 - alpha) * taste_vector
    elif taste_indices:
        # No valid features, use taste only
        user_vector = taste_vector
    elif valid_count > 0:
        # No onboarding songs in model, use features only
        user_vector = feature_vector
    else:
        logger.warning("Hybrid: no features and no onboarding songs found in model")
        return [], []

    # 計算所有歌曲分數（含 bias dampening）
    bias_beta = settings.LIGHTFM_BIAS_DAMPENING
    scores = user_vector @ item_embeddings.T + bias_beta * (item_biases + feature_bias)

    return _top_k_excluding(scores, song_ids, song_id_to_idx, exclude_song_ids, top_n)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _top_k_excluding(
    scores: np.ndarray,
    song_ids: np.ndarray,
    song_id_to_idx: dict[int, int],
    exclude_song_ids: set[int],
    top_n: int,
) -> tuple[list[int], list[float]]:
    """從 scores 中排除指定歌曲後取 top-K。"""
    exclude_indices = set()
    for sid in exclude_song_ids:
        idx = song_id_to_idx.get(sid)
        if idx is not None:
            exclude_indices.add(idx)

    ranked = np.argsort(-scores)

    result_ids: list[int] = []
    result_scores: list[float] = []
    for idx in ranked:
        if idx in exclude_indices:
            continue
        result_ids.append(int(song_ids[idx]))
        result_scores.append(float(scores[idx]))
        if len(result_ids) >= top_n:
            break

    return result_ids, result_scores
