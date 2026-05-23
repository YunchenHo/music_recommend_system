"""Plot cold-start research results from `reports/cs_model_comparison.csv`.

Produces:
- cs_ndcg_by_split.png   — Grouped bar chart NDCG@20 / split × model
- cs_recall_by_split.png — Same for Recall@20
- cs_ablation.png        — LightFM-hybrid vs pureCF gap across A_N1/A_N3/A_N5 (NDCG@20)

Saves to `reports/cs_figures/`.

Run:
    PYTHONPATH=. uv run python scripts/plot_coldstart.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def _setup_cjk_font() -> None:
    """Pick whichever CJK-capable font is installed on this machine."""
    candidates = [
        "PingFang TC",        # macOS Big Sur+
        "Heiti TC",           # older macOS
        "Hiragino Sans GB",   # macOS bundled
        "Arial Unicode MS",   # macOS bundled
        "Noto Sans CJK TC",   # Linux / cross-platform
        "Microsoft JhengHei", # Windows
    ]
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return
    # fall back silently if none found


MODEL_ORDER = ["Popularity", "ItemKNN", "LightFM-pureCF", "LightFM-hybrid"]
MODEL_COLORS = {
    "Popularity":     "#9aa0a6",  # neutral gray (baseline)
    "ItemKNN":        "#d97757",  # warm orange (struggling)
    "LightFM-pureCF": "#9bc8a3",  # light green
    "LightFM-hybrid": "#2c6e3f",  # dark green (the protagonist)
}
SPLIT_ORDER = ["A_N1", "A_N3", "A_N5", "C"]
SPLIT_LABELS = {
    "A_N1": "A (N=1 seed)",
    "A_N3": "A (N=3 seeds)",
    "A_N5": "A (N=5 seeds)",
    "C": "C (cold users)",
}


def _load_latest(path: Path, k: int) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["K"] == k].copy()
    # Latest row per (Split, Model)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("Date").drop_duplicates(subset=["Split", "Model"], keep="last")
    return df


def _bar_by_split(df: pd.DataFrame, metric: str, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    splits = [s for s in SPLIT_ORDER if s in df["Split"].unique()]
    models = [m for m in MODEL_ORDER if m in df["Model"].unique()]

    x = np.arange(len(splits))
    width = 0.18
    offsets = (np.arange(len(models)) - (len(models) - 1) / 2) * width

    for i, model in enumerate(models):
        sub = df[df["Model"] == model].set_index("Split")
        ys = [sub.loc[s, metric] if s in sub.index else np.nan for s in splits]
        ax.bar(
            x + offsets[i], ys, width,
            label=model, color=MODEL_COLORS.get(model, "#888"),
        )
        for xi, y in zip(x + offsets[i], ys):
            if not np.isnan(y):
                ax.text(xi, y + 0.005, f"{y:.3f}", ha="center", va="bottom", fontsize=7)

    # Annotate structurally-missing cells
    for i, model in enumerate(models):
        sub = df[df["Model"] == model].set_index("Split")
        for j, s in enumerate(splits):
            if s not in sub.index:
                ax.text(
                    x[j] + offsets[i], 0.005, "N/A",
                    ha="center", va="bottom", fontsize=7, color="#999",
                    style="italic",
                )

    ax.set_xticks(x)
    ax.set_xticklabels([SPLIT_LABELS[s] for s in splits])
    ax.set_ylabel(metric)
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    sns.despine()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_path}")


def _ablation_plot(df: pd.DataFrame, k: int, out_path: Path) -> None:
    """Line chart: hybrid vs pureCF on NDCG@K across N=1,3,5 (Scenario A only)."""
    a_splits = ["A_N1", "A_N3", "A_N5"]
    ns = [1, 3, 5]
    sub = df[df["Split"].isin(a_splits)].set_index(["Split", "Model"])

    hybrid = [sub.loc[(s, "LightFM-hybrid"), "NDCG"] for s in a_splits]
    purecf = [sub.loc[(s, "LightFM-pureCF"), "NDCG"] for s in a_splits]
    gap = [h - p for h, p in zip(hybrid, purecf)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.4, 1]})

    ax1.plot(ns, hybrid, "o-", color=MODEL_COLORS["LightFM-hybrid"], label="LightFM-hybrid (with user features)", linewidth=2)
    ax1.plot(ns, purecf, "s-", color=MODEL_COLORS["LightFM-pureCF"], label="LightFM-pureCF (no features)", linewidth=2)
    for n, h, p in zip(ns, hybrid, purecf):
        ax1.text(n, h + 0.005, f"{h:.3f}", ha="center", va="bottom", fontsize=8)
        ax1.text(n, p - 0.015, f"{p:.3f}", ha="center", va="top", fontsize=8)
    ax1.set_xlabel("N (seed interactions per user)")
    ax1.set_ylabel(f"NDCG@{k}")
    ax1.set_xticks(ns)
    ax1.set_title(f"Ablation: user features 對 NDCG@{k} 的貢獻 (Scenario A)")
    ax1.legend(loc="lower right", fontsize=9, frameon=False)
    ax1.grid(linestyle=":", alpha=0.4)
    ax1.set_axisbelow(True)

    bar_color = ["#7caa8e" if g > 0 else "#d97757" for g in gap]
    ax2.bar(ns, gap, color=bar_color, width=0.6)
    for n, g in zip(ns, gap):
        ax2.text(n, g + 0.002 if g > 0 else g - 0.002,
                 f"+{g:.3f}" if g > 0 else f"{g:.3f}",
                 ha="center", va="bottom" if g > 0 else "top", fontsize=9)
    ax2.axhline(0, color="black", linewidth=0.5)
    ax2.set_xlabel("N (seed interactions per user)")
    ax2.set_ylabel(f"ΔNDCG@{k}  (hybrid − pureCF)")
    ax2.set_xticks(ns)
    ax2.set_title("user features 的淨增益")
    ax2.grid(axis="y", linestyle=":", alpha=0.4)
    ax2.set_axisbelow(True)

    sns.despine(fig=fig)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot cold-start comparison results")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reports" / "cs_model_comparison.csv",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reports" / "cs_figures",
    )
    parser.add_argument("--k", type=int, default=20, help="K for the main plots (default 20)")
    args = parser.parse_args()

    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    _setup_cjk_font()  # AFTER seaborn so it doesn't clobber the font setting
    print(f"  font.sans-serif: {matplotlib.rcParams['font.sans-serif']}")

    df = _load_latest(args.input, args.k)
    print(f"[plot_coldstart] loaded {len(df)} rows from {args.input.name} (K={args.k})")
    print(f"  splits: {sorted(df['Split'].unique())}")
    print(f"  models: {sorted(df['Model'].unique())}")

    _bar_by_split(
        df, "NDCG",
        f"冷啟動 NDCG@{args.k} —— 4 個模型在 4 個場景下的對比",
        args.out_dir / f"cs_ndcg_at_{args.k}_by_split.png",
    )
    _bar_by_split(
        df, "Recall",
        f"冷啟動 Recall@{args.k} —— 4 個模型在 4 個場景下的對比",
        args.out_dir / f"cs_recall_at_{args.k}_by_split.png",
    )
    _ablation_plot(df, args.k, args.out_dir / f"cs_ablation_ndcg_at_{args.k}.png")

    print(f"\n[plot_coldstart] all figures → {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
