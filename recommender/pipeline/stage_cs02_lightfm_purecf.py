"""Stage cs02 — LightFM without features (pureCF), serves as both ablation
(vs hybrid) and MF-replacement baseline.

Only runs on Scenario A. pureCF cannot predict for Scenario C users: the
model's user embedding table is fixed at training size, so cold users have
no embedding row and predict() would index out-of-bounds.

Run:
    PYTHONPATH=. uv run python pipeline/stage_cs02_lightfm_purecf.py --smoke
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pipeline.config import Paths
from src.coldstart.eval_metrics import append_metrics, compute_topk_metrics
from src.coldstart.lightfm_helpers import (
    build_lightfm_data_from_split,
    predict_topk_known_users,
)
from src.io import load_table
from src.models.lightfm_model import train_lightfm_model


A_SPLITS = ["A_N1", "A_N3", "A_N5"]


def _load_idx(path: Path) -> dict:
    import json
    raw = json.loads(path.read_text())
    return {_maybe_int(k): int(v) for k, v in raw.items()}


def _maybe_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return x


def evaluate_split(
    *,
    split: str,
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    useridx: dict,
    itemidx: dict,
    no_components: int,
    epochs: int,
    learning_rate: float,
    loss: str,
    max_sampled: int,
    eval_ks: tuple[int, ...],
) -> pd.DataFrame:
    max_k = max(eval_ks)

    print(f"  building LightFMData (pureCF, no features)...")
    data = build_lightfm_data_from_split(
        df_train, df_test, useridx, itemidx,
        members=None, songs=None,
        use_features=False,
    )
    print(f"    interactions {data.interactions.shape}, nnz={data.interactions.nnz}")

    print(f"  training (components={no_components}, epochs={epochs}, loss={loss})...")
    model = train_lightfm_model(
        data,
        no_components=no_components,
        loss=loss,
        learning_rate=learning_rate,
        epochs=epochs,
        max_sampled=max_sampled,
        num_threads=1,
        verbose=False,
    )

    user_truth = df_test.groupby("msno_idx")["song_idx"].apply(list).to_dict()
    print(f"  predicting for {len(user_truth)} test users (Scenario A)...")
    user_topk = predict_topk_known_users(model, data, user_truth, max_k=max_k)

    return compute_topk_metrics(
        user_topk, user_truth,
        eval_ks=eval_ks,
        model_name="LightFM-pureCF",
        notes=(
            f"split={split}, components={no_components}, epochs={epochs}, "
            f"loss={loss}, max_sampled={max_sampled}"
        ),
    )


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Cold-start LightFM pureCF (stage cs02)")
    parser.add_argument("--splits-dir", type=Path, default=paths.processed)
    parser.add_argument(
        "--splits", nargs="+", default=A_SPLITS, choices=A_SPLITS,
        help="Only A_N1 / A_N3 / A_N5 are valid (C scenario unsupported for pureCF)",
    )
    parser.add_argument(
        "--out-path", type=Path,
        default=paths.reports / "cs_lightfm_purecf_metrics.csv",
    )
    parser.add_argument("--eval-ks", nargs="+", type=int, default=[10, 20])
    parser.add_argument("--no-components", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--loss", default="warp", choices=["warp", "bpr", "logistic", "warp-kos"])
    parser.add_argument("--max-sampled", type=int, default=10)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    if args.smoke:
        args.no_components = 32
        args.epochs = 2

    eval_ks = tuple(args.eval_ks)
    print(f"[stage_cs02] LightFM pureCF (ablation), components={args.no_components}, epochs={args.epochs}")

    for split in args.splits:
        train_path = args.splits_dir / f"cs_{split}_train.parquet"
        test_path = args.splits_dir / f"cs_{split}_test.parquet"
        useridx_path = args.splits_dir / f"cs_{split}_useridx.json"
        itemidx_path = args.splits_dir / f"cs_{split}_itemidx.json"
        if not all(p.exists() for p in [train_path, test_path, useridx_path, itemidx_path]):
            print(f"  [skip] {split}: split files not found")
            continue

        print(f"\n  {split}: loading splits")
        df_train = load_table(train_path)
        df_test = load_table(test_path)
        useridx = _load_idx(useridx_path)
        itemidx = _load_idx(itemidx_path)

        df_metrics = evaluate_split(
            split=split,
            df_train=df_train, df_test=df_test,
            useridx=useridx, itemidx=itemidx,
            no_components=args.no_components,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            loss=args.loss,
            max_sampled=args.max_sampled,
            eval_ks=eval_ks,
        )
        print(df_metrics[["Model", "K", "Recall", "Precision", "NDCG", "Users_evaluated", "Notes"]].to_string(index=False))
        append_metrics(df_metrics, args.out_path)

    print(f"\n[stage_cs02] metrics appended to {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
