from __future__ import annotations

import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_itemknn_grid(metrics_df: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    df = metrics_df.copy()

    def parse_agg(model_str: str) -> str:
        m = re.search(r"ItemKNN\((.*?)\)", str(model_str))
        return m.group(1) if m else str(model_str)

    df["agg"] = df["Model"].apply(parse_agg)

    num_cols = [
        "Item_K",
        "sim_threshold",
        "Recall@10",
        "NDCG@10",
        "Recall@20",
        "NDCG@20",
    ]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Item_K", "sim_threshold", "Recall@10", "NDCG@10"]).copy()
    df = df.sort_values(["agg", "Item_K", "sim_threshold"]).reset_index(drop=True)

    def savefig(fname: str) -> None:
        path = out_dir / fname
        plt.savefig(path, dpi=170, bbox_inches="tight")
        plt.close()
        print("Saved:", path)

    ranked = df.sort_values(
        ["Recall@10", "NDCG@10", "Recall@20", "NDCG@20"], ascending=False
    ).reset_index(drop=True)
    ranked.to_csv(out_dir / "ranked_all_configs.csv", index=False, encoding="utf-8-sig")

    best_per_agg = (
        df.sort_values(["agg", "Recall@10", "NDCG@10"], ascending=[True, False, False])
        .groupby("agg", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )

    plt.figure()
    plt.bar(best_per_agg["agg"], best_per_agg["Recall@10"])
    plt.xticks(rotation=45, ha="right")
    plt.title("Best Recall@10 per aggregation")
    plt.ylabel("Recall@10")
    savefig("bar_best_recall10_per_agg.png")

    plt.figure()
    plt.bar(best_per_agg["agg"], best_per_agg["NDCG@10"])
    plt.xticks(rotation=45, ha="right")
    plt.title("Best NDCG@10 per aggregation")
    plt.ylabel("NDCG@10")
    savefig("bar_best_ndcg10_per_agg.png")

    metrics = ["Recall@10", "NDCG@10", "Recall@20", "NDCG@20"]
    for agg in sorted(df["agg"].unique()):
        sub = df[df["agg"] == agg].copy()
        if sub.empty:
            continue

        for metric in metrics:
            piv = sub.pivot_table(
                index="Item_K", columns="sim_threshold", values=metric, aggfunc="mean"
            )
            piv = piv.sort_index().sort_index(axis=1)

            arr = piv.to_numpy()
            plt.figure()
            im = plt.imshow(arr, aspect="auto", interpolation="nearest")
            plt.colorbar(im)
            plt.title(f"{metric} heatmap | agg={agg}")
            plt.xlabel("sim_threshold")
            plt.ylabel("Item_K")
            plt.xticks(
                list(range(piv.shape[1])), [f"{x:.2f}" for x in piv.columns.tolist()]
            )
            plt.yticks(list(range(piv.shape[0])), piv.index.tolist())
            savefig(f"heatmap_{metric.replace('@','at')}_agg_{agg}.png")

    for agg in sorted(df["agg"].unique()):
        sub = df[df["agg"] == agg].copy()
        if sub.empty:
            continue

        for metric in metrics:
            plt.figure()
            for sim_t in sorted(sub["sim_threshold"].unique()):
                sub2 = sub[sub["sim_threshold"] == sim_t].sort_values("Item_K")
                plt.plot(sub2["Item_K"], sub2[metric], marker="o", label=f"sim_t={sim_t:.2f}")
            plt.title(f"{metric} vs Item_K | agg={agg}")
            plt.xlabel("Item_K")
            plt.ylabel(metric)
            plt.legend()
            savefig(f"line_{metric.replace('@','at')}_vs_itemk_agg_{agg}.png")

    for sim_t in sorted(df["sim_threshold"].unique()):
        sub = df[df["sim_threshold"] == sim_t].copy()
        if sub.empty:
            continue

        for metric in metrics:
            plt.figure()
            for agg in sorted(sub["agg"].unique()):
                sub2 = sub[sub["agg"] == agg].sort_values("Item_K")
                plt.plot(sub2["Item_K"], sub2[metric], marker="o", label=agg)
            plt.title(f"{metric} vs Item_K | sim_threshold={sim_t:.2f}")
            plt.xlabel("Item_K")
            plt.ylabel(metric)
            plt.legend()
            savefig(f"compare_aggs_{metric.replace('@','at')}_simt_{sim_t:.2f}.png")

    for agg in sorted(df["agg"].unique()):
        sub = df[df["agg"] == agg].copy()
        if sub.empty:
            continue
        plt.figure()
        plt.scatter(sub["Recall@10"], sub["NDCG@10"])
        plt.title(f"Tradeoff scatter | agg={agg}")
        plt.xlabel("Recall@10")
        plt.ylabel("NDCG@10")
        savefig(f"scatter_recall10_vs_ndcg10_agg_{agg}.png")

    plt.figure()
    plt.scatter(df["Recall@10"], df["NDCG@10"])
    plt.title("Tradeoff scatter (all configs)")
    plt.xlabel("Recall@10")
    plt.ylabel("NDCG@10")
    savefig("scatter_recall10_vs_ndcg10_all.png")

    print("Plots saved to:", out_dir)
