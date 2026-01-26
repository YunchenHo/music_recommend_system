import argparse
from pathlib import Path

import pandas as pd

from pipeline.config import Paths
from src.io import load_table
from src.models.itemknn import run_itemknn_grid
from src.models.itemknn_plots import plot_itemknn_grid


def _parse_int_list(value: str) -> list[int]:
    return [int(x) for x in value.split(",") if x.strip()]


def _parse_float_list(value: str) -> list[float]:
    return [float(x) for x in value.split(",") if x.strip()]


def _parse_str_list(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 10: ItemKNN grid search")
    parser.add_argument(
        "--train-path",
        type=Path,
        default=paths.processed / "train_encoded.parquet",
    )
    parser.add_argument(
        "--members-path",
        type=Path,
        default=paths.processed / "complete_members_small.csv",
    )
    parser.add_argument("--item-k-list", type=str, default="5,25,50,75,100")
    parser.add_argument("--sim-thresholds", type=str, default="0.0,0.01,0.02,0.05")
    parser.add_argument(
        "--agg-list",
        type=str,
        default="baseline,sim2,normalize_seed,pop_pow,pop_log",
    )
    parser.add_argument("--reco-n", type=int, default=20)
    parser.add_argument("--eval-ks", type=str, default="10,20")
    parser.add_argument("--pop-alpha", type=float, default=0.5)
    parser.add_argument("--top-n-users", type=int, default=5000)
    parser.add_argument("--min-membership-days", type=int, default=30)
    parser.add_argument("--min-pos-per-user", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-users", type=int, default=None)
    parser.add_argument(
        "--no-top-users",
        action="store_true",
        help="do not restrict to top users",
    )
    parser.add_argument(
        "--use-all-targets",
        action="store_true",
        help="treat all interactions as positives (ignore target==1 filter)",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="show progress bars for LOO split and evaluation",
    )
    parser.add_argument("--knn-batch-size", type=int, default=5000)
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=paths.reports / "itemknn_grid_metrics.csv",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="generate plots into reports/itemknn_plots",
    )
    args = parser.parse_args()

    train_df = load_table(args.train_path)
    members_df = pd.read_csv(args.members_path)

    try:
        metrics_df = run_itemknn_grid(
            train_encoded=train_df,
            complete_members_small=members_df,
            item_k_list=_parse_int_list(args.item_k_list),
            sim_thresholds=_parse_float_list(args.sim_thresholds),
            agg_list=_parse_str_list(args.agg_list),
            reco_n=args.reco_n,
            eval_ks=tuple(int(x) for x in args.eval_ks.split(",") if x.strip()),
            pop_alpha=args.pop_alpha,
            top_n_users=args.top_n_users,
            min_membership_days=args.min_membership_days,
            min_pos_per_user=args.min_pos_per_user,
            seed=args.seed,
            max_users=args.max_users,
            use_top_users=not args.no_top_users,
            use_all_targets=args.use_all_targets,
            progress=args.progress,
            knn_batch_size=args.knn_batch_size,
        )
    except ValueError as exc:
        metrics_df = pd.DataFrame(
            [
                {
                    "Model": "ItemKNN",
                    "Split": "LOO(pos-only)",
                    "Item_K": None,
                    "Reco_N": args.reco_n,
                    "Users": 0,
                    "Recall@10": 0.0,
                    "Precision@10": 0.0,
                    "NDCG@10": 0.0,
                    "Recall@20": 0.0,
                    "Precision@20": 0.0,
                    "NDCG@20": 0.0,
                    "error": str(exc),
                }
            ]
        )
        print("[ItemKNN Grid] Skipped due to error:", exc)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(args.out_csv, index=False, encoding="utf-8-sig")
    print("Saved grid metrics:", args.out_csv)

    if args.plot:
        out_dir = paths.reports / "itemknn_plots"
        plot_itemknn_grid(metrics_df, out_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
