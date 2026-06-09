"""Stage db02 — Train LightFM from KKBOX dataset and produce backend artifacts.

Uses the pre-processed `train_encoded.parquet` (5000 users, ~246K songs),
`complete_members.parquet`, and `song_merge.parquet` to train two separate
LightFM models:

1. Pure CF  → artifacts/lightfm_purecf.npz
   - Identity-only matrix factorization (no user features, no item features).
   - Best for warm users with ≥10 history songs where collaborative signal
     dominates and side-information adds noise.
   - Exports raw item embeddings directly from `model.item_embeddings`.

2. Hybrid   → artifacts/lightfm_hybrid.npz
   - Item features (~5208 tags): artist (5001), language (~10), length (5),
     genre (~192).  Built via `build_item_feature_tags()`.
   - User features (21 tags): bd_group (7), gender (3), membership_group (7),
     lang_pref (4).
   - For cold-start users who lack sufficient interaction history.
   - Exports feature-weighted embeddings (item_feature_matrix @ feature_embeddings).

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
from src.models.lightfm_model import build_item_feature_tags, collect_unique_feature_tags


# ---------------------------------------------------------------------------
# Language preference derivation
# ---------------------------------------------------------------------------

# Only recognize these 4 language codes (aligned with build_top5000_members_with_language.py)
# 3=Chinese(Mandarin), 52=English, 17=Japanese, 31=Korean
LANGUAGE_MAP = {3: "Chinese", 52: "English", 17: "Japanese", 31: "Korean"}

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

    Only considers songs with language codes in LANGUAGE_MAP (3, 17, 31, 52).

    Returns {msno_id: [lang_pref_3, lang_pref_52, ...]}
    """
    # Map each positive interaction to its song language
    pos_with_lang = positives.copy()
    pos_with_lang["language"] = pos_with_lang["song_id"].map(song_lang_map)
    # Only keep songs with recognized language codes
    pos_with_lang = pos_with_lang[pos_with_lang["language"].isin(LANGUAGE_MAP.keys())]

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


# Recognized language codes for user language preference tags
# 3=Chinese(Mandarin), 17=Japanese, 31=Korean, 52=English
KNOWN_LANG_PREF_CODES = [3, 17, 31, 52]


def get_all_user_feature_names() -> list[str]:
    """All possible user feature tag names (must match backend encoding)."""
    names = []
    for i in range(7):
        names.append(f"bd_{i}")
    names.extend(["gender_female", "gender_male", "gender_unknown"])
    for i in range(7):
        names.append(f"ms_{i}")
    # Language preference tags
    for code in KNOWN_LANG_PREF_CODES:
        names.append(f"lang_pref_{code}")
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


def load_song_metadata(
    song_merge_path: Path, all_song_ids: list[int]
) -> pd.DataFrame:
    """Load song metadata from song_merge.parquet for item feature construction.

    Returns a DataFrame with columns: song_id_new, language, artist_name,
    song_length, genre_ids — filtered to songs present in the training set.
    """
    cols = ["song_id_new", "language", "artist_name", "song_length", "genre_ids"]
    songs = pd.read_parquet(song_merge_path, columns=cols)
    songs = songs[songs["song_id_new"].isin(set(all_song_ids))]
    # Fill NaN for language (needed by derive_user_lang_prefs)
    songs["language"] = songs["language"].fillna(-1).astype(int)
    print(f"  Song metadata loaded: {len(songs):,} songs")
    print(f"  Columns: {list(songs.columns)}")
    lang_dist = songs["language"].value_counts().head(10)
    print(f"  Top language codes:\n{lang_dist.to_string()}")
    return songs


def train_purecf(
    positives: pd.DataFrame,
    all_user_ids: list[int],
    all_song_ids: list[int],
    *,
    no_components: int,
    epochs: int,
    loss: str,
    learning_rate: float,
    max_sampled: int,
    item_alpha: float,
    user_alpha: float,
    num_threads: int,
    seed: int,
):
    """Train pure CF LightFM (no user/item features, identity-only MF)."""
    from lightfm import LightFM
    from lightfm.data import Dataset

    print("\n[Pure CF] Building dataset (identity-only, no features) ...")
    dataset = Dataset()
    dataset.fit(users=all_user_ids, items=all_song_ids)

    interactions, _ = dataset.build_interactions(
        zip(positives["msno_id"].tolist(), positives["song_id"].tolist())
    )

    print(f"  Interactions matrix: {dataset.interactions_shape()}")

    print(f"[Pure CF] Training (components={no_components}, epochs={epochs}, "
          f"loss={loss}, max_sampled={max_sampled}, "
          f"item_alpha={item_alpha}, user_alpha={user_alpha}) ...")
    t0 = time.time()
    model = LightFM(
        no_components=no_components,
        loss=loss,
        learning_rate=learning_rate,
        max_sampled=max_sampled,
        item_alpha=item_alpha,
        user_alpha=user_alpha,
        random_state=seed,
    )
    model.fit(
        interactions,
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
    max_sampled: int,
    item_alpha: float,
    user_alpha: float,
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
          f"loss={loss}, max_sampled={max_sampled}, "
          f"item_alpha={item_alpha}, user_alpha={user_alpha}) ...")
    t0 = time.time()
    model = LightFM(
        no_components=no_components,
        loss=loss,
        learning_rate=learning_rate,
        max_sampled=max_sampled,
        item_alpha=item_alpha,
        user_alpha=user_alpha,
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
    output: Path,
) -> None:
    """Export pure CF artifacts to .npz (raw item latent vectors, no features)."""
    item_id_mapping = dataset._item_id_mapping

    song_ids_list = []
    embeddings_list = []
    biases_list = []
    for song_id in all_song_ids:
        if song_id not in item_id_mapping:
            continue
        idx = item_id_mapping[song_id]
        song_ids_list.append(song_id)
        embeddings_list.append(model.item_embeddings[idx])
        biases_list.append(float(model.item_biases[idx]))

    embeddings = np.array(embeddings_list, dtype=np.float32)
    biases = np.array(biases_list, dtype=np.float32)

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
        help="Song metadata for hybrid item features (not needed for purecf-only)",
    )
    parser.add_argument(
        "--output-purecf", type=Path,
        default=paths.artifacts / "lightfm_purecf.npz",
    )
    parser.add_argument(
        "--output-hybrid", type=Path,
        default=paths.artifacts / "lightfm_hybrid.npz",
    )

    # --- Shared parameters ---
    parser.add_argument("--loss", type=str, default="warp",
                        choices=["warp", "bpr", "logistic", "warp-kos"])
    parser.add_argument("--num-threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--lang-pref-threshold", type=float, default=LANG_PREF_RATIO_THRESHOLD,
        help="Min ratio for a language to be tagged as user preference",
    )
    parser.add_argument(
        "--top-k-artists", type=int, default=5000,
        help="[Hybrid] Top-K artists to keep as individual tags (rest → artist_other)",
    )
    parser.add_argument(
        "--length-buckets", type=int, default=5,
        help="[Hybrid] Number of quantile buckets for song length",
    )

    # --- Pure CF model hyperparameters ---
    purecf_group = parser.add_argument_group("Pure CF hyperparameters")
    purecf_group.add_argument("--purecf-components", type=int, default=256,
                              help="Embedding dimension for pure CF (default: 256)")
    purecf_group.add_argument("--purecf-epochs", type=int, default=50)
    purecf_group.add_argument("--purecf-lr", type=float, default=0.05,
                              help="Learning rate for pure CF")
    purecf_group.add_argument("--purecf-max-sampled", type=int, default=80,
                              help="WARP max negative samples for pure CF")
    purecf_group.add_argument("--purecf-item-alpha", type=float, default=1e-6,
                              help="L2 regularization on item latent vectors (pure CF)")
    purecf_group.add_argument("--purecf-user-alpha", type=float, default=1e-5,
                              help="L2 regularization on user latent vectors (pure CF)")

    # --- Hybrid model hyperparameters ---
    hybrid_group = parser.add_argument_group("Hybrid hyperparameters")
    hybrid_group.add_argument("--hybrid-components", type=int, default=128,
                              help="Embedding dimension for hybrid (default: 128)")
    hybrid_group.add_argument("--hybrid-epochs", type=int, default=30)
    hybrid_group.add_argument("--hybrid-lr", type=float, default=0.05,
                              help="Learning rate for hybrid")
    hybrid_group.add_argument("--hybrid-max-sampled", type=int, default=50,
                              help="WARP max negative samples for hybrid")
    hybrid_group.add_argument("--hybrid-item-alpha", type=float, default=0.0,
                              help="L2 regularization on item embeddings (hybrid)")
    hybrid_group.add_argument("--hybrid-user-alpha", type=float, default=0.0,
                              help="L2 regularization on user embeddings (hybrid)")

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

    # --- Pure CF (no features, identity-only MF) ---
    if args.mode in ("both", "purecf"):
        purecf_kwargs = dict(
            no_components=args.purecf_components,
            epochs=args.purecf_epochs,
            loss=args.loss,
            learning_rate=args.purecf_lr,
            max_sampled=args.purecf_max_sampled,
            item_alpha=args.purecf_item_alpha,
            user_alpha=args.purecf_user_alpha,
            num_threads=args.num_threads,
            seed=args.seed,
        )
        model, dataset = train_purecf(
            positives, all_user_ids, all_song_ids,
            **purecf_kwargs,
        )
        export_purecf_npz(model, dataset, all_song_ids, args.output_purecf)
        del model, dataset

    # --- Hybrid (user features + item features) ---
    if args.mode in ("both", "hybrid"):
        if not args.members_path.exists():
            raise SystemExit(
                f"[stage_db02] Members file not found: {args.members_path}\n"
                f"Need member features for hybrid mode."
            )
        if not args.songs_path.exists():
            raise SystemExit(
                f"[stage_db02] Song metadata not found: {args.songs_path}\n"
                f"Need song_merge.parquet for hybrid item features."
            )

        # Load song metadata (for item features + lang_pref derivation)
        print(f"\n[Hybrid] Loading song metadata from {args.songs_path} ...")
        songs_df = load_song_metadata(args.songs_path, all_song_ids)

        # Build song_lang_map for derive_user_lang_prefs
        song_lang_map = dict(zip(
            songs_df["song_id_new"].astype(int),
            songs_df["language"].astype(int),
        ))
        for sid in all_song_ids:
            if sid not in song_lang_map:
                song_lang_map[sid] = -1

        # Build item feature tags (artist + language + length + genre)
        item_feature_tags = build_item_feature_tags(
            songs_df, top_k_artists=args.top_k_artists, length_buckets=args.length_buckets
        )
        for sid in all_song_ids:
            if sid not in item_feature_tags:
                item_feature_tags[sid] = ["lang_-1", "artist_other", "len_0", "genre_unknown"]

        all_item_feature_names = collect_unique_feature_tags(item_feature_tags)
        print(f"  Item feature tags: {len(all_item_feature_names):,} unique tags")
        print(f"  Sample tags: {all_item_feature_names[:10]} ...")

        # Load members
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
        all_user_feature_names = get_all_user_feature_names()
        print(f"  All user feature names ({len(all_user_feature_names)}): "
              f"{all_user_feature_names}")

        hybrid_kwargs = dict(
            no_components=args.hybrid_components,
            epochs=args.hybrid_epochs,
            loss=args.loss,
            learning_rate=args.hybrid_lr,
            max_sampled=args.hybrid_max_sampled,
            item_alpha=args.hybrid_item_alpha,
            user_alpha=args.hybrid_user_alpha,
            num_threads=args.num_threads,
            seed=args.seed,
        )
        model, dataset = train_hybrid(
            positives, all_user_ids, all_song_ids,
            user_feature_tags, all_user_feature_names,
            item_feature_tags, all_item_feature_names,
            **hybrid_kwargs,
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
