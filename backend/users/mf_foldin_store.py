"""將 MF Fold-in 推薦結果寫入資料庫，供 API 讀取。"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from . import mf_service
from .models import (
    History,
    Song,
    RecommendationBatch,
    RecommendationItem,
    UserSongLike,
)

logger = logging.getLogger(__name__)

ALGORITHM_NAME = "MF-FoldIn"
ALGORITHM_VERSION = "v1.0"
DEFAULT_TOP_N = 30
MIN_WATCH_SECONDS = 10


def _collect_interactions(user) -> tuple[list[dict], set[int]]:
    """
    從 DB 收集使用者的互動，組成 fold-in 所需的 interactions list。

    回傳:
      - interactions: [{"song_id": int, "target": 0 or 1}, ...]
        包含正樣本 + 明確負樣本 + 隨機負樣本
      - positive_song_ids: 正樣本的 song_id 集合
    """
    # 1. UserSongLike: 明確的 like / dislike
    likes = UserSongLike.objects.filter(user=user).values_list("song_id", "is_liked")
    liked_songs = set()
    disliked_songs = set()
    interactions = []

    for song_id, is_liked in likes:
        if is_liked:
            liked_songs.add(song_id)
            interactions.append({"song_id": song_id, "target": 1})
        else:
            disliked_songs.add(song_id)
            interactions.append({"song_id": song_id, "target": 0})

    # 2. History: watch_seconds >= 10, 且不在 like/dislike 中的不重複歌曲
    history_songs = (
        History.objects.filter(user=user, watch_seconds__gte=MIN_WATCH_SECONDS)
        .exclude(song_id__in=liked_songs | disliked_songs)
        .values_list("song_id", flat=True)
        .distinct()
    )
    history_song_set = set(history_songs)
    for song_id in history_song_set:
        interactions.append({"song_id": song_id, "target": 1})

    positive_song_ids = liked_songs | history_song_set
    all_interacted = positive_song_ids | disliked_songs

    # 3. 隨機負樣本 (1:1)
    negative_samples = mf_service.generate_negative_samples(
        positive_song_ids=positive_song_ids,
        all_interacted_song_ids=all_interacted,
        ratio=mf_service.MF_NEGATIVE_RATIO,
        seed=user.pk,
    )
    interactions.extend(negative_samples)

    return interactions, positive_song_ids


def get_positive_count(user) -> int:
    """取得使用者的正樣本數（用於判斷是否啟動 MF）。"""
    liked_count = UserSongLike.objects.filter(user=user, is_liked=True).count()
    # History 中不重複的歌曲（排除已有 like 的）
    liked_song_ids = set(
        UserSongLike.objects.filter(user=user).values_list("song_id", flat=True)
    )
    history_count = (
        History.objects.filter(user=user, watch_seconds__gte=MIN_WATCH_SECONDS)
        .exclude(song_id__in=liked_song_ids)
        .values_list("song_id", flat=True)
        .distinct()
        .count()
    )
    return liked_count + history_count


def should_refresh(user) -> bool:
    """判斷是否需要重算 MF 推薦。"""
    batch = RecommendationBatch.objects.filter(
        user=user, algorithm=ALGORITHM_NAME
    ).order_by("-generated_at").first()

    if batch is None:
        return True

    # 計算上次 batch 之後的新互動數
    since = batch.generated_at
    new_likes = UserSongLike.objects.filter(user=user, updated_at__gt=since).count()
    new_history = (
        History.objects.filter(user=user, played_at__gt=since, watch_seconds__gte=MIN_WATCH_SECONDS)
        .values_list("song_id", flat=True)
        .distinct()
        .count()
    )
    new_interactions = new_likes + new_history
    return new_interactions >= 30


@transaction.atomic
def refresh_stored_mf_recommendations(user, top_n: int = DEFAULT_TOP_N) -> tuple[list[int], bool]:
    """
    重算 MF Fold-in 推薦並寫入 DB。

    回傳 (recommended_song_ids, success)。
    若互動不足或計算失敗，回傳 ([], False)。
    """
    interactions, positive_song_ids = _collect_interactions(user)

    if len(positive_song_ids) < mf_service.MF_MIN_INTERACTIONS:
        return [], False

    result = mf_service.recommend_song_ids_for_user(interactions, top_n=top_n * 5)
    if result is None:
        return [], False

    rec_ids, scores = result

    if not rec_ids:
        logger.warning("[MF] fold-in returned no recommendations for user %s", user.pk)
        return [], False

    # 篩選 Song 表中存在的歌
    existing = set(Song.objects.filter(id__in=rec_ids).values_list("id", flat=True))
    filtered: list[tuple[int, float]] = []
    for sid, sc in zip(rec_ids, scores):
        if int(sid) not in existing:
            continue
        if len(filtered) >= top_n:
            break
        filtered.append((int(sid), float(sc)))

    if not filtered:
        logger.warning(
            "[MF] No recommended song_id exists in Song table (MF returned %d candidates).",
            len(rec_ids),
        )
        return [], False

    # 刪除舊 MF batch，寫入新 batch
    RecommendationBatch.objects.filter(user=user, algorithm=ALGORITHM_NAME).delete()

    batch = RecommendationBatch.objects.create(
        user=user,
        algorithm=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        generated_at=timezone.now(),
        total_size=len(filtered),
    )

    RecommendationItem.objects.bulk_create([
        RecommendationItem(
            batch=batch,
            rank=rank,
            song_id=sid,
            score=sc,
        )
        for rank, (sid, sc) in enumerate(filtered, start=1)
    ])

    return [sid for sid, _ in filtered], True
