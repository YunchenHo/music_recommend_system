"""
User feature encoding for LightFM hybrid cold-start inference.

Replicates the bucketing logic from recommender/src/preprocess/members.py
so that backend can convert DB User fields into the same feature tags
that were used during LightFM training.

Training feature tags:
  - bd_{0-6}       (age bucket)
  - gender_female / gender_male / gender_unknown
  - ms_{0-6}       (membership days bucket)
  - lang_pref_{code}  (language preference, from user's preferred_languages)
"""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone


# KKBOX language codes mapping from app language names
# 3=Chinese(Mandarin), 24=Cantonese, 52=English, 17=Japanese, 31=Korean
APP_LANG_TO_KKBOX_CODE: dict[str, list[int]] = {
    'Chinese': [3, 24],   # 國語 + 粵語
    'English': [52],
    'Japanese': [17],
    'Korean': [31],
}


def encode_user_features(
    age: int | None,
    gender: str | None,
    created_at: datetime | None,
    preferred_languages: str | None = None,
) -> list[str]:
    """Convert DB User fields to LightFM feature tags.

    Args:
        age: User's age (0-150). None or out-of-range defaults to bd_3.
        gender: 'M', 'F', or 'O'. None defaults to gender_unknown.
        created_at: User's registration datetime. None defaults to ms_0.
        preferred_languages: Comma-separated language names, e.g. "Chinese,English".
            None means no language preference tags are added.

    Returns:
        List of feature tag strings, e.g. ["bd_3", "gender_male", "ms_1", "lang_pref_3"]
    """
    # --- bd_group (age bucket) ---
    if age is None or age < 10 or age > 80:
        bd_group = 3  # default to young adult
    elif age <= 12:
        bd_group = 1
    elif age <= 18:
        bd_group = 2
    elif age <= 25:
        bd_group = 3
    elif age <= 35:
        bd_group = 4
    elif age <= 50:
        bd_group = 5
    else:
        bd_group = 6

    # --- gender ---
    gender_map = {"F": "gender_female", "M": "gender_male"}
    gender_tag = gender_map.get(gender, "gender_unknown")

    # --- ms_group (membership days bucket) ---
    if created_at is None:
        ms_group = 0
    else:
        days = (timezone.now() - created_at).days
        if days < 0:
            days = 0
        if days <= 30:
            ms_group = 0
        elif days <= 180:
            ms_group = 1
        elif days <= 365:
            ms_group = 2
        elif days <= 730:
            ms_group = 3
        elif days <= 1825:
            ms_group = 4
        elif days <= 3650:
            ms_group = 5
        else:
            ms_group = 6

    tags = [f"bd_{bd_group}", gender_tag, f"ms_{ms_group}"]

    # --- language preference ---
    if preferred_languages:
        for lang_name in preferred_languages.split(','):
            lang_name = lang_name.strip()
            codes = APP_LANG_TO_KKBOX_CODE.get(lang_name)
            if codes:
                for code in codes:
                    tags.append(f"lang_pref_{code}")

    return tags


def get_all_feature_names() -> list[str]:
    """All possible feature tag names (must match training pipeline)."""
    names = []
    for i in range(7):
        names.append(f"bd_{i}")
    names.extend(["gender_female", "gender_male", "gender_unknown"])
    for i in range(7):
        names.append(f"ms_{i}")
    # Language preference tags (known KKBOX codes)
    for code in [3, 10, 17, 24, 31, 45, 52, 59]:
        names.append(f"lang_pref_{code}")
    names.append("lang_pref_-1")
    return names
