import argparse
from pathlib import Path
from pipeline.config import Paths
import pickle

import pandas as pd

from src.io import load_table, save_df
from src.preprocess.train import (
    calculate_sparsity,
    encode_ids,
    encode_sources,
    filter_top_members,
)
from src.utils import resolve_input_path


def run(
    train_path: Path,
    complete_members_path: Path,
    out_path: Path,
    members_small_path: Path,
    msno_encoder_path: Path,
    song_encoder_path: Path,
    source_encoder_path: Path,
    top_k: int,
    min_membership_days: int,
    raw_dir: Path | None = None,
) -> None:
    raw_dir = raw_dir or train_path.parent
    train_path = resolve_input_path(train_path, raw_dir, "train.csv")
    train = pd.read_csv(train_path)

    train, source_encoders = encode_sources(train)
    train = encode_ids(train, msno_encoder_path, song_encoder_path)

    complete_members = load_table(complete_members_path)

    if top_k > 0:
        train, top_members = filter_top_members(
            train, complete_members, top_k=top_k, min_membership_days=min_membership_days
        )
        top_members[["msno_id", "membership_days"]].to_csv(
            members_small_path, index=False
        )
        print(f"[stage_04] Saved top members to {members_small_path}")

    save_df(train, out_path)
    with open(source_encoder_path, "wb") as f:
        pickle.dump(source_encoders, f)

    print(f"[stage_04] Saved train to {out_path}")
    print(f"[stage_04] Saved source encoders to {source_encoder_path}")
    calculate_sparsity(train)


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 04: preprocess train")
    parser.add_argument("--train-path", type=Path, default=paths.raw / "train.csv")
    parser.add_argument(
        "--complete-members-path",
        type=Path,
        default=paths.processed / "complete_members.parquet",
    )
    parser.add_argument(
        "--out-path", type=Path, default=paths.processed / "train_encoded.parquet"
    )
    parser.add_argument(
        "--members-small-path",
        type=Path,
        default=paths.processed / "complete_members_small.csv",
    )
    parser.add_argument(
        "--msno-encoder-path", type=Path, default=paths.artifacts / "msno_encoder.pkl"
    )
    parser.add_argument(
        "--song-encoder-path", type=Path, default=paths.artifacts / "song_encoder.pkl"
    )
    parser.add_argument(
        "--source-encoder-path",
        type=Path,
        default=paths.artifacts / "source_encoders.pkl",
    )
    parser.add_argument("--top-k", type=int, default=5000)
    parser.add_argument("--min-membership-days", type=int, default=30)

    args = parser.parse_args()

    run(
        train_path=args.train_path,
        complete_members_path=args.complete_members_path,
        out_path=args.out_path,
        members_small_path=args.members_small_path,
        msno_encoder_path=args.msno_encoder_path,
        song_encoder_path=args.song_encoder_path,
        source_encoder_path=args.source_encoder_path,
        top_k=args.top_k,
        min_membership_days=args.min_membership_days,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
