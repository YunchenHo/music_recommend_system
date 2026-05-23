"""Stage cs00 — produce 4 cold-start splits:
- A_N1, A_N3, A_N5 (Scenario A with N=1, 3, 5 seed positives per user)
- C (Scenario C, n_test_users held-out users)

Outputs to `data/processed/cs_*_{train,test}.parquet` plus json id maps in
`data/processed/cs_*_useridx.json` / `_itemidx.json`. For Scenario C also
writes `cs_C_test_users.json` (raw msno_ids of held-out users).

Each split is independent — re-run with `--scenarios A_N1` to refresh just one.

Run:
    PYTHONPATH=. uv run python pipeline/stage_cs00_make_splits.py
    PYTHONPATH=. uv run python pipeline/stage_cs00_make_splits.py --smoke
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.config import Paths
from src.coldstart.split import make_split_a, make_split_c
from src.io import load_table


ALL_SCENARIOS = ["A_N1", "A_N3", "A_N5", "C"]


def _save_mapping(mapping: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON keys must be str; mapping is {int_or_str: int}
    serializable = {str(k): int(v) for k, v in mapping.items()}
    path.write_text(json.dumps(serializable, ensure_ascii=False))


def _save_list(items: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([str(x) for x in items], ensure_ascii=False))


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Cold-start split generator (stage cs00)")
    parser.add_argument(
        "--train-path",
        type=Path,
        default=paths.processed / "train_encoded.parquet",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=paths.processed,
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=ALL_SCENARIOS,
        choices=ALL_SCENARIOS,
        help="Which splits to generate (default: all 4)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--n-test-users",
        type=int,
        default=1000,
        help="Scenario C: number of users to hold out",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke test: cap users + n_test_users for fast iteration",
    )
    args = parser.parse_args()

    max_users = 500 if args.smoke else None
    n_test_users = 50 if args.smoke else args.n_test_users

    print(f"[stage_cs00] loading {args.train_path}")
    train_encoded = load_table(args.train_path)
    print(f"  total rows: {len(train_encoded):,}")

    for scenario in args.scenarios:
        print(f"\n[stage_cs00] scenario={scenario}")
        out_train = args.out_dir / f"cs_{scenario}_train.parquet"
        out_test = args.out_dir / f"cs_{scenario}_test.parquet"
        out_userix = args.out_dir / f"cs_{scenario}_useridx.json"
        out_itemix = args.out_dir / f"cs_{scenario}_itemidx.json"

        if scenario.startswith("A_N"):
            n_seed = int(scenario.split("N")[1])
            df_train, df_test, useridx, itemidx = make_split_a(
                train_encoded,
                n_seed=n_seed,
                seed=args.seed,
                max_users=max_users,
            )
        elif scenario == "C":
            df_train, df_test, useridx, itemidx, test_user_ids = make_split_c(
                train_encoded,
                n_test_users=n_test_users,
                seed=args.seed,
            )
            _save_list(test_user_ids, args.out_dir / "cs_C_test_users.json")
            print(f"  test users held out: {len(test_user_ids)}")
        else:
            raise ValueError(f"unknown scenario {scenario}")

        df_train.to_parquet(out_train, index=False)
        df_test.to_parquet(out_test, index=False)
        _save_mapping(useridx, out_userix)
        _save_mapping(itemidx, out_itemix)

        n_users_train = df_train["msno_idx"].nunique() if "msno_idx" in df_train else 0
        print(f"  train: {len(df_train):,} rows, {n_users_train} users → {out_train.name}")
        print(f"  test:  {len(df_test):,} rows → {out_test.name}")
        print(f"  useridx: {len(useridx)} entries, itemidx: {len(itemidx)} entries")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
