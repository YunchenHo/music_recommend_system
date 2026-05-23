import argparse
import pickle
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline.config import Paths
from src.io import load_table


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 15: LightFM evaluation")
    parser.add_argument(
        "--model-path",
        type=Path,
        default=paths.artifacts / "lightfm_model.pkl",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=paths.artifacts / "lightfm_dataset.pkl",
    )
    parser.add_argument(
        "--train-path",
        type=Path,
        default=paths.processed / "lightfm_train.parquet",
    )
    parser.add_argument(
        "--test-path",
        type=Path,
        default=paths.processed / "lightfm_test.parquet",
    )
    parser.add_argument("--eval-ks", type=str, default="10,20")
    parser.add_argument("--num-threads", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--notes",
        type=str,
        default="",
        help=(
            "Free-form note for this run (e.g. 'top-5000, hybrid, epochs=10'). "
            "Stored in the Notes column to distinguish runs."
        ),
    )
    parser.add_argument(
        "--run-date",
        type=str,
        default=None,
        help="Override the training/eval date (YYYY-MM-DD HH:MM:SS). Defaults to now.",
    )
    parser.add_argument(
        "--out-path",
        type=Path,
        default=paths.reports / "lightfm_metrics.csv",
    )
    args = parser.parse_args()

    try:
        import lightfm  # noqa: F401
    except ImportError:
        raise SystemExit(
            "[LightFM] lightfm is not installed. See pyproject.toml comment for "
            "instructions on installing in a Python 3.11 venv."
        )

    from src.models.lightfm_model import LightFMData, evaluate_lightfm

    with open(args.model_path, "rb") as f:
        model = pickle.load(f)
    with open(args.data_path, "rb") as f:
        payload = pickle.load(f)

    df_train = load_table(args.train_path)
    df_test = load_table(args.test_path)

    data = LightFMData(
        dataset=payload["dataset"],
        interactions=payload["interactions"],
        user_features=payload.get("user_features"),
        item_features=payload.get("item_features"),
        df_train=df_train,
        df_test=df_test,
        num_users=payload["num_users"],
        num_items=payload["num_items"],
    )

    eval_ks = tuple(int(x) for x in args.eval_ks.split(",") if x.strip())
    metrics_df = evaluate_lightfm(
        model,
        data,
        eval_ks=eval_ks,
        num_threads=args.num_threads,
        batch_size=args.batch_size,
    )

    run_date = args.run_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics_df.insert(0, "Date", run_date)
    metrics_df["Notes"] = args.notes

    column_order = [
        "Date", "Model", "K", "Recall", "Precision", "NDCG",
        "Users_evaluated", "Notes",
    ]
    metrics_df = metrics_df[[c for c in column_order if c in metrics_df.columns]]

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.out_path.exists():
        existing = pd.read_csv(args.out_path)
        for col in column_order:
            if col not in existing.columns:
                existing[col] = pd.NA
        existing = existing[[c for c in column_order if c in existing.columns]]
        combined = pd.concat([existing, metrics_df], ignore_index=True)
        action = "Appended to"
    else:
        combined = metrics_df
        action = "Created"

    combined.to_csv(args.out_path, index=False, encoding="utf-8-sig")
    print(f"{action} LightFM metrics: {args.out_path} "
          f"({len(combined)} total rows, {len(metrics_df)} new)")
    print(metrics_df.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
