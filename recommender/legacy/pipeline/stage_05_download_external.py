import argparse
from pathlib import Path

from pipeline.config import Paths
from src.data.external import DEFAULT_FILES, download_external_files


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 05: download external tables")
    parser.add_argument(
        "--dest-dir", type=Path, default=paths.data / "external"
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="comma-separated filenames to download (e.g., artist_table.csv)",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="force re-download even if file exists",
    )
    args = parser.parse_args()

    files = DEFAULT_FILES
    if args.only:
        names = [x.strip() for x in args.only.split(",") if x.strip()]
        files = {k: v for k, v in DEFAULT_FILES.items() if k in names}

    download_external_files(args.dest_dir, files=files, skip_existing=not args.no_skip_existing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
