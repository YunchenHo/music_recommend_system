"""
Add FULLTEXT INDEX with ngram parser on Song.song_title and Song.artist_name
for fast full-text search supporting CJK characters.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_recommendationbatch_recommendationitem'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE users_song ADD FULLTEXT INDEX ft_song_title_artist (song_title, artist_name) WITH PARSER ngram;",
            reverse_sql="ALTER TABLE users_song DROP INDEX ft_song_title_artist;",
        ),
    ]
