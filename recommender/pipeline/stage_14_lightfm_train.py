import argparse
import pickle
import time
from pathlib import Path

from pipeline.config import Paths
from src.io import load_table, save_df


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 14: train LightFM model")
    parser.add_argument(
        "--train-path",
        type=Path,
        default=paths.processed / "train_encoded.parquet",
    )
    parser.add_argument(
        "--members-path",
        type=Path,
        default=paths.processed / "complete_members.parquet",
    )
    parser.add_argument(
        "--songs-path",
        type=Path,
        default=paths.processed / "song_features.parquet",
    )
    parser.add_argument("--no-components", type=int, default=128)
    parser.add_argument("--loss", type=str, default="warp",
                        choices=["warp", "bpr", "logistic", "warp-kos"])
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--num-threads", type=int, default=4)
    parser.add_argument(
        "--max-sampled",
        type=int,
        default=10,
        help=(
            "Max negative samples per WARP update. Default 10 is often too low "
            "for large catalogs; try 30-100 for better ranking signal."
        ),
    )
    parser.add_argument(
        "--item-alpha",
        type=float,
        default=0.0,
        help="L2 regularization on item embeddings. Try 1e-6 if overfitting.",
    )
    parser.add_argument(
        "--user-alpha",
        type=float,
        default=0.0,
        help="L2 regularization on user embeddings. Try 1e-6 if overfitting.",
    )
    parser.add_argument("--min-pos-per-user", type=int, default=2)
    parser.add_argument(
        "--top-k-members",
        type=int,
        default=5000,
        help=(
            "Filter to top-K members by total play_count, matching ItemKNN's "
            "filter_top_members convention. Set 0 to disable."
        ),
    )
    parser.add_argument(
        "--min-membership-days",
        type=int,
        default=30,
        help="Only consider members with membership_days > N for top-K filter.",
    )
    parser.add_argument(
        "--max-users",
        type=int,
        default=None,
        help=(
            "Cap users to first N from the filtered set (mostly for smoke tests). "
            "Applied AFTER --top-k-members."
        ),
    )
    parser.add_argument("--sample-rate", type=float, default=None)
    parser.add_argument("--top-k-cities", type=int, default=30)
    parser.add_argument("--top-k-artists", type=int, default=5000)
    parser.add_argument("--no-features", action="store_true",
                        help="disable user/item features (pure CF mode)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--model-out",
        type=Path,
        default=paths.artifacts / "lightfm_model.pkl",
    )
    parser.add_argument(
        "--data-out",
        type=Path,
        default=paths.artifacts / "lightfm_dataset.pkl",
    )
    parser.add_argument(
        "--train-out",
        type=Path,
        default=paths.processed / "lightfm_train.parquet",
    )
    parser.add_argument(
        "--test-out",
        type=Path,
        default=paths.processed / "lightfm_test.parquet",
    )
    args = parser.parse_args()

    try:
        import lightfm  # noqa: F401
    except ImportError:
        raise SystemExit(
            "[LightFM] lightfm is not installed in the active venv. "
            "Root .venv (Py 3.11.13) should have it; see the LightFM install "
            "recipe in recommender/pyproject.toml comment for the patched-sdist steps."
        )

    from src.models.lightfm_model import (
        filter_top_users_by_activity,
        prepare_lightfm_dataset,
        train_lightfm_model,
    )

    print(f"[LightFM] loading train from {args.train_path} ...", flush=True)
    t0 = time.time()
    train_df = load_table(args.train_path)
    print(f"[LightFM] loaded {len(train_df)} rows in {time.time() - t0:.2f}s",
          flush=True)

    use_features = not args.no_features
    members_df = load_table(args.members_path) if use_features else None
    songs_df = load_table(args.songs_path) if use_features else None
    if use_features:
        print(f"[LightFM] members: {len(members_df)} rows, "
              f"songs: {len(songs_df)} rows", flush=True)

    if args.top_k_members and args.top_k_members > 0:
        members_for_filter = (
            members_df if members_df is not None else load_table(args.members_path)
        )
        before_rows = len(train_df)
        before_users = train_df["msno_id"].nunique()
        train_df = filter_top_users_by_activity(
            train_df,
            members_for_filter,
            top_k=args.top_k_members,
            min_membership_days=args.min_membership_days,
        )
        print(
            f"[LightFM] top-K member filter (k={args.top_k_members}, "
            f"min_days>{args.min_membership_days}): "
            f"{before_users} → {train_df['msno_id'].nunique()} users, "
            f"{before_rows} → {len(train_df)} interactions",
            flush=True,
        )

    print("[LightFM] preparing dataset ...", flush=True)
    t1 = time.time()
    data = prepare_lightfm_dataset(
        train_df,
        members=members_df,
        songs=songs_df,
        use_features=use_features,
        min_pos_per_user=args.min_pos_per_user,
        seed=args.seed,
        max_users=args.max_users,
        sample_rate=args.sample_rate,
        top_k_cities=args.top_k_cities,
        top_k_artists=args.top_k_artists,
    )
    print(f"[LightFM] prepared in {time.time() - t1:.2f}s | "
          f"users={data.num_users} items={data.num_items} "
          f"interactions={data.interactions.nnz} test={len(data.df_test)}",
          flush=True)

    print(
        f"[LightFM] training (loss={args.loss}, components={args.no_components}, "
        f"epochs={args.epochs}, features={use_features}, "
        f"max_sampled={args.max_sampled}, item_alpha={args.item_alpha}, "
        f"user_alpha={args.user_alpha}) ...",
        flush=True,
    )
    t2 = time.time()
    model = train_lightfm_model(
        data,
        no_components=args.no_components,
        loss=args.loss,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        num_threads=args.num_threads,
        seed=args.seed,
        verbose=True,
        max_sampled=args.max_sampled,
        item_alpha=args.item_alpha,
        user_alpha=args.user_alpha,
    )
    print(f"[LightFM] trained in {time.time() - t2:.2f}s", flush=True)

    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.model_out, "wb") as f:
        pickle.dump(model, f)
    print("Saved LightFM model:", args.model_out)

    args.data_out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": data.dataset,
        "interactions": data.interactions,
        "user_features": data.user_features,
        "item_features": data.item_features,
        "num_users": data.num_users,
        "num_items": data.num_items,
    }
    with open(args.data_out, "wb") as f:
        pickle.dump(payload, f)
    print("Saved LightFM dataset payload:", args.data_out)

    save_df(data.df_train, args.train_out)
    save_df(data.df_test, args.test_out)
    print("Saved LightFM train/test splits:", args.train_out, args.test_out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
