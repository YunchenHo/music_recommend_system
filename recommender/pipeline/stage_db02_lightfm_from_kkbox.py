"""Stage db02 — Train LightFM from KKBOX dataset and produce backend artifacts.

Uses the pre-processed `train_encoded.parquet` (5000 users, ~246K songs) and
`complete_members.parquet` to train two separate LightFM models:

1. Pure CF  → artifacts/lightfm_purecf.npz  (for warm users with ≥10 history songs)
2. Hybrid   → artifacts/lightfm_hybrid.npz  (for cold-start users, includes user feature embeddings)

The output .npz files are directly consumed by the backend `lightfm_service.py`
without needing the lightfm package at serving time.

Run from `recommender/`:
    python -m pipeline.stage_db02_lightfm_from_kkbox
    python -m pipeline.stage_db02_lightfm_from_kkbox --mode purecf
    python -m pipeline.stage_db02_lightfm_from_kkbox --mode hybrid
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.config import Paths


# ---------------------------------------------------------------------------
# Feature encoding (mirrors backend/users/feature_encoding.py bucketing)
# ---------------------------------------------------------------------------

def _gender_tag(row: pd.Series) -> str:
    """Convert gender_female/gender_male columns to tag string."""
    if row.get("gender_female", 0) == 1:
        return "gender_female"
    elif row.get("gender_male", 0) == 1:
        return "gender_male"
    return "gender_unknown"


def build_user_feature_tags(members: pd.DataFrame) -> dict[int, list[str]]:
    """Build {msno_id: [bd_X, gender_Y, ms_Z]} mapping from members df."""
    features: dict[int, list[str]] = {}
    for _, row in members.iterrows():
        bd_tag = f"bd_{int(row['bd_group'])}"
        g_tag = _gender_tag(row)
        ms_tag = f"ms_{int(row['membership_group'])}"
        features[int(row["msno_id"])] = [bd_tag, g_tag, ms_tag]
    return features


def get_all_feature_names() -> list[str]:
    """All possible user feature tag names (must match backend encoding)."""
    names = []
    for i in range(7):
        names.append(f"bd_{i}")
    names.extend(["gender_female", "gender_male", "gender_unknown"])
    for i in range(7):
        names.append(f"ms_{i}")
    return names


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------

def load_positive_interactions(train_path: Path) -> pd.DataFrame:
    """Load train_encoded.parquet and return deduplicated positive pairs."""
    df = pd.read_parquet(train_path, columns=["msno_id", "song_id", "target"])
    positives = df[df["target"] == 1][["msno_id", "song_id"]].drop_duplicates()
    print(f"  Total interactions: {len(df):,}")
    print(f"  Positive (target=1) unique pairs: {len(positives):,}")
    return positives


def train_purecf(
    positives: pd.DataFrame,
    all_user_ids: list[int],
    all_song_ids: list[int],
    *,
    no_components: int,
    epochs: int,
    loss: str,
    learning_rate: float,
    num_threads: int,
    seed: int,
) -> Path:
    """Train pure CF LightFM and return item embeddings."""
    from lightfm import LightFM
    from lightfm.data import Dataset

    print("\n[Pure CF] Building dataset ...")
    dataset = Dataset()
    dataset.fit(users=all_user_ids, items=all_song_ids)

    interactions, _ = dataset.build_interactions(
        zip(positives["msno_id"].tolist(), positives["song_id"].tolist())
    )
    print(f"  Interactions matrix: {dataset.interactions_shape()}")

    print(f"[Pure CF] Training (components={no_components}, epochs={epochs}, "
          f"loss={loss}) ...")
    t0 = time.time()
    model = LightFM(
        no_components=no_components,
        loss=loss,
        learning_rate=learning_rate,
        random_state=seed,
    )
    model.fit(interactions, epochs=epochs, num_threads=num_threads, verbose=True)
    print(f"[Pure CF] Done in {time.time() - t0:.1f}s")

    return model, dataset


def train_hybrid(
    positives: pd.DataFrame,
    all_user_ids: list[int],
    all_song_ids: list[int],
    user_feature_tags: dict[int, list[str]],
    all_feature_names: list[str],
    *,
    no_components: int,
    epochs: int,
    loss: str,
    learning_rate: float,
    num_threads: int,
    seed: int,
):
    """Train hybrid LightFM with user features."""
    from lightfm import LightFM
    from lightfm.data import Dataset

    print("\n[Hybrid] Building dataset ...")
    dataset = Dataset()
    dataset.fit(
        users=all_user_ids,
        items=all_song_ids,
        user_features=all_feature_names,
    )

    interactions, _ = dataset.build_interactions(
        zip(positives["msno_id"].tolist(), positives["song_id"].tolist())
    )

    # Build user features matrix
    user_features_iter = []
    for uid in all_user_ids:
        tags = user_feature_tags.get(uid)
        if tags:
            user_features_iter.append((uid, tags))
        else:
            # Users without member info get no extra features (identity only)
            user_features_iter.append((uid, []))

    user_features = dataset.build_user_features(user_features_iter, normalize=False)

    print(f"  Interactions matrix: {dataset.interactions_shape()}")
    print(f"  User features shape: {user_features.shape}")

    print(f"[Hybrid] Training (components={no_components}, epochs={epochs}, "
          f"loss={loss}) ...")
    t0 = time.time()
    model = LightFM(
        no_components=no_components,
        loss=loss,
        learning_rate=learning_rate,
        random_state=seed,
    )
    model.fit(
        interactions,
        user_features=user_features,
        epochs=epochs,
        num_threads=num_threads,
        verbose=True,
    )
    print(f"[Hybrid] Done in {time.time() - t0:.1f}s")

    return model, dataset


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_purecf_npz(model, dataset, all_song_ids: list[int], output: Path) -> None:
    """Export pure CF artifacts to .npz."""
    item_id_mapping = dataset._item_id_mapping

    song_ids_list = []
    embeddings_list = []
    biases_list = []

    for song_id in all_song_ids:
        if song_id not in item_id_mapping:
            continue
        idx = item_id_mapping[song_id]
        if idx >= len(model.item_embeddings):
            continue
        song_ids_list.append(song_id)
        embeddings_list.append(model.item_embeddings[idx])
        biases_list.append(model.item_biases[idx])

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        output,
        item_embeddings=np.array(embeddings_list, dtype=np.float32),
        item_biases=np.array(biases_list, dtype=np.float32),
        song_ids=np.array(song_ids_list, dtype=np.int32),
    )
    print(f"[Pure CF] Saved {len(song_ids_list)} songs → {output} "
          f"({output.stat().st_size / 1024 / 1024:.1f} MB)")


def export_hybrid_npz(
    model, dataset, all_song_ids: list[int], all_feature_names: list[str], output: Path
) -> None:
    """Export hybrid artifacts to .npz (item embeddings + user feature embeddings)."""
    item_id_mapping = dataset._item_id_mapping

    song_ids_list = []
    embeddings_list = []
    biases_list = []

    for song_id in all_song_ids:
        if song_id not in item_id_mapping:
            continue
        idx = item_id_mapping[song_id]
        if idx >= len(model.item_embeddings):
            continue
        song_ids_list.append(song_id)
        embeddings_list.append(model.item_embeddings[idx])
        biases_list.append(model.item_biases[idx])

    # Extract user feature embeddings
    _, user_feature_map, _, _ = dataset.mapping()
    n_users = len(dataset._user_id_mapping)

    feature_names = []
    feature_indices = []
    for feat_name, col_idx in sorted(user_feature_map.items(), key=lambda x: x[1]):
        if col_idx >= n_users:
            feature_names.append(feat_name)
            feature_indices.append(col_idx)

    user_feat_emb = model.user_embeddings[feature_indices].astype(np.float32)
    user_feat_bias = model.user_biases[feature_indices].astype(np.float32)

    print(f"[Hybrid] User feature tags: {feature_names}")
    print(f"[Hybrid] User feature embeddings shape: {user_feat_emb.shape}")

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        output,
        item_embeddings=np.array(embeddings_list, dtype=np.float32),
        item_biases=np.array(biases_list, dtype=np.float32),
        song_ids=np.array(song_ids_list, dtype=np.int32),
        user_feature_embeddings=user_feat_emb,
        user_feature_biases=user_feat_bias,
        user_feature_names=json.dumps(feature_names),
    )
    print(f"[Hybrid] Saved {len(song_ids_list)} songs → {output} "
          f"({output.stat().st_size / 1024 / 1024:.1f} MB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(
        description="Stage db02: train LightFM from KKBOX dataset for backend serving"
    )
    parser.add_argument(
        "--mode", choices=["both", "purecf", "hybrid"], default="both",
        help="Which model(s) to train (default: both)",
    )
    parser.add_argument(
        "--train-path", type=Path,
        default=paths.processed / "train_encoded.parquet",
    )
    parser.add_argument(
        "--members-path", type=Path,
        default=paths.processed / "complete_members.parquet",
    )
    parser.add_argument(
        "--output-purecf", type=Path,
        default=paths.artifacts / "lightfm_purecf.npz",
    )
    parser.add_argument(
        "--output-hybrid", type=Path,
        default=paths.artifacts / "lightfm_hybrid.npz",
    )
    parser.add_argument("--no-components", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--loss", type=str, default="warp")
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--num-threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # --- Validate ---
    try:
        import lightfm  # noqa: F401
    except ImportError:
        raise SystemExit(
            "[stage_db02] lightfm is not installed. "
            "Run in the recommender container or root .venv (Py 3.11)."
        )

    if not args.train_path.exists():
        raise SystemExit(f"[stage_db02] Train file not found: {args.train_path}")

    # --- Load interactions ---
    print(f"[stage_db02] Loading interactions from {args.train_path} ...")
    positives = load_positive_interactions(args.train_path)

    all_user_ids = sorted(positives["msno_id"].unique().tolist())
    all_song_ids = sorted(positives["song_id"].unique().tolist())
    print(f"  Users: {len(all_user_ids):,}, Songs: {len(all_song_ids):,}")

    train_kwargs = dict(
        no_components=args.no_components,
        epochs=args.epochs,
        loss=args.loss,
        learning_rate=args.learning_rate,
        num_threads=args.num_threads,
        seed=args.seed,
    )

    # --- Pure CF ---
    if args.mode in ("both", "purecf"):
        model, dataset = train_purecf(
            positives, all_user_ids, all_song_ids, **train_kwargs
        )
        export_purecf_npz(model, dataset, all_song_ids, args.output_purecf)
        del model, dataset

    # --- Hybrid ---
    if args.mode in ("both", "hybrid"):
        if not args.members_path.exists():
            raise SystemExit(
                f"[stage_db02] Members file not found: {args.members_path}\n"
                f"Need member features for hybrid mode."
            )

        print(f"\n[Hybrid] Loading members from {args.members_path} ...")
        members = pd.read_parquet(args.members_path)
        # Only keep members that appear in our training set
        members = members[members["msno_id"].isin(set(all_user_ids))]
        print(f"  Members matched to training users: {len(members):,}")

        user_feature_tags = build_user_feature_tags(members)
        all_feature_names = get_all_feature_names()

        model, dataset = train_hybrid(
            positives, all_user_ids, all_song_ids,
            user_feature_tags, all_feature_names,
            **train_kwargs,
        )
        export_hybrid_npz(model, dataset, all_song_ids, all_feature_names, args.output_hybrid)
        del model, dataset

    print("\n[stage_db02] All done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
