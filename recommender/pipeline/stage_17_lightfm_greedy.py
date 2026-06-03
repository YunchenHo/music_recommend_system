"""Stage 17 — LightFM greedy (coordinate-descent) hyperparameter search.

Tunes one hyperparameter at a time (others fixed at the current best), in a
fixed order of decreasing expected impact. Uses a THREE-way split
(train/val/test): every search trial is scored on VALIDATION only, and the
chosen config is reported once on the untouched TEST set at the end. This keeps
the test set free of selection bias — the optimistic bias you would otherwise
get from picking the config that maximizes a metric on the same set you report.

Why greedy and not full grid: coordinate descent is additive (~28 trainings per
variant) instead of multiplicative (~15k). It finds a good local optimum, not a
guaranteed global one, and the result depends on the dimension order below.

Both LightFM variants are searched: hybrid (with user/item features) and pureCF
(no features), via prepare_lightfm_dataset(use_features=...).

LightFM is pure Python (no TensorFlow), so a full run is fine locally — run it
under tmux/nohup for the long full-data sweep.

Run (smoke):
    PYTHONPATH=. uv run python pipeline/stage_17_lightfm_greedy.py --variant both --smoke

Run (full, under tmux):
    PYTHONPATH=. uv run python pipeline/stage_17_lightfm_greedy.py --variant both \
        --num-threads 4 2>&1 | tee reports/lightfm_greedy_run.log
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline.config import Paths
from src.coldstart.eval_metrics import append_metrics
from src.io import load_table

# Coordinate-descent order: high-impact first, regularization last.
SEARCH_ORDER = [
    "loss",
    "no_components",
    "learning_rate",
    "max_sampled",
    "epochs",
    "item_alpha",
    "user_alpha",
]

# Hyperparameter keys -> the train_lightfm_model kwarg name (identical here, but
# kept explicit so the CSV column names and kwargs stay in sync).
CONFIG_COLUMNS = [
    "no_components",
    "loss",
    "learning_rate",
    "max_sampled",
    "epochs",
    "item_alpha",
    "user_alpha",
]


def _parse_int_list(value: str) -> list[int]:
    return [int(x) for x in value.split(",") if x.strip()]


def _parse_float_list(value: str) -> list[float]:
    return [float(x) for x in value.split(",") if x.strip()]


def _parse_str_list(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def _select_value(metrics_df: pd.DataFrame, metric: str, k: int) -> float:
    """Pull a single scalar (e.g. NDCG@20) out of the long-format metrics df."""
    row = metrics_df[metrics_df["K"] == k]
    if row.empty:
        raise ValueError(f"K={k} not found in eval output (eval_ks must include it)")
    return float(row.iloc[0][metric])


def _rows_from_metrics(
    metrics_df: pd.DataFrame,
    *,
    variant: str,
    phase: str,
    eval_on: str,
    config: dict,
    select_metric: str,
    select_value: float,
    is_best: bool,
    run_date: str,
) -> pd.DataFrame:
    """Annotate a long-format eval df (one row per K) with run context."""
    df = metrics_df.copy()
    df.insert(0, "Date", run_date)
    df.insert(1, "variant", variant)
    df.insert(2, "phase", phase)
    df.insert(3, "eval_on", eval_on)
    for i, col in enumerate(CONFIG_COLUMNS):
        df.insert(4 + i, col, config[col])
    df["Model"] = f"LightFM-{variant}"
    df["select_metric"] = select_metric
    df["select_value"] = round(select_value, 5)
    df["is_best"] = is_best
    return df


def _build_dataset(args, variant: str):
    from src.models.lightfm_model import (
        filter_top_users_by_activity,
        prepare_lightfm_dataset,
    )

    use_features = variant == "hybrid"

    print(f"\n[stage_17/{variant}] loading train from {args.train_path} ...", flush=True)
    train_df = load_table(args.train_path)

    members_df = load_table(args.members_path) if use_features else None
    songs_df = load_table(args.songs_path) if use_features else None

    if args.top_k_members and args.top_k_members > 0:
        members_for_filter = (
            members_df if members_df is not None else load_table(args.members_path)
        )
        before_users = train_df["msno_id"].nunique()
        train_df = filter_top_users_by_activity(
            train_df,
            members_for_filter,
            top_k=args.top_k_members,
            min_membership_days=args.min_membership_days,
        )
        print(
            f"[stage_17/{variant}] top-K member filter: "
            f"{before_users} -> {train_df['msno_id'].nunique()} users",
            flush=True,
        )

    data = prepare_lightfm_dataset(
        train_df,
        members=members_df,
        songs=songs_df,
        use_features=use_features,
        min_pos_per_user=args.min_pos_per_user,
        seed=args.seed,
        max_users=args.max_users,
        top_k_cities=args.top_k_cities,
        top_k_artists=args.top_k_artists,
        three_way=True,
    )
    print(
        f"[stage_17/{variant}] dataset ready | users={data.num_users} "
        f"items={data.num_items} train_nnz={data.interactions.nnz} "
        f"val={len(data.df_val)} test={len(data.df_test)}",
        flush=True,
    )
    return data


def _train_and_eval(data, config: dict, *, eval_ks, num_threads, seed, eval_df):
    from src.models.lightfm_model import evaluate_lightfm, train_lightfm_model

    model = train_lightfm_model(
        data,
        no_components=config["no_components"],
        loss=config["loss"],
        learning_rate=config["learning_rate"],
        epochs=config["epochs"],
        max_sampled=config["max_sampled"],
        item_alpha=config["item_alpha"],
        user_alpha=config["user_alpha"],
        num_threads=num_threads,
        seed=seed,
        verbose=False,
    )
    metrics_df = evaluate_lightfm(
        model,
        data,
        eval_ks=eval_ks,
        num_threads=num_threads,
        eval_df=eval_df,
    )
    return model, metrics_df


def search_variant(args, variant: str, candidates: dict, run_date: str) -> dict:
    """Run coordinate-descent for one variant. Returns the best config."""
    from src.models.lightfm_model import evaluate_lightfm, train_lightfm_model  # noqa: F401

    metric_name, sel_k = args.select_metric.split("@")
    sel_k = int(sel_k)
    eval_ks = tuple(_parse_int_list(args.eval_ks))
    if sel_k not in eval_ks:
        eval_ks = tuple(sorted(set(eval_ks) | {sel_k}))

    data = _build_dataset(args, variant)

    # Baseline config = current stage_14 defaults.
    config = {
        "no_components": 128,
        "loss": "warp",
        "learning_rate": 0.05,
        "max_sampled": 10,
        "epochs": 10,
        "item_alpha": 0.0,
        "user_alpha": 0.0,
    }

    for dim in SEARCH_ORDER:
        cands = candidates[dim]
        if dim == "max_sampled" and config["loss"] not in ("warp", "warp-kos"):
            print(
                f"[stage_17/{variant}] skip max_sampled "
                f"(only affects WARP; current loss={config['loss']})",
                flush=True,
            )
            continue
        if not cands:
            continue

        print(f"\n[stage_17/{variant}] tuning {dim} over {cands} "
              f"(others fixed at best) ...", flush=True)

        dim_rows = []
        best_choice = config[dim]
        best_val = float("-inf")
        for c in cands:
            trial = {**config, dim: c}
            t0 = time.time()
            _, mdf = _train_and_eval(
                data, trial,
                eval_ks=eval_ks, num_threads=args.num_threads,
                seed=args.seed, eval_df=data.df_val,
            )
            sval = _select_value(mdf, metric_name, sel_k)
            print(
                f"    {dim}={c!s:<10} | {args.select_metric}(val)={sval:.5f} "
                f"| {time.time() - t0:.1f}s",
                flush=True,
            )
            dim_rows.append((c, trial, mdf, sval))
            if sval > best_val:
                best_val = sval
                best_choice = c

        # Write all trials for this dimension, flagging the winner.
        frames = [
            _rows_from_metrics(
                mdf, variant=variant, phase=f"tune:{dim}", eval_on="val",
                config=trial, select_metric=args.select_metric,
                select_value=sval, is_best=(c == best_choice), run_date=run_date,
            )
            for (c, trial, mdf, sval) in dim_rows
        ]
        append_metrics(pd.concat(frames, ignore_index=True), args.out_csv)

        config[dim] = best_choice
        print(f"[stage_17/{variant}] best {dim} = {best_choice} "
              f"({args.select_metric}(val)={best_val:.5f})", flush=True)

    # Final report: retrain best config, score on val / test / train.
    print(f"\n[stage_17/{variant}] FINAL config: {config}", flush=True)
    final_frames = []
    for eval_on, eval_df in (
        ("val", data.df_val),
        ("test", data.df_test),
        ("train", data.df_train[data.df_train["target"] == 1]),
    ):
        _, mdf = _train_and_eval(
            data, config,
            eval_ks=eval_ks, num_threads=args.num_threads,
            seed=args.seed, eval_df=eval_df,
        )
        sval = _select_value(mdf, metric_name, sel_k)
        print(f"    final {eval_on:<5} | {args.select_metric}={sval:.5f}", flush=True)
        final_frames.append(
            _rows_from_metrics(
                mdf, variant=variant, phase="final", eval_on=eval_on,
                config=config, select_metric=args.select_metric,
                select_value=sval, is_best=True, run_date=run_date,
            )
        )
    final_df = pd.concat(final_frames, ignore_index=True)
    append_metrics(final_df, args.out_csv)

    # Overfitting signal: train vs test gap on the selection metric.
    train_score = _select_value(
        final_df[final_df["eval_on"] == "train"], metric_name, sel_k
    )
    test_score = _select_value(
        final_df[final_df["eval_on"] == "test"], metric_name, sel_k
    )
    gap = train_score - test_score
    print(
        f"[stage_17/{variant}] overfitting check {args.select_metric}: "
        f"train={train_score:.5f} test={test_score:.5f} gap={gap:.5f}"
        + ("  <-- large gap, suspect overfitting" if gap > 2 * max(test_score, 1e-9) else ""),
        flush=True,
    )
    return config


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(
        description="Stage 17: LightFM greedy (coordinate-descent) hyperparameter search"
    )
    parser.add_argument("--variant", choices=["hybrid", "purecf", "both"], default="both")
    parser.add_argument("--train-path", type=Path,
                        default=paths.processed / "train_encoded.parquet")
    parser.add_argument("--members-path", type=Path,
                        default=paths.processed / "complete_members.parquet")
    parser.add_argument("--songs-path", type=Path,
                        default=paths.processed / "song_features.parquet")

    parser.add_argument("--loss-list", type=str, default="warp,bpr,logistic")
    parser.add_argument("--components-list", type=str, default="32,64,128,256")
    parser.add_argument("--lr-list", type=str, default="0.01,0.025,0.05,0.1")
    parser.add_argument("--max-sampled-list", type=str, default="5,10,30,50")
    parser.add_argument("--epochs-list", type=str, default="5,10,20,30,50")
    parser.add_argument("--item-alpha-list", type=str, default="0,1e-7,1e-6,1e-5")
    parser.add_argument("--user-alpha-list", type=str, default="0,1e-7,1e-6,1e-5")

    parser.add_argument("--select-metric", type=str, default="NDCG@20")
    parser.add_argument("--eval-ks", type=str, default="10,20")
    parser.add_argument("--top-k-members", type=int, default=5000)
    parser.add_argument("--min-membership-days", type=int, default=30)
    parser.add_argument("--min-pos-per-user", type=int, default=3)
    parser.add_argument("--max-users", type=int, default=None)
    parser.add_argument("--top-k-cities", type=int, default=30)
    parser.add_argument("--top-k-artists", type=int, default=5000)
    parser.add_argument("--num-threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-csv", type=Path,
                        default=paths.reports / "lightfm_greedy_metrics.csv")
    parser.add_argument("--smoke", action="store_true",
                        help="tiny candidate lists + small cohort for a fast sanity run")
    args = parser.parse_args()

    candidates = {
        "loss": _parse_str_list(args.loss_list),
        "no_components": _parse_int_list(args.components_list),
        "learning_rate": _parse_float_list(args.lr_list),
        "max_sampled": _parse_int_list(args.max_sampled_list),
        "epochs": _parse_int_list(args.epochs_list),
        "item_alpha": _parse_float_list(args.item_alpha_list),
        "user_alpha": _parse_float_list(args.user_alpha_list),
    }

    if args.smoke:
        args.max_users = args.max_users or 300
        args.top_k_members = min(args.top_k_members, 1000)
        candidates = {
            "loss": ["warp", "bpr"],
            "no_components": [16, 32],
            "learning_rate": [0.05],
            "max_sampled": [10],
            "epochs": [2],
            "item_alpha": [0.0],
            "user_alpha": [0.0],
        }
        print("[stage_17] SMOKE mode: tiny candidates + small cohort", flush=True)

    try:
        import lightfm  # noqa: F401
    except ImportError:
        raise SystemExit(
            "[LightFM] lightfm is not installed in the active venv. "
            "Root .venv (Py 3.11.13) should have it."
        )

    run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    variants = ["hybrid", "purecf"] if args.variant == "both" else [args.variant]

    best_configs = {}
    for variant in variants:
        best_configs[variant] = search_variant(args, variant, candidates, run_date)

    print("\n[stage_17] done. Best configs:")
    for variant, cfg in best_configs.items():
        print(f"  {variant}: {cfg}")
    print(f"[stage_17] metrics appended to {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
