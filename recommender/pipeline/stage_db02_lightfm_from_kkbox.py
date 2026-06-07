"""Stage db02 — Train LightFM from KKBOX dataset and produce backend artifacts.

Uses the pre-processed `train_encoded.parquet` (5000 users, ~246K songs),
`complete_members.parquet`, and `song_merge.parquet` to train two separate
LightFM models:

1. Pure CF  → artifacts/lightfm_purecf.npz  (for warm users with ≥10 history songs)
2. Hybrid   → artifacts/lightfm_hybrid.npz  (for cold-start users, includes user feature embeddings)

Both models now include:
- Item features: song language tag (lang_{code}) to encode language in embeddings
- User features (hybrid only): demographics + language preference (lang_pref_{code})

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
# Language preference derivation
# ---------------------------------------------------------------------------

# Minimum ratio of a language in user's positive interactions to be considered
# a language preference tag.
LANG_PREF_RATIO_THRESHOLD = 0.30


def derive_user_lang_prefs(
    positives: pd.DataFrame,
    song_lang_map: dict[int, int],
    threshold: float = LANG_PREF_RATIO_THRESHOLD,
) -> dict[int, list[str]]:
    """Derive language preference tags for each user from their positive interactions.

    For each user, if a language accounts for ≥ threshold of their
    positive interactions, they get a `lang_pref_{code}` tag.

    Returns {msno_id: [lang_pref_3, lang_pref_52, ...]}
    """
    # Map each positive interaction to its song language
    pos_with_lang = positives.copy()
    pos_with_lang["language"] = pos_with_lang["song_id"].map(song_lang_map)
    # Drop rows with unknown language (-1)
    pos_with_lang = pos_with_lang[pos_with_lang["language"] != -1]

    # Count interactions per user per language
    lang_counts = (
        pos_with_lang.groupby(["msno_id", "language"])
        .size()
        .reset_index(name="count")
    )
    # Total interactions per user
    user_totals = lang_counts.groupby("msno_id")["count"].sum().rename("total")
    lang_counts = lang_counts.merge(user_totals, on="msno_id")
    lang_counts["ratio"] = lang_counts["count"] / lang_counts["total"]

    # Filter to those above threshold
    significant = lang_counts[lang_counts["ratio"] >= threshold]

    user_lang_prefs: dict[int, list[str]] = {}
    for _, row in significant.iterrows():
        uid = int(row["msno_id"])
        tag = f"lang_pref_{int(row['language'])}"
        user_lang_prefs.setdefault(uid, []).append(tag)

    print(f"  Users with lang_pref tags: {len(user_lang_prefs):,} "
          f"(threshold={threshold})")
    return user_lang_prefs


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


def build_user_feature_tags(
    members: pd.DataFrame,
    user_lang_prefs: dict[int, list[str]] | None = None,
) -> dict[int, list[str]]:
    """Build {msno_id: [bd_X, gender_Y, ms_Z, lang_pref_*...]} mapping."""
    features: dict[int, list[str]] = {}
    for _, row in members.iterrows():
        uid = int(row["msno_id"])
        bd_tag = f"bd_{int(row['bd_group'])}"
        g_tag = _gender_tag(row)
        ms_tag = f"ms_{int(row['membership_group'])}"
        tags = [bd_tag, g_tag, ms_tag]
        # Append language preference tags
        if user_lang_prefs and uid in user_lang_prefs:
            tags.extend(user_lang_prefs[uid])
        features[uid] = tags
    return features


# Known language codes in KKBOX dataset
# 3=Chinese(Mandarin), 24=Cantonese, 52=English, 17=Japanese, 31=Korean
KNOWN_LANG_CODES = [3, 10, 17, 24, 31, 45, 52, 59]


def get_all_feature_names() -> list[str]:
    """All possible user feature tag names (must match backend encoding)."""
    names = []
    for i in range(7):
        names.append(f"bd_{i}")
    names.extend(["gender_female", "gender_male", "gender_unknown"])
    for i in range(7):
        names.append(f"ms_{i}")
    # Language preference tags
    for code in KNOWN_LANG_CODES:
        names.append(f"lang_pref_{code}")
    names.append("lang_pref_-1")
    return names


def get_all_item_feature_names(song_lang_map: dict[int, int]) -> list[str]:
    """All unique item (song) feature tag names."""
    codes = set(song_lang_map.values())
    return sorted([f"lang_{code}" for code in codes])


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


def load_song_language(song_merge_path: Path, all_song_ids: list[int]) -> dict[int, int]:
    """Load song language mapping from song_merge.parquet.

    Returns {song_id_new: language_code} (int). Missing/NaN → -1.
    """
    songs = pd.read_parquet(song_merge_path, columns=["song_id_new", "language"])
    songs["language"] = songs["language"].fillna(-1).astype(int)
    # Only keep songs in our training set
    songs = songs[songs["song_id_new"].isin(set(all_song_ids))]
    song_lang_map = dict(zip(songs["song_id_new"], songs["language"]))
    # Fill missing songs with -1
    for sid in all_song_ids:
        if sid not in song_lang_map:
            song_lang_map[sid] = -1
    print(f"  Song language map loaded: {len(song_lang_map):,} songs")
    lang_dist = pd.Series(song_lang_map).value_counts().head(10)
    print(f"  Top language codes:\n{lang_dist.to_string()}")
    return song_lang_map


def train_purecf(
    positives: pd.DataFrame,
    all_user_ids: list[int],
    all_song_ids: list[int],
    item_feature_tags: dict[int, list[str]],
    all_item_feature_names: list[str],
    *,
    no_components: int,
    epochs: int,
    loss: str,
    learning_rate: float,
    num_threads: int,
    seed: int,
):
    """Train pure CF LightFM with item features (no user features)."""
    from lightfm import LightFM
    from lightfm.data import Dataset

    print("\n[Pure CF] Building dataset ...")
    dataset = Dataset()
    dataset.fit(
        users=all_user_ids,
        items=all_song_ids,
        item_features=all_item_feature_names,
    )

    interactions, _ = dataset.build_interactions(
        zip(positives["msno_id"].tolist(), positives["song_id"].tolist())
    )

    # Build item features matrix
    item_features_iter = [
        (sid, item_feature_tags.get(sid, []))
        for sid in all_song_ids
    ]
    item_features = dataset.build_item_features(item_features_iter, normalize=False)

    print(f"  Interactions matrix: {dataset.interactions_shape()}")
    print(f"  Item features shape: {item_features.shape}")

    print(f"[Pure CF] Training (components={no_components}, epochs={epochs}, "
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
        item_features=item_features,
        epochs=epochs,
        num_threads=num_threads,
        verbose=True,
    )
    print(f"[Pure CF] Done in {time.time() - t0:.1f}s")

    return model, dataset


def train_hybrid(
    positives: pd.DataFrame,
    all_user_ids: list[int],
    all_song_ids: list[int],
    user_feature_tags: dict[int, list[str]],
    all_user_feature_names: list[str],
    item_feature_tags: dict[int, list[str]],
    all_item_feature_names: list[str],
    *,
    no_components: int,
    epochs: int,
    loss: str,
    learning_rate: float,
    num_threads: int,
    seed: int,
):
    """Train hybrid LightFM with user features + item features."""
    from lightfm import LightFM
    from lightfm.data import Dataset

    print("\n[Hybrid] Building dataset ...")
    dataset = Dataset()
    dataset.fit(
        users=all_user_ids,
        items=all_song_ids,
        user_features=all_user_feature_names,
        item_features=all_item_feature_names,
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
            user_features_iter.append((uid, []))

    user_features = dataset.build_user_features(user_features_iter, normalize=False)

    # Build item features matrix
    item_features_iter = [
        (sid, item_feature_tags.get(sid, []))
        for sid in all_song_ids
    ]
    item_features = dataset.build_item_features(item_features_iter, normalize=False)

    print(f"  Interactions matrix: {dataset.interactions_shape()}")
    print(f"  User features shape: {user_features.shape}")
    print(f"  Item features shape: {item_features.shape}")

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
        item_features=item_features,
        epochs=epochs,
        num_threads=num_threads,
        verbose=True,
    )
    print(f"[Hybrid] Done in {time.time() - t0:.1f}s")

    return model, dataset


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _compute_full_item_representations(
    model,
    dataset,
    all_song_ids: list[int],
    item_feature_tags: dict[int, list[str]],
) -> tuple[list[int], np.ndarray, np.ndarray]:
    """Compute full item representations: item_latent + Σ(feature embeddings).

    When item features are used, each item's full representation is the sum of
    its own latent vector and all its feature embeddings.

    Returns (song_ids_list, full_embeddings, full_biases)
    """
    item_id_mapping = dataset._item_id_mapping
    _, _, item_feature_map, _ = dataset.mapping()
    n_items = len(item_id_mapping)

    song_ids_list = []
    embeddings_list = []
    biases_list = []

    for song_id in all_song_ids:
        if song_id not in item_id_mapping:
            continue
        item_idx = item_id_mapping[song_id]
        if item_idx >= n_items:
            continue

        # Start with item's own latent vector
        full_emb = model.item_embeddings[item_idx].copy()
        full_bias = float(model.item_biases[item_idx])

        # Add feature embeddings
        for feat_tag in item_feature_tags.get(song_id, []):
            feat_col = item_feature_map.get(feat_tag)
            if feat_col is not None:
                full_emb += model.item_embeddings[feat_col]
                full_bias += float(model.item_biases[feat_col])

        song_ids_list.append(song_id)
        embeddings_list.append(full_emb)
        biases_list.append(full_bias)

    return (
        song_ids_list,
        np.array(embeddings_list, dtype=np.float32),
        np.array(biases_list, dtype=np.float32),
    )


def export_purecf_npz(
    model,
    dataset,
    all_song_ids: list[int],
    item_feature_tags: dict[int, list[str]],
    output: Path,
) -> None:
    """Export pure CF artifacts to .npz (with full item representations)."""
    song_ids_list, embeddings, biases = _compute_full_item_representations(
        model, dataset, all_song_ids, item_feature_tags
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        output,
        item_embeddings=embeddings,
        item_biases=biases,
        song_ids=np.array(song_ids_list, dtype=np.int32),
    )
    print(f"[Pure CF] Saved {len(song_ids_list)} songs → {output} "
          f"({output.stat().st_size / 1024 / 1024:.1f} MB)")


def export_hybrid_npz(
    model,
    dataset,
    all_song_ids: list[int],
    all_user_feature_names: list[str],
    item_feature_tags: dict[int, list[str]],
    output: Path,
) -> None:
    """Export hybrid artifacts to .npz (full item representations + user feature embeddings)."""
    # Full item representations (item latent + feature embeddings pre-computed)
    song_ids_list, embeddings, biases = _compute_full_item_representations(
        model, dataset, all_song_ids, item_feature_tags
    )

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
        item_embeddings=embeddings,
        item_biases=biases,
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
        "--songs-path", type=Path,
        default=paths.interim / "song_merge.parquet",
        help="Song metadata with language field",
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
    parser.add_argument(
        "--lang-pref-threshold", type=float, default=LANG_PREF_RATIO_THRESHOLD,
        help="Min ratio for a language to be tagged as user preference",
    )
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

    # --- Load song language data ---
    if not args.songs_path.exists():
        raise SystemExit(
            f"[stage_db02] Song metadata not found: {args.songs_path}\n"
            f"Need song_merge.parquet for language item features."
        )
    print(f"\n[stage_db02] Loading song language from {args.songs_path} ...")
    song_lang_map = load_song_language(args.songs_path, all_song_ids)

    # Build item feature tags (language)
    item_feature_tags = {
        sid: [f"lang_{song_lang_map.get(sid, -1)}"]
        for sid in all_song_ids
    }
    all_item_feature_names = get_all_item_feature_names(song_lang_map)
    print(f"  Item feature names: {all_item_feature_names}")

    train_kwargs = dict(
        no_components=args.no_components,
        epochs=args.epochs,
        loss=args.loss,
        learning_rate=args.learning_rate,
        num_threads=args.num_threads,
        seed=args.seed,
    )

    # --- Pure CF (with item features) ---
    if args.mode in ("both", "purecf"):
        model, dataset = train_purecf(
            positives, all_user_ids, all_song_ids,
            item_feature_tags, all_item_feature_names,
            **train_kwargs,
        )
        export_purecf_npz(model, dataset, all_song_ids, item_feature_tags, args.output_purecf)
        del model, dataset

    # --- Hybrid (user features + item features) ---
    if args.mode in ("both", "hybrid"):
        if not args.members_path.exists():
            raise SystemExit(
                f"[stage_db02] Members file not found: {args.members_path}\n"
                f"Need member features for hybrid mode."
            )

        print(f"\n[Hybrid] Loading members from {args.members_path} ...")
        members = pd.read_parquet(args.members_path)
        members = members[members["msno_id"].isin(set(all_user_ids))]
        print(f"  Members matched to training users: {len(members):,}")

        # Derive user language preferences from positive interactions
        print(f"\n[Hybrid] Deriving user language preferences ...")
        user_lang_prefs = derive_user_lang_prefs(
            positives, song_lang_map, threshold=args.lang_pref_threshold
        )

        user_feature_tags = build_user_feature_tags(members, user_lang_prefs)
        all_user_feature_names = get_all_feature_names()
        print(f"  All user feature names ({len(all_user_feature_names)}): "
              f"{all_user_feature_names}")

        model, dataset = train_hybrid(
            positives, all_user_ids, all_song_ids,
            user_feature_tags, all_user_feature_names,
            item_feature_tags, all_item_feature_names,
            **train_kwargs,
        )
        export_hybrid_npz(
            model, dataset, all_song_ids, all_user_feature_names,
            item_feature_tags, args.output_hybrid,
        )
        del model, dataset

    print("\n[stage_db02] All done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
