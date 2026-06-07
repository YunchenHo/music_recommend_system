from pathlib import Path
import pandas as pd

SCRIPT_DIR = Path(__file__).parent          # recommender/scripts/
RECOMMENDER_DIR = SCRIPT_DIR.parent         # recommender/
PROJECT_DIR = RECOMMENDER_DIR.parent        # music_recommend_system/

DATA_DIR = PROJECT_DIR / "data" / "processed"
ARTIFACTS_DIR = RECOMMENDER_DIR / "artifacts"

# =========================
# 讀資料
# =========================

members = pd.read_parquet(DATA_DIR / "complete_members.parquet")

train = pd.read_parquet(DATA_DIR / "train_encoded.parquet")

songs = pd.read_csv(ARTIFACTS_DIR / "song_for_db.csv")

# =========================
# 只保留 target == 1
# =========================

liked = train[train["target"] == 1]

# =========================
# 找 top 5000 users
# =========================

top5000 = (
    liked.groupby("msno_id")
    .size()
    .sort_values(ascending=False)
    .head(5000)
    .reset_index(name="like_count")
)

print("Top5000 users:", len(top5000))

# =========================
# merge members
# =========================

top5000_members = top5000.merge(
    members,
    on="msno_id",
    how="left"
)

# =========================
# merge song language
# =========================

liked_with_lang = liked.merge(
    songs[["song_id", "language"]],
    on="song_id",
    how="left"
)

# =========================
# 語言對照
# =========================

LANGUAGE_MAP = {
    3.0: "Chinese",
    52.0: "English",
    17.0: "Japanese",
    31.0: "Korean",
}

# =========================
# 計算 preferred_languages
# =========================

language_rows = []

for msno_id in top5000["msno_id"]:

    user_df = liked_with_lang[
        liked_with_lang["msno_id"] == msno_id
    ]

    lang_counts = (
        user_df["language"]
        .value_counts()
        .to_dict()
    )

    total = sum(
        lang_counts.get(code, 0)
        for code in LANGUAGE_MAP.keys()
    )

    if total == 0:
        preferred = "Unknown"

    else:

        ratios = {
            LANGUAGE_MAP[code]:
            lang_counts.get(code, 0) / total
            for code in LANGUAGE_MAP.keys()
        }

        # 如果某語言 >= 70%
        major_lang = [
            lang
            for lang, ratio in ratios.items()
            if ratio >= 0.7
        ]

        if len(major_lang) > 0:
            preferred = major_lang[0]

        else:
            # 否則取 >= 30% 的語言
            selected = [
                lang
                for lang, ratio in ratios.items()
                if ratio >= 0.3
            ]

            if len(selected) > 0:
                preferred = ",".join(selected)

            else:
                preferred = "Chinese,English,Japanese,Korean"

    language_rows.append({
        "msno_id": msno_id,
        "preferred_languages": preferred
    })

# =========================
# merge preferred_languages
# =========================

language_df = pd.DataFrame(language_rows)

final_df = top5000_members.merge(
    language_df,
    on="msno_id",
    how="left"
)

# =========================
# 輸出
# =========================

final_df.to_csv(
    DATA_DIR / "top5000_members_with_language.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\nSaved:")
print("data/processed/top5000_members_with_language.csv")

print("\nPreferred language distribution:")
print(
    final_df["preferred_languages"]
    .value_counts()
)