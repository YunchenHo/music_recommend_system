"""
ItemKNN artifact 載入與推薦（lazy + lru_cache 快取一份於行程內）。

不依賴 recommender 套件；推薦加總邏輯與 recommender/src/models/itemknn.recommend_from_seed_item_indices 一致。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from django.conf import settings


def clear_itemknn_cache() -> None:
    """測試或重新載入設定時清除快取。"""
    _load_itemknn_bundle.cache_clear()


@lru_cache(maxsize=1)
def _load_itemknn_bundle() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[int, int], int]:
    path_raw = getattr(settings, "ITEMKNN_ARTIFACT_PATH", None)
    if not path_raw:
        raise FileNotFoundError("ITEMKNN_ARTIFACT_PATH is not set")
    path = Path(path_raw)
    if not path.is_file():
        raise FileNotFoundError(f"ItemKNN artifact not found: {path}")

    with np.load(path, allow_pickle=False) as data:
        neigh_items = np.asarray(data["neigh_items"], dtype=np.int32)
        neigh_sims = np.asarray(data["neigh_sims"], dtype=np.float32)
        idx2item = np.asarray(data["idx2item"], dtype=np.int32)
        if "item_k" in data:
            item_k = int(np.asarray(data["item_k"]).reshape(-1)[0])
        else:
            item_k = int(neigh_items.shape[1])

    if neigh_items.shape[0] != idx2item.shape[0]:
        raise ValueError(
            f"neigh_items rows {neigh_items.shape[0]} != len(idx2item) {idx2item.shape[0]}"
        )
    if neigh_sims.shape != neigh_items.shape:
        raise ValueError("neigh_sims shape must match neigh_items")

    song_id_to_idx = {int(sid): i for i, sid in enumerate(idx2item)}
    return neigh_items, neigh_sims, idx2item, song_id_to_idx, item_k


def _recommend_from_seed_item_indices(
    seed_item_indices: np.ndarray,
    neigh_items: np.ndarray,
    neigh_sims: np.ndarray,
    top_n: int = 20,
    aggregation: str = "baseline",
    sim_threshold: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    seed_item_indices = np.asarray(seed_item_indices, dtype=np.int32).ravel()
    if seed_item_indices.size == 0:
        return np.array([], dtype=np.int32), np.array([], dtype=np.float32)

    seen = {int(x) for x in seed_item_indices.tolist()}
    scores: dict[int, float] = {}
    num_seed = int(seed_item_indices.size)

    for it in seed_item_indices:
        it = int(it)
        for nb, sim in zip(neigh_items[it], neigh_sims[it]):
            if int(nb) in seen:
                continue
            if float(sim) <= sim_threshold:
                continue
            add = float(sim) / num_seed if aggregation == "normalize_seed" else float(sim)
            nb_i = int(nb)
            scores[nb_i] = scores.get(nb_i, 0.0) + add

    if not scores:
        return np.array([], dtype=np.int32), np.array([], dtype=np.float32)

    cand_items = np.fromiter(scores.keys(), dtype=np.int32)
    cand_scores = np.fromiter(scores.values(), dtype=np.float32)

    if cand_items.size > top_n:
        top_idx = np.argpartition(-cand_scores, top_n - 1)[:top_n]
        cand_items = cand_items[top_idx]
        cand_scores = cand_scores[top_idx]

    order = np.argsort(-cand_scores)
    return cand_items[order], cand_scores[order]


def recommend_song_ids_from_seed_song_ids(
    seed_song_ids: list[int],
    top_n: int = 20,
    aggregation: str = "baseline",
    sim_threshold: float = 0.0,
) -> tuple[list[int], list[float], list[int]]:
    """
    依種子 song_id（與訓練資料 song_id / Song.pk 一致）回傳推薦 song_id 與分數。

    回傳 (recommended_song_ids, scores, skipped_seed_ids)：
    skipped_seed_ids 為在模型詞彙中找不到的種子 id。
    """
    neigh_items, neigh_sims, idx2item, song_id_to_idx, _item_k = _load_itemknn_bundle()

    skipped: list[int] = []
    indices: list[int] = []
    seen_j: set[int] = set()
    for sid in seed_song_ids:
        j = song_id_to_idx.get(int(sid))
        if j is None:
            skipped.append(int(sid))
            continue
        if j in seen_j:
            continue
        seen_j.add(j)
        indices.append(j)

    if not indices:
        return [], [], skipped

    cand_idx, cand_scores = _recommend_from_seed_item_indices(
        np.asarray(indices, dtype=np.int32),
        neigh_items,
        neigh_sims,
        top_n=top_n,
        aggregation=aggregation,
        sim_threshold=sim_threshold,
    )

    out_ids = [int(idx2item[i]) for i in cand_idx]
    out_scores = [float(s) for s in cand_scores]
    return out_ids, out_scores, skipped
