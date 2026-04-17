import argparse
import csv
from pathlib import Path
import pickle

from pipeline.config import Paths
from src.io import load_csv, save_df
from src.preprocess.songs import preprocess_songs
from src.utils import resolve_input_path


def run(
    songs_path: Path,
    song_extra_path: Path,
    out_path: Path,
    encoder_path: Path,
    artist_id_map_path: Path,
    song_for_db_path: Path,
    raw_dir: Path | None = None,
) -> None:
    raw_dir = raw_dir or songs_path.parent
    songs_path = resolve_input_path(songs_path, raw_dir, "songs.csv")
    song_extra_path = resolve_input_path(song_extra_path, raw_dir, "song_extra_info.csv")
    songs = load_csv(songs_path)
    song_extra = load_csv(song_extra_path)

    song_merge, song_encoder, artist_id_map = preprocess_songs(songs, song_extra)

    save_df(song_merge, out_path)
    encoder_path.parent.mkdir(parents=True, exist_ok=True)
    with open(encoder_path, "wb") as f:
        pickle.dump(song_encoder, f)

    # --- Save artist_id_map.csv ---
    # Clean for MySQL LOAD DATA compatibility:
    #   - artist_name containing newlines (CSV parse errors) → "unknown"
    #   - double quotes → single quotes (preserve meaning, avoid LOAD DATA parse errors)
    artist_id_map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(artist_id_map_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["artist_id", "artist_name"])
        for name, aid in sorted(artist_id_map.items(), key=lambda x: x[1]):
            clean_name = "unknown" if "\n" in name else name.replace('"', "'")
            writer.writerow([aid, clean_name])

    # --- Save song_for_db.csv ---
    song_for_db = song_merge[["song_id_new", "name", "artist_id", "artist_name", "language"]].rename(
        columns={"song_id_new": "song_id", "name": "song_title"}
    ).copy()
    # Clean for MySQL LOAD DATA compatibility:
    #   - artist_name containing newlines → "unknown"
    #   - double quotes in artist_name → single quotes
    #   - newlines in song_title → spaces (garbage from raw CSV parse errors)
    #   - double quotes in song_title → single quotes
    song_for_db["artist_name"] = song_for_db["artist_name"].where(
        ~song_for_db["artist_name"].str.contains("\n", na=False), "unknown"
    )
    song_for_db["artist_name"] = song_for_db["artist_name"].str.replace('"', "'", regex=False)
    song_for_db["song_title"] = song_for_db["song_title"].str.replace("\n", " ", regex=False)
    song_for_db["song_title"] = song_for_db["song_title"].str.replace('"', "'", regex=False)
    song_for_db.to_csv(song_for_db_path, index=False, encoding="utf-8")

    print(f"[stage_02] Saved song merge to {out_path}")
    print(f"[stage_02] Saved song encoder to {encoder_path}")
    print(f"[stage_02] Saved artist_id_map to {artist_id_map_path} ({len(artist_id_map)} artists)")
    print(f"[stage_02] Saved song_for_db to {song_for_db_path} ({len(song_for_db)} songs)")


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 02: preprocess songs + song_extra")
    parser.add_argument("--songs-path", type=Path, default=paths.raw / "songs.csv")
    parser.add_argument(
        "--song-extra-path", type=Path, default=paths.raw / "song_extra_info.csv"
    )
    parser.add_argument(
        "--out-path", type=Path, default=paths.interim / "song_merge.parquet"
    )
    parser.add_argument(
        "--encoder-path", type=Path, default=paths.artifacts / "song_encoder.pkl"
    )
    parser.add_argument(
        "--artist-id-map-path", type=Path, default=paths.artifacts / "artist_id_map.csv"
    )
    parser.add_argument(
        "--song-for-db-path", type=Path, default=paths.artifacts / "song_for_db.csv"
    )
    args = parser.parse_args()

    run(
        args.songs_path,
        args.song_extra_path,
        args.out_path,
        args.encoder_path,
        args.artist_id_map_path,
        args.song_for_db_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
