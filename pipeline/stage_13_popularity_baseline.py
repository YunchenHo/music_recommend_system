import argparse
from pathlib import Path

import pandas as pd

from pipeline.config import Paths
from src.io import load_table
from src.models.popularity import evaluate_popularity_loo


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 13: popularity baseline")
    parser.add_argument(
        "--train-path",
        type=Path,
        default=paths.processed / "mf_train.parquet",
    )
    parser.add_argument(
        "--test-path",
        type=Path,
        default=paths.processed / "mf_test.parquet",
    )
    parser.add_argument("--eval-k", type=int, default=20)
    parser.add_argument(
        "--out-path",
        type=Path,
        default=paths.reports / "popularity_baseline.csv",
    )
    args = parser.parse_args()

    df_train = load_table(args.train_path)
    df_test = load_table(args.test_path)

    recall = evaluate_popularity_loo(df_train, df_test, eval_k=args.eval_k)
    out_df = pd.DataFrame([
        {"Model": "Popularity", "Recall@K": recall, "K": args.eval_k}
    ])

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out_path, index=False, encoding="utf-8-sig")
    print("Saved popularity baseline:", args.out_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
