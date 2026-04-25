from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator

class User(AbstractUser):
    password = None
    # 內建欄位
    # 將內建欄位設為可留白，且不顯示在表單中
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)

    # 1. 名稱：限英文數字大小寫，16字元以內
    # 使用 RegexValidator 確保只能輸入英數字
    nickname = models.CharField(
        max_length=16,
        validators=[RegexValidator(r'^[a-zA-Z0-9]*$', '僅限英文字母與數字')],
        null=True,
        blank=True
    )

    # 2. 性別：男、女、其他
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True)

    # 3. 年齡：0~150 的整數
    age = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(150)],
        null=True
    )

    # 4. 喜歡的語言：因為是複選，存成逗號分隔的字串，例如 "Chinese,English,Japanese"
    preferred_languages = models.CharField(max_length=255, default='Chinese')
    
    # 針對「其他」自行輸入的國家語言
    other_language = models.CharField(max_length=50, blank=True, null=True)

    # 前端規格要求的其他欄位
    google_id = models.CharField(max_length=255, unique=True, null=False)
    google_name = models.CharField(max_length=255, blank=True) # 存 Google 給的全名 (不限格式)
    profile_picture = models.URLField(max_length=500, null=True, blank=True)
    profile_completed = models.BooleanField(default=False)
    
    # 時間戳記
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # 有暱稱秀暱稱 -> 沒暱稱秀 Google 名 -> 都沒有就秀 Email/Username
        return self.nickname or self.google_name or self.username

class Artist(models.Model):
    id = models.IntegerField(primary_key=True)
    artist_name = models.CharField(max_length=255)
    artist_image = models.CharField(max_length=500, null=True, blank=True)
    language = models.CharField(max_length=50, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.artist_name


class Song(models.Model):
    id = models.IntegerField(primary_key=True)
    song_title = models.CharField(max_length=255)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='songs')
    artist_name = models.CharField(max_length=255, blank=True, default='')
    album_name = models.CharField(max_length=255, blank=True, default='')
    language = models.CharField(max_length=50, blank=True, default='')
    song_image = models.CharField(max_length=500, null=True, blank=True)
    release_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.song_title


class UserOnboardingArtist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='onboarding_artists')
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='onboarding_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'artist'], name='unique_user_onboarding_artist')
        ]

    def __str__(self):
        return f"{self.user} - {self.artist}"


class UserOnboardingSong(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='onboarding_songs')
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='onboarding_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'song'], name='unique_user_onboarding_song')
        ]

    def __str__(self):
        return f"{self.user} - {self.song}"


class Playlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='playlists')
    playlist_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.playlist_name}"


class PlaylistSong(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='songs')
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='in_playlists')
    added_at = models.DateTimeField(auto_now_add=True)
    sort_order = models.SmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['playlist', 'song'], name='unique_playlist_song')
        ]

    def __str__(self):
        return f"{self.playlist.playlist_name} - {self.song.song_title}"


class RecommendationBatch(models.Model):
    """一次推薦批次，記錄使用的演算法與版本。"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendation_batches')
    algorithm = models.CharField(max_length=50)
    algorithm_version = models.CharField(max_length=50, blank=True, default='')
    generated_at = models.DateTimeField()
    total_size = models.SmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.algorithm} @ {self.generated_at}"


class RecommendationItem(models.Model):
    """推薦批次中的單首歌曲，依 rank 排序。"""

    batch = models.ForeignKey(RecommendationBatch, on_delete=models.CASCADE, related_name='items')
    rank = models.SmallIntegerField()
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='recommendation_entries')
    score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rank']
        constraints = [
            models.UniqueConstraint(fields=['batch', 'rank'], name='unique_batch_rank'),
            models.UniqueConstraint(fields=['batch', 'song'], name='unique_batch_song'),
        ]

    def __str__(self):
        return f"Batch {self.batch_id} #{self.rank} → {self.song_id}"

class History(models.Model):
    # 定義 ENUM 選項，左邊是存進資料庫的值，右邊是給人看的標籤
    class SourceChoices(models.TextChoices):
        RECOMMENDATION = 'RECOMMENDATION', '推薦系統'
        SEARCH = 'SEARCH', '主動搜尋'
        PLAYLIST = 'PLAYLIST', '播放清單'
        ONBOARDING = 'ONBOARDING', '冷啟動預選'
        FRIEND = 'FRIEND', '好友也在聽'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='histories')
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='histories')
    played_at = models.DateTimeField(auto_now_add=True)
    watch_seconds = models.IntegerField()
    # 使用 choices 來嚴格限制傳入的值
    source = models.CharField(max_length=20, choices=SourceChoices.choices, default=SourceChoices.RECOMMENDATION)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 效能加速器：針對「尋找特定用戶的紀錄並依時間排序」進行優化
        indexes = [
            models.Index(fields=['user', '-played_at']),
        ]

    def __str__(self):
        return f"{self.user.username} 聽了 {self.song.song_title} ({self.watch_seconds}秒)"