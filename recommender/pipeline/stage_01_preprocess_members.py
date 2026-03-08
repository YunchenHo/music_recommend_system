import argparse
from pathlib import Path
import pickle

from pipeline.config import Paths
from src.io import load_csv, save_df
from src.preprocess.members import preprocess_members
from src.utils import resolve_input_path


def run(
    members_path: Path, out_path: Path, encoder_path: Path, raw_dir: Path | None = None
) -> None:
    raw_dir = raw_dir or members_path.parent
    members_path = resolve_input_path(members_path, raw_dir, "members.csv")
    members = load_csv(members_path)
    processed, msno_encoder = preprocess_members(members)

    save_df(processed, out_path)
    encoder_path.parent.mkdir(parents=True, exist_ok=True)
    with open(encoder_path, "wb") as f:
        pickle.dump(msno_encoder, f)

    print(f"[stage_01] Saved members to {out_path}")
    print(f"[stage_01] Saved msno encoder to {encoder_path}")


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 01: preprocess members")
    parser.add_argument("--members-path", type=Path, default=paths.raw / "members.csv")
    parser.add_argument(
        "--out-path", type=Path, default=paths.processed / "complete_members.parquet"
    )
    parser.add_argument(
        "--encoder-path", type=Path, default=paths.artifacts / "msno_encoder.pkl"
    )
    args = parser.parse_args()

    run(args.members_path, args.out_path, args.encoder_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
