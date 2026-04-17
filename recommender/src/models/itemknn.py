from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors


@dataclass
class KNNData:
    train_subset: pd.DataFrame
    pos_df: pd.DataFrame
    train_split: pd.DataFrame
    test_split: pd.DataFrame
    user2idx: dict
    idx2user: np.ndarray
    item2idx: dict
    idx2item: np.ndarray
    X_ui: csr_matrix


def select_top_users_same_as_preprocess(
    train_encoded: pd.DataFrame,
    complete_members_small: pd.DataFrame,
    top_n_users: int = 5000,
    min_membership_days: int = 30,
) -> np.ndarray:
    if "msno_id" not in train_encoded.columns:
        raise ValueError("train_encoded 必須包含 msno_id")
    if not {"msno_id", "membership_days"}.issubset(
        set(complete_members_small.columns)
    ):
        raise ValueError("complete_members_small 必須包含 msno_id 與 membership_days")

    play_count = train_encoded["msno_id"].value_counts()
    candidates = complete_members_small[
        complete_members_small["membership_days"] > min_membership_days
    ].copy()
    candidates["play_count"] = (
        candidates["msno_id"].map(play_count).fillna(0).astype(np.int32)
    )

    top_users = (
        candidates.sort_values("play_count", ascending=False)
        .head(top_n_users)["msno_id"]
        .to_numpy(dtype=np.int32)
    )
    return top_users


def filter_train_to_top_users(
    train_encoded: pd.DataFrame, top_users: np.ndarray
) -> pd.DataFrame:
    filtered = train_encoded[train_encoded["msno_id"].isin(top_users)].copy()
    filtered.reset_index(drop=True, inplace=True)
    return filtered


def prepare_train_for_knn(
    train_subset: pd.DataFrame, use_all_targets: bool = False
) -> pd.DataFrame:
    required = {"msno_id", "song_id", "target"}
    missing = required - set(train_subset.columns)
    if missing:
        raise ValueError(f"train_subset 缺少必要欄位：{missing}")

    df = train_subset.loc[:, ["msno_id", "song_id", "target"]].copy()
    if not use_all_targets:
        df = df[df["target"] == 1]
    df = df.drop(columns=["target"])
    df = df.drop_duplicates(["msno_id", "song_id"]).reset_index(drop=True)

    df["msno_id"] = df["msno_id"].astype(np.int32)
    df["song_id"] = df["song_id"].astype(np.int32)
    return df


def filter_items_by_min_freq(pos_df: pd.DataFrame, min_freq: int = 3) -> pd.DataFrame:
    item_counts = pos_df["song_id"].value_counts()
    keep_items = item_counts[item_counts >= min_freq].index
    filtered = pos_df[pos_df["song_id"].isin(keep_items)].copy()
    filtered.reset_index(drop=True, inplace=True)
    return filtered


def leave_one_out_split(
    pos_df: pd.DataFrame,
    min_pos_per_user: int = 2,
    seed: int = 42,
    progress: bool = False,
):
    rng = np.random.default_rng(seed)
    counts = pos_df["msno_id"].value_counts()
    eligible_users = counts[counts >= min_pos_per_user].index
    df = pos_df[pos_df["msno_id"].isin(eligible_users)].copy()

    train_rows = []
    test_rows = []

    groups = df.groupby("msno_id", sort=False)
    iterable = groups
    if progress:
        from tqdm import tqdm

        iterable = tqdm(groups, total=eligible_users.size, desc="LOO split")

    for u, g in iterable:
        items = g["song_id"].to_numpy()
        test_idx = rng.integers(0, len(items))
        test_item = items[test_idx]
        train_items = np.delete(items, test_idx)

        test_rows.append((u, test_item))
        for it in train_items:
            train_rows.append((u, it))

    train_split = pd.DataFrame(train_rows, columns=["msno_id", "song_id"])
    test_split = pd.DataFrame(test_rows, columns=["msno_id", "test_song_id"])
    return train_split, test_split


def build_index_maps(train_split: pd.DataFrame):
    unique_users = train_split["msno_id"].unique()
    unique_items = train_split["song_id"].unique()

    user2idx = {u: i for i, u in enumerate(unique_users)}
    idx2user = np.array(unique_users, dtype=np.int32)

    item2idx = {it: j for j, it in enumerate(unique_items)}
    idx2item = np.array(unique_items, dtype=np.int32)

    return user2idx, idx2user, item2idx, idx2item


def build_user_item_matrix(train_split: pd.DataFrame, user2idx, item2idx):
    rows = train_split["msno_id"].map(user2idx).to_numpy()
    cols = train_split["song_id"].map(item2idx).to_numpy()
    data = np.ones(len(train_split), dtype=np.float32)

    n_users = len(user2idx)
    n_items = len(item2idx)
    X_ui = csr_matrix((data, (rows, cols)), shape=(n_users, n_items))
    return X_ui


def fit_item_knn(
    X_ui: csr_matrix,
    item_k: int = 200,
    progress: bool = False,
    batch_size: int = 5000,
):
    n_items = X_ui.shape[1]
    if n_items <= 1:
        raise ValueError("Need at least 2 items to run ItemKNN.")

    effective_k = min(item_k, n_items - 1)
    X_iu = X_ui.T.tocsr()
    nn = NearestNeighbors(
        n_neighbors=effective_k + 1,
        metric="cosine",
        algorithm="brute",
        n_jobs=-1,
    )
    nn.fit(X_iu)

    if not progress:
        distances, indices = nn.kneighbors(X_iu, return_distance=True)
        sims = 1.0 - distances
        neigh_items = indices[:, 1 : effective_k + 1]
        neigh_sims = sims[:, 1 : effective_k + 1]
        return neigh_items, neigh_sims

    from tqdm import tqdm

    n_items = X_iu.shape[0]
    neigh_items = np.empty((n_items, effective_k), dtype=np.int32)
    neigh_sims = np.empty((n_items, effective_k), dtype=np.float32)

    for start in tqdm(range(0, n_items, batch_size), desc="KNN neighbors"):
        end = min(start + batch_size, n_items)
        distances, indices = nn.kneighbors(X_iu[start:end], return_distance=True)
        sims = 1.0 - distances
        neigh_items[start:end] = indices[:, 1 : effective_k + 1]
        neigh_sims[start:end] = sims[:, 1 : effective_k + 1]

    return neigh_items, neigh_sims


def recommend_from_seed_item_indices(
    seed_item_indices: np.ndarray,
    neigh_items: np.ndarray,
    neigh_sims: np.ndarray,
    top_n: int = 20,
    aggregation: str = "baseline",
    sim_threshold: float = 0.0,
):
    """
    ItemKNN 推薦：僅依「種子歌曲」在模型中的 item 欄位索引（與 X_ui 的欄位索引一致）。
    適用 onboarding 等沒有訓練集 user 列的情形。
    """
    seed_item_indices = np.asarray(seed_item_indices, dtype=np.int32).ravel()
    if seed_item_indices.size == 0:
        return np.array([], dtype=np.int32), np.array([], dtype=np.float32)

    seen = set(int(x) for x in seed_item_indices.tolist())
    scores = {}
    num_seed = int(seed_item_indices.size)

    for it in seed_item_indices:
        it = int(it)
        for nb, sim in zip(neigh_items[it], neigh_sims[it]):
            if nb in seen:
                continue
            if sim <= sim_threshold:
                continue

            if aggregation == "normalize_seed":
                add = float(sim) / num_seed
            else:
                add = float(sim)

            scores[nb] = scores.get(nb, 0.0) + add

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


def recommend_for_user(
    user_idx: int,
    X_ui: csr_matrix,
    neigh_items: np.ndarray,
    neigh_sims: np.ndarray,
    top_n: int = 20,
    aggregation: str = "baseline",
    sim_threshold: float = 0.0,
):
    s, e = X_ui.indptr[user_idx], X_ui.indptr[user_idx + 1]
    user_items = X_ui.indices[s:e]
    return recommend_from_seed_item_indices(
        user_items,
        neigh_items,
        neigh_sims,
        top_n=top_n,
        aggregation=aggregation,
        sim_threshold=sim_threshold,
    )


def evaluate_loou(
    test_split: pd.DataFrame,
    user2idx,
    item2idx,
    X_ui: csr_matrix,
    neigh_items: np.ndarray,
    neigh_sims: np.ndarray,
    eval_ks=(10, 20),
    reco_n=20,
    progress: bool = False,
):
    hits = {k: 0 for k in eval_ks}
    ndcgs = {k: 0.0 for k in eval_ks}
    n_eval = 0

    rows = test_split.itertuples(index=False)
    if progress:
        from tqdm import tqdm

        rows = tqdm(rows, total=len(test_split), desc="Evaluate LOO")

    for row in rows:
        u = row.msno_id
        test_item_original = row.test_song_id

        if u not in user2idx:
            continue
        if test_item_original not in item2idx:
            continue

        uidx = user2idx[u]
        test_item_idx = item2idx[test_item_original]

        rec_items, _ = recommend_for_user(
            uidx,
            X_ui,
            neigh_items,
            neigh_sims,
            top_n=reco_n,
            # 與 stage_10 grid search 最佳組合一致：aggregation = "baseline"
            aggregation="baseline",
            sim_threshold=0.0,
        )

        n_eval += 1
        if rec_items.size == 0:
            continue

        pos = np.where(rec_items == test_item_idx)[0]
        rank = int(pos[0]) + 1 if pos.size > 0 else None

        for k in eval_ks:
            if rank is not None and rank <= k:
                hits[k] += 1
                ndcgs[k] += 1.0 / np.log2(rank + 1)

    results = {}
    for k in eval_ks:
        recall = hits[k] / n_eval if n_eval > 0 else 0.0
        precision = hits[k] / (n_eval * k) if n_eval > 0 else 0.0
        ndcg = ndcgs[k] / n_eval if n_eval > 0 else 0.0

        results[f"Recall@{k}"] = recall
        results[f"Precision@{k}"] = precision
        results[f"NDCG@{k}"] = ndcg

    results["Users_evaluated"] = n_eval
    results["Reco_N"] = reco_n
    results["Item_K"] = neigh_items.shape[1] if neigh_items is not None else None
    return results


def results_to_table(
    results: dict, model_name="ItemKNN", split_name="LOO(pos-only)"
) -> pd.DataFrame:
    row = {
        "Model": model_name,
        "Split": split_name,
        "Item_K": results.get("Item_K"),
        "Reco_N": results.get("Reco_N"),
        "Users": results.get("Users_evaluated"),
        "Recall@10": results.get("Recall@10"),
        "Precision@10": results.get("Precision@10"),
        "NDCG@10": results.get("NDCG@10"),
        "Recall@20": results.get("Recall@20"),
        "Precision@20": results.get("Precision@20"),
        "NDCG@20": results.get("NDCG@20"),
    }
    return pd.DataFrame([row])


def prepare_knn_data(
    train_encoded: pd.DataFrame,
    complete_members_small: pd.DataFrame,
    use_top_users: bool = True,
    top_n_users: int = 5000,
    min_membership_days: int = 30,
    use_min_item_freq: bool = False,
    min_item_freq: int = 3,
    min_pos_per_user: int = 2,
    seed: int = 42,
    max_users: int | None = None,
    use_all_targets: bool = False,
    progress: bool = False,
) -> KNNData:
    train_subset = train_encoded
    if use_top_users:
        top_users = select_top_users_same_as_preprocess(
            train_encoded,
            complete_members_small,
            top_n_users=top_n_users,
            min_membership_days=min_membership_days,
        )
        if max_users is not None:
            top_users = top_users[:max_users]
        train_subset = filter_train_to_top_users(train_encoded, top_users)

    pos_df = prepare_train_for_knn(train_subset, use_all_targets=use_all_targets)

    if use_min_item_freq:
        pos_df = filter_items_by_min_freq(pos_df, min_item_freq)

    train_split, test_split = leave_one_out_split(
        pos_df, min_pos_per_user=min_pos_per_user, seed=seed, progress=progress
    )
    if train_split.empty or test_split.empty:
        user_pos_counts = pos_df.groupby("msno_id").size()
        eligible_users = (user_pos_counts >= min_pos_per_user).sum()
        raise ValueError(
            "LOO split is empty. "
            f"Eligible users with >= {min_pos_per_user} positives: {eligible_users}. "
            "Try lowering --min-membership-days, removing top-user filter (--no-top-users), "
            "or increasing --max-users. If train_encoded was built with Top-K filtering, "
            "rebuild it with `--top-k 0` (stage_04) or use stage_04b for full data."
        )

    user2idx, idx2user, item2idx, idx2item = build_index_maps(train_split)
    X_ui = build_user_item_matrix(train_split, user2idx, item2idx)
    if X_ui.shape[0] == 0 or X_ui.shape[1] == 0:
        raise ValueError("User-item matrix is empty; cannot train ItemKNN.")

    return KNNData(
        train_subset=train_subset,
        pos_df=pos_df,
        train_split=train_split,
        test_split=test_split,
        user2idx=user2idx,
        idx2user=idx2user,
        item2idx=item2idx,
        idx2item=idx2item,
        X_ui=X_ui,
    )


def run_itemknn_baseline(
    train_encoded: pd.DataFrame,
    complete_members_small: pd.DataFrame,
    item_k: int = 5,
    reco_n: int = 20,
    eval_ks: Iterable[int] = (10, 20),
    min_pos_per_user: int = 2,
    use_top_users: bool = True,
    top_n_users: int = 5000,
    min_membership_days: int = 30,
    use_min_item_freq: bool = False,
    min_item_freq: int = 3,
    seed: int = 42,
    max_users: int | None = None,
    demo_users: int = 5,
    use_all_targets: bool = False,
    progress: bool = False,
    knn_batch_size: int = 5000,
):
    data = prepare_knn_data(
        train_encoded,
        complete_members_small,
        use_top_users=use_top_users,
        top_n_users=top_n_users,
        min_membership_days=min_membership_days,
        use_min_item_freq=use_min_item_freq,
        min_item_freq=min_item_freq,
        min_pos_per_user=min_pos_per_user,
        seed=seed,
        max_users=max_users,
        use_all_targets=use_all_targets,
        progress=progress,
    )

    neigh_items, neigh_sims = fit_item_knn(
        data.X_ui, item_k=item_k, progress=progress, batch_size=knn_batch_size
    )
    results = evaluate_loou(
        data.test_split,
        data.user2idx,
        data.item2idx,
        data.X_ui,
        neigh_items,
        neigh_sims,
        eval_ks=eval_ks,
        reco_n=reco_n,
        progress=progress,
    )

    metrics_df = results_to_table(results, model_name="ItemKNN", split_name="LOO(pos-only)")

    demo_df = None
    if demo_users > 0:
        demo_rows = []
        users = list(data.user2idx.keys())[:demo_users]
        for u in users:
            uidx = data.user2idx[u]
            rec_items, rec_scores = recommend_for_user(
                uidx,
                data.X_ui,
                neigh_items,
                neigh_sims,
                top_n=reco_n,
                aggregation="normalize_seed",
            )
            for rank, (item_idx, score) in enumerate(
                zip(rec_items.tolist(), rec_scores.tolist()), start=1
            ):
                demo_rows.append(
                    {
                        "msno_id": u,
                        "rank": rank,
                        "song_id": data.idx2item[item_idx],
                        "score": score,
                    }
                )
        demo_df = pd.DataFrame(demo_rows)

    artifacts = {
        "neigh_items": neigh_items,
        "neigh_sims": neigh_sims,
        "data": data,
    }
    return results, metrics_df, demo_df, artifacts


def compute_item_pop(X_ui: csr_matrix) -> np.ndarray:
    X_ui_csc = X_ui.tocsc()
    return np.diff(X_ui_csc.indptr).astype(np.int32)


def recommend_for_user_cfg2(
    user_idx: int,
    X_ui: csr_matrix,
    neigh_items: np.ndarray,
    neigh_sims: np.ndarray,
    top_n: int = 20,
    sim_threshold: float = 0.0,
    aggregation: str = "baseline",
    item_pop: np.ndarray | None = None,
    pop_alpha: float = 0.5,
    pop_min: int = 1,
):
    s, e = X_ui.indptr[user_idx], X_ui.indptr[user_idx + 1]
    user_items = X_ui.indices[s:e]
    if user_items.size == 0:
        return np.array([], dtype=np.int32), np.array([], dtype=np.float32)

    seen = set(user_items.tolist())
    scores = {}
    denom = float(user_items.size) if aggregation == "normalize_seed" else 1.0

    for it in user_items:
        for nb, sim in zip(neigh_items[it], neigh_sims[it]):
            if nb in seen:
                continue
            if sim <= sim_threshold:
                continue

            if aggregation == "baseline":
                add = float(sim)
            elif aggregation == "sim2":
                add = float(sim * sim)
            elif aggregation == "normalize_seed":
                add = float(sim) / denom
            elif aggregation in ("pop_pow", "pop_log"):
                if item_pop is None:
                    raise ValueError("pop_* needs item_pop")
                pop = max(int(item_pop[nb]), pop_min)
                if aggregation == "pop_pow":
                    add = float(sim) / (pop ** pop_alpha)
                else:
                    add = float(sim) / (np.log1p(pop) ** pop_alpha)
            else:
                raise ValueError(f"Unknown aggregation: {aggregation}")

            if add <= 0:
                continue
            scores[nb] = scores.get(nb, 0.0) + add

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


def evaluate_loou_cfg2(
    test_split: pd.DataFrame,
    user2idx,
    item2idx,
    X_ui: csr_matrix,
    neigh_items: np.ndarray,
    neigh_sims: np.ndarray,
    eval_ks=(10, 20),
    reco_n=20,
    sim_threshold: float = 0.0,
    aggregation: str = "baseline",
    item_pop: np.ndarray | None = None,
    pop_alpha: float = 0.5,
):
    hits = {k: 0 for k in eval_ks}
    ndcgs = {k: 0.0 for k in eval_ks}
    n_eval = 0

    for row in test_split.itertuples(index=False):
        u = row.msno_id
        t = row.test_song_id
        if u not in user2idx:
            continue
        if t not in item2idx:
            continue

        uidx = user2idx[u]
        tidx = item2idx[t]

        rec_items, _ = recommend_for_user_cfg2(
            uidx,
            X_ui,
            neigh_items,
            neigh_sims,
            top_n=reco_n,
            sim_threshold=sim_threshold,
            aggregation=aggregation,
            item_pop=item_pop,
            pop_alpha=pop_alpha,
        )

        n_eval += 1
        if rec_items.size == 0:
            continue

        pos = np.where(rec_items == tidx)[0]
        rank = int(pos[0]) + 1 if pos.size > 0 else None

        for k in eval_ks:
            if rank is not None and rank <= k:
                hits[k] += 1
                ndcgs[k] += 1.0 / np.log2(rank + 1)

    out = {"Users": n_eval, "Reco_N": reco_n, "Item_K": neigh_items.shape[1]}
    for k in eval_ks:
        out[f"Recall@{k}"] = hits[k] / n_eval if n_eval else 0.0
        out[f"Precision@{k}"] = hits[k] / (n_eval * k) if n_eval else 0.0
        out[f"NDCG@{k}"] = ndcgs[k] / n_eval if n_eval else 0.0
    return out


def run_itemknn_grid(
    train_encoded: pd.DataFrame,
    complete_members_small: pd.DataFrame,
    item_k_list: Iterable[int],
    sim_thresholds: Iterable[float],
    agg_list: Iterable[str],
    reco_n: int = 20,
    eval_ks: Iterable[int] = (10, 20),
    pop_alpha: float = 0.5,
    use_top_users: bool = True,
    top_n_users: int = 5000,
    min_membership_days: int = 30,
    min_pos_per_user: int = 2,
    seed: int = 42,
    max_users: int | None = None,
    use_all_targets: bool = False,
    progress: bool = False,
    knn_batch_size: int = 5000,
):
    data = prepare_knn_data(
        train_encoded,
        complete_members_small,
        use_top_users=use_top_users,
        top_n_users=top_n_users,
        min_membership_days=min_membership_days,
        min_pos_per_user=min_pos_per_user,
        seed=seed,
        max_users=max_users,
        use_all_targets=use_all_targets,
        progress=progress,
    )

    max_k = min(max(item_k_list), data.X_ui.shape[1] - 1)
    neigh_items_all, neigh_sims_all = fit_item_knn(
        data.X_ui, item_k=max_k, progress=progress, batch_size=knn_batch_size
    )
    item_pop = compute_item_pop(data.X_ui)

    rows = []
    for k in item_k_list:
        effective_k = min(k, neigh_items_all.shape[1])
        neigh_items = neigh_items_all[:, :effective_k]
        neigh_sims = neigh_sims_all[:, :effective_k]

        for sim_t in sim_thresholds:
            for agg in agg_list:
                res = evaluate_loou_cfg2(
                    test_split=data.test_split,
                    user2idx=data.user2idx,
                    item2idx=data.item2idx,
                    X_ui=data.X_ui,
                    neigh_items=neigh_items,
                    neigh_sims=neigh_sims,
                    eval_ks=eval_ks,
                    reco_n=reco_n,
                    sim_threshold=sim_t,
                    aggregation=agg,
                    item_pop=item_pop,
                    pop_alpha=pop_alpha,
                )
                res.update(
                    {
                        "Model": f"ItemKNN({agg})",
                        "Split": "LOO(pos-only)",
                        "sim_threshold": sim_t,
                        "pop_alpha": pop_alpha if agg in ("pop_pow", "pop_log") else np.nan,
                    }
                )
                rows.append(res)
                print(
                    f"k={k:3d} | sim_t={sim_t:.2f} | agg={agg:12s} | R@10={res['Recall@10']:.5f} | N@10={res['NDCG@10']:.5f}"
                )

    metrics_grid_df = pd.DataFrame(rows)
    return metrics_grid_df
