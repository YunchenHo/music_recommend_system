"""
匯出 LightFM 線上推理用 artifact。

=== Pure CF mode (default) ===
輸出 NPZ 欄位：
  - item_embeddings: float32, shape (n_items, n_components)
  - item_biases: float32, shape (n_items,)
  - song_ids: int32, shape (n_items,)

=== Hybrid mode (--hybrid) ===
額外輸出：
  - user_feature_embeddings: float32, shape (n_user_features, n_components)
  - user_feature_names: JSON string (list of feature tag names)

後端載入後只需 numpy，不需要 lightfm 套件。

Usage (在有 lightfm 的環境 / container 內):
    cd recommender

    # Pure CF:
    python scripts/export_lightfm_artifacts.py \
        --model artifacts/lightfm_purecf_model.pkl \
        --dataset artifacts/lightfm_purecf_dataset.pkl \
        --output artifacts/lightfm_purecf.npz

    # Hybrid:
    python scripts/export_lightfm_artifacts.py --hybrid \
        --model artifacts/lightfm_hybrid_model.pkl \
        --dataset artifacts/lightfm_hybrid_dataset.pkl \
        --output artifacts/lightfm_hybrid.npz
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np


def main() -> int:
    default_artifacts = ROOT / "artifacts"

    parser = argparse.ArgumentParser(
        description="Export LightFM embeddings to .npz for backend serving."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=default_artifacts / "lightfm_model.pkl",
        help="Path to lightfm_model.pkl",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=default_artifacts / "lightfm_dataset.pkl",
        help="Path to lightfm_dataset.pkl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_artifacts / "lightfm_artifacts.npz",
        help="Output .npz path",
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Export user feature embeddings for hybrid cold-start inference.",
    )
    args = parser.parse_args()

    # --- Load model ---
    if not args.model.exists():
        raise SystemExit(f"Model file not found: {args.model}")
    print(f"Loading model from {args.model} ...")
    with open(args.model, "rb") as f:
        model = pickle.load(f)

    # model.item_embeddings shape: (n_internal_items + n_item_features, n_components)
    # model.user_embeddings shape: (n_internal_users + n_user_features, n_components)
    item_embeddings = model.item_embeddings
    item_biases = model.item_biases
    print(f"  item_embeddings shape: {item_embeddings.shape}")
    print(f"  item_biases shape: {item_biases.shape}")

    if args.hybrid:
        user_embeddings = model.user_embeddings
        user_biases = model.user_biases
        print(f"  user_embeddings shape: {user_embeddings.shape}")
        print(f"  user_biases shape: {user_biases.shape}")

    # --- Load dataset payload ---
    if not args.dataset.exists():
        raise SystemExit(f"Dataset file not found: {args.dataset}")
    print(f"Loading dataset from {args.dataset} ...")
    with open(args.dataset, "rb") as f:
        payload = pickle.load(f)

    dataset = payload["dataset"]
    # dataset._item_id_mapping: {user_provided_id (song_idx) -> lightfm_internal_idx}
    item_id_mapping = dataset._item_id_mapping

    # --- Build song_id -> lightfm_internal_idx mapping ---
    if "itemidx" in payload:
        itemidx = payload["itemidx"]  # {song_id: song_idx}
        print("  Using itemidx from dataset payload.")
    else:
        # Fallback: reconstruct from lightfm_train.parquet
        import pandas as pd

        train_parquet_candidates = [
            ROOT / "data" / "processed" / "lightfm_train.parquet",
            ROOT / "processed" / "lightfm_train.parquet",
        ]
        train_path = None
        for p in train_parquet_candidates:
            if p.exists():
                train_path = p
                break

        if train_path is None:
            raise SystemExit(
                "Cannot find lightfm_train.parquet to reconstruct song_id mapping.\n"
                "Looked in:\n" + "\n".join(f"  {p}" for p in train_parquet_candidates)
            )

        print(f"  Reconstructing itemidx from {train_path} ...")
        df = pd.read_parquet(train_path, columns=["song_id", "song_idx"])
        df = df.drop_duplicates(subset=["song_id"])
        itemidx = dict(zip(df["song_id"].astype(int), df["song_idx"].astype(int)))

    print(f"  itemidx contains {len(itemidx)} songs")

    # --- Align items: create arrays where song_ids[i] corresponds to embeddings[i] ---
    song_ids_list = []
    embeddings_list = []
    biases_list = []

    for song_id, song_idx in itemidx.items():
        if song_idx not in item_id_mapping:
            continue
        internal_idx = item_id_mapping[song_idx]
        if internal_idx >= len(item_embeddings):
            continue
        song_ids_list.append(song_id)
        embeddings_list.append(item_embeddings[internal_idx])
        biases_list.append(item_biases[internal_idx])

    if not song_ids_list:
        raise SystemExit("No songs could be mapped. Check that model and dataset are compatible.")

    song_ids_arr = np.array(song_ids_list, dtype=np.int32)
    embeddings_arr = np.array(embeddings_list, dtype=np.float32)
    biases_arr = np.array(biases_list, dtype=np.float32)

    print(f"\nAligned {len(song_ids_arr)} songs:")
    print(f"  item_embeddings: {embeddings_arr.shape}")
    print(f"  item_biases: {biases_arr.shape}")
    print(f"  song_ids range: {song_ids_arr.min()} - {song_ids_arr.max()}")

    # --- Hybrid: extract user feature embeddings ---
    save_kwargs = {
        "item_embeddings": embeddings_arr,
        "item_biases": biases_arr,
        "song_ids": song_ids_arr,
    }

    if args.hybrid:
        # dataset.mapping() returns:
        #   (user_id_map, user_feature_map, item_id_map, item_feature_map)
        # user_feature_map: {feature_name: column_index_in_user_feature_matrix}
        _, user_feature_map, _, _ = dataset.mapping()

        # user_embeddings layout:
        #   rows 0..n_users-1 = identity embeddings (one per training user)
        #   rows n_users..end = feature tag embeddings
        # user_feature_map values are the column indices in the feature matrix,
        # which correspond to rows in user_embeddings.
        n_users = len(dataset._user_id_mapping)

        # Filter to only non-identity features (index >= n_users)
        feature_names = []
        feature_indices = []
        for feat_name, col_idx in sorted(user_feature_map.items(), key=lambda x: x[1]):
            if col_idx >= n_users:
                feature_names.append(feat_name)
                feature_indices.append(col_idx)

        if not feature_names:
            raise SystemExit("No user feature tags found in dataset mapping.")

        user_feat_emb = user_embeddings[feature_indices].astype(np.float32)
        user_feat_bias = user_biases[feature_indices].astype(np.float32)

        print(f"\nHybrid user features:")
        print(f"  n_user_identity: {n_users}")
        print(f"  n_user_feature_tags: {len(feature_names)}")
        print(f"  user_feature_embeddings shape: {user_feat_emb.shape}")
        print(f"  feature_names: {feature_names}")

        save_kwargs["user_feature_embeddings"] = user_feat_emb
        save_kwargs["user_feature_biases"] = user_feat_bias
        save_kwargs["user_feature_names"] = json.dumps(feature_names)

    # --- Save ---
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.output, **save_kwargs)
    print(f"\nSaved to {args.output} ({args.output.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
