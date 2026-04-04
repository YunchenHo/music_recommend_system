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
    artist_name = models.CharField(max_length=255)
    artist_image = models.CharField(max_length=500, null=True, blank=True)
    language = models.CharField(max_length=50, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.artist_name


class Song(models.Model):
    song_title = models.CharField(max_length=255)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='songs')
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