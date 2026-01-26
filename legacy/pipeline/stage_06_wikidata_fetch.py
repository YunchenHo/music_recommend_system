import argparse
from pathlib import Path

from pipeline.config import Paths
from src.data.wikidata import fetch_wikidata_by_isrc
from src.io import load_table


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 06: fetch Wikidata by ISRC")
    parser.add_argument(
        "--song-features-path",
        type=Path,
        default=paths.processed / "song_features.parquet",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=paths.data / "external" / "wikidata_isrc_cache.parquet",
    )
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--request-sleep", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-isrc", type=int, default=None)
    parser.add_argument("--user-agent", type=str, default="kkbox-class-project/0.1")
    args = parser.parse_args()

    song_df = load_table(args.song_features_path)
    if "has_valid_isrc" in song_df.columns:
        isrc_list = (
            song_df.loc[song_df["has_valid_isrc"] == 1, "isrc"]
            .dropna()
            .unique()
            .tolist()
        )
    else:
        isrc_list = song_df["isrc"].dropna().unique().tolist()

    if args.max_isrc:
        isrc_list = isrc_list[: args.max_isrc]

    fetch_wikidata_by_isrc(
        isrc_list,
        cache_path=args.cache_path,
        batch_size=args.batch_size,
        request_sleep=args.request_sleep,
        max_retries=args.max_retries,
        timeout=args.timeout,
        user_agent=args.user_agent,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
