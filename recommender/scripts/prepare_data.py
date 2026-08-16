import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import Paths
from pipeline import stage_00_download
from pipeline import stage_01_preprocess_members
from pipeline import stage_02_preprocess_songs
from pipeline import stage_03_feature_engineering_songs
from pipeline import stage_04_preprocess_train


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(
        description="Download and preprocess data (end-to-end)."
    )
    parser.add_argument("--gdrive-id", type=str, default=None)
    parser.add_argument("--zip-path", type=Path, default=paths.root / "datasets.zip")
    parser.add_argument("--out-dir", type=Path, default=paths.raw)
    parser.add_argument("--force", action="store_true", help="force re-extract zip")
    parser.add_argument(
        "--force-download", action="store_true", help="force re-download zip"
    )
    parser.add_argument("--current-year", type=int, default=datetime.now().year)
    parser.add_argument("--top-k", type=int, default=5000)
    parser.add_argument("--min-membership-days", type=int, default=30)
    args = parser.parse_args()

    stage_00_download.run(
        args.zip_path,
        args.out_dir,
        args.gdrive_id,
        args.force,
        force_download=args.force_download,
    )

    stage_01_preprocess_members.run(
        paths.raw / "members.csv",
        paths.processed / "complete_members.parquet",
        paths.artifacts / "msno_encoder.pkl",
        raw_dir=paths.raw,
    )

    stage_02_preprocess_songs.run(
        paths.raw / "songs.csv",
        paths.raw / "song_extra_info.csv",
        paths.interim / "song_merge.parquet",
        paths.artifacts / "song_encoder.pkl",
        paths.artifacts / "artist_id_map.csv",
        paths.artifacts / "song_for_db.csv",
        raw_dir=paths.raw,
    )

    stage_03_feature_engineering_songs.run(
        paths.interim / "song_merge.parquet",
        paths.processed / "song_features.parquet",
        args.current_year,
    )

    stage_04_preprocess_train.run(
        paths.raw / "train.csv",
        paths.processed / "complete_members.parquet",
        paths.processed / "train_encoded.parquet",
        paths.processed / "complete_members_small.csv",
        paths.artifacts / "msno_encoder.pkl",
        paths.artifacts / "song_encoder.pkl",
        paths.artifacts / "source_encoders.pkl",
        args.top_k,
        args.min_membership_days,
        raw_dir=paths.raw,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
