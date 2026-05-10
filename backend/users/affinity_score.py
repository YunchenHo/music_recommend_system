"""使用者對歌曲的偏好分數（affinity）批次計算。

訊號來源：
- History.watch_seconds（單次 < SKIP_THRESHOLD_SECONDS 視為 skip，分開計）
- PlaylistSong（在 archive playlist 中視為收藏）
- UserSongLike.is_liked

最終分數 clip 到 [SCORE_MIN, SCORE_MAX]，寫入 UserSongAffinity 表。
"""

from __future__ import annotations

import logging
from collections import defaultdict

from django.db import transaction
from django.db.models import Count, Q, Sum

from .models import (
    History,
    PlaylistSong,
    User,
    UserSongAffinity,
    UserSongLike,
)

logger = logging.getLogger(__name__)


# --- 權重設定（調權重只改這裡） ----------------------------------------------

# 聽歌秒數分桶：(上限秒數, 加分)；上限為 inf 代表最後一桶
WATCH_BUCKETS: list[tuple[float, float]] = [
    (10, 0.0),
    (30, 0.1),
    (60, 0.3),
    (180, 0.5),
    (float('inf'), 0.7),
]

SKIP_THRESHOLD_SECONDS = 5
SKIP_PENALTY_PER_EVENT = -0.1
SKIP_PENALTY_FLOOR = -0.5

LIKE_WEIGHT = 0.5
DISLIKE_WEIGHT = -1.0
FAVORITE_WEIGHT = 0.5

SCORE_MIN = -1.0
SCORE_MAX = 1.0

# 重排與過濾參數（供 RecommendationsView 使用）
AFFINITY_FILTER_THRESHOLD = -0.5  # affinity 低於此值的候選歌將從推薦結果中移除

# 與 views.ARCHIVE_PLAYLIST_NAME 對齊
ARCHIVE_PLAYLIST_NAME = "archive"


# --- 公開 API ---------------------------------------------------------------

@transaction.atomic
def compute_affinity_for_user(user) -> int:
    """聚合該使用者所有訊號並覆寫 UserSongAffinity。回傳寫入筆數。"""
    user_id = user.id if hasattr(user, 'id') else int(user)

    # 以 song_id 為 key 聚合各種原始訊號
    aggregates: dict[int, dict] = defaultdict(_empty_aggregate)

    # 1) History：分桶秒數 + skip 次數
    history_rows = (
        History.objects
        .filter(user_id=user_id)
        .values('song_id')
        .annotate(
            total=Sum('watch_seconds', filter=Q(watch_seconds__gte=SKIP_THRESHOLD_SECONDS)),
            skips=Count('id', filter=Q(watch_seconds__lt=SKIP_THRESHOLD_SECONDS)),
        )
    )
    for row in history_rows:
        agg = aggregates[row['song_id']]
        agg['total_watch_seconds'] = int(row['total'] or 0)
        agg['skip_count'] = int(row['skips'] or 0)

    # 2) UserSongLike：like / dislike 狀態
    like_rows = UserSongLike.objects.filter(user_id=user_id).values_list('song_id', 'is_liked')
    for song_id, is_liked in like_rows:
        aggregates[song_id]['like_state'] = 1 if is_liked else -1

    # 3) PlaylistSong：是否在 archive playlist
    favorite_rows = (
        PlaylistSong.objects
        .filter(
            playlist__user_id=user_id,
            playlist__playlist_name=ARCHIVE_PLAYLIST_NAME,
        )
        .values_list('song_id', flat=True)
    )
    for song_id in favorite_rows:
        aggregates[song_id]['is_favorited'] = True

    # 沒有任何訊號就清掉舊資料、結束
    UserSongAffinity.objects.filter(user_id=user_id).delete()
    if not aggregates:
        return 0

    rows = [
        UserSongAffinity(
            user_id=user_id,
            song_id=song_id,
            total_watch_seconds=agg['total_watch_seconds'],
            skip_count=agg['skip_count'],
            is_favorited=agg['is_favorited'],
            like_state=agg['like_state'],
            score=_compute_score(agg),
        )
        for song_id, agg in aggregates.items()
    ]

    UserSongAffinity.objects.bulk_create(rows, batch_size=1000)
    return len(rows)


def compute_affinity_for_all_users() -> int:
    """對所有使用者重新計算 affinity，回傳總寫入筆數。"""
    total = 0
    user_ids = User.objects.values_list('id', flat=True)
    for user_id in user_ids:
        total += compute_affinity_for_user(user_id)
    return total


# --- 內部工具 ---------------------------------------------------------------

def _empty_aggregate() -> dict:
    return {
        'total_watch_seconds': 0,
        'skip_count': 0,
        'is_favorited': False,
        'like_state': 0,
    }


def _bucket_watch_seconds(seconds: int) -> float:
    for upper, weight in WATCH_BUCKETS:
        if seconds < upper:
            return weight
    return WATCH_BUCKETS[-1][1]


def _compute_score(agg: dict) -> float:
    score = 0.0
    score += _bucket_watch_seconds(agg['total_watch_seconds'])
    score += max(SKIP_PENALTY_PER_EVENT * agg['skip_count'], SKIP_PENALTY_FLOOR)
    if agg['is_favorited']:
        score += FAVORITE_WEIGHT
    if agg['like_state'] == 1:
        score += LIKE_WEIGHT
    elif agg['like_state'] == -1:
        score += DISLIKE_WEIGHT
    return max(SCORE_MIN, min(SCORE_MAX, score))
