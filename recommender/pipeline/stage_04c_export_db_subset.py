"""
Stage 04c: Export DB subset
=============================
從 train.csv 中出現過的歌曲，篩選出精簡版的 song_for_db_small.csv 和 artist_id_map_small.csv。

用途：只把訓練集中實際出現的歌曲和藝術家塞進資料庫，
      而非全部 230 萬首（完整版太大，MySQL LOAD DATA 容易掛）。

執行方式（在 recommender 容器內）：
    python -m pipeline.stage_04c_export_db_subset
"""

import argparse
import gc
import pickle
from pathlib import Path

import pandas as pd

from pipeline.config import Paths


def collect_train_song_hashes(train_path: Path, chunksize: int = 500_000) -> set[str]:
    """分批讀取 train.csv，收集所有不重複的 song_id (hash string)。"""
    song_hashes: set[str] = set()
    for chunk in pd.read_csv(train_path, usecols=["song_id"], chunksize=chunksize):
        song_hashes.update(chunk["song_id"].unique())
        del chunk
        gc.collect()
    return song_hashes


def run(
    train_path: Path,
    song_encoder_path: Path,
    song_for_db_path: Path,
    artist_id_map_path: Path,
    out_song_path: Path,
    out_artist_path: Path,
) -> None:
    # 1. 收集 train.csv 中所有不重複的 song_id (hash string)
    print(f"[stage_04c] Reading train.csv: {train_path}")
    song_hashes = collect_train_song_hashes(train_path)
    print(f"[stage_04c] Unique song hashes in train.csv: {len(song_hashes):,}")

    # 2. 用 song_encoder 把 hash → integer
    print(f"[stage_04c] Loading song encoder: {song_encoder_path}")
    with open(song_encoder_path, "rb") as f:
        song_encoder = pickle.load(f)

    known_hashes = set(song_encoder.classes_)
    valid_hashes = song_hashes & known_hashes
    dropped = len(song_hashes) - len(valid_hashes)
    if dropped > 0:
        print(f"[stage_04c] Dropped {dropped:,} song hashes not in encoder")

    valid_hashes_list = sorted(valid_hashes)
    song_id_ints = set(song_encoder.transform(valid_hashes_list).tolist())
    print(f"[stage_04c] Valid song_id integers: {len(song_id_ints):,}")

    # 3. 從完整 song_for_db.csv 篩選
    print(f"[stage_04c] Filtering song_for_db.csv: {song_for_db_path}")
    song_df = pd.read_csv(song_for_db_path)
    original_song_count = len(song_df)
    song_df = song_df[song_df["song_id"].isin(song_id_ints)]
    print(
        f"[stage_04c] Songs: {original_song_count:,} → {len(song_df):,} "
        f"(removed {original_song_count - len(song_df):,})"
    )

    # 4. 從篩選後的歌曲取出不重複 artist_id，篩選 artist_id_map.csv
    used_artist_ids = set(song_df["artist_id"].unique())
    print(f"[stage_04c] Filtering artist_id_map.csv: {artist_id_map_path}")
    artist_df = pd.read_csv(artist_id_map_path)
    original_artist_count = len(artist_df)
    artist_df = artist_df[artist_df["artist_id"].isin(used_artist_ids)]
    print(
        f"[stage_04c] Artists: {original_artist_count:,} → {len(artist_df):,} "
        f"(removed {original_artist_count - len(artist_df):,})"
    )

    # 5. 輸出精簡版 CSV
    out_song_path.parent.mkdir(parents=True, exist_ok=True)
    song_df.to_csv(out_song_path, index=False, encoding="utf-8")
    print(f"[stage_04c] Saved {out_song_path} ({len(song_df):,} songs)")

    out_artist_path.parent.mkdir(parents=True, exist_ok=True)
    artist_df.to_csv(out_artist_path, index=False, encoding="utf-8")
    print(f"[stage_04c] Saved {out_artist_path} ({len(artist_df):,} artists)")


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(
        description="Stage 04c: export song/artist subset for DB import"
    )
    parser.add_argument(
        "--train-path",
        type=Path,
        default=paths.raw / "kkbox_datasets" / "train.csv",
    )
    parser.add_argument(
        "--song-encoder-path",
        type=Path,
        default=paths.artifacts / "song_encoder.pkl",
    )
    parser.add_argument(
        "--song-for-db-path",
        type=Path,
        default=paths.artifacts / "song_for_db.csv",
    )
    parser.add_argument(
        "--artist-id-map-path",
        type=Path,
        default=paths.artifacts / "artist_id_map.csv",
    )
    parser.add_argument(
        "--out-song-path",
        type=Path,
        default=paths.artifacts / "song_for_db_small.csv",
    )
    parser.add_argument(
        "--out-artist-path",
        type=Path,
        default=paths.artifacts / "artist_id_map_small.csv",
    )
    args = parser.parse_args()

    run(
        train_path=args.train_path,
        song_encoder_path=args.song_encoder_path,
        song_for_db_path=args.song_for_db_path,
        artist_id_map_path=args.artist_id_map_path,
        out_song_path=args.out_song_path,
        out_artist_path=args.out_artist_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
