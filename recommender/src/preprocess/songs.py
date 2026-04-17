import pandas as pd
from sklearn.preprocessing import LabelEncoder


def preprocess_songs(
    songs: pd.DataFrame, song_extra: pd.DataFrame
) -> tuple[pd.DataFrame, LabelEncoder, dict[str, int]]:
    song_extra_copy = song_extra.copy()
    song_encoder = LabelEncoder()
    song_extra_copy["song_id_new"] = song_encoder.fit_transform(song_extra_copy["song_id"])
    song_extra_copy = song_extra_copy.drop(columns=["song_id"])

    mapping_table_song = pd.DataFrame(
        {
            "song_id_new": range(len(song_encoder.classes_)),
            "original_song_id": song_encoder.classes_,
        }
    )

    songs_copy = songs.merge(
        mapping_table_song, left_on="song_id", right_on="original_song_id", how="left"
    )
    songs_copy = songs_copy.drop(columns=["song_id", "original_song_id"])

    song_merge = songs_copy.merge(song_extra_copy, on="song_id_new", how="left")

    song_merge["has_isrc"] = song_merge["isrc"].notna().astype(int)
    song_merge["has_genre"] = song_merge["genre_ids"].notna().astype(int)
    song_merge["has_composer"] = song_merge["composer"].notna().astype(int)
    song_merge["has_lyricist"] = song_merge["lyricist"].notna().astype(int)
    song_merge["has_name"] = song_merge["name"].notna().astype(int)
    song_merge["has_song_extra"] = song_merge["song_id_new"].notna().astype(int)

    song_merge["song_length"] = song_merge["song_length"].fillna(
        song_merge["song_length"].median()
    )
    song_merge["genre_ids"] = song_merge["genre_ids"].fillna("unknown")
    song_merge["artist_name"] = song_merge["artist_name"].fillna("unknown")
    song_merge["composer"] = song_merge["composer"].fillna("unknown")
    song_merge["lyricist"] = song_merge["lyricist"].fillna("unknown")
    if "language" in song_merge.columns:
        song_merge["language"] = song_merge["language"].fillna(
            song_merge["language"].mode()[0]
        )
    song_merge["name"] = song_merge["name"].fillna("unknown")
    song_merge["isrc"] = song_merge["isrc"].fillna("NONE")
    song_merge["song_id_new"] = song_merge["song_id_new"].fillna(-1).astype(int)

    # --- Artist encoding: sorted unique artist_name -> integer ID (1-based) ---
    sorted_artists = sorted(song_merge["artist_name"].unique())
    artist_id_map: dict[str, int] = {
        name: idx + 1 for idx, name in enumerate(sorted_artists)
    }
    song_merge["artist_id"] = song_merge["artist_name"].map(artist_id_map)

    return song_merge, song_encoder, artist_id_map
