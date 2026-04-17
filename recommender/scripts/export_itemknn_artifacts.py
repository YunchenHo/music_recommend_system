"""
匯出 ItemKNN 線上推理用 artifact（不依賴 LOO 評估）。

輸出 NPZ 欄位：
  - neigh_items: int32, shape (n_items, item_k)
  - neigh_sims: float32
  - idx2item: int32, shape (n_items,) — 欄位索引 j 對應的原始 song_id
  - item_k: int32 長度 1
  - format_version: int32 長度 1（目前為 1）

載入端可依 idx2item 建立 song_id -> 欄位索引對照，再呼叫
src.models.itemknn.recommend_from_seed_item_indices。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from pipeline.config import Paths
from src.io import load_table
from src.models.itemknn import fit_item_knn, prepare_knn_data


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(
        description="Train ItemKNN and export .npz artifacts for serving (no evaluation)."
    )
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
    parser.add_argument("--min-pos-per-user", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-n-users", type=int, default=5000)
    parser.add_argument("--min-membership-days", type=int, default=30)
    parser.add_argument("--max-users", type=int, default=None)
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
        help="if LOO split is empty, retry with --use-all-targets",
    )
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--knn-batch-size", type=int, default=5000)
    parser.add_argument(
        "--out",
        type=Path,
        default=paths.artifacts / "itemknn_artifacts.npz",
        help="output .npz path",
    )
    args = parser.parse_args()

    train_df = load_table(args.train_path)
    members_df = pd.read_csv(args.members_path)

    def _prepare(use_all: bool):
        return prepare_knn_data(
            train_df,
            members_df,
            use_top_users=not args.no_top_users,
            top_n_users=args.top_n_users,
            min_membership_days=args.min_membership_days,
            use_min_item_freq=args.use_min_item_freq,
            min_item_freq=args.min_item_freq,
            min_pos_per_user=args.min_pos_per_user,
            seed=args.seed,
            max_users=args.max_users,
            use_all_targets=use_all,
            progress=args.progress,
        )

    try:
        data = _prepare(use_all=args.use_all_targets)
    except ValueError as exc:
        if args.auto_fallback and "LOO split is empty" in str(exc):
            print("[export_itemknn] LOO empty; retrying with use_all_targets=True")
            data = _prepare(use_all=True)
        else:
            raise

    neigh_items, neigh_sims = fit_item_knn(
        data.X_ui,
        item_k=args.item_k,
        progress=args.progress,
        batch_size=args.knn_batch_size,
    )
    idx2item = np.asarray(data.idx2item, dtype=np.int32)
    if neigh_items.shape[0] != idx2item.shape[0]:
        raise RuntimeError(
            f"neigh_items rows {neigh_items.shape[0]} != len(idx2item) {idx2item.shape[0]}"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.out,
        neigh_items=neigh_items.astype(np.int32, copy=False),
        neigh_sims=neigh_sims.astype(np.float32, copy=False),
        idx2item=idx2item,
        item_k=np.array([args.item_k], dtype=np.int32),
        format_version=np.array([1], dtype=np.int32),
    )

    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(f"Saved ItemKNN artifacts: {args.out} ({size_mb:.2f} MiB)")
    print(
        f"  n_items={idx2item.shape[0]}, item_k={args.item_k}, "
        f"neigh_items={neigh_items.shape}, idx2item dtype=int32"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
