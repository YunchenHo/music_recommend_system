import argparse
from pathlib import Path

from pipeline.config import Paths
from src.data.wikidata import prepare_wikidata_matched_csv


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 07: prepare Wikidata CSVs")
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=paths.data / "external" / "wikidata_isrc_cache.parquet",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=paths.data / "external"
    )
    parser.add_argument("--lang", type=str, default="en")
    parser.add_argument("--no-features", action="store_true")
    args = parser.parse_args()

    prepare_wikidata_matched_csv(
        cache_path=args.cache_path,
        out_dir=args.out_dir,
        lang=args.lang,
        add_features=not args.no_features,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
