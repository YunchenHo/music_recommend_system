import pickle

import pandas as pd
from sklearn.preprocessing import LabelEncoder


def calculate_sparsity(df: pd.DataFrame) -> float:
    n_users = df["msno_id"].nunique()
    n_songs = df["song_id"].nunique()
    n_interactions = len(df)
    total_cells = n_users * n_songs
    sparsity = 1 - (n_interactions / total_cells)

    print("-----------------------------------")
    print(f"📊 矩陣維度: {n_users} (Users) x {n_songs} (Songs)")
    print(f"📦 總格子數: {total_cells:,}")
    print(f"📝 實際紀錄數: {n_interactions:,}")
    print("-----------------------------------")
    print(f"🌌 稀疏度 (Sparsity): {sparsity:.4%}")
    print(f"dense 密度 (Density) : {(1 - sparsity):.4%}")
    print("-----------------------------------")

    return sparsity


def encode_sources(train: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    source_cols = ["source_system_tab", "source_screen_name", "source_type"]
    encoders: dict[str, LabelEncoder] = {}
    for col in source_cols:
        train[col] = train[col].fillna("Unknown")
        le = LabelEncoder()
        train[col] = le.fit_transform(train[col]).astype("int8")
        encoders[col] = le
    return train, encoders


def encode_ids(
    train: pd.DataFrame, msno_encoder_path, song_encoder_path
) -> pd.DataFrame:
    try:
        with open(msno_encoder_path, "rb") as f:
            msno_le = pickle.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError("Missing msno_encoder.pkl; run stage_01 first.") from exc

    with open(song_encoder_path, "rb") as f:
        song_encoder = pickle.load(f)

    known_msno = set(msno_le.classes_)
    train = train[train["msno"].isin(known_msno)].copy()
    train["msno_id"] = msno_le.transform(train["msno"]).astype("int32")
    train = train.drop(columns=["msno"])

    known_songs = set(song_encoder.classes_)
    before_len = len(train)
    train = train[train["song_id"].isin(known_songs)].copy()
    after_len = len(train)
    print(f"過濾未知歌曲完成：刪除了 {before_len - after_len} 筆資料")

    train["song_id"] = song_encoder.transform(train["song_id"]).astype("int32")
    train["target"] = train["target"].astype("int8")

    return train


def filter_top_members(
    train: pd.DataFrame,
    complete_members: pd.DataFrame,
    top_k: int,
    min_membership_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    member_play_counts = train["msno_id"].value_counts()
    complete_members = complete_members.copy()
    complete_members["play_count"] = complete_members["msno_id"].map(member_play_counts)
    complete_members["songs_per_day"] = (
        complete_members["play_count"]
        / complete_members["membership_days"].clip(lower=1)
    )

    candidates = complete_members[complete_members["membership_days"] > min_membership_days]
    top_members = (
        candidates.sort_values(by="play_count", ascending=False)
        .head(top_k)
        .copy()
    )

    vip_ids = top_members["msno_id"].values
    train_filtered = train[train["msno_id"].isin(vip_ids)].copy()

    return train_filtered, top_members


def load_and_encode_train_for_knn(
    train_csv_path: str,
    msno_encoder_path: str,
    song_encoder_path: str,
    usecols=("msno", "song_id", "target"),
    chunksize: int = 2_000_000,
):
    import gc

    with open(msno_encoder_path, "rb") as f:
        msno_le = pickle.load(f)
    with open(song_encoder_path, "rb") as f:
        song_le = pickle.load(f)

    known_msno = set(msno_le.classes_)
    known_song = set(song_le.classes_)

    out_parts = []
    total_in = 0
    total_keep = 0

    for chunk in pd.read_csv(train_csv_path, usecols=list(usecols), chunksize=chunksize):
        total_in += len(chunk)
        chunk = chunk[chunk["msno"].isin(known_msno)]
        chunk = chunk[chunk["song_id"].isin(known_song)]

        if len(chunk) == 0:
            continue

        chunk["msno_id"] = msno_le.transform(chunk["msno"]).astype("int32")
        chunk["song_id"] = song_le.transform(chunk["song_id"]).astype("int32")
        chunk["target"] = chunk["target"].astype("int8")
        chunk = chunk[["msno_id", "song_id", "target"]]

        out_parts.append(chunk)
        total_keep += len(chunk)

        del chunk
        gc.collect()

    if not out_parts:
        raise ValueError("沒有任何資料通過白名單過濾，請檢查 encoder 路徑或 train.csv 欄位。")

    train_encoded = pd.concat(out_parts, ignore_index=True)
    print(f"讀入原始筆數（分批累計）：{total_in:,}")
    print(f"白名單過濾後保留筆數：{total_keep:,}")
    print(f"最終 train_encoded shape：{train_encoded.shape}")

    return train_encoded
