"""Stage cs05 — aggregate cold-start metrics from all 4 models into one CSV.

Reads:
- `reports/cs_lightfm_hybrid_metrics.csv`
- `reports/cs_lightfm_purecf_metrics.csv`
- `reports/cs_itemknn_metrics.csv`
- `reports/cs_popularity_metrics.csv`

Outputs:
- `reports/cs_model_comparison.csv` (sorted by split, K, NDCG desc)

Schema across all input CSVs matches stage_16's long format:
`Date, Model, K, Recall, Precision, NDCG, Users_evaluated, Notes`.
Notes column carries `split=A_N1` etc. — this stage parses split from Notes
to enable per-split / per-K pivots.

Run:
    PYTHONPATH=. uv run python pipeline/stage_cs05_compare.py
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from pipeline.config import Paths


SPLIT_PATTERN = re.compile(r"split=([A-Za-z0-9_]+)")


def _extract_split(notes: str) -> str:
    if not isinstance(notes, str):
        return ""
    m = SPLIT_PATTERN.search(notes)
    return m.group(1) if m else ""


def _load_metrics(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    # Keep latest row per (Model, K, split) — earlier runs may have stale results
    df["Split"] = df["Notes"].apply(_extract_split)
    df = df.sort_values("Date").drop_duplicates(
        subset=["Model", "K", "Split"], keep="last"
    )
    return df


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Cold-start model comparison (stage cs05)")
    parser.add_argument("--reports-dir", type=Path, default=paths.reports)
    parser.add_argument(
        "--out-path", type=Path,
        default=paths.reports / "cs_model_comparison.csv",
    )
    args = parser.parse_args()

    sources = [
        ("LightFM-hybrid", args.reports_dir / "cs_lightfm_hybrid_metrics.csv"),
        ("LightFM-pureCF", args.reports_dir / "cs_lightfm_purecf_metrics.csv"),
        ("ItemKNN", args.reports_dir / "cs_itemknn_metrics.csv"),
        ("Popularity", args.reports_dir / "cs_popularity_metrics.csv"),
    ]

    frames = []
    for label, p in sources:
        df = _load_metrics(p)
        if df.empty:
            print(f"  [skip] {label}: {p.name} not found or empty")
            continue
        print(f"  loaded {label}: {len(df)} rows from {p.name}")
        frames.append(df)

    if not frames:
        print("[stage_cs05] no metrics to compare")
        return 1

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(
        ["Split", "K", "NDCG", "Recall"],
        ascending=[True, True, False, False],
    )

    cols = ["Date", "Split", "Model", "K", "Recall", "Precision", "NDCG", "Users_evaluated", "Notes"]
    cols = [c for c in cols if c in combined.columns]
    combined = combined[cols]

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.out_path, index=False, encoding="utf-8-sig")
    print(f"\n[stage_cs05] wrote {len(combined)} rows → {args.out_path}")

    print("\n--- per-split summary (K=20) ---")
    pivot = combined[combined["K"] == 20].pivot_table(
        index="Split", columns="Model", values="NDCG", aggfunc="first"
    )
    if not pivot.empty:
        print(pivot.round(4).to_string())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
