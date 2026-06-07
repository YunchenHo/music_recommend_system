"""Stage cs04 — Popularity baseline for cold-start scenarios.

Top-K most-played songs from the **train portion** of each split.
Recommend the same top-K to every test user; evaluate per-user Recall@K /
Precision@K / NDCG@K via the shared `compute_topk_metrics()` helper.

Runs all 4 splits (A_N1 / A_N3 / A_N5 / C) by default. Output appends to
`reports/cs_popularity_metrics.csv` in stage_16 long format.

Run:
    PYTHONPATH=. uv run python pipeline/stage_cs04_popularity.py
    PYTHONPATH=. uv run python pipeline/stage_cs04_popularity.py --splits A_N3 --smoke
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pipeline.config import Paths
from src.coldstart.eval_metrics import append_metrics, compute_topk_metrics
from src.io import load_table


ALL_SPLITS = ["A_N1", "A_N3", "A_N5", "C"]


def _ground_truth(df_test: pd.DataFrame) -> dict[int, list[int]]:
    """Group test positives by user (using msno_idx if present, else msno_id)."""
    user_col = "msno_idx" if "msno_idx" in df_test.columns else "msno_id"
    return df_test.groupby(user_col)["song_idx"].apply(list).to_dict()


def evaluate_split(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    *,
    eval_ks: tuple[int, ...],
    split_name: str,
) -> pd.DataFrame:
    max_k = max(eval_ks)

    pop_ranking = (
        df_train[df_train["target"] == 1]["song_idx"]
        .value_counts()
        .head(max_k)
        .index.tolist()
    )
    user_truth = _ground_truth(df_test)
    user_topk = {uid: pop_ranking for uid in user_truth}

    return compute_topk_metrics(
        user_topk,
        user_truth,
        eval_ks=eval_ks,
        model_name="Popularity",
        notes=f"split={split_name}",
    )


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Cold-start Popularity baseline (stage cs04)")
    parser.add_argument(
        "--splits-dir",
        type=Path,
        default=paths.processed,
        help="Directory holding cs_*_{train,test}.parquet",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=ALL_SPLITS,
        choices=ALL_SPLITS,
    )
    parser.add_argument(
        "--out-path",
        type=Path,
        default=paths.reports / "cs_popularity_metrics.csv",
    )
    parser.add_argument(
        "--eval-ks",
        nargs="+",
        type=int,
        default=[10, 20],
    )
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    eval_ks = tuple(args.eval_ks)
    print(f"[stage_cs04] popularity baseline, K={eval_ks}")

    for split in args.splits:
        train_path = args.splits_dir / f"cs_{split}_train.parquet"
        test_path = args.splits_dir / f"cs_{split}_test.parquet"
        if not train_path.exists() or not test_path.exists():
            print(f"  [skip] {split}: split files not found ({train_path.name})")
            continue

        df_train = load_table(train_path)
        df_test = load_table(test_path)
        n_truth_users = df_test["msno_idx"].nunique() if "msno_idx" in df_test.columns else df_test["msno_id"].nunique()
        print(f"  {split}: train {len(df_train):,} rows, test {len(df_test):,} rows, {n_truth_users} test users")

        df_metrics = evaluate_split(df_train, df_test, eval_ks=eval_ks, split_name=split)
        print(df_metrics[["Model", "K", "Recall", "Precision", "NDCG", "Users_evaluated", "Notes"]].to_string(index=False))
        append_metrics(df_metrics, args.out_path)

    print(f"\n[stage_cs04] metrics appended to {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
