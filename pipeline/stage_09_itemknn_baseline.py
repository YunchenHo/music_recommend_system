import argparse
from pathlib import Path

import pandas as pd

from pipeline.config import Paths
from src.io import load_table
from src.models.itemknn import run_itemknn_baseline


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 09: ItemKNN baseline")
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
    parser.add_argument("--item-k", type=int, default=5)
    parser.add_argument("--reco-n", type=int, default=20)
    parser.add_argument("--eval-ks", type=str, default="10,20")
    parser.add_argument("--min-pos-per-user", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-n-users", type=int, default=5000)
    parser.add_argument("--min-membership-days", type=int, default=30)
    parser.add_argument("--max-users", type=int, default=None)
    parser.add_argument("--demo-users", type=int, default=5)
    parser.add_argument("--use-min-item-freq", action="store_true")
    parser.add_argument("--min-item-freq", type=int, default=3)
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
        "--auto-fallback",
        action="store_true",
        help="if LOO is empty, retry with --use-all-targets",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="show progress bars for LOO split and evaluation",
    )
    parser.add_argument("--knn-batch-size", type=int, default=5000)
    parser.add_argument(
        "--out-metrics",
        type=Path,
        default=paths.reports / "itemknn_baseline_metrics.csv",
    )
    parser.add_argument(
        "--out-demo",
        type=Path,
        default=paths.reports / "itemknn_baseline_demo.csv",
    )
    args = parser.parse_args()

    train_df = load_table(args.train_path)
    members_df = pd.read_csv(args.members_path)
    eval_ks = tuple(int(x) for x in args.eval_ks.split(",") if x.strip())

    try:
        results, metrics_df, demo_df, _ = run_itemknn_baseline(
            train_encoded=train_df,
            complete_members_small=members_df,
            item_k=args.item_k,
            reco_n=args.reco_n,
            eval_ks=eval_ks,
            min_pos_per_user=args.min_pos_per_user,
            seed=args.seed,
            use_top_users=not args.no_top_users,
            top_n_users=args.top_n_users,
            min_membership_days=args.min_membership_days,
            max_users=args.max_users,
            demo_users=args.demo_users,
            use_min_item_freq=args.use_min_item_freq,
            min_item_freq=args.min_item_freq,
            use_all_targets=args.use_all_targets,
            progress=args.progress,
            knn_batch_size=args.knn_batch_size,
        )
    except ValueError as exc:
        if args.auto_fallback and "LOO split is empty" in str(exc):
            print("[ItemKNN] LOO empty; retrying with --use-all-targets")
            results, metrics_df, demo_df, _ = run_itemknn_baseline(
                train_encoded=train_df,
                complete_members_small=members_df,
                item_k=args.item_k,
                reco_n=args.reco_n,
                eval_ks=eval_ks,
                min_pos_per_user=args.min_pos_per_user,
                seed=args.seed,
                use_top_users=not args.no_top_users,
                top_n_users=args.top_n_users,
                min_membership_days=args.min_membership_days,
                max_users=args.max_users,
                demo_users=args.demo_users,
                use_min_item_freq=args.use_min_item_freq,
                min_item_freq=args.min_item_freq,
                use_all_targets=True,
                progress=args.progress,
                knn_batch_size=args.knn_batch_size,
            )
        else:
            raise

    args.out_metrics.parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(args.out_metrics, index=False, encoding="utf-8-sig")
    print("Saved metrics:", args.out_metrics)

    if demo_df is not None:
        demo_df.to_csv(args.out_demo, index=False, encoding="utf-8-sig")
        print("Saved demo recommendations:", args.out_demo)

    print("Results:", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
