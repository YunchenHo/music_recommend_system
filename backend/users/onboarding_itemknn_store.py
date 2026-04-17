"""將 ItemKNN onboarding 推薦結果寫入資料庫，供後續 API 直接讀取。"""

from __future__ import annotations

import logging

from django.db import transaction

from . import itemknn_service
from .models import (
    Song,
    UserItemKNNRawCandidate,
    UserItemKNNRecommendation,
    UserOnboardingSong,
)

logger = logging.getLogger(__name__)

DEFAULT_STORE_TOP_N = 30

# 向 ItemKNN 多要候選（矩陣每列仍只有 item_k 個鄰居，唯一候選數約為「種子數 × item_k」量級）。
# 設大一點可吃滿演算法能產生的排序結果，再篩進資料庫裡存在的 Song。
_INTERNAL_KNN_TOP_N_CAP = 8000


@transaction.atomic
def refresh_stored_itemknn_recommendations(user, top_n: int = DEFAULT_STORE_TOP_N) -> tuple[list[int], list[int]]:
    """
    依目前 UserOnboardingSong 種子重算並覆寫該使用者的快取推薦列。

    回傳 (recommended_song_ids, skipped_seed_ids)。
    若無種子，僅清空舊列並回傳 ([], [])。
    """
    seed_ids = list(
        UserOnboardingSong.objects.filter(user=user).values_list("song_id", flat=True)
    )
    UserItemKNNRecommendation.objects.filter(user=user).delete()
    UserItemKNNRawCandidate.objects.filter(user=user).delete()

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

    UserItemKNNRawCandidate.objects.bulk_create(
        [
            UserItemKNNRawCandidate(
                user=user,
                song_id=int(sid),
                score=float(sc),
                position=pos,
            )
            for pos, (sid, sc) in enumerate(zip(rec_ids, scores))
        ]
    )

    existing = set(Song.objects.filter(id__in=rec_ids).values_list("id", flat=True))
    rows: list[UserItemKNNRecommendation] = []
    pos = 0
    for sid, sc in zip(rec_ids, scores):
        if int(sid) not in existing:
            continue
        if pos >= top_n:
            break
        rows.append(
            UserItemKNNRecommendation(
                user=user,
                song_id=int(sid),
                score=float(sc),
                position=pos,
            )
        )
        pos += 1

    if not rows and rec_ids:
        logger.warning(
            "ItemKNN: no recommended song_id exists in Song table (KNN returned %d "
            "candidates; expand Song seed data or re-export artifact with larger --item-k).",
            len(rec_ids),
        )
    elif len(rows) < top_n and rec_ids:
        logger.warning(
            "ItemKNN: stored %d/%d recommendations: KNN ranked %d candidates but only %d of those "
            "song_ids exist in Song table (need overlap between artifact IDs and users_song rows).",
            len(rows),
            top_n,
            len(rec_ids),
            len(existing),
        )

    if rows:
        UserItemKNNRecommendation.objects.bulk_create(rows)

    return [r.song_id for r in rows], skipped
