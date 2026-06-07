from django.core.management.base import BaseCommand
from users.models import DailyChallenge

CHALLENGES = [
    (1, "聆聽", "首歌曲", 1, 5),
    (2, "加入", "首歌曲至收藏或個人清單", 1, 5),
    (3, "對", "首歌曲按讚或倒讚", 1, 5),
    (4, "重聽", "首歌曲", 1, 3),
    (5, "新創", "個清單", 1, 3),
    (6, "從推薦清單聆聽", "首歌曲", 1, 5),
]

# 已移除（邏輯複雜或改編號）
REMOVED_TYPES = [7, 8, 9]


class Command(BaseCommand):
    help = "Write the 6 daily challenge definitions into the DB (idempotent). Removes types 6/8/9."

    def handle(self, *args, **kwargs):
        # 刪除已不使用的類型（CASCADE 會一併刪掉相關 Progress 記錄）
        deleted, _ = DailyChallenge.objects.filter(challenge_type__in=REMOVED_TYPES).delete()
        if deleted:
            self.stdout.write(self.style.WARNING(f"Removed {deleted} obsolete challenge type(s): {REMOVED_TYPES}"))

        created = 0
        for challenge_type, prefix, suffix, min_n, max_n in CHALLENGES:
            _, is_new = DailyChallenge.objects.update_or_create(
                challenge_type=challenge_type,
                defaults={"prefix": prefix, "suffix": suffix,
                          "min_n": min_n, "max_n": max_n},
            )
            if is_new:
                created += 1

        updated = len(CHALLENGES) - created
        self.stdout.write(self.style.SUCCESS(
            f"Done. {created} new, {updated} updated."
        ))
