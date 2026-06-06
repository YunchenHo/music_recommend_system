"""Stage cs06 — switching-threshold sweep: pureCF vs hybrid across activity N.

Research question: at what user-activity level (number of training interactions)
does the best LightFM variant flip? We sweep training-history length
`n_seed` (N) and, for each N, train both pureCF (no features) and hybrid (with
features) on the SAME fixed-held-out split, then read off NDCG@K vs N. The N
where the curves cross = the switching threshold.

Methodology (controls the two confounds in the plain A_N1/N3/N5 splits):
- FIXED held-out size H per user (`make_split_a_fixed_holdout`) → NDCG scale is
  comparable across N.
- Natural population per N (users with >= N+H positives) → matches deployment.
- IDENTICAL training config for both variants → the only differences are
  features (on/off) and N, so this is a clean feature-ablation across activity.

LightFM is pure Python (no TensorFlow) → fine to run locally under tmux.

Run:
    PYTHONPATH=. uv run python pipeline/stage_cs06_switch_threshold.py --smoke
    PYTHONPATH=. uv run python pipeline/stage_cs06_switch_threshold.py   # full
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pipeline.config import Paths
from src.coldstart.eval_metrics import append_metrics, compute_topk_metrics
from src.coldstart.lightfm_helpers import (
    build_lightfm_data_from_split,
    predict_topk_known_users,
)
from src.coldstart.split import make_split_a_fixed_holdout
from src.io import load_table
from src.models.lightfm_model import train_lightfm_model


def _parse_int_list(value: str) -> list[int]:
    return [int(x) for x in value.split(",") if x.strip()]


def evaluate_variant(
    *,
    n_seed: int,
    variant: str,
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    useridx: dict,
    itemidx: dict,
    members: pd.DataFrame | None,
    songs: pd.DataFrame | None,
    cfg: dict,
    eval_ks: tuple[int, ...],
    n_holdout: int,
) -> pd.DataFrame:
    use_features = variant == "hybrid"
    data = build_lightfm_data_from_split(
        df_train, df_test, useridx, itemidx,
        members=members if use_features else None,
        songs=songs if use_features else None,
        use_features=use_features,
    )
    model = train_lightfm_model(
        data,
        no_components=cfg["no_components"],
        loss=cfg["loss"],
        learning_rate=cfg["learning_rate"],
        epochs=cfg["epochs"],
        max_sampled=cfg["max_sampled"],
        item_alpha=cfg["item_alpha"],
        user_alpha=cfg["user_alpha"],
        num_threads=1,
        verbose=False,
    )
    user_truth = df_test.groupby("msno_idx")["song_idx"].apply(list).to_dict()
    user_topk = predict_topk_known_users(model, data, user_truth, max_k=max(eval_ks))

    df = compute_topk_metrics(
        user_topk, user_truth,
        eval_ks=eval_ks,
        model_name=f"LightFM-{variant}",
        notes=(
            f"N={n_seed}, H={n_holdout}, variant={variant}, "
            f"loss={cfg['loss']}, components={cfg['no_components']}, "
            f"epochs={cfg['epochs']}, max_sampled={cfg['max_sampled']}"
        ),
    )
    df.insert(1, "N", n_seed)
    df.insert(2, "n_users", len(user_truth))
    return df


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(
        description="Stage cs06: switching-threshold sweep (pureCF vs hybrid across activity N)"
    )
    parser.add_argument("--train-path", type=Path, default=paths.processed / "train_encoded.parquet")
    parser.add_argument("--members-path", type=Path, default=paths.processed / "complete_members.parquet")
    parser.add_argument("--songs-path", type=Path, default=paths.processed / "song_features.parquet")
    parser.add_argument("--n-list", type=str, default="1,2,3,5,8,12,20,30,50",
                        help="training-history lengths to sweep")
    parser.add_argument("--n-holdout", type=int, default=5, help="fixed held-out positives per user")
    parser.add_argument("--variants", nargs="+", default=["purecf", "hybrid"],
                        choices=["purecf", "hybrid"])
    parser.add_argument("--eval-ks", nargs="+", type=int, default=[10, 20])
    parser.add_argument("--seed", type=int, default=42)
    # Identical training config for both variants (isolates features + N).
    parser.add_argument("--loss", default="warp", choices=["warp", "bpr", "logistic", "warp-kos"])
    parser.add_argument("--no-components", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--max-sampled", type=int, default=30)
    parser.add_argument("--item-alpha", type=float, default=0.0)
    parser.add_argument("--user-alpha", type=float, default=0.0)
    parser.add_argument("--out-path", type=Path, default=paths.reports / "cs_switch_threshold.csv")
    parser.add_argument("--max-users", type=int, default=None, help="cap users per N (smoke only)")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    if args.smoke:
        args.n_list = "1,5,20"
        args.no_components = 32
        args.epochs = 2
        args.max_users = args.max_users or 400

    n_list = _parse_int_list(args.n_list)
    eval_ks = tuple(args.eval_ks)
    cfg = {
        "loss": args.loss, "no_components": args.no_components,
        "learning_rate": args.learning_rate, "epochs": args.epochs,
        "max_sampled": args.max_sampled,
        "item_alpha": args.item_alpha, "user_alpha": args.user_alpha,
    }

    print(f"[stage_cs06] switching-threshold sweep N={n_list}, H={args.n_holdout}, "
          f"variants={args.variants}, config={cfg}", flush=True)

    need_features = "hybrid" in args.variants
    train_encoded = load_table(args.train_path)
    members = load_table(args.members_path) if need_features else None
    songs = load_table(args.songs_path) if need_features else None

    for n_seed in n_list:
        print(f"\n[stage_cs06] === N={n_seed} (users need >= {n_seed + args.n_holdout} positives) ===",
              flush=True)
        df_train, df_test, useridx, itemidx = make_split_a_fixed_holdout(
            train_encoded, n_seed=n_seed, n_holdout=args.n_holdout,
            seed=args.seed, max_users=args.max_users,
        )
        print(f"  users={len(useridx)} items={len(itemidx)} "
              f"train_rows={len(df_train)} test_rows={len(df_test)}", flush=True)

        for variant in args.variants:
            df_metrics = evaluate_variant(
                n_seed=n_seed, variant=variant,
                df_train=df_train, df_test=df_test,
                useridx=useridx, itemidx=itemidx,
                members=members, songs=songs,
                cfg=cfg, eval_ks=eval_ks, n_holdout=args.n_holdout,
            )
            for _, r in df_metrics[df_metrics.K == max(eval_ks)].iterrows():
                print(f"    {variant:7s} N={n_seed:<3d} NDCG@{int(r.K)}={r.NDCG:.4f} "
                      f"Recall@{int(r.K)}={r.Recall:.4f} (users={int(r.n_users)})", flush=True)
            append_metrics(df_metrics, args.out_path)

    # Crossover summary: per K, find the N where the argmax variant changes.
    print("\n[stage_cs06] === crossover summary ===", flush=True)
    allrows = pd.read_csv(args.out_path)
    allrows = allrows[allrows["N"].notna()]
    for k in eval_ks:
        sub = allrows[allrows.K == k].drop_duplicates(["N", "Model"], keep="last")
        piv = sub.pivot_table(index="N", columns="Model", values="NDCG").sort_index()
        print(f"\n  NDCG@{k} vs N:")
        print(piv.round(4).to_string())
        if piv.shape[1] == 2:
            winner = piv.idxmax(axis=1)
            print(f"  winner by N: {winner.to_dict()}")

    print(f"\n[stage_cs06] metrics appended to {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
