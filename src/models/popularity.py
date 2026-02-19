import pandas as pd


def evaluate_popularity_loo(df_train: pd.DataFrame, df_test: pd.DataFrame, eval_k: int = 20) -> float:
    popular_songs = (
        df_train[df_train["target"] == 1]["song_id"].value_counts().head(eval_k).index.tolist()
    )

    hits = 0
    n_eval = 0
    pop_set = set(popular_songs)

    for target_song in df_test["song_id"]:
        n_eval += 1
        if target_song in pop_set:
            hits += 1

    return hits / n_eval if n_eval else 0.0
