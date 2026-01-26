from pathlib import Path

import gdown

DEFAULT_FILES = {
    "artist_table.csv": "13-N6bK8RSACVQmqbwEyrGqZZvCdjQqry",
    "song_merge.csv": "1QD_UZZfLf8HCFQ-T6AgEg21O0zC5jsHe",
    "wikidata_isrc_matched_en_by_isrc.csv": "1XaLe-HmxuUaA0leKd7tT-i7h_b-mugeH",
}


def download_external_files(
    dest_dir: Path,
    files: dict[str, str] | None = None,
    skip_existing: bool = True,
) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    files = files or DEFAULT_FILES

    for filename, file_id in files.items():
        out_path = dest_dir / filename
        if skip_existing and out_path.exists():
            print(f"[external] Skip existing: {out_path}")
            continue
        url = f"https://drive.google.com/uc?id={file_id}"
        print(f"[external] Downloading {filename}...")
        gdown.download(url, str(out_path), quiet=False, fuzzy=True)
