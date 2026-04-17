import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_useritemknnrecommendation"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserItemKNNRawCandidate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("song_id", models.PositiveIntegerField()),
                ("score", models.FloatField()),
                ("position", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="itemknn_raw_candidates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["position"],
            },
        ),
        migrations.AddConstraint(
            model_name="useritemknnrawcandidate",
            constraint=models.UniqueConstraint(
                fields=("user", "position"),
                name="unique_user_itemknn_raw_position",
            ),
        ),
    ]
