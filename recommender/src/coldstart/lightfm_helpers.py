"""LightFM helpers tailored for the cold-start pipeline.

Three pieces:

1. `build_lightfm_data_from_split` — takes the pre-split (df_train, df_test,
   useridx, itemidx) emitted by `src/coldstart/split.py` and builds a
   `LightFMData`. Mirrors the post-split half of
   `src/models/lightfm_model.py::prepare_lightfm_dataset` but skips the LOO
   call (we already have a cold-start split).

2. `predict_topk_known_users` — Scenario A top-K predictions for users that
   are in the training matrix. Thin wrapper around `model.predict()`.

3. `predict_topk_unseen_users` — Scenario C top-K predictions for users
   **not** in the training matrix. Implementation detail: we keep the
   trained `dataset` / `model` untouched and manually construct each cold
   user's feature row in the existing `(n_train + n_user_tags)`-wide feature
   space — identity columns = 0, tag columns = normalized — then vstack
   with `data.user_features` so `model.predict(row_idx)` works. This avoids
   `fit_partial` (which would extend the identity feature space and break
   the model's embedding table dimensions).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.lightfm_model import (
    LightFMData,
    build_item_feature_tags,
    build_user_feature_tags,
    collect_unique_feature_tags,
)


def build_lightfm_data_from_split(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    useridx: dict,
    itemidx: dict,
    members: pd.DataFrame | None = None,
    songs: pd.DataFrame | None = None,
    *,
    use_features: bool = True,
    top_k_cities: int = 30,
    top_k_artists: int = 5000,
) -> LightFMData:
    """Build LightFMData directly from a cold-start split (no internal LOO)."""
    from lightfm.data import Dataset

    user_ids = list(useridx.values())
    item_ids = list(itemidx.values())

    user_feature_map: dict[int, list[str]] = {}
    item_feature_map: dict[int, list[str]] = {}
    user_feature_tags: list[str] = []
    item_feature_tags: list[str] = []

    if use_features:
        if members is None or songs is None:
            raise ValueError("use_features=True requires both members and songs")

        member_subset = members[members["msno_id"].isin(useridx)].copy()
        raw_user_tags = build_user_feature_tags(member_subset, top_k_cities=top_k_cities)
        user_feature_map = {
            useridx[msno]: tags
            for msno, tags in raw_user_tags.items()
            if msno in useridx
        }
        user_feature_tags = collect_unique_feature_tags(user_feature_map)

        song_subset = songs[songs["song_id_new"].isin(itemidx)].copy()
        raw_item_tags = build_item_feature_tags(
            song_subset, top_k_artists=top_k_artists
        )
        item_feature_map = {
            itemidx[sid]: tags
            for sid, tags in raw_item_tags.items()
            if sid in itemidx
        }
        item_feature_tags = collect_unique_feature_tags(item_feature_map)

    # Keep LightFM's default identity_features=True for BOTH hybrid and pureCF:
    # - pureCF needs identity (no tags provided); identity = its only embedding source
    # - hybrid uses identity + tag features (matches `prepare_lightfm_dataset`'s
    #   conventional setup); warm users in Scenario A get expressive per-user
    #   embeddings instead of being squashed into a tiny ~41-dim tag space.
    # Scenario C cold-start is handled separately in `predict_topk_unseen_users`
    # by manually building a (1, n_features) row with 0s in identity columns.
    dataset = Dataset()
    dataset.fit(
        users=user_ids,
        items=item_ids,
        user_features=user_feature_tags if use_features else None,
        item_features=item_feature_tags if use_features else None,
    )

    train_pos = df_train[df_train["target"] == 1]
    pairs = zip(
        train_pos["msno_idx"].astype(int).tolist(),
        train_pos["song_idx"].astype(int).tolist(),
    )
    interactions, _ = dataset.build_interactions(pairs)

    user_features = None
    item_features = None
    if use_features:
        user_features = dataset.build_user_features(
            ((uid, tags) for uid, tags in user_feature_map.items()),
            normalize=True,
        )
        item_features = dataset.build_item_features(
            ((iid, tags) for iid, tags in item_feature_map.items()),
            normalize=True,
        )

    return LightFMData(
        dataset=dataset,
        interactions=interactions,
        user_features=user_features,
        item_features=item_features,
        df_train=df_train,
        df_test=df_test,
        num_users=len(user_ids),
        num_items=len(item_ids),
    )


def predict_topk_known_users(
    model,
    data: LightFMData,
    user_truth: dict[int, list[int]],
    *,
    max_k: int,
    num_threads: int = 1,
) -> dict[int, list[int]]:
    """Top-K predictions for users already in the training matrix (Scenario A)."""
    n_items = data.num_items
    all_items = np.arange(n_items, dtype=np.int32)

    train_pos = data.df_train[data.df_train["target"] == 1]
    train_history = train_pos.groupby("msno_idx")["song_idx"].apply(set).to_dict()

    user_topk: dict[int, list[int]] = {}
    for uid in user_truth:
        scores = model.predict(
            int(uid),
            all_items,
            user_features=data.user_features,
            item_features=data.item_features,
            num_threads=num_threads,
        )
        seen = train_history.get(uid)
        if seen:
            seen_arr = np.fromiter(seen, dtype=np.int32, count=len(seen))
            scores[seen_arr] = -np.inf

        top_idx = np.argpartition(-scores, max_k)[:max_k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]
        user_topk[uid] = top_idx.tolist()
    return user_topk


def predict_topk_unseen_users(
    model,
    data: LightFMData,
    members: pd.DataFrame,
    useridx: dict,
    test_user_ids: list,
    user_truth: dict,
    *,
    max_k: int,
    top_k_cities: int = 30,
    num_threads: int = 1,
) -> dict:
    """Top-K predictions for users **not** in the training matrix (Scenario C).

    Requires use_features=True. PureCF would fail (no embedding row for cold user).

    Implementation: instead of `fit_partial`-ing cold users into the dataset
    (which would extend the identity feature space and break the model's
    embedding table dimensions), we **manually** construct each cold user's
    feature row in the existing `(n_train + n_user_tags)`-wide feature space:
      - identity columns (first n_train) = 0  (cold user has no identity)
      - tag columns = normalized 1/k for each tag the user has

    Then vstack with the trained user_features and predict at row index
    `n_train + i`.
    """
    if data.user_features is None:
        raise RuntimeError(
            "predict_topk_unseen_users requires use_features=True. "
            "Scenario C is not supported for LightFM-pureCF."
        )

    from scipy.sparse import csr_matrix, vstack as sparse_vstack

    dataset = data.dataset
    n_items = data.num_items
    n_train, n_total_cols = data.user_features.shape
    all_items = np.arange(n_items, dtype=np.int32)

    # dataset.mapping() returns (user_id_map, user_feature_map, item_id_map, item_feature_map).
    # user_feature_map already includes identity entries (user_ids) AND tag strings.
    _, user_feature_mapping, _, _ = dataset.mapping()

    cold_member_subset = members[members["msno_id"].isin(set(test_user_ids))].copy()
    cold_user_tags_raw = build_user_feature_tags(
        cold_member_subset, top_k_cities=top_k_cities
    )

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    cold_row_idx: dict = {}  # raw_msno → row idx in the vstack-extended matrix

    for i, raw_msno in enumerate(test_user_ids):
        tags = cold_user_tags_raw.get(raw_msno, [])
        valid_cols = [
            user_feature_mapping[t] for t in tags if t in user_feature_mapping
        ]
        if not valid_cols:
            continue
        weight = 1.0 / len(valid_cols)
        for col in valid_cols:
            rows.append(i)
            cols.append(col)
            vals.append(weight)
        cold_row_idx[raw_msno] = n_train + i

    cold_user_features = csr_matrix(
        (vals, (rows, cols)),
        shape=(len(test_user_ids), n_total_cols),
        dtype=data.user_features.dtype,
    )
    extended_user_features = sparse_vstack(
        [data.user_features, cold_user_features], format="csr"
    )

    user_topk: dict = {}
    for cold_msno in user_truth:
        ext_idx = cold_row_idx.get(cold_msno)
        if ext_idx is None:
            continue
        scores = model.predict(
            ext_idx,
            all_items,
            user_features=extended_user_features,
            item_features=data.item_features,
            num_threads=num_threads,
        )
        top_idx = np.argpartition(-scores, max_k)[:max_k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]
        user_topk[cold_msno] = top_idx.tolist()
    return user_topk
