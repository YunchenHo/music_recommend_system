"""Stage db00 — sanity-check the system DB exports.

Reads the four CSV files written by the backend Django command
(`python manage.py export_for_lightfm --output-dir <REPO>/data/db_processed/`)
through `src.data.db_loader.load_db_data`, then prints row counts, the seeded/
real split, and a peek at each table.

Run from `recommender/` with the root `.venv` activated:

    uv run python pipeline/stage_db00_load_from_db.py
    uv run python pipeline/stage_db00_load_from_db.py --dir ../data/db_processed
"""

import argparse
from pathlib import Path

from src.data.db_loader import DBData, load_db_data


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DIR = _REPO_ROOT / "data" / "db_processed"


def _assert_schema(db: DBData) -> None:
    """Light schema asserts — downstream LightFM Dataset API needs these columns/dtypes."""
    required = {
        "users": {"user_id", "source_tag"},
        "songs": {"song_id", "artist_id"},
        "interactions": {"user_id", "song_id"},
        "onboarding": {"user_id", "kind", "entity_id"},
    }
    for name, cols in required.items():
        df = getattr(db, name)
        missing = cols - set(df.columns)
        assert not missing, f"{name}.csv missing required columns: {missing}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage db00: load + sanity-check DB exports")
    parser.add_argument(
        "--dir",
        type=Path,
        default=_DEFAULT_DIR,
        help=f"Directory holding the four CSV files (default: {_DEFAULT_DIR})",
    )
    args = parser.parse_args()

    if not args.dir.exists():
        raise SystemExit(
            f"[stage_db00] Directory not found: {args.dir}\n"
            f"Run the backend export first:\n"
            f"  cd backend && python manage.py export_for_lightfm --output-dir {args.dir}"
        )

    db = load_db_data(args.dir)
    _assert_schema(db)

    print(f"[stage_db00] Loaded from {args.dir}")
    print(f"  users         {len(db.users):>8} rows  (cols: {list(db.users.columns)})")
    print(f"  songs         {len(db.songs):>8} rows  (cols: {list(db.songs.columns)})")
    print(f"  interactions  {len(db.interactions):>8} rows  (cols: {list(db.interactions.columns)})")
    print(f"  onboarding    {len(db.onboarding):>8} rows  (cols: {list(db.onboarding.columns)})")

    tag_counts = db.users["source_tag"].value_counts(dropna=False).to_dict()
    print(f"\n  users by source_tag: {tag_counts}")
    if "seeded" not in tag_counts:
        print(
            "  NOTE: no 'seeded' users yet — this is expected until dataset "
            "users get imported into the DB. The source_tag field is forward-"
            "looking; the prefix rule (google_id starts with --seeded-prefix, "
            "default 'dev_') only matters once seeding actually happens."
        )
    elif "real" not in tag_counts:
        print(
            "  NOTE: no 'real' (OAuth) users yet — all users matched the "
            "seeded-prefix rule."
        )

    # Engagement spread — confirms histories / likes / affinities were populated
    if len(db.interactions):
        n_users_with_history = db.interactions["user_id"].nunique()
        n_with_like = db.interactions["is_liked"].notna().sum()
        n_with_affinity = db.interactions["affinity_score"].notna().sum()
        print(
            f"\n  interactions: {n_users_with_history} unique users, "
            f"{n_with_like} rows w/ like signal, "
            f"{n_with_affinity} rows w/ affinity score"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
