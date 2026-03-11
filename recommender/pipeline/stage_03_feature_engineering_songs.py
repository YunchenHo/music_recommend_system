import argparse
from datetime import datetime
from pathlib import Path

from pipeline.config import Paths
from src.features.songs import build_song_features
from src.io import load_table, save_df


def run(song_merge_path: Path, out_path: Path, current_year: int) -> None:
    song_merge = load_table(song_merge_path)
    song_features = build_song_features(song_merge, current_year=current_year)
    save_df(song_features, out_path)
    print(f"[stage_03] Saved song features to {out_path}")


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 03: feature engineering for songs")
    parser.add_argument(
        "--song-merge-path", type=Path, default=paths.interim / "song_merge.parquet"
    )
    parser.add_argument(
        "--out-path", type=Path, default=paths.processed / "song_features.parquet"
    )
    parser.add_argument(
        "--current-year", type=int, default=datetime.now().year
    )
    args = parser.parse_args()

    run(args.song_merge_path, args.out_path, args.current_year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
