"""
User feature encoding for LightFM hybrid cold-start inference.

Replicates the bucketing logic from recommender/src/preprocess/members.py
so that backend can convert DB User fields into the same feature tags
that were used during LightFM training.

Training feature tags (3 total):
  - bd_{0-6}       (age bucket)
  - gender_female / gender_male / gender_unknown
  - ms_{0-6}       (membership days bucket)
"""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone


def encode_user_features(age: int | None, gender: str | None, created_at: datetime | None) -> list[str]:
    """Convert DB User fields to LightFM feature tags.

    Args:
        age: User's age (0-150). None or out-of-range defaults to bd_3.
        gender: 'M', 'F', or 'O'. None defaults to gender_unknown.
        created_at: User's registration datetime. None defaults to ms_0.

    Returns:
        List of 3 feature tag strings, e.g. ["bd_3", "gender_male", "ms_1"]
    """
    # --- bd_group (age bucket) ---
    # Bins: (-1,0], (0,12], (12,18], (18,25], (25,35], (35,50], (50,80]
    # Labels:  0       1       2        3        4        5        6
    # Training filters age to 10-80, so group 0 is effectively unused.
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
    # Bins: [0,30], (30,180], (180,365], (365,730], (730,1825], (1825,3650], (3650,inf)
    # Labels: 0       1         2          3          4           5           6
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

    return [f"bd_{bd_group}", gender_tag, f"ms_{ms_group}"]
