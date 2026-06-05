"""Stage cs01 — LightFM with user/item features (hybrid).

For each split (A_N1 / A_N3 / A_N5 / C):
1. Load split + members + songs
2. Build LightFMData via `build_lightfm_data_from_split(use_features=True)`
3. Train LightFM via existing `train_lightfm_model`
4. Predict top-K:
   - A scenarios → `predict_topk_known_users`
   - C scenario → `predict_topk_unseen_users` (uses fit_partial + extended user_features)
5. Compute metrics via shared `compute_topk_metrics`
6. Append to `reports/cs_lightfm_hybrid_metrics.csv`

Run:
    PYTHONPATH=. uv run python pipeline/stage_cs01_lightfm_hybrid.py --smoke
    PYTHONPATH=. uv run python pipeline/stage_cs01_lightfm_hybrid.py  # full local run
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
    predict_topk_unseen_users,
)
from src.io import load_table
from src.models.lightfm_model import train_lightfm_model


ALL_SPLITS = ["A_N1", "A_N3", "A_N5", "C"]


def _load_useridx(path: Path) -> dict:
    import json
    raw = json.loads(path.read_text())
    return {_maybe_int(k): int(v) for k, v in raw.items()}


def _load_test_user_ids(path: Path) -> list:
    import json
    raw = json.loads(path.read_text())
    return [_maybe_int(x) for x in raw]


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
    members: pd.DataFrame,
    songs: pd.DataFrame,
    test_user_ids: list | None,
    no_components: int,
    epochs: int,
    learning_rate: float,
    loss: str,
    max_sampled: int,
    eval_ks: tuple[int, ...],
    item_alpha: float = 0.0,
    user_alpha: float = 0.0,
) -> pd.DataFrame:
    max_k = max(eval_ks)

    print(f"  building LightFMData (hybrid)...")
    data = build_lightfm_data_from_split(
        df_train, df_test, useridx, itemidx,
        members=members, songs=songs,
        use_features=True,
    )
    print(f"    interactions {data.interactions.shape}, nnz={data.interactions.nnz}")
    print(f"    user_features {data.user_features.shape}")
    print(f"    item_features {data.item_features.shape}")

    print(f"  training (components={no_components}, epochs={epochs}, loss={loss})...")
    model = train_lightfm_model(
        data,
        no_components=no_components,
        loss=loss,
        learning_rate=learning_rate,
        epochs=epochs,
        max_sampled=max_sampled,
        item_alpha=item_alpha,
        user_alpha=user_alpha,
        num_threads=1,  # single-thread LightFM (compiled without OpenMP)
        verbose=False,
    )

    if split == "C":
        if test_user_ids is None:
            raise RuntimeError("scenario C requires test_user_ids loaded")
        user_truth = df_test.groupby("msno_id")["song_idx"].apply(list).to_dict()
        print(f"  predicting for {len(user_truth)} cold users (Scenario C)...")
        user_topk = predict_topk_unseen_users(
            model, data, members, useridx, test_user_ids, user_truth,
            max_k=max_k,
        )
    else:
        user_truth = df_test.groupby("msno_idx")["song_idx"].apply(list).to_dict()
        print(f"  predicting for {len(user_truth)} test users (Scenario A)...")
        user_topk = predict_topk_known_users(
            model, data, user_truth,
            max_k=max_k,
        )

    return compute_topk_metrics(
        user_topk, user_truth,
        eval_ks=eval_ks,
        model_name="LightFM-hybrid",
        notes=(
            f"split={split}, components={no_components}, epochs={epochs}, "
            f"loss={loss}, max_sampled={max_sampled}, "
            f"item_alpha={item_alpha}, user_alpha={user_alpha}"
        ),
    )


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Cold-start LightFM hybrid (stage cs01)")
    parser.add_argument("--splits-dir", type=Path, default=paths.processed)
    parser.add_argument(
        "--splits", nargs="+", default=ALL_SPLITS, choices=ALL_SPLITS,
    )
    parser.add_argument("--members-path", type=Path, default=paths.processed / "complete_members.parquet")
    parser.add_argument("--songs-path", type=Path, default=paths.processed / "song_features.parquet")
    parser.add_argument(
        "--out-path", type=Path,
        default=paths.reports / "cs_lightfm_hybrid_metrics.csv",
    )
    parser.add_argument("--eval-ks", nargs="+", type=int, default=[10, 20])
    parser.add_argument("--no-components", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--loss", default="warp", choices=["warp", "bpr", "logistic", "warp-kos"])
    parser.add_argument("--max-sampled", type=int, default=10)
    parser.add_argument("--item-alpha", type=float, default=0.0,
                        help="L2 reg on item embeddings (抑制冷啟動過擬合；greedy hybrid 最佳=1e-7)")
    parser.add_argument("--user-alpha", type=float, default=0.0,
                        help="L2 reg on user embeddings (greedy hybrid 最佳=1e-6)")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    if args.smoke:
        args.no_components = 32
        args.epochs = 2

    eval_ks = tuple(args.eval_ks)
    print(f"[stage_cs01] LightFM hybrid, components={args.no_components}, epochs={args.epochs}")

    print(f"  loading members + songs...")
    members = load_table(args.members_path)
    songs = load_table(args.songs_path)

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
        useridx = _load_useridx(useridx_path)
        itemidx = _load_useridx(itemidx_path)
        test_user_ids = None
        if split == "C":
            tu_path = args.splits_dir / "cs_C_test_users.json"
            if tu_path.exists():
                test_user_ids = _load_test_user_ids(tu_path)

        df_metrics = evaluate_split(
            split=split,
            df_train=df_train, df_test=df_test,
            useridx=useridx, itemidx=itemidx,
            members=members, songs=songs,
            test_user_ids=test_user_ids,
            no_components=args.no_components,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            loss=args.loss,
            max_sampled=args.max_sampled,
            item_alpha=args.item_alpha,
            user_alpha=args.user_alpha,
            eval_ks=eval_ks,
        )
        print(df_metrics[["Model", "K", "Recall", "Precision", "NDCG", "Users_evaluated", "Notes"]].to_string(index=False))
        append_metrics(df_metrics, args.out_path)

    print(f"\n[stage_cs01] metrics appended to {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
