import time

from django.core.management.base import BaseCommand, CommandError

from users.affinity_score import (
    compute_affinity_for_all_users,
    compute_affinity_for_user,
)
from users.models import User


class Command(BaseCommand):
    help = "Recompute UserSongAffinity scores in batch for one user or all users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=int,
            default=None,
            help="User id to refresh. If omitted, refreshes all users.",
        )

    def handle(self, *args, **options):
        user_id = options["user"]
        started = time.monotonic()

        if user_id is not None:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist as exc:
                raise CommandError(f"User id={user_id} does not exist.") from exc

            written = compute_affinity_for_user(user)
            elapsed = time.monotonic() - started
            self.stdout.write(self.style.SUCCESS(
                f"Refreshed affinity for user {user_id}: {written} rows in {elapsed:.2f}s."
            ))
            return

        written = compute_affinity_for_all_users()
        elapsed = time.monotonic() - started
        self.stdout.write(self.style.SUCCESS(
            f"Refreshed affinity for all users: {written} rows in {elapsed:.2f}s."
        ))
