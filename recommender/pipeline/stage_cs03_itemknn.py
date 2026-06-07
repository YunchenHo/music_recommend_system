"""Stage cs03 — ItemKNN baseline for Scenario A only.

ItemKNN needs seed items to recommend from, so it's not applicable to
Scenario C (held-out users have zero training history). We run it only on
A_N1 / A_N3 / A_N5.

For each split:
1. Build sparse X_ui from `df_train` positives (using msno_idx / song_idx which
   are already 0..N encoded by `make_split_a`).
2. fit_item_knn → (neigh_items, neigh_sims).
3. For each test user: collect their N seed song_idxs from df_train,
   recommend_from_seed_item_indices → top-K predictions.
4. Compute Recall@K / Precision@K / NDCG@K via shared `compute_topk_metrics`.

Output: `reports/cs_itemknn_metrics.csv` (long format, append).

Run:
    PYTHONPATH=. uv run python pipeline/stage_cs03_itemknn.py
    PYTHONPATH=. uv run python pipeline/stage_cs03_itemknn.py --splits A_N3 --smoke
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

from pipeline.config import Paths
from src.coldstart.eval_metrics import append_metrics, compute_topk_metrics
from src.io import load_table
from src.models.itemknn import fit_item_knn, recommend_from_seed_item_indices


A_SPLITS = ["A_N1", "A_N3", "A_N5"]


def _build_xui(df_train: pd.DataFrame, n_users: int, n_items: int) -> csr_matrix:
    pos = df_train[df_train["target"] == 1]
    rows = pos["msno_idx"].to_numpy(dtype=np.int32)
    cols = pos["song_idx"].to_numpy(dtype=np.int32)
    data = np.ones(len(pos), dtype=np.float32)
    return csr_matrix((data, (rows, cols)), shape=(n_users, n_items))


def _user_seeds(df_train: pd.DataFrame) -> dict[int, np.ndarray]:
    """Per-user seed song_idx arrays (positives in train)."""
    pos = df_train[df_train["target"] == 1]
    return {
        uid: np.asarray(songs, dtype=np.int32)
        for uid, songs in pos.groupby("msno_idx")["song_idx"]
    }


def _ground_truth(df_test: pd.DataFrame) -> dict[int, list[int]]:
    return df_test.groupby("msno_idx")["song_idx"].apply(list).to_dict()


def evaluate_split(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    *,
    eval_ks: tuple[int, ...],
    item_k: int,
    split_name: str,
    aggregation: str = "baseline",
) -> pd.DataFrame:
    max_k = max(eval_ks)
    n_users = int(df_train["msno_idx"].max()) + 1
    n_items = int(max(df_train["song_idx"].max(), df_test["song_idx"].max())) + 1

    X_ui = _build_xui(df_train, n_users, n_items)
    print(f"    X_ui: {X_ui.shape}, nnz={X_ui.nnz}")

    neigh_items, neigh_sims = fit_item_knn(X_ui, item_k=item_k, progress=False)

    seeds = _user_seeds(df_train)
    user_truth = _ground_truth(df_test)
    user_topk: dict[int, list[int]] = {}

    for uid, truth_items in user_truth.items():
        seed_arr = seeds.get(uid)
        if seed_arr is None or seed_arr.size == 0:
            user_topk[uid] = []
            continue
        rec_items, _ = recommend_from_seed_item_indices(
            seed_arr,
            neigh_items,
            neigh_sims,
            top_n=max_k,
            aggregation=aggregation,
            sim_threshold=0.0,
        )
        user_topk[uid] = rec_items.tolist()

    return compute_topk_metrics(
        user_topk,
        user_truth,
        eval_ks=eval_ks,
        model_name="ItemKNN",
        notes=f"split={split_name}, item_k={item_k}, agg={aggregation}",
    )


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Cold-start ItemKNN baseline (stage cs03)")
    parser.add_argument(
        "--splits-dir",
        type=Path,
        default=paths.processed,
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=A_SPLITS,
        choices=A_SPLITS,
        help="Only A_N1 / A_N3 / A_N5 are valid (Scenario C skipped for ItemKNN)",
    )
    parser.add_argument(
        "--out-path",
        type=Path,
        default=paths.reports / "cs_itemknn_metrics.csv",
    )
    parser.add_argument("--eval-ks", nargs="+", type=int, default=[10, 20])
    parser.add_argument(
        "--item-k",
        type=int,
        default=5,
        help="Item neighbors per item (matches stage_10 best config)",
    )
    parser.add_argument(
        "--aggregation",
        default="baseline",
        choices=["baseline", "normalize_seed"],
    )
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    if args.smoke:
        args.item_k = 5

    eval_ks = tuple(args.eval_ks)
    print(f"[stage_cs03] ItemKNN baseline, K={eval_ks}, item_k={args.item_k}, agg={args.aggregation}")

    for split in args.splits:
        train_path = args.splits_dir / f"cs_{split}_train.parquet"
        test_path = args.splits_dir / f"cs_{split}_test.parquet"
        if not train_path.exists() or not test_path.exists():
            print(f"  [skip] {split}: split files not found")
            continue

        print(f"\n  {split}: loading splits")
        df_train = load_table(train_path)
        df_test = load_table(test_path)
        print(f"    train {len(df_train):,} rows, test {len(df_test):,} rows")

        df_metrics = evaluate_split(
            df_train, df_test,
            eval_ks=eval_ks,
            item_k=args.item_k,
            split_name=split,
            aggregation=args.aggregation,
        )
        print(df_metrics[["Model", "K", "Recall", "Precision", "NDCG", "Users_evaluated", "Notes"]].to_string(index=False))
        append_metrics(df_metrics, args.out_path)

    print(f"\n[stage_cs03] metrics appended to {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
