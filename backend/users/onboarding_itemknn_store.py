"""將 ItemKNN onboarding 推薦結果寫入資料庫，供後續 API 直接讀取。"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from . import itemknn_service
from .models import (
    Song,
    RecommendationBatch,
    RecommendationItem,
    UserOnboardingSong,
)

logger = logging.getLogger(__name__)

DEFAULT_STORE_TOP_N = 30

# 向 ItemKNN 多要候選（矩陣每列仍只有 item_k 個鄰居，唯一候選數約為「種子數 × item_k」量級）。
# 設大一點可吃滿演算法能產生的排序結果，再篩進資料庫裡存在的 Song。
_INTERNAL_KNN_TOP_N_CAP = 8000

ALGORITHM_NAME = "ItemKNN"
ALGORITHM_VERSION = "v1.0"


@transaction.atomic
def refresh_stored_itemknn_recommendations(user, top_n: int = DEFAULT_STORE_TOP_N) -> tuple[list[int], list[int]]:
    """
    依目前 UserOnboardingSong 種子重算並覆寫該使用者的 ItemKNN 推薦批次。

    回傳 (recommended_song_ids, skipped_seed_ids)。
    若無種子，僅清空舊批次並回傳 ([], [])。
    """
    seed_ids = list(
        UserOnboardingSong.objects.filter(user=user).values_list("song_id", flat=True)
    )

    # 刪除該使用者的舊 ItemKNN 批次（CASCADE 會連帶刪除 RecommendationItem）
    RecommendationBatch.objects.filter(user=user, algorithm=ALGORITHM_NAME).delete()

    if not seed_ids:
        return [], []

    ask_n = min(_INTERNAL_KNN_TOP_N_CAP, max(top_n * 50, 500))
    rec_ids, scores, skipped = itemknn_service.recommend_song_ids_from_seed_song_ids(
        seed_ids,
        top_n=ask_n,
    )

    if not rec_ids:
        if skipped:
            logger.warning(
                "ItemKNN: all seed song_ids missing from artifact vocabulary: %s",
                skipped,
            )
        return [], skipped

    # 篩選出 Song 表中存在的推薦歌曲
    existing = set(Song.objects.filter(id__in=rec_ids).values_list("id", flat=True))
    filtered: list[tuple[int, float]] = []
    for sid, sc in zip(rec_ids, scores):
        if int(sid) not in existing:
            continue
        if len(filtered) >= top_n:
            break
        filtered.append((int(sid), float(sc)))

    if not filtered and rec_ids:
        logger.warning(
            "ItemKNN: no recommended song_id exists in Song table (KNN returned %d "
            "candidates; expand Song seed data or re-export artifact with larger --item-k).",
            len(rec_ids),
        )
    elif len(filtered) < top_n and rec_ids:
        logger.warning(
            "ItemKNN: stored %d/%d recommendations: KNN ranked %d candidates but only %d of those "
            "song_ids exist in Song table (need overlap between artifact IDs and users_song rows).",
            len(filtered),
            top_n,
            len(rec_ids),
            len(existing),
        )

    if not filtered:
        return [], skipped

    # 建立新的推薦批次
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

    return [sid for sid, _ in filtered], skipped
