"""Stage db01 — Train LightFM from DB-exported data and produce backend artifacts.

Reads the CSV files exported by `export_for_lightfm`, trains a LightFM model,
and outputs `lightfm_artifacts.npz` ready for the backend to consume.

Run from `recommender/` with LightFM available:

    python pipeline/stage_db01_lightfm_train.py
    python pipeline/stage_db01_lightfm_train.py --dir ../data/db_processed --output ../recommender/artifacts/lightfm_artifacts.npz
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DIR = _REPO_ROOT / "data" / "db_processed"
_DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "lightfm_artifacts.npz"


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage db01: train LightFM from DB data")
    parser.add_argument(
        "--dir", type=Path, default=_DEFAULT_DIR,
        help="Directory holding the exported CSV files",
    )
    parser.add_argument(
        "--output", type=Path, default=_DEFAULT_OUTPUT,
        help="Output .npz path for backend artifacts",
    )
    parser.add_argument("--no-components", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--loss", type=str, default="warp")
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--num-threads", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.dir.exists():
        raise SystemExit(
            f"[stage_db01] Directory not found: {args.dir}\n"
            f"Run the backend export first:\n"
            f"  cd backend && python manage.py export_for_lightfm --output-dir {args.dir}"
        )

    # --- Import LightFM ---
    try:
        from lightfm import LightFM
        from lightfm.data import Dataset
    except ImportError:
        raise SystemExit(
            "[stage_db01] lightfm is not installed. "
            "Run this in the recommender container or root .venv (Py 3.11)."
        )

    from src.data.db_loader import load_db_data

    # --- Load data ---
    print(f"[stage_db01] Loading data from {args.dir} ...")
    db = load_db_data(args.dir)

    print(f"  users: {len(db.users)}, songs: {len(db.songs)}, "
          f"interactions: {len(db.interactions)}, onboarding: {len(db.onboarding)}")

    # --- Prepare interactions ---
    # Only use positive interactions (affinity_score > 0 or watch_seconds > 30)
    interactions_df = db.interactions.copy()

    # Define positive signal: has affinity > 0, or watched > 30s, or is_liked == 1
    if "affinity_score" in interactions_df.columns:
        interactions_df["affinity_score"] = interactions_df["affinity_score"].fillna(0)
    if "is_liked" in interactions_df.columns:
        interactions_df["is_liked"] = interactions_df["is_liked"].fillna(0)

    positive_mask = (
        (interactions_df.get("affinity_score", 0) > 0) |
        (interactions_df.get("watch_seconds", 0) > 30) |
        (interactions_df.get("is_liked", 0) == 1)
    )
    positives = interactions_df[positive_mask][["user_id", "song_id"]].drop_duplicates()

    if len(positives) < 5:
        raise SystemExit(
            f"[stage_db01] Only {len(positives)} positive interactions found. "
            f"Need more data to train a useful model."
        )

    print(f"  positive interactions (unique user-song pairs): {len(positives)}")

    # --- Build LightFM Dataset ---
    print("[stage_db01] Building LightFM Dataset ...")
    all_user_ids = db.users["user_id"].unique().tolist()
    all_song_ids = db.songs["song_id"].unique().tolist()

    dataset = Dataset()
    dataset.fit(users=all_user_ids, items=all_song_ids)

    interactions_matrix, _ = dataset.build_interactions(
        zip(positives["user_id"].tolist(), positives["song_id"].tolist())
    )

    print(f"  Dataset: {dataset.interactions_shape()} "
          f"(users={len(all_user_ids)}, items={len(all_song_ids)})")

    # --- Train ---
    print(f"[stage_db01] Training LightFM (components={args.no_components}, "
          f"epochs={args.epochs}, loss={args.loss}) ...")
    t0 = time.time()

    model = LightFM(
        no_components=args.no_components,
        loss=args.loss,
        learning_rate=args.learning_rate,
        random_state=args.seed,
    )
    model.fit(
        interactions_matrix,
        epochs=args.epochs,
        num_threads=args.num_threads,
        verbose=True,
    )

    print(f"[stage_db01] Trained in {time.time() - t0:.2f}s")

    # --- Export npz ---
    # item_id_mapping: {song_id -> internal_idx}
    item_id_mapping = dataset._item_id_mapping

    song_ids_list = []
    embeddings_list = []
    biases_list = []

    for song_id in all_song_ids:
        if song_id not in item_id_mapping:
            continue
        internal_idx = item_id_mapping[song_id]
        if internal_idx >= len(model.item_embeddings):
            continue
        song_ids_list.append(int(song_id))
        embeddings_list.append(model.item_embeddings[internal_idx])
        biases_list.append(model.item_biases[internal_idx])

    song_ids_arr = np.array(song_ids_list, dtype=np.int32)
    embeddings_arr = np.array(embeddings_list, dtype=np.float32)
    biases_arr = np.array(biases_list, dtype=np.float32)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.output,
        item_embeddings=embeddings_arr,
        item_biases=biases_arr,
        song_ids=song_ids_arr,
    )

    print(f"\n[stage_db01] Saved {len(song_ids_arr)} songs to {args.output} "
          f"({args.output.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  embeddings shape: {embeddings_arr.shape}")
    print(f"  song_ids range: {song_ids_arr.min()} - {song_ids_arr.max()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
