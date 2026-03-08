from datetime import datetime
import re

import numpy as np
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer


def add_isrc_features(song_merge: pd.DataFrame) -> pd.DataFrame:
    isrc_pattern = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{2}[0-9]{5}$")

    def is_valid_isrc(x) -> int:
        if x == "NONE":
            return 0
        if not isinstance(x, str):
            return 0
        return 1 if isrc_pattern.match(x) else 0

    song_merge["has_valid_isrc"] = song_merge["isrc"].apply(is_valid_isrc)

    song_merge["isrc_country"] = "UNK"
    song_merge["isrc_registrant"] = "UNK"
    song_merge["isrc_year"] = "UNK"
    song_merge["isrc_item_id"] = "UNK"

    valid_mask = song_merge["has_valid_isrc"] == 1
    valid_isrc = song_merge.loc[valid_mask, "isrc"]
    song_merge.loc[valid_mask, "isrc_country"] = valid_isrc.str[:2]
    song_merge.loc[valid_mask, "isrc_registrant"] = valid_isrc.str[2:5]
    song_merge.loc[valid_mask, "isrc_year"] = valid_isrc.str[5:7]
    song_merge.loc[valid_mask, "isrc_item_id"] = valid_isrc.str[7:]

    def convert_isrc_year(yy: str) -> float:
        if yy == "UNK":
            return np.nan
        yy_int = int(yy)
        return 2000 + yy_int if yy_int <= 25 else 1900 + yy_int

    song_merge["isrc_year_full"] = song_merge["isrc_year"].apply(convert_isrc_year)
    return song_merge


def add_genre_features(song_merge: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    def to_genre_list(x: str):
        if x == "unknown":
            return []
        return x.split("|")

    song_merge["genre_list"] = song_merge["genre_ids"].apply(to_genre_list)
    song_merge["genre_count"] = song_merge["genre_list"].apply(len)

    mlb = MultiLabelBinarizer()
    genre_ohe = mlb.fit_transform(song_merge["genre_list"])
    genre_cols = [f"genre_{g}" for g in mlb.classes_]
    genre_df = pd.DataFrame(genre_ohe, columns=genre_cols, index=song_merge.index)
    genre_df = genre_df.astype("uint8")

    song_merge = pd.concat([song_merge, genre_df], axis=1)
    return song_merge, genre_cols


def add_popularity_features(song_merge: pd.DataFrame) -> pd.DataFrame:
    artist_popularity = song_merge["artist_name"].value_counts()
    song_merge["artist_popularity"] = song_merge["artist_name"].map(artist_popularity)
    song_merge["artist_popularity_log"] = np.log1p(song_merge["artist_popularity"])
    return song_merge


def add_metadata_scores(song_merge: pd.DataFrame) -> pd.DataFrame:
    meta_cols_basic = [
        "has_name",
        "has_genre",
        "has_composer",
        "has_lyricist",
        "has_isrc",
        "has_song_extra",
    ]
    song_merge["metadata_score"] = song_merge[meta_cols_basic].sum(axis=1)

    meta_cols_strict = [
        "has_name",
        "has_genre",
        "has_composer",
        "has_lyricist",
        "has_valid_isrc",
        "has_song_extra",
    ]
    song_merge["metadata_score_strict"] = song_merge[meta_cols_strict].sum(axis=1)
    return song_merge


def build_song_features(
    song_merge: pd.DataFrame, current_year: int | None = None
) -> pd.DataFrame:
    if current_year is None:
        current_year = datetime.now().year

    song_merge = add_isrc_features(song_merge)
    song_merge["song_age"] = current_year - song_merge["isrc_year_full"]

    song_merge, genre_cols = add_genre_features(song_merge)
    song_merge = add_popularity_features(song_merge)

    song_merge["genre_vector"] = song_merge[genre_cols].astype("uint8").values.tolist()
    song_merge = add_metadata_scores(song_merge)

    return song_merge
