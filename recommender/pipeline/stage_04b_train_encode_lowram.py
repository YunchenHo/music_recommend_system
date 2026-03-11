import argparse
from pathlib import Path

from pipeline.config import Paths
from src.io import save_df
from src.preprocess.train import load_and_encode_train_for_knn


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 04b: low-RAM train encoding")
    parser.add_argument("--train-path", type=Path, default=paths.raw / "train.csv")
    parser.add_argument(
        "--msno-encoder-path", type=Path, default=paths.artifacts / "msno_encoder.pkl"
    )
    parser.add_argument(
        "--song-encoder-path", type=Path, default=paths.artifacts / "song_encoder.pkl"
    )
    parser.add_argument(
        "--out-path", type=Path, default=paths.processed / "train_encoded.parquet"
    )
    parser.add_argument("--chunksize", type=int, default=2_000_000)
    args = parser.parse_args()

    train_encoded = load_and_encode_train_for_knn(
        str(args.train_path),
        str(args.msno_encoder_path),
        str(args.song_encoder_path),
        chunksize=args.chunksize,
    )

    save_df(train_encoded, args.out_path)
    print(f"[stage_04b] Saved train_encoded to {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
