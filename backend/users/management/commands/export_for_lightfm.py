"""Export DB tables to CSV for the LightFM pipeline (and other recommender stages).

Output goes to `--output-dir` (e.g. `../data/db_processed/`) and feeds
`recommender/src/data/db_loader.py` on the recommender side.

Format choice: CSV (not parquet) so backend stays free of pyarrow/pandas deps.
The recommender side already reads CSV via `recommender/src/io.py::load_table()`.
"""

from pathlib import Path
import csv

from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery

from users.models import (
    Artist,
    History,
    Song,
    User,
    UserOnboardingArtist,
    UserOnboardingSong,
    UserSongAffinity,
    UserSongLike,
)


# Heuristic for distinguishing "real OAuth users" from "dataset-seeded users".
# Dev-only login at users/views.py::DevLoginView sets google_id="dev_<username>".
# Frontend team's dataset-seeded users follow the same pattern (per current convention).
# If that changes, override via --seeded-prefix.
_DEFAULT_SEEDED_PREFIX = "dev_"


class Command(BaseCommand):
    help = (
        "Export users/songs/interactions/onboarding to CSV for the LightFM pipeline. "
        "Tags users as 'seeded' (dataset/dev) vs 'real' (OAuth) via google_id prefix."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            type=Path,
            required=True,
            help="Directory to write the CSV files into (created if missing).",
        )
        parser.add_argument(
            "--seeded-prefix",
            type=str,
            default=_DEFAULT_SEEDED_PREFIX,
            help=(
                "google_id prefix that identifies dataset-seeded / dev users "
                f"(default: '{_DEFAULT_SEEDED_PREFIX}'). Users whose google_id "
                "starts with this prefix get source_tag='seeded'; others 'real'."
            ),
        )

    def handle(self, *args, **options):
        out_dir: Path = options["output_dir"]
        seeded_prefix: str = options["seeded_prefix"]
        out_dir.mkdir(parents=True, exist_ok=True)

        n_users = self._export_users(out_dir / "users.csv", seeded_prefix)
        n_songs = self._export_songs(out_dir / "songs.csv")
        n_interactions = self._export_interactions(out_dir / "interactions.csv")
        n_onboarding = self._export_onboarding(out_dir / "onboarding.csv")

        self.stdout.write(self.style.SUCCESS(
            f"Wrote to {out_dir}:\n"
            f"  users.csv         {n_users:>8} rows\n"
            f"  songs.csv         {n_songs:>8} rows\n"
            f"  interactions.csv  {n_interactions:>8} rows\n"
            f"  onboarding.csv    {n_onboarding:>8} rows"
        ))

    def _export_users(self, path: Path, seeded_prefix: str) -> int:
        fields = [
            "user_id", "google_id", "email", "nickname",
            "age", "gender", "preferred_languages",
            "profile_completed", "google_name", "source_tag", "created_at",
        ]
        seeded_count = 0
        real_count = 0
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for u in User.objects.all().iterator():
                tag = "seeded" if u.google_id.startswith(seeded_prefix) else "real"
                if tag == "seeded":
                    seeded_count += 1
                else:
                    real_count += 1
                writer.writerow({
                    "user_id": u.id,
                    "google_id": u.google_id,
                    "email": u.email,
                    "nickname": u.nickname or "",
                    "age": u.age if u.age is not None else "",
                    "gender": u.gender or "",
                    "preferred_languages": u.preferred_languages,
                    "profile_completed": int(u.profile_completed),
                    "google_name": u.google_name,
                    "source_tag": tag,
                    "created_at": u.created_at.isoformat(),
                })
        self.stdout.write(
            f"  users:        seeded={seeded_count}, real={real_count} "
            f"(prefix='{seeded_prefix}')"
        )
        return seeded_count + real_count

    def _export_songs(self, path: Path) -> int:
        fields = [
            "song_id", "song_title", "artist_id", "artist_name",
            "album_name", "language", "release_date",
        ]
        count = 0
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            # select_related to avoid N+1 on artist join
            for s in Song.objects.select_related("artist").iterator():
                writer.writerow({
                    "song_id": s.id,
                    "song_title": s.song_title,
                    "artist_id": s.artist_id,
                    "artist_name": s.artist_name or (s.artist.artist_name if s.artist_id else ""),
                    "album_name": s.album_name,
                    "language": s.language,
                    "release_date": s.release_date.isoformat() if s.release_date else "",
                })
                count += 1
        return count

    def _export_interactions(self, path: Path) -> int:
        """One row per History event, with is_liked + affinity_score joined in.

        UserSongLike / UserSongAffinity are unique per (user, song), so the same
        like_state / affinity score is repeated across plays of the same song —
        denormalization is intentional for offline analytics.
        """
        likes_sq = UserSongLike.objects.filter(
            user_id=OuterRef("user_id"),
            song_id=OuterRef("song_id"),
        ).values("is_liked")[:1]
        affinity_sq = UserSongAffinity.objects.filter(
            user_id=OuterRef("user_id"),
            song_id=OuterRef("song_id"),
        ).values("score")[:1]

        qs = (
            History.objects
            .annotate(
                is_liked=Subquery(likes_sq),
                affinity_score=Subquery(affinity_sq),
            )
            .values(
                "user_id", "song_id", "source",
                "watch_seconds", "played_at",
                "is_liked", "affinity_score",
            )
            .iterator()
        )

        fields = [
            "user_id", "song_id", "source", "watch_seconds",
            "played_at", "is_liked", "affinity_score",
        ]
        count = 0
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in qs:
                writer.writerow({
                    "user_id": row["user_id"],
                    "song_id": row["song_id"],
                    "source": row["source"],
                    "watch_seconds": row["watch_seconds"],
                    "played_at": row["played_at"].isoformat() if row["played_at"] else "",
                    "is_liked": "" if row["is_liked"] is None else int(row["is_liked"]),
                    "affinity_score": "" if row["affinity_score"] is None else row["affinity_score"],
                })
                count += 1
        return count

    def _export_onboarding(self, path: Path) -> int:
        fields = ["user_id", "kind", "entity_id", "created_at"]
        count = 0
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for oa in UserOnboardingArtist.objects.values(
                "user_id", "artist_id", "created_at"
            ).iterator():
                writer.writerow({
                    "user_id": oa["user_id"],
                    "kind": "artist",
                    "entity_id": oa["artist_id"],
                    "created_at": oa["created_at"].isoformat() if oa["created_at"] else "",
                })
                count += 1
            for os_ in UserOnboardingSong.objects.values(
                "user_id", "song_id", "created_at"
            ).iterator():
                writer.writerow({
                    "user_id": os_["user_id"],
                    "kind": "song",
                    "entity_id": os_["song_id"],
                    "created_at": os_["created_at"].isoformat() if os_["created_at"] else "",
                })
                count += 1
        return count
