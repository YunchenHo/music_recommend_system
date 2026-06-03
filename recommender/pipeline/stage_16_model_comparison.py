import argparse
from pathlib import Path

import pandas as pd

from pipeline.config import Paths


def _load_long_metrics(path: Path) -> pd.DataFrame | None:
    """Load a metrics CSV in long format (Model, K, Recall, Precision, NDCG).

    Also keeps Date/Notes columns when present (e.g. lightfm_metrics.csv) so the
    aggregated comparison can distinguish multiple runs of the same model.
    Returns None if file does not exist.
    """
    if not path.exists():
        print(f"[compare] skip (missing): {path}")
        return None
    df = pd.read_csv(path)
    keep = [
        c for c in ["Date", "Model", "K", "Recall", "Precision", "NDCG", "Notes"]
        if c in df.columns
    ]
    return df[keep].copy()


def _load_itemknn_wide(path: Path) -> pd.DataFrame | None:
    """itemknn_grid_metrics.csv is wide (Recall@10, Precision@10, NDCG@10, @20...).

    Picks the row with highest NDCG@20 (best config), then melts to long.
    """
    if not path.exists():
        print(f"[compare] skip (missing): {path}")
        return None
    df = pd.read_csv(path)
    if "NDCG@20" in df.columns:
        best = df.sort_values("NDCG@20", ascending=False).head(1).iloc[0]
    else:
        best = df.head(1).iloc[0]

    rows = []
    for k in (10, 20):
        rows.append(
            {
                "Model": best.get("Model", "ItemKNN"),
                "K": k,
                "Recall": best.get(f"Recall@{k}"),
                "Precision": best.get(f"Precision@{k}"),
                "NDCG": best.get(f"NDCG@{k}"),
            }
        )
    return pd.DataFrame(rows)


def _load_lightfm_greedy(path: Path) -> pd.DataFrame | None:
    """lightfm_greedy_metrics.csv (stage_17 coordinate-descent search).

    Only the FINAL chosen config evaluated on the held-out TEST set is comparable
    across models — that is the selection-bias-free estimate (the val rows were
    used to pick the config, so they are optimistically biased). Keeps one row per
    (variant, K) from the most recent run, with the chosen config summarized in Notes.
    """
    if not path.exists():
        print(f"[compare] skip (missing): {path}")
        return None
    df = pd.read_csv(path)
    needed = {"phase", "eval_on", "Model", "K", "Recall", "Precision", "NDCG"}
    if not needed.issubset(df.columns):
        print(f"[compare] skip (unexpected schema): {path}")
        return None

    fin = df[(df["phase"] == "final") & (df["eval_on"] == "test")].copy()
    if fin.empty:
        print(f"[compare] skip (no final/test rows yet): {path}")
        return None

    # Keep only the latest run per model (variant).
    if "Date" in fin.columns:
        fin["Date"] = fin["Date"].astype(str)
        latest = fin.groupby("Model")["Date"].transform("max")
        fin = fin[fin["Date"] == latest]

    cfg_cols = [
        "loss", "no_components", "learning_rate",
        "max_sampled", "epochs", "item_alpha", "user_alpha",
    ]
    rows = []
    for _, r in fin.iterrows():
        cfg = ", ".join(f"{c}={r[c]}" for c in cfg_cols if c in fin.columns)
        rows.append(
            {
                "Date": r.get("Date"),
                "Model": r.get("Model"),
                "K": int(r["K"]),
                "Recall": r["Recall"],
                "Precision": r["Precision"],
                "NDCG": r["NDCG"],
                "Notes": f"greedy best (test): {cfg}",
            }
        )
    return pd.DataFrame(rows)


def _load_popularity(path: Path) -> pd.DataFrame | None:
    """popularity_baseline.csv has columns Model, Recall@K, K.

    Map to long format and leave Precision/NDCG as NaN.
    """
    if not path.exists():
        print(f"[compare] skip (missing): {path}")
        return None
    df = pd.read_csv(path)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "Model": r.get("Model", "Popularity"),
                "K": int(r["K"]) if "K" in r else None,
                "Recall": r.get("Recall@K", r.get("Recall")),
                "Precision": None,
                "NDCG": None,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 16: aggregate model comparison")
    parser.add_argument("--itemknn-path", type=Path,
                        default=paths.reports / "itemknn_grid_metrics.csv")
    parser.add_argument("--mf-path", type=Path,
                        default=paths.reports / "mf_faiss_metrics.csv")
    parser.add_argument("--popularity-path", type=Path,
                        default=paths.reports / "popularity_baseline.csv")
    parser.add_argument("--lightfm-path", type=Path,
                        default=paths.reports / "lightfm_metrics.csv")
    parser.add_argument("--lightfm-greedy-path", type=Path,
                        default=paths.reports / "lightfm_greedy_metrics.csv")
    parser.add_argument("--out-path", type=Path,
                        default=paths.reports / "model_comparison.csv")
    args = parser.parse_args()

    frames: list[pd.DataFrame] = []

    itemknn_df = _load_itemknn_wide(args.itemknn_path)
    if itemknn_df is not None:
        frames.append(itemknn_df)

    mf_df = _load_long_metrics(args.mf_path)
    if mf_df is not None:
        frames.append(mf_df)

    pop_df = _load_popularity(args.popularity_path)
    if pop_df is not None:
        frames.append(pop_df)

    lightfm_df = _load_long_metrics(args.lightfm_path)
    if lightfm_df is not None:
        frames.append(lightfm_df)

    greedy_df = _load_lightfm_greedy(args.lightfm_greedy_path)
    if greedy_df is not None:
        frames.append(greedy_df)

    if not frames:
        raise SystemExit("[compare] no metrics files found; nothing to aggregate.")

    combined = pd.concat(frames, ignore_index=True)
    column_order = [
        "Date", "Model", "K", "Recall", "Precision", "NDCG", "Notes",
    ]
    combined = combined[[c for c in column_order if c in combined.columns]]
    combined = combined.sort_values(["K", "NDCG", "Recall"],
                                    ascending=[True, False, False],
                                    na_position="last").reset_index(drop=True)

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.out_path, index=False, encoding="utf-8-sig")
    print("Saved comparison:", args.out_path)
    print()
    try:
        print(combined.to_markdown(index=False, floatfmt=".4f"))
    except ImportError:
        print(combined.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
