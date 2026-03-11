import argparse
from pathlib import Path

import pandas as pd
import tensorflow as tf

from pipeline.config import Paths
from src.io import load_table
from src.models.mf import evaluate_mf_with_faiss


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 12: MF FAISS evaluation")
    parser.add_argument(
        "--model-path",
        type=Path,
        default=paths.artifacts / "mf_model.h5",
    )
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
    parser.add_argument("--eval-ks", type=str, default="10,20")
    parser.add_argument(
        "--out-path",
        type=Path,
        default=paths.reports / "mf_faiss_metrics.csv",
    )
    args = parser.parse_args()

    model = tf.keras.models.load_model(args.model_path)
    df_train = load_table(args.train_path)
    df_test = load_table(args.test_path)

    eval_ks = tuple(int(x) for x in args.eval_ks.split(",") if x.strip())
    metrics_df = evaluate_mf_with_faiss(model, df_train, df_test, eval_ks=eval_ks)

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(args.out_path, index=False, encoding="utf-8-sig")
    print("Saved MF FAISS metrics:", args.out_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
