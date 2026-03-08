import argparse
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
    raw_dir: Path | None = None,
) -> None:
    raw_dir = raw_dir or songs_path.parent
    songs_path = resolve_input_path(songs_path, raw_dir, "songs.csv")
    song_extra_path = resolve_input_path(song_extra_path, raw_dir, "song_extra_info.csv")
    songs = load_csv(songs_path)
    song_extra = load_csv(song_extra_path)

    song_merge, song_encoder = preprocess_songs(songs, song_extra)

    save_df(song_merge, out_path)
    encoder_path.parent.mkdir(parents=True, exist_ok=True)
    with open(encoder_path, "wb") as f:
        pickle.dump(song_encoder, f)

    print(f"[stage_02] Saved song merge to {out_path}")
    print(f"[stage_02] Saved song encoder to {encoder_path}")


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
    args = parser.parse_args()

    run(args.songs_path, args.song_extra_path, args.out_path, args.encoder_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
