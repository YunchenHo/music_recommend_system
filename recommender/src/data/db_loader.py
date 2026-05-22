"""Loader for the system DB exports produced by
`backend/users/management/commands/export_for_lightfm.py`.

Reads the four CSV files under `data/db_processed/` (relative to the repo root)
and returns them as a `DBData` namedtuple of pandas DataFrames.

Downstream consumers (LightFM cold-start research, recommender pipeline DB
integration) build on this. ID encoding and feature engineering live elsewhere
— this module is intentionally thin.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from src.io import load_table


_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "db_processed"


@dataclass
class DBData:
    """Container for the four DB exports."""

    users: pd.DataFrame
    songs: pd.DataFrame
    interactions: pd.DataFrame
    onboarding: pd.DataFrame


def load_db_data(directory: Optional[Path] = None) -> DBData:
    """Load the four exports as DataFrames.

    `directory` defaults to `<repo>/data/db_processed/`. CSV is read via
    `src.io.load_table`, which transparently falls back from .parquet to .csv.
    """
    base = Path(directory) if directory else _DEFAULT_DIR

    users = load_table(base / "users.csv")
    songs = load_table(base / "songs.csv")
    interactions = load_table(base / "interactions.csv")
    onboarding = load_table(base / "onboarding.csv")

    # Normalize dtypes that CSV loses. user_id / song_id must be int for LightFM.
    users["user_id"] = users["user_id"].astype("int64")
    users["profile_completed"] = users["profile_completed"].astype("int8")
    songs["song_id"] = songs["song_id"].astype("int64")
    songs["artist_id"] = songs["artist_id"].astype("Int64")  # nullable
    interactions["user_id"] = interactions["user_id"].astype("int64")
    interactions["song_id"] = interactions["song_id"].astype("int64")
    interactions["watch_seconds"] = interactions["watch_seconds"].astype("int64")
    interactions["played_at"] = pd.to_datetime(
        interactions["played_at"], errors="coerce", utc=True
    )
    # is_liked / affinity_score may be blank → keep as nullable
    interactions["is_liked"] = interactions["is_liked"].astype("Int8")
    interactions["affinity_score"] = interactions["affinity_score"].astype("Float64")
    onboarding["user_id"] = onboarding["user_id"].astype("int64")
    onboarding["entity_id"] = onboarding["entity_id"].astype("int64")

    return DBData(
        users=users,
        songs=songs,
        interactions=interactions,
        onboarding=onboarding,
    )
