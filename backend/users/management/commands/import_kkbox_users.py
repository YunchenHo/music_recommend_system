import pandas as pd

from django.core.management.base import BaseCommand

from users.models import (
    User,
    Song,
    UserOnboardingSong,
    UserKKBoxProfile,
)

# Google user 對應 KKBOX msno
KKBOX_USERS = {
    "doonghuiyen@gmail.com": {
        "msno_id": 11372,
        "msno": "o+5RNlSWrzvrphgBNGIo1FLkGxBgyICns6qXj3nS7Pk=",
    },
    "yunchenbts0613@gmail.com": {
        "msno_id": 4739,
        "msno": "YTpPQjWoHZBKRsjmZCFgTwouQKfWA/cgG4LiQbpubtw=",
    },
    "jdjh70105@gmail.com": {
        "msno_id": 8771,
        "msno": "c6VEZ/zdVI3Zg5HkaU4Ayb6ZDcZad1lx7kL7d4pVkRQ=",
    },
    "hyc0603.mg12@nycu.edu.tw": {
        "msno_id": 9252,
        "msno": "eJP7ZSOy+X4USH8FmsI4SPl155s+8h65BoC8xE6dGmc=",
    },
    "dhy.mg12@nycu.edu.tw": {
        "msno_id": 7203,
        "msno": "VHpRaOzuJSgJb5VfbMLKnB6wVuCfBR4YRiStxK7XrN4=",
    },
    "nicolechen7923934@gmail.com": {
        "msno_id": 3456,
        "msno": "DqwB7smOAIbNnnQbWOpfsmy9znTwfDEQCW1I6ujFG48=",
    },
}


class Command(BaseCommand):

    help = "Import KKBOX old users"


    def handle(self, *args, **kwargs):

        # 讀取 train.csv
        train = pd.read_parquet(
            "/app/data/processed/train_encoded.parquet"
        )

        for email, info in KKBOX_USERS.items():
            msno_id = info["msno_id"]
            msno = info["msno"]

            self.stdout.write(f"\nProcessing {email}")

            try:
                user = User.objects.get(email=email)

            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"User not found: {email}"
                    )
                )
                continue

            UserKKBoxProfile.objects.update_or_create(
                user=user,
                defaults={
                    "msno": msno
                }
            )

            liked = train[
                (train["msno_id"] == msno_id) &
                (train["target"] == 1)
            ]

            song_ids = liked["song_id"].unique()[:100]

            count = 0

            for song_id in song_ids:

                try:
                    song = Song.objects.get(id=song_id)

                    UserOnboardingSong.objects.get_or_create(
                        user=user,
                        song=song
                    )

                    count += 1

                except Song.DoesNotExist:
                    continue

            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {count} songs"
                )
            )