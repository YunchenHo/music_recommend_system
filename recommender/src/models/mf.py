from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from tensorflow.keras import layers, models, regularizers


@dataclass
class MFData:
    df_train: pd.DataFrame
    df_test: pd.DataFrame
    X_train: np.ndarray
    X_val: np.ndarray
    y_train: np.ndarray
    y_val: np.ndarray
    X_train_full: np.ndarray
    y_train_full: np.ndarray
    num_users: int
    num_items: int
    useridx: dict | None = None
    itemidx: dict | None = None


def prepare_mf_data(
    train_encoded: pd.DataFrame,
    min_pos_per_user: int = 2,
    seed: int = 42,
    test_size: float = 0.1,
    max_users: int | None = None,
    sample_rate: float | None = None,
) -> MFData:
    df_pos = train_encoded[train_encoded["target"] == 1].copy()
    user_counts = df_pos.groupby("msno_id").size()
    valid_users = user_counts[user_counts >= min_pos_per_user].index

    if max_users is not None:
        valid_users = valid_users[:max_users]

    df_filtered = train_encoded[train_encoded["msno_id"].isin(valid_users)].copy()
    if sample_rate is not None and 0 < sample_rate < 1:
        df_filtered = df_filtered.sample(frac=sample_rate, random_state=seed).copy()

    unique_users = df_filtered["msno_id"].unique()
    useridx = {old_id: new_id for new_id, old_id in enumerate(unique_users)}

    unique_songs = df_filtered["song_id"].unique()
    itemidx = {old_id: new_id for new_id, old_id in enumerate(unique_songs)}

    df_filtered["msno_idx"] = df_filtered["msno_id"].map(useridx)
    df_filtered["song_idx"] = df_filtered["song_id"].map(itemidx)

    df_positives = df_filtered[df_filtered["target"] == 1].copy()
    df_positives = df_positives.sample(frac=1, random_state=seed).sort_values("msno_idx")
    test_indices = df_positives.groupby("msno_idx").tail(1).index

    df_test = df_positives.loc[test_indices].copy()
    df_train = df_filtered.drop(test_indices).copy()
    df_train = df_train.sample(frac=1, random_state=seed).reset_index(drop=True)

    X_train_full = df_train[["msno_idx", "song_idx"]].values
    y_train_full = df_train["target"].values

    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=test_size, random_state=seed
    )

    num_users = len(useridx)
    num_items = len(itemidx)

    return MFData(
        df_train=df_train,
        df_test=df_test,
        X_train=X_train,
        X_val=X_val,
        y_train=y_train,
        y_val=y_val,
        X_train_full=X_train_full,
        y_train_full=y_train_full,
        num_users=num_users,
        num_items=num_items,
        useridx=useridx,
        itemidx=itemidx,
    )


def build_mf_model(num_users: int, num_items: int, embedding_dim: int = 64):
    user_input = layers.Input(shape=(1,), name="user_input")
    item_input = layers.Input(shape=(1,), name="song_input")

    user_embedding = layers.Embedding(
        input_dim=num_users, output_dim=embedding_dim, name="user_embedding"
    )(user_input)
    item_embedding = layers.Embedding(
        input_dim=num_items, output_dim=embedding_dim, name="song_embedding"
    )(item_input)

    user_vec = layers.Flatten()(user_embedding)
    item_vec = layers.Flatten()(item_embedding)

    dot_product = layers.Dot(axes=1, name="dot_product")([user_vec, item_vec])
    output = layers.Activation("sigmoid")(dot_product)

    model = models.Model(inputs=[user_input, item_input], outputs=output)
    return model


def build_improved_mf_model(
    num_users: int, num_items: int, embedding_dim: int = 128
):
    user_input = layers.Input(shape=(1,), name="user_input")
    item_input = layers.Input(shape=(1,), name="song_input")

    user_embedding = layers.Embedding(
        input_dim=num_users,
        output_dim=embedding_dim,
        embeddings_regularizer=regularizers.l2(1e-6),
        name="user_embedding",
    )(user_input)

    item_embedding = layers.Embedding(
        input_dim=num_items,
        output_dim=embedding_dim,
        embeddings_regularizer=regularizers.l2(1e-6),
        name="song_embedding",
    )(item_input)

    user_bias = layers.Embedding(input_dim=num_users, output_dim=1, name="user_bias")(
        user_input
    )
    item_bias = layers.Embedding(input_dim=num_items, output_dim=1, name="song_bias")(
        item_input
    )

    user_vec = layers.Flatten()(user_embedding)
    item_vec = layers.Flatten()(item_embedding)
    u_bias = layers.Flatten()(user_bias)
    i_bias = layers.Flatten()(item_bias)

    dot_product = layers.Dot(axes=1, name="dot_product")([user_vec, item_vec])
    x = layers.Add()([dot_product, u_bias, i_bias])
    output = layers.Activation("sigmoid")(x)

    model = models.Model(inputs=[user_input, item_input], outputs=output)
    return model


def train_mf_model(
    data: MFData,
    embedding_dim: int = 128,
    epochs: int = 10,
    batch_size: int = 2048,
    learning_rate: float = 0.001,
    improved: bool = True,
    steps_per_epoch: int | None = None,
    verbose: int = 1,
    debug: bool = False,
    fit_one_batch: bool = False,
    threads: int | None = None,
    manual_fit: bool = False,
    log_every: int = 100,
    eager: bool = False,
):
    if threads is not None:
        tf.config.threading.set_intra_op_parallelism_threads(threads)
        tf.config.threading.set_inter_op_parallelism_threads(threads)
    if eager:
        tf.config.run_functions_eagerly(True)

    if debug:
        print(f"[MF] build model (improved={improved})", flush=True)
    if improved:
        model = build_improved_mf_model(
            data.num_users, data.num_items, embedding_dim=embedding_dim
        )
        optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    else:
        model = build_mf_model(data.num_users, data.num_items, embedding_dim=embedding_dim)
        optimizer = "adam"

    if debug:
        print("[MF] compile model", flush=True)
    model.compile(
        optimizer=optimizer,
        loss="binary_crossentropy",
        metrics=[
            tf.keras.metrics.AUC(name="auc"),
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
        ],
    )

    if fit_one_batch:
        if debug:
            print("[MF] train_on_batch (single step)", flush=True)
        x_batch = data.X_train[:batch_size]
        y_batch = data.y_train[:batch_size]
        model.train_on_batch([x_batch[:, 0], x_batch[:, 1]], y_batch)
        return model, None

    if manual_fit:
        if debug:
            print("[MF] manual fit start", flush=True)
        rng = np.random.default_rng(42)
        X = data.X_train
        y = data.y_train
        n = len(X)
        total_steps = steps_per_epoch or int(np.ceil(n / batch_size))
        for epoch in range(1, epochs + 1):
            idx = rng.permutation(n)
            if debug or verbose:
                print(f"[MF] Epoch {epoch}/{epochs} (manual)", flush=True)
            for step in range(total_steps):
                start = step * batch_size
                end = min(start + batch_size, n)
                batch_idx = idx[start:end]
                xb = X[batch_idx]
                yb = y[batch_idx]
                if debug and step == 0:
                    print("[MF] step 1 start", flush=True)
                t_step = time.time()
                model.train_on_batch([xb[:, 0], xb[:, 1]], yb)
                if log_every and (step + 1) % log_every == 0:
                    print(
                        f"[MF] step {step + 1}/{total_steps} ({time.time() - t_step:.2f}s)",
                        flush=True,
                    )
        return model, None

    if debug:
        print("[MF] fit start", flush=True)
    history = model.fit(
        x=[data.X_train[:, 0], data.X_train[:, 1]],
        y=data.y_train,
        batch_size=batch_size,
        epochs=epochs,
        steps_per_epoch=steps_per_epoch,
        validation_data=([data.X_val[:, 0], data.X_val[:, 1]], data.y_val),
        verbose=verbose,
    )

    return model, history


def evaluate_classification(model, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    y_pred_prob = model.predict([X_test[:, 0], X_test[:, 1]], batch_size=2048).flatten()
    y_pred = (y_pred_prob >= 0.5).astype(int)

    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)

    return {
        "report": report,
        "confusion_matrix": cm.tolist(),
    }


def evaluate_mf_with_faiss(model, df_train: pd.DataFrame, df_test: pd.DataFrame, eval_ks=(10, 20)) -> pd.DataFrame:
    import faiss
    from tqdm import tqdm
    import math

    user_layer = model.get_layer("user_embedding")
    item_layer = model.get_layer("song_embedding")

    user_embeddings = user_layer.get_weights()[0].astype("float32")
    item_embeddings = item_layer.get_weights()[0].astype("float32")

    dim = item_embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(item_embeddings)

    train_history = df_train.groupby("msno_idx")["song_idx"].apply(set).to_dict()
    test_ground_truth = df_test.groupby("msno_idx")["song_idx"].apply(list).to_dict()
    train_known_items = set(df_train["song_idx"].unique())

    hits = {k: 0 for k in eval_ks}
    ndcgs = {k: 0.0 for k in eval_ks}
    n_eval = 0
    search_k = max(eval_ks) * 10
    test_users = list(test_ground_truth.keys())
    batch_size = 1000

    for i in tqdm(range(0, len(test_users), batch_size)):
        batch_users = test_users[i : i + batch_size]

        valid_uids = []
        for u in batch_users:
            if u >= len(user_embeddings):
                continue

            test_item = test_ground_truth[u][0]
            if test_item not in train_known_items:
                continue
            valid_uids.append(u)

        if not valid_uids:
            continue

        query_vectors = user_embeddings[valid_uids]
        _, I = index.search(query_vectors, search_k)

        for idx, uid in enumerate(valid_uids):
            true_sids = test_ground_truth[uid]
            seen_items = train_history.get(uid, set())

            raw_recs = I[idx]
            final_recs = []
            for item_id in raw_recs:
                if item_id not in seen_items:
                    final_recs.append(item_id)
                if len(final_recs) >= max(eval_ks):
                    break

            n_eval += 1

            for k in eval_ks:
                top_k = final_recs[:k]
                hit = 0
                gain = 0

                target = true_sids[0]
                if target in top_k:
                    hit = 1
                    rank = top_k.index(target)
                    gain = 1.0 / math.log2(rank + 2)

                hits[k] += hit
                ndcgs[k] += gain

    results = []
    for k in eval_ks:
        results.append(
            {
                "Model": "MF",
                "K": k,
                "Recall": round(hits[k] / n_eval, 5) if n_eval else 0.0,
                "Precision": round(hits[k] / (n_eval * k), 5) if n_eval else 0.0,
                "NDCG": round(ndcgs[k] / n_eval, 5) if n_eval else 0.0,
            }
        )

    return pd.DataFrame(results)


def evaluate_mf_for_comparison(
    model,
    df_test: pd.DataFrame,
    all_song_ids: np.ndarray,
    eval_ks=(10, 20),
) -> pd.DataFrame:
    import math
    from tqdm import tqdm

    pos_test_data = df_test[df_test["target"] == 1].copy()
    test_users = pos_test_data["msno_id"].unique()
    user_pos_dict = pos_test_data.groupby("msno_id")["song_id"].apply(list).to_dict()

    metrics = {k: {"hits": 0, "ndcg": 0.0} for k in eval_ks}
    n_eval = len(test_users)

    for uid in tqdm(test_users):
        true_sids = user_pos_dict[uid]
        target_sid = np.random.choice(true_sids)

        neg_candidates = np.random.choice(all_song_ids, 1500, replace=False)
        neg_sids = neg_candidates[~np.isin(neg_candidates, true_sids)][:999]

        test_list = np.append(neg_sids, target_sid)
        u_input = np.full(1000, uid)

        preds = model.predict([u_input, test_list], batch_size=1000, verbose=0).flatten()
        rank_idx = preds.argsort()[::-1]
        rank = np.where(rank_idx == 999)[0][0] + 1

        for k in eval_ks:
            if rank <= k:
                metrics[k]["hits"] += 1
                metrics[k]["ndcg"] += 1.0 / math.log2(rank + 1)

    results = []
    for k in eval_ks:
        recall = metrics[k]["hits"] / n_eval if n_eval else 0.0
        precision = metrics[k]["hits"] / (n_eval * k) if n_eval else 0.0
        ndcg = metrics[k]["ndcg"] / n_eval if n_eval else 0.0

        results.append(
            {
                "Model": "Matrix Factorization",
                "K": k,
                "Recall": round(recall, 4),
                "Precision": round(precision, 4),
                "NDCG": round(ndcg, 4),
            }
        )

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Artifact export for fold-in serving
# ---------------------------------------------------------------------------


def export_mf_artifacts(model, mf_data: MFData, output_dir: str | Path) -> dict[str, Path]:
    """
    從訓練好的 MF 模型中匯出 fold-in 所需的 artifacts。

    輸出：
      - mf_song_embeddings.npy  (num_items × embedding_dim)
      - mf_song_bias.npy        (num_items,)  — 若模型無 bias layer 則全 0
      - mf_item_mapping.json    {song_id: embedding_index}

    回傳各檔案的 Path。
    """
    import json

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 提取 song embedding
    item_layer = model.get_layer("song_embedding")
    song_embeddings = item_layer.get_weights()[0].astype("float32")

    # 提取 song bias（improved model 才有）
    try:
        bias_layer = model.get_layer("song_bias")
        song_bias = bias_layer.get_weights()[0].flatten().astype("float32")
    except ValueError:
        song_bias = np.zeros(song_embeddings.shape[0], dtype="float32")

    # item mapping: song_id → embedding index
    if mf_data.itemidx is None:
        raise ValueError("MFData.itemidx is None; cannot export item mapping.")
    item_mapping = {int(k): int(v) for k, v in mf_data.itemidx.items()}

    # 儲存
    emb_path = output_dir / "mf_song_embeddings.npy"
    bias_path = output_dir / "mf_song_bias.npy"
    mapping_path = output_dir / "mf_item_mapping.json"

    np.save(emb_path, song_embeddings)
    np.save(bias_path, song_bias)
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(item_mapping, f)

    print(f"[MF] Exported artifacts to {output_dir}")
    print(f"  song_embeddings: {song_embeddings.shape}")
    print(f"  song_bias: {song_bias.shape}")
    print(f"  item_mapping: {len(item_mapping)} items")

    return {
        "song_embeddings": emb_path,
        "song_bias": bias_path,
        "item_mapping": mapping_path,
    }
