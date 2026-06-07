from django.db import migrations


ICONS = [
    "yeah-rabbit.svg",
    "mifi.svg",
    "jojo.svg",
    "egg.svg",
    "ahhh.svg",
    "angry_heart.svg",
    "chicken_nugget.svg",
    "one_punch.svg",
    "cutie.svg",
    "star.svg",
    "tail.svg",
]


def seed_icons(apps, schema_editor):
    PlaylistIcon = apps.get_model('users', 'PlaylistIcon')
    for filename in ICONS:
        PlaylistIcon.objects.get_or_create(filename=filename)


def remove_icons(apps, schema_editor):
    PlaylistIcon = apps.get_model('users', 'PlaylistIcon')
    PlaylistIcon.objects.filter(filename__in=ICONS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_playlisticon_playlist_icon'),
    ]

    operations = [
        migrations.RunPython(seed_icons, remove_icons),
    ]
