from pathlib import Path
import zipfile

EXPECTED_RAW_FILES = [
    "train.csv",
    "members.csv",
    "songs.csv",
    "song_extra_info.csv",
]

import gdown


def download_from_gdrive(gdrive_id: str, out_path: Path) -> None:
    url = f"https://drive.google.com/uc?id={gdrive_id}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdown.download(url, str(out_path), quiet=False)


def extract_zip(zip_path: Path, out_dir: Path, force: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not force and any(out_dir.iterdir()):
        print(f"[stage_00] Skip unzip: {out_dir} already has files.")
        return
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)
    print(f"[stage_00] Extracted to {out_dir}")


def _raw_dir_looks_invalid(out_dir: Path, min_total_bytes: int) -> bool:
    if not out_dir.exists():
        return True
    files = list(out_dir.glob("*"))
    if not files:
        return True
    total_bytes = sum(p.stat().st_size for p in files if p.is_file())
    if total_bytes < min_total_bytes:
        return True
    names = {p.name for p in files}
    missing = [name for name in EXPECTED_RAW_FILES if name not in names]
    return len(missing) > 0


def download_and_extract(
    zip_path: Path,
    out_dir: Path,
    gdrive_id: str | None,
    force: bool,
    force_download: bool = False,
    min_zip_bytes: int = 1_000_000,
    min_raw_bytes: int = 10_000_000,
) -> None:
    if zip_path.exists() and gdrive_id and not force_download:
        size = zip_path.stat().st_size
        if size < min_zip_bytes:
            print(
                f"[stage_00] Warning: {zip_path} is only {size} bytes. "
                "If this is not the real dataset, rerun with --force-download."
            )

    if (not zip_path.exists()) or (gdrive_id and force_download):
        if not gdrive_id:
            raise FileNotFoundError(
                f"Zip not found at {zip_path}. Provide --gdrive-id or place the zip file."
            )
        print(f"[stage_00] Downloading dataset zip to {zip_path}...")
        download_from_gdrive(gdrive_id, zip_path)

    if force_download:
        force = True
    if not force and _raw_dir_looks_invalid(out_dir, min_raw_bytes):
        print("[stage_00] Raw data looks invalid; forcing re-extract.")
        force = True

    extract_zip(zip_path, out_dir, force=force)
