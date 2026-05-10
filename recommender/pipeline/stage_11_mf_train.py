import argparse
from pathlib import Path
import time

from pipeline.config import Paths
from src.io import load_table, save_df


def main() -> int:
    paths = Paths.default()
    paths.ensure()

    parser = argparse.ArgumentParser(description="Stage 11: train MF model")
    parser.add_argument(
        "--train-path",
        type=Path,
        default=paths.processed / "train_encoded.parquet",
    )
    parser.add_argument("--min-pos-per-user", type=int, default=2)
    parser.add_argument("--max-users", type=int, default=None)
    parser.add_argument("--sample-rate", type=float, default=None)
    parser.add_argument("--embedding-dim", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--steps-per-epoch", type=int, default=None)
    parser.add_argument("--verbose", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--basic", action="store_true", help="use basic MF model")
    parser.add_argument("--warmup", action="store_true", help="run a quick warmup predict")
    parser.add_argument("--threads", type=int, default=None)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--fit-one-batch", action="store_true")
    parser.add_argument("--manual-fit", action="store_true")
    parser.add_argument("--log-every", type=int, default=100)
    parser.add_argument("--eager", action="store_true")
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "gpu"],
        help="select device placement",
    )
    parser.add_argument(
        "--require-gpu",
        action="store_true",
        help="fail if no GPU is available",
    )
    parser.add_argument(
        "--mixed-precision",
        action="store_true",
        help="enable mixed precision (GPU only)",
    )
    parser.add_argument(
        "--memory-growth",
        action="store_true",
        help="enable GPU memory growth if supported",
    )
    parser.add_argument(
        "--train-head",
        type=int,
        default=None,
        help="only load the first N rows (fast smoke test)",
    )
    parser.add_argument(
        "--model-out",
        type=Path,
        default=paths.artifacts / "mf_model.h5",
    )
    parser.add_argument(
        "--train-out",
        type=Path,
        default=paths.processed / "mf_train.parquet",
    )
    parser.add_argument(
        "--test-out",
        type=Path,
        default=paths.processed / "mf_test.parquet",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=paths.reports / "mf_classification_report.json",
    )
    args = parser.parse_args()

    import tensorflow as tf

    gpus = tf.config.list_physical_devices("GPU")
    print(f"[MF] tf: {tf.__version__} | GPUs: {len(gpus)}", flush=True)
    if args.require_gpu and not gpus:
        raise SystemExit("[MF] No GPU detected. Install Apple Metal plugin or use CPU mode.")

    if args.device == "cpu":
        tf.config.set_visible_devices([], "GPU")
        print("[MF] device: CPU (GPU disabled)", flush=True)
    elif args.device == "gpu":
        if not gpus:
            raise SystemExit("[MF] device=gpu requested but no GPU found.")
        tf.config.set_visible_devices(gpus[0], "GPU")
        print("[MF] device: GPU", flush=True)
    else:
        print("[MF] device: auto", flush=True)

    if gpus and args.memory_growth:
        for gpu in gpus:
            try:
                tf.config.experimental.set_memory_growth(gpu, True)
            except Exception as exc:
                print(f"[MF] memory growth not supported: {exc}", flush=True)

    if args.mixed_precision:
        if not gpus:
            print("[MF] mixed precision requested but no GPU found; ignoring", flush=True)
        else:
            tf.keras.mixed_precision.set_global_policy("mixed_float16")
            print("[MF] mixed precision: enabled", flush=True)

    from src.models.mf import prepare_mf_data, train_mf_model, evaluate_classification, export_mf_artifacts

    print(f"[MF] loading train from {args.train_path} ...", flush=True)
    t0 = time.time()
    if args.train_head:
        if args.train_path.suffix == ".parquet":
            import pyarrow.parquet as pq
            import pandas as pd

            pf = pq.ParquetFile(args.train_path)
            rows = []
            remaining = args.train_head
            for batch in pf.iter_batches(batch_size=min(100_000, remaining)):
                rows.append(batch.to_pandas())
                remaining -= len(rows[-1])
                if remaining <= 0:
                    break
            train_df = pd.concat(rows, ignore_index=True).head(args.train_head)
        else:
            import pandas as pd

            train_df = pd.read_csv(args.train_path, nrows=args.train_head)
    else:
        train_df = load_table(args.train_path)
    print(f"[MF] loaded rows: {len(train_df)} in {time.time() - t0:.2f}s", flush=True)

    print("[MF] preparing data ...", flush=True)
    t1 = time.time()
    data = prepare_mf_data(
        train_df,
        min_pos_per_user=args.min_pos_per_user,
        max_users=args.max_users,
        sample_rate=args.sample_rate,
    )
    print(f"[MF] prepared in {time.time() - t1:.2f}s", flush=True)

    print(
        "[MF] users:",
        data.num_users,
        "items:",
        data.num_items,
        "train rows:",
        len(data.df_train),
        "test rows:",
        len(data.df_test),
    )

    if args.warmup:
        import tensorflow as tf

        warm_x = data.X_train[: min(1024, len(data.X_train))]
        warm_y = data.y_train[: len(warm_x)]
        model = tf.keras.Sequential(
            [tf.keras.layers.Dense(1, input_shape=(2,))]
        )
        model.compile(optimizer="adam", loss="mse")
        t0 = time.time()
        model.fit(warm_x, warm_y, epochs=1, batch_size=256, verbose=0)
        print(f"[MF] warmup ok in {time.time() - t0:.2f}s")

    model, _ = train_mf_model(
        data,
        embedding_dim=args.embedding_dim,
        epochs=args.epochs,
        batch_size=args.batch_size,
        steps_per_epoch=args.steps_per_epoch,
        verbose=args.verbose,
        learning_rate=args.learning_rate,
        improved=not args.basic,
        debug=args.debug,
        fit_one_batch=args.fit_one_batch,
        threads=args.threads,
        manual_fit=args.manual_fit,
        log_every=args.log_every,
        eager=args.eager,
    )

    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    model.save(args.model_out)
    print("Saved model:", args.model_out)

    save_df(data.df_train, args.train_out)
    save_df(data.df_test, args.test_out)
    print("Saved mf train/test splits:", args.train_out, args.test_out)

    report = evaluate_classification(model, data.X_val, data.y_val)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    import json

    with open(args.report_out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Saved classification report:", args.report_out)

    # Export fold-in artifacts
    export_mf_artifacts(model, data, paths.artifacts)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
