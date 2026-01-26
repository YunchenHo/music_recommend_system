import argparse
from pathlib import Path

from pipeline.config import Paths
from src.data.wikidata import merge_wikidata_by_isrc
from src.io import load_table, save_df


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 08: merge Wikidata into song features")
    parser.add_argument(
        "--song-features-path",
        type=Path,
        default=paths.processed / "song_features.parquet",
    )
    parser.add_argument(
        "--wikidata-path",
        type=Path,
        default=paths.data / "external" / "wikidata_isrc_matched_en_by_isrc.csv",
    )
    parser.add_argument(
        "--out-path",
        type=Path,
        default=paths.processed / "song_features_wikidata.parquet",
    )
    args = parser.parse_args()

    song_df = load_table(args.song_features_path)
    merged = merge_wikidata_by_isrc(song_df, args.wikidata_path)
    save_df(merged, args.out_path)
    print(f"[stage_08] Saved merged data to {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
