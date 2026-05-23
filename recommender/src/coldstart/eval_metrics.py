"""Shared top-K metric computation for the cold-start pipeline.

All four models (LightFM-hybrid / LightFM-pureCF / ItemKNN / Popularity)
produce per-user top-K predictions and feed them through this single helper
to get a comparable metrics row. Output format matches `stage_16` long format:
`Date, Model, K, Recall, Precision, NDCG, Users_evaluated, Notes`.

Recall@K and NDCG@K are computed per-user then averaged. Multi-truth aware
(each user can have many ground-truth items, unlike the LOO eval in
`evaluate_lightfm` which only checks the first one).
"""

from __future__ import annotations

import math
from datetime import datetime

import pandas as pd


def compute_topk_metrics(
    user_topk: dict[int, list[int]],
    user_truth: dict[int, list[int]],
    *,
    eval_ks: tuple[int, ...] = (10, 20),
    model_name: str,
    notes: str = "",
    date: str | None = None,
) -> pd.DataFrame:
    """Compute per-user Recall@K / Precision@K / NDCG@K, averaged over users.

    Args:
        user_topk: {user_id: [item_id, ...]} — predictions ordered by score desc,
            length ≥ max(eval_ks).
        user_truth: {user_id: [item_id, ...]} — ground-truth held-out positives.
            Users with empty truth are skipped.
        eval_ks: K values to evaluate
        model_name: tag for the `Model` column
        notes: free-form note column (e.g. hyperparams, split id)
        date: ISO timestamp; defaults to now

    Returns:
        DataFrame with one row per K and columns:
        Date, Model, K, Recall, Precision, NDCG, Users_evaluated, Notes
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    max_k = max(eval_ks)

    sums = {k: {"recall": 0.0, "precision": 0.0, "ndcg": 0.0} for k in eval_ks}
    n_eval = 0

    for uid, truth_items in user_truth.items():
        if not truth_items:
            continue
        topk = user_topk.get(uid)
        if topk is None:
            continue
        truth_set = set(truth_items)
        n_truth = len(truth_set)

        n_eval += 1
        for k in eval_ks:
            top_k = topk[:k]
            hits = sum(1 for item in top_k if item in truth_set)
            sums[k]["recall"] += hits / n_truth
            sums[k]["precision"] += hits / k

            dcg = 0.0
            for rank, item in enumerate(top_k):
                if item in truth_set:
                    dcg += 1.0 / math.log2(rank + 2)
            ideal_hits = min(n_truth, k)
            idcg = sum(1.0 / math.log2(r + 2) for r in range(ideal_hits))
            sums[k]["ndcg"] += (dcg / idcg) if idcg > 0 else 0.0

    rows = []
    for k in eval_ks:
        if n_eval == 0:
            recall = precision = ndcg = 0.0
        else:
            recall = sums[k]["recall"] / n_eval
            precision = sums[k]["precision"] / n_eval
            ndcg = sums[k]["ndcg"] / n_eval
        rows.append({
            "Date": date,
            "Model": model_name,
            "K": k,
            "Recall": round(recall, 5),
            "Precision": round(precision, 5),
            "NDCG": round(ndcg, 5),
            "Users_evaluated": n_eval,
            "Notes": notes,
        })

    return pd.DataFrame(rows)


def append_metrics(df_new: pd.DataFrame, out_path) -> None:
    """Append metrics rows to a CSV (utf-8-sig, creates parent dir if needed)."""
    from pathlib import Path
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        df_existing = pd.read_csv(out_path)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new
    df_combined.to_csv(out_path, index=False, encoding="utf-8-sig")
