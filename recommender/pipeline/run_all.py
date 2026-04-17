import argparse
import os
from datetime import datetime
from pathlib import Path

from pipeline.config import Paths
from pipeline import stage_00_download
from pipeline import stage_01_preprocess_members
from pipeline import stage_02_preprocess_songs
from pipeline import stage_03_feature_engineering_songs
from pipeline import stage_04_preprocess_train


STAGES = [
    ("00_download", stage_00_download.run),
    ("01_members", stage_01_preprocess_members.run),
    ("02_songs", stage_02_preprocess_songs.run),
    ("03_song_features", stage_03_feature_engineering_songs.run),
    ("04_train", stage_04_preprocess_train.run),
]


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Run the full data pipeline")
    parser.add_argument("--from-stage", type=str, default="00_download")
    parser.add_argument("--to-stage", type=str, default="04_train")
    parser.add_argument("--zip-path", type=Path, default=paths.root / "datasets.zip")
    parser.add_argument("--out-dir", type=Path, default=paths.raw)
    parser.add_argument("--gdrive-id", type=str, default=os.environ.get("GDRIVE_ID"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--top-k", type=int, default=5000)
    parser.add_argument("--min-membership-days", type=int, default=30)
    parser.add_argument("--current-year", type=int, default=None)

    args = parser.parse_args()

    stage_names = [name for name, _ in STAGES]
    if args.from_stage not in stage_names or args.to_stage not in stage_names:
        raise ValueError(f"Stage must be one of: {stage_names}")

    start = stage_names.index(args.from_stage)
    end = stage_names.index(args.to_stage)
    if start > end:
        raise ValueError("--from-stage must be <= --to-stage")

    for name, fn in STAGES[start : end + 1]:
        print(f"\n===== Running {name} =====")
        if name == "00_download":
            fn(
                args.zip_path,
                args.out_dir,
                args.gdrive_id,
                args.force,
                force_download=args.force_download,
            )
        elif name == "01_members":
            fn(
                paths.raw / "members.csv",
                paths.processed / "complete_members.parquet",
                paths.artifacts / "msno_encoder.pkl",
                paths.raw,
            )
        elif name == "02_songs":
            fn(
                paths.raw / "songs.csv",
                paths.raw / "song_extra_info.csv",
                paths.interim / "song_merge.parquet",
                paths.artifacts / "song_encoder.pkl",
                paths.artifacts / "artist_id_map.csv",
                paths.artifacts / "song_for_db.csv",
                paths.raw,
            )
        elif name == "03_song_features":
            current_year = args.current_year or datetime.now().year
            fn(
                paths.interim / "song_merge.parquet",
                paths.processed / "song_features.parquet",
                current_year,
            )
        elif name == "04_train":
            fn(
                paths.raw / "train.csv",
                paths.processed / "complete_members.parquet",
                paths.processed / "train_encoded.parquet",
                paths.processed / "complete_members_small.csv",
                paths.artifacts / "msno_encoder.pkl",
                paths.artifacts / "song_encoder.pkl",
                paths.artifacts / "source_encoders.pkl",
                args.top_k,
                args.min_membership_days,
                paths.raw,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
