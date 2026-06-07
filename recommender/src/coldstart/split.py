"""Cold-start train/test splits.

Two scenarios:

- **Scenario A (leave-first-N)**: For each user with ≥ N+1 positives, randomly
  pick N positives as the "seed" interactions (go into train) and put the rest
  into test. Negatives stay in train. Simulates "user with limited history".

- **Scenario C (held-out users)**: Randomly sample `n_test_users` from users
  with ≥ 1 positive. Their positives become the test set. All other users go
  fully into train. Simulates "brand new user — only features available".

Both functions return `(df_train, df_test, useridx, itemidx)`. For Scenario C
the test rows carry raw `msno_id` (not in `useridx`) because the test users
are deliberately absent from the training matrix; downstream LightFM eval
constructs user feature vectors directly from `complete_members.parquet`.
"""

from __future__ import annotations

import pandas as pd


def _encode_ids(df: pd.DataFrame, useridx: dict, itemidx: dict) -> pd.DataFrame:
    df = df.copy()
    df["msno_idx"] = df["msno_id"].map(useridx)
    df["song_idx"] = df["song_id"].map(itemidx)
    return df


def make_split_a(
    train_encoded: pd.DataFrame,
    *,
    n_seed: int,
    seed: int = 42,
    max_users: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    """Scenario A: leave-first-N seed interactions, rest goes to test.

    Args:
        train_encoded: rows with at least `msno_id`, `song_id`, `target` columns
        n_seed: how many positives to keep in train per user (N=1, 3, 5, ...)
        seed: random seed for shuffle
        max_users: cap on number of users (mainly for smoke tests)

    Returns:
        df_train: training interactions with `msno_idx`/`song_idx` encoded;
            includes the N seed positives per user **plus all negatives**.
        df_test: test interactions (positives only) with the same encoding.
            Same users as df_train but disjoint song-level rows.
        useridx: {msno_id: msno_idx}
        itemidx: {song_id: song_idx}
    """
    if n_seed < 1:
        raise ValueError(f"n_seed must be ≥ 1, got {n_seed}")

    df_pos = train_encoded[train_encoded["target"] == 1]
    user_pos_counts = df_pos.groupby("msno_id").size()
    eligible_users = user_pos_counts[user_pos_counts >= n_seed + 1].index

    if max_users is not None:
        eligible_users = eligible_users[:max_users]

    eligible_set = set(eligible_users)
    df_filtered = train_encoded[train_encoded["msno_id"].isin(eligible_set)].copy()

    unique_users = df_filtered["msno_id"].unique()
    useridx = {old: new for new, old in enumerate(unique_users)}
    unique_songs = df_filtered["song_id"].unique()
    itemidx = {old: new for new, old in enumerate(unique_songs)}

    df_filtered = _encode_ids(df_filtered, useridx, itemidx)

    df_positives = df_filtered[df_filtered["target"] == 1].copy()
    df_positives = (
        df_positives.sample(frac=1, random_state=seed)
        .sort_values("msno_idx")
        .reset_index()
    )

    seed_indices = (
        df_positives.groupby("msno_idx").head(n_seed)["index"].tolist()
    )
    seed_set = set(seed_indices)
    test_indices = df_positives[~df_positives["index"].isin(seed_set)]["index"].tolist()

    df_test = df_filtered.loc[test_indices].copy().reset_index(drop=True)
    df_train = df_filtered.drop(test_indices).copy()
    df_train = df_train.sample(frac=1, random_state=seed).reset_index(drop=True)

    return df_train, df_test, useridx, itemidx


def make_split_c(
    train_encoded: pd.DataFrame,
    *,
    n_test_users: int,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict, list]:
    """Scenario C: hold out a group of users entirely.

    Args:
        train_encoded: rows with `msno_id`, `song_id`, `target` columns
        n_test_users: how many users to hold out as cold-start test users
        seed: random seed

    Returns:
        df_train: training interactions (rows from non-test users only) with
            `msno_idx`/`song_idx` encoded.
        df_test: test positives from held-out users. `msno_id` is **raw**
            (not in `useridx`); `song_idx` is encoded.
        useridx: {msno_id: msno_idx} for train users only.
        itemidx: {song_id: song_idx} — built from train items; test items
            outside this set are dropped (item cold-start is out of scope).
        test_user_ids: list of held-out raw `msno_id`s
    """
    df_pos = train_encoded[train_encoded["target"] == 1]
    users_with_pos = df_pos["msno_id"].drop_duplicates()

    if n_test_users >= len(users_with_pos):
        raise ValueError(
            f"n_test_users={n_test_users} but only {len(users_with_pos)} users have positives"
        )

    rng = users_with_pos.sample(n=n_test_users, random_state=seed)
    test_user_ids = rng.tolist()
    test_user_set = set(test_user_ids)

    df_train_raw = train_encoded[~train_encoded["msno_id"].isin(test_user_set)].copy()

    unique_users = df_train_raw["msno_id"].unique()
    useridx = {old: new for new, old in enumerate(unique_users)}
    unique_songs = df_train_raw["song_id"].unique()
    itemidx = {old: new for new, old in enumerate(unique_songs)}

    df_train = _encode_ids(df_train_raw, useridx, itemidx)
    df_train = df_train.sample(frac=1, random_state=seed).reset_index(drop=True)

    df_test_raw = train_encoded[
        train_encoded["msno_id"].isin(test_user_set)
        & (train_encoded["target"] == 1)
    ].copy()
    df_test_raw = df_test_raw[df_test_raw["song_id"].isin(itemidx)].copy()
    df_test_raw["song_idx"] = df_test_raw["song_id"].map(itemidx)
    df_test = df_test_raw.reset_index(drop=True)

    return df_train, df_test, useridx, itemidx, test_user_ids
