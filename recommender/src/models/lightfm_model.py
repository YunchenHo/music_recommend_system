from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


@dataclass
class LightFMData:
    dataset: object
    interactions: csr_matrix
    user_features: csr_matrix | None
    item_features: csr_matrix | None
    df_train: pd.DataFrame
    df_test: pd.DataFrame
    num_users: int
    num_items: int


def filter_top_users_by_activity(
    train_encoded: pd.DataFrame,
    members: pd.DataFrame,
    top_k: int,
    min_membership_days: int = 30,
) -> pd.DataFrame:
    """Filter train_encoded to the top_k users by total play_count.

    Mirrors `src.preprocess.train.filter_top_members` exactly so that LightFM's
    user set is identical to ItemKNN's top-K cohort:
      1. play_count = total interactions per msno_id in train (includes target=0).
      2. Eligible members satisfy membership_days > min_membership_days.
      3. Sort eligible members by play_count desc, take top_k.
    """
    member_play_counts = train_encoded["msno_id"].value_counts()
    m = members.copy()
    m["play_count"] = m["msno_id"].map(member_play_counts).fillna(0).astype("int64")
    candidates = m[m["membership_days"] > min_membership_days]
    top_members = (
        candidates.sort_values(by="play_count", ascending=False).head(top_k).copy()
    )
    vip_ids = set(top_members["msno_id"].values.tolist())
    return train_encoded[train_encoded["msno_id"].isin(vip_ids)].copy()


def loo_split(
    train_encoded: pd.DataFrame,
    min_pos_per_user: int = 2,
    seed: int = 42,
    max_users: int | None = None,
    sample_rate: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    """Leave-one-out split mirroring `src.models.mf.prepare_mf_data` exactly.

    Inlined here so importing this module does not pull in TensorFlow.
    Returns (df_train, df_test, useridx, itemidx).
    """
    df_pos = train_encoded[train_encoded["target"] == 1].copy()
    user_counts = df_pos.groupby("msno_id").size()
    valid_users = user_counts[user_counts >= min_pos_per_user].index

    if max_users is not None:
        valid_users = valid_users[:max_users]

    df_filtered = train_encoded[train_encoded["msno_id"].isin(valid_users)].copy()
    if sample_rate is not None and 0 < sample_rate < 1:
        df_filtered = df_filtered.sample(frac=sample_rate, random_state=seed).copy()

    unique_users = df_filtered["msno_id"].unique()
    useridx = {old_id: new_id for new_id, old_id in enumerate(unique_users)}

    unique_songs = df_filtered["song_id"].unique()
    itemidx = {old_id: new_id for new_id, old_id in enumerate(unique_songs)}

    df_filtered["msno_idx"] = df_filtered["msno_id"].map(useridx)
    df_filtered["song_idx"] = df_filtered["song_id"].map(itemidx)

    df_positives = df_filtered[df_filtered["target"] == 1].copy()
    df_positives = df_positives.sample(frac=1, random_state=seed).sort_values("msno_idx")
    test_indices = df_positives.groupby("msno_idx").tail(1).index

    df_test = df_positives.loc[test_indices].copy()
    df_train = df_filtered.drop(test_indices).copy()
    df_train = df_train.sample(frac=1, random_state=seed).reset_index(drop=True)

    return df_train, df_test, useridx, itemidx


def _bucket_quantile(s: pd.Series, n_buckets: int = 5, prefix: str = "b") -> pd.Series:
    try:
        labels = [f"{prefix}{i}" for i in range(n_buckets)]
        return pd.qcut(s, q=n_buckets, labels=labels, duplicates="drop").astype(str)
    except ValueError:
        return pd.Series([f"{prefix}0"] * len(s), index=s.index)


def build_user_feature_tags(
    members: pd.DataFrame, top_k_cities: int = 30
) -> dict[int, list[str]]:
    """Build a {msno_id: [feature_tag, ...]} map from complete_members.parquet."""
    m = members.copy()

    city_counts = m["city"].value_counts()
    top_cities = set(city_counts.head(top_k_cities).index.tolist())
    m["city_tag"] = m["city"].apply(
        lambda c: f"city_{int(c)}" if c in top_cities else "city_other"
    )

    gender_tag = []
    for fem, mal in zip(m["gender_female"].values, m["gender_male"].values):
        if fem == 1:
            gender_tag.append("gender_female")
        elif mal == 1:
            gender_tag.append("gender_male")
        else:
            gender_tag.append("gender_unknown")
    m["gender_tag"] = gender_tag

    m["bd_tag"] = "bd_" + m["bd_group"].astype(int).astype(str)
    m["ms_tag"] = "ms_" + m["membership_group"].astype(int).astype(str)
    m["reg_tag"] = "reg_" + m["registered_via"].astype(int).astype(str)

    feature_cols = ["bd_tag", "gender_tag", "ms_tag", "reg_tag", "city_tag"]
    user_features = {
        int(row.msno_id): [getattr(row, c) for c in feature_cols]
        for row in m.itertuples(index=False)
    }
    return user_features


def build_item_feature_tags(
    songs: pd.DataFrame, top_k_artists: int = 5000, length_buckets: int = 5
) -> dict[int, list[str]]:
    """Build a {song_id_new: [feature_tag, ...]} map from song_features.parquet."""
    s = songs.copy()

    artist_counts = s["artist_name"].value_counts()
    top_artists = set(artist_counts.head(top_k_artists).index.tolist())
    s["artist_tag"] = s["artist_name"].apply(
        lambda a: f"artist_{a}" if a in top_artists else "artist_other"
    )

    s["lang_tag"] = "lang_" + s["language"].fillna(-1).astype(int).astype(str)
    s["length_tag"] = _bucket_quantile(
        s["song_length"].fillna(s["song_length"].median()),
        n_buckets=length_buckets,
        prefix="len_",
    )

    def genre_tags(g):
        if not isinstance(g, str) or g == "unknown":
            return ["genre_unknown"]
        return [f"genre_{x}" for x in g.split("|") if x]

    s["genre_tag_list"] = s["genre_ids"].apply(genre_tags)

    item_features: dict[int, list[str]] = {}
    for row in s.itertuples(index=False):
        tags = [row.lang_tag, row.artist_tag, row.length_tag, *row.genre_tag_list]
        item_features[int(row.song_id_new)] = tags

    return item_features


def collect_unique_feature_tags(tag_map: dict[int, list[str]]) -> list[str]:
    seen: set[str] = set()
    for tags in tag_map.values():
        seen.update(tags)
    return sorted(seen)


def prepare_lightfm_dataset(
    train_encoded: pd.DataFrame,
    members: pd.DataFrame | None = None,
    songs: pd.DataFrame | None = None,
    *,
    use_features: bool = True,
    min_pos_per_user: int = 2,
    seed: int = 42,
    max_users: int | None = None,
    sample_rate: float | None = None,
    top_k_cities: int = 30,
    top_k_artists: int = 5000,
) -> LightFMData:
    """Build a LightFM Dataset + interactions + (optional) feature matrices.

    `members` and `songs` are required when `use_features=True`. The interactions
    matrix is built from the LOO split's train portion (positives only). Test
    interactions are returned separately in `df_test` for downstream evaluation.
    """
    from lightfm.data import Dataset

    df_train, df_test, useridx, itemidx = loo_split(
        train_encoded,
        min_pos_per_user=min_pos_per_user,
        seed=seed,
        max_users=max_users,
        sample_rate=sample_rate,
    )

    user_ids = list(useridx.values())
    item_ids = list(itemidx.values())

    user_feature_map: dict[int, list[str]] = {}
    item_feature_map: dict[int, list[str]] = {}
    user_feature_tags: Iterable[str] = []
    item_feature_tags: Iterable[str] = []

    if use_features:
        if members is None or songs is None:
            raise ValueError("use_features=True requires both members and songs")

        msno_to_user_idx = useridx
        member_subset = members[members["msno_id"].isin(msno_to_user_idx)].copy()
        raw_user_tags = build_user_feature_tags(member_subset, top_k_cities=top_k_cities)
        user_feature_map = {
            msno_to_user_idx[msno]: tags
            for msno, tags in raw_user_tags.items()
            if msno in msno_to_user_idx
        }
        user_feature_tags = collect_unique_feature_tags(user_feature_map)

        song_to_item_idx = itemidx
        song_subset = songs[songs["song_id_new"].isin(song_to_item_idx)].copy()
        raw_item_tags = build_item_feature_tags(
            song_subset, top_k_artists=top_k_artists
        )
        item_feature_map = {
            song_to_item_idx[sid]: tags
            for sid, tags in raw_item_tags.items()
            if sid in song_to_item_idx
        }
        item_feature_tags = collect_unique_feature_tags(item_feature_map)

    dataset = Dataset()
    dataset.fit(
        users=user_ids,
        items=item_ids,
        user_features=user_feature_tags,
        item_features=item_feature_tags,
    )

    train_pos = df_train[df_train["target"] == 1]
    pairs = zip(train_pos["msno_idx"].astype(int).tolist(),
                train_pos["song_idx"].astype(int).tolist())
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


def train_lightfm_model(
    data: LightFMData,
    *,
    no_components: int = 128,
    loss: str = "warp",
    learning_rate: float = 0.05,
    epochs: int = 10,
    num_threads: int = 4,
    seed: int = 42,
    verbose: bool = True,
    max_sampled: int = 10,
    item_alpha: float = 0.0,
    user_alpha: float = 0.0,
):
    from lightfm import LightFM

    model = LightFM(
        no_components=no_components,
        loss=loss,
        learning_rate=learning_rate,
        random_state=seed,
        max_sampled=max_sampled,
        item_alpha=item_alpha,
        user_alpha=user_alpha,
    )
    model.fit(
        data.interactions,
        user_features=data.user_features,
        item_features=data.item_features,
        epochs=epochs,
        num_threads=num_threads,
        verbose=verbose,
    )
    return model


def evaluate_lightfm(
    model,
    data: LightFMData,
    *,
    eval_ks: tuple[int, ...] = (10, 20),
    num_threads: int = 4,
    batch_size: int = 500,
) -> pd.DataFrame:
    """Top-K recommendation evaluation matching evaluate_mf_with_faiss schema.

    For each test user: score all items, mask out items already seen in train,
    take top-max(eval_ks), record hit + NDCG gain.
    Output columns: Model, K, Recall, Precision, NDCG (long format).
    """
    import math
    from tqdm import tqdm

    n_items = data.num_items
    all_items = np.arange(n_items, dtype=np.int32)

    train_pos = data.df_train[data.df_train["target"] == 1]
    train_history: dict[int, set[int]] = (
        train_pos.groupby("msno_idx")["song_idx"].apply(set).to_dict()
    )
    test_ground_truth: dict[int, list[int]] = (
        data.df_test.groupby("msno_idx")["song_idx"].apply(list).to_dict()
    )
    train_known_items = set(train_pos["song_idx"].unique().tolist())

    hits = {k: 0 for k in eval_ks}
    ndcgs = {k: 0.0 for k in eval_ks}
    n_eval = 0
    max_k = max(eval_ks)

    test_users = list(test_ground_truth.keys())

    for i in tqdm(range(0, len(test_users), batch_size), desc="LightFM eval"):
        batch_uids = test_users[i : i + batch_size]
        for uid in batch_uids:
            test_item = test_ground_truth[uid][0]
            if test_item not in train_known_items:
                continue

            scores = model.predict(
                int(uid),
                all_items,
                user_features=data.user_features,
                item_features=data.item_features,
                num_threads=num_threads,
            )

            seen = train_history.get(uid, set())
            if seen:
                seen_arr = np.fromiter(seen, dtype=np.int32, count=len(seen))
                scores[seen_arr] = -np.inf

            top_idx = np.argpartition(-scores, max_k)[:max_k]
            top_idx = top_idx[np.argsort(-scores[top_idx])]

            n_eval += 1
            for k in eval_ks:
                top_k = top_idx[:k]
                if test_item in top_k:
                    hits[k] += 1
                    rank = int(np.where(top_k == test_item)[0][0])
                    ndcgs[k] += 1.0 / math.log2(rank + 2)

    results = []
    for k in eval_ks:
        recall = hits[k] / n_eval if n_eval else 0.0
        precision = hits[k] / (n_eval * k) if n_eval else 0.0
        ndcg = ndcgs[k] / n_eval if n_eval else 0.0
        results.append(
            {
                "Model": "LightFM",
                "K": k,
                "Recall": round(recall, 5),
                "Precision": round(precision, 5),
                "NDCG": round(ndcg, 5),
                "Users_evaluated": n_eval,
            }
        )
    return pd.DataFrame(results)
