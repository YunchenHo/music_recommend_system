from django.core.management.base import BaseCommand
from users.models import Artist, Song


class Command(BaseCommand):
    help = "Seed Artist and Song tables with onboarding data (using dataset IDs)"

    def handle(self, *args, **options):
        # --- Seed Artists (with dataset IDs) ---
        artists_data = [
            # Chinese
            {"id": 213320, "name": "Jay Chou", "image": "/artists/jaychou.jpg", "language": "Chinese"},
            {"id": 66286, "name": "G.E.M.", "image": "/artists/gem.jpg", "language": "Chinese"},
            {"id": 216168, "name": "JJ Lin", "image": "/artists/jjlin.jpg", "language": "Chinese"},
            {"id": 2528, "name": "A-Lin", "image": "/artists/alin.jpg", "language": "Chinese"},
            {"id": 218875, "name": "Jolin Tsai", "image": "/artists/jolin.jpg", "language": "Chinese"},
            {"id": 58626, "name": "Eric Chou", "image": "/artists/ericchou.jpg", "language": "Chinese"},
            {"id": 212101, "name": "Mayday", "image": "/artists/mayday.jpg", "language": "Chinese"},
            {"id": 216221, "name": "Yoga Lin", "image": "/artists/yogalin.jpg", "language": "Chinese"},
            # English
            {"id": 175638, "name": "Taylor Swift", "image": "/artists/taylorswift.jpg", "language": "English"},
            {"id": 54966, "name": "Ed Sheeran", "image": "/artists/edsheeran.jpg", "language": "English"},
            {"id": 21835, "name": "Billie Eilish", "image": "/artists/billie.jpg", "language": "English"},
            {"id": 186296, "name": "The Weeknd", "image": "/artists/theweeknd.jpg", "language": "English"},
            {"id": 13396, "name": "Ariana Grande", "image": "/artists/ariana.jpg", "language": "English"},
            {"id": 53286, "name": "Dua Lipa", "image": "/artists/dualipa.jpg", "language": "English"},
            {"id": 26702, "name": "Bruno Mars", "image": "/artists/brunomars.jpg", "language": "English"},
            {"id": 102703, "name": "Lady Gaga", "image": "/artists/ladygaga.jpg", "language": "English"},
            # Japanese
            {"id": 2998, "name": "AKB48", "image": "/artists/akb48.jpg", "language": "Japanese"},
            {"id": 97509, "name": "Kenshi Yonezu", "image": "/artists/yonezu.jpg", "language": "Japanese"},
            {"id": 5684, "name": "Aimer", "image": "/artists/aimer.jpg", "language": "Japanese"},
            {"id": 214422, "name": "Higedan", "image": "/artists/higedan.jpg", "language": "Japanese"},
            {"id": 105936, "name": "LiSA", "image": "/artists/lisa.jpg", "language": "Japanese"},
            {"id": 128744, "name": "Namie Amuro", "image": "/artists/namie.jpg", "language": "Japanese"},
            {"id": 204927, "name": "Yui Aragaki", "image": "/artists/yui.jpg", "language": "Japanese"},
            {"id": 111645, "name": "Mamoru Miyano", "image": "/artists/mamoru.jpg", "language": "Japanese"},
            # Korean
            {"id": 128087, "name": "NCT 127", "image": "/artists/nct127.jpg", "language": "Korean"},
            {"id": 16523, "name": "BLACKPINK", "image": "/artists/blackpink.jpg", "language": "Korean"},
            {"id": 157035, "name": "SUPER JUNIOR", "image": "/artists/superjunior.png", "language": "Korean"},
            {"id": 66449, "name": "GFRIEND", "image": "/artists/gfriend.jpg", "language": "Korean"},
            {"id": 79228, "name": "IU", "image": "/artists/iu.jpg", "language": "Korean"},
            {"id": 156534, "name": "SEVENTEEN", "image": "/artists/seventeen.jpg", "language": "Korean"},
            {"id": 69454, "name": "SNSD", "image": "/artists/snsd.jpg", "language": "Korean"},
            {"id": 54451, "name": "EXO", "image": "/artists/exo.jpg", "language": "Korean"},
        ]

        artist_map = {}  # artist_name -> Artist instance
        for a in artists_data:
            obj, _ = Artist.objects.update_or_create(
                id=a["id"],
                defaults={
                    "artist_name": a["name"],
                    "artist_image": a["image"],
                    "language": a["language"],
                },
            )
            artist_map[a["name"]] = obj

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(artists_data)} artists"))

        # --- Song artist name -> known artist_id mapping ---
        song_artist_to_known = {
            "周杰倫": 213320,
            "蔡依林": 218875,
            "五月天": 212101,
            "Ed Sheeran": 54966,
            "Taylor Swift": 175638,
            "The Weeknd": 186296,
            "Lady Gaga": 102703,
            "Yui Aragaki (新垣結衣)": 204927,
            "AKB48": 2998,
            "Namie Amuro (安室奈美恵)": 128744,
            "LiSA": 105936,
            "BLACKPINK": 16523,
            "SUPER JUNIOR": 157035,
            "IU": 79228,
            "EXO": 54451,
            "Girls' Generation": 69454,
        }

        # --- Seed Songs (with dataset IDs) ---
        songs_data = [
            # Chinese
            {"id": 1262202, "title": "晴天", "artist": "周杰倫", "language": "Chinese", "image": "/songs-cover/1262202.png"},
            {"id": 1654654, "title": "小幸運", "artist": "田馥甄", "language": "Chinese", "image": "/songs-cover/1654654.png"},
            {"id": 904399, "title": "夢醒時分", "artist": "伍佰 & China Blue", "language": "Chinese", "image": "/songs-cover/904399.png"},
            {"id": 551976, "title": "演員", "artist": "薛之謙", "language": "Chinese", "image": "/songs-cover/551976.png"},
            {"id": 1118607, "title": "告白氣球", "artist": "周杰倫", "language": "Chinese", "image": "/songs-cover/1118607.png"},
            {"id": 1262259, "title": "我很好騙", "artist": "動力火車", "language": "Chinese", "image": "/songs-cover/1262259.png"},
            {"id": 556389, "title": "說好的幸福呢", "artist": "周杰倫", "language": "Chinese", "image": "/songs-cover/556389.png"},
            {"id": 523020, "title": "焚情", "artist": "張信哲", "language": "Chinese", "image": "/songs-cover/523020.png"},
            {"id": 1589161, "title": "私奔到月球", "artist": "五月天", "language": "Chinese", "image": "/songs-cover/1589161.png"},
            {"id": 334128, "title": "夜會", "artist": "王菲", "language": "Chinese", "image": "/songs-cover/334128.png"},
            {"id": 1567790, "title": "如果可以", "artist": "韋禮安", "language": "Chinese", "image": "/songs-cover/1567790.png"},
            {"id": 803123, "title": "倒帶", "artist": "蔡依林", "language": "Chinese", "image": "/songs-cover/803123.png"},
            # English
            {"id": 689229, "title": "Shape of You", "artist": "Ed Sheeran", "language": "English", "image": "/songs-cover/689229.png"},
            {"id": 1919590, "title": "Love Story", "artist": "Taylor Swift", "language": "English", "image": "/songs-cover/1919590.png"},
            {"id": 1392127, "title": "Everglow", "artist": "Coldplay", "language": "English", "image": "/songs-cover/1392127.png"},
            {"id": 2109591, "title": "Photograph", "artist": "Ed Sheeran", "language": "English", "image": "/songs-cover/2109591.png"},
            {"id": 1453829, "title": "Someone Like You", "artist": "Adele", "language": "English", "image": "/songs-cover/1453829.png"},
            {"id": 13468, "title": "Losers", "artist": "The Weeknd", "language": "English", "image": "/songs-cover/13468.png"},
            {"id": 402252, "title": "Thinking Out Loud", "artist": "Ed Sheeran", "language": "English", "image": "/songs-cover/402252.png"},
            {"id": 1804300, "title": "All of Me", "artist": "John Legend", "language": "English", "image": "/songs-cover/1804300.png"},
            {"id": 139694, "title": "Do What U Want", "artist": "Lady Gaga", "language": "English", "image": "/songs-cover/139694.png"},
            {"id": 50398, "title": "The One That Got Away", "artist": "Katy Perry", "language": "English", "image": "/songs-cover/50398.png"},
            {"id": 416909, "title": "Eagle", "artist": "ABBA", "language": "English", "image": "/songs-cover/416909.png"},
            {"id": 1779285, "title": "Youth", "artist": "Daughter", "language": "English", "image": "/songs-cover/1779285.png"},
            # Japanese
            {"id": 1938707, "title": "うつし絵", "artist": "Yui Aragaki (新垣結衣)", "language": "Japanese", "image": "/songs-cover/1938707.png"},
            {"id": 1221880, "title": "誕生日の夜", "artist": "AKB48", "language": "Japanese", "image": "/songs-cover/1221880.png"},
            {"id": 1644537, "title": "ブラックアウト", "artist": "Tokyo Incidents", "language": "Japanese", "image": "/songs-cover/1644537.png"},
            {"id": 2155543, "title": "make it happen", "artist": "Namie Amuro (安室奈美恵)", "language": "Japanese", "image": "/songs-cover/2155543.png"},
            {"id": 1697710, "title": "shooting star", "artist": "Ai Otsuka (大塚愛)", "language": "Japanese", "image": "/songs-cover/1697710.png"},
            {"id": 422571, "title": "ドライフラワー", "artist": "優里", "language": "Japanese", "image": "/songs-cover/422571.png"},
            {"id": 1502091, "title": "Risky", "artist": "LiSA", "language": "Japanese", "image": "/songs-cover/1502091.png"},
            {"id": 552011, "title": "夏日情懷", "artist": "MISIA", "language": "Japanese", "image": "/songs-cover/552011.png"},
            {"id": 78734, "title": "ひまわりの約束", "artist": "秦基博", "language": "Japanese", "image": "/songs-cover/78734.png"},
            {"id": 1073371, "title": "Love in the Ice", "artist": "Tohoshinki (東方神起)", "language": "Japanese", "image": "/songs-cover/1073371.png"},
            {"id": 407150, "title": "胸キュン", "artist": "AOA", "language": "Japanese", "image": "/songs-cover/407150.png"},
            {"id": 925086, "title": "アイドル", "artist": "YOASOBI", "language": "Japanese", "image": "/songs-cover/925086.png"},
            # Korean
            {"id": 1867000, "title": "PLAYING WITH FIRE", "artist": "BLACKPINK", "language": "Korean", "image": "/songs-cover/1867000.png"},
            {"id": 792933, "title": "Believe", "artist": "SUPER JUNIOR", "language": "Korean", "image": "/songs-cover/792933.png"},
            {"id": 1021592, "title": "Shake It", "artist": "BIGBANG", "language": "Korean", "image": "/songs-cover/1021592.png"},
            {"id": 1358918, "title": "미운오리", "artist": "IU", "language": "Korean", "image": "/songs-cover/1358918.png"},
            {"id": 1543538, "title": "Very Very Very", "artist": "I.O.I", "language": "Korean", "image": "/songs-cover/1543538.png"},
            {"id": 2126048, "title": "THE LEADERS", "artist": "G-DRAGON", "language": "Korean", "image": "/songs-cover/2126048.png"},
            {"id": 335663, "title": "So Good", "artist": "Jay Park", "language": "Korean", "image": "/songs-cover/335663.png"},
            {"id": 308, "title": "My Romeo", "artist": "Jessi", "language": "Korean", "image": "/songs-cover/308.png"},
            {"id": 1217522, "title": "Growl", "artist": "EXO", "language": "Korean", "image": "/songs-cover/1217522.png"},
            {"id": 488759, "title": "Gee", "artist": "Girls' Generation", "language": "Korean", "image": "/songs-cover/488759.png"},
            {"id": 2096562, "title": "그렇게 하면 돼", "artist": "Lena Park", "language": "Korean", "image": "/songs-cover/2096562.png"},
            {"id": 1721221, "title": "왜 나만 아프죠", "artist": "IVY", "language": "Korean", "image": "/songs-cover/1721221.png"},
        ]

        # Build artist instance lookup (by name from artist_map, or by ID from known mapping)
        for name, aid in song_artist_to_known.items():
            if name not in artist_map:
                artist_map[name] = Artist.objects.get(id=aid)

        for s in songs_data:
            # Artist not yet in map -> create without explicit ID
            if s["artist"] not in artist_map:
                obj, _ = Artist.objects.get_or_create(
                    artist_name=s["artist"],
                    defaults={"language": s["language"]},
                )
                artist_map[s["artist"]] = obj

            Song.objects.update_or_create(
                id=s["id"],
                defaults={
                    "song_title": s["title"],
                    "artist": artist_map[s["artist"]],
                    "language": s["language"],
                    "song_image": s["image"],
                },
            )

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(songs_data)} songs"))