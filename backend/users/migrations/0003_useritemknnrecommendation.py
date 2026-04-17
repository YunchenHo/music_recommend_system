# Generated manually for UserItemKNNRecommendation

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_artist_song_useronboardingartist_useronboardingsong"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserItemKNNRecommendation",
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
                ("score", models.FloatField()),
                ("position", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "song",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="itemknn_recommended_entries",
                        to="users.song",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="itemknn_recommendations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["position"],
            },
        ),
        migrations.AddConstraint(
            model_name="useritemknnrecommendation",
            constraint=models.UniqueConstraint(
                fields=("user", "position"),
                name="unique_user_itemknn_rec_position",
            ),
        ),
        migrations.AddConstraint(
            model_name="useritemknnrecommendation",
            constraint=models.UniqueConstraint(
                fields=("user", "song"),
                name="unique_user_itemknn_rec_song",
            ),
        ),
    ]
