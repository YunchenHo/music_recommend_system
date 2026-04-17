import argparse
from pathlib import Path
from pipeline.config import Paths
from src.data.download import download_and_extract
import os


def run(
    zip_path: Path,
    out_dir: Path,
    gdrive_id: str | None,
    force: bool,
    force_download: bool = False,
) -> None:
    download_and_extract(
        zip_path, out_dir, gdrive_id, force, force_download=force_download
    )


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 00: download/unzip dataset")
    parser.add_argument("--zip-path", type=Path, default=paths.root / "datasets.zip")
    parser.add_argument("--out-dir", type=Path, default=paths.raw)
    parser.add_argument("--gdrive-id", type=str, default=os.environ.get("GDRIVE_ID"))
    parser.add_argument("--force", action="store_true", help="force re-extract")
    parser.add_argument(
        "--force-download", action="store_true", help="force re-download zip"
    )
    args = parser.parse_args()

    run(
        args.zip_path,
        args.out_dir,
        args.gdrive_id,
        args.force,
        force_download=args.force_download,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
