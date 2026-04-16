import re

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.conf import settings
from django.contrib.auth import login
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from google.oauth2 import id_token
from google.auth.transport import requests

from .models import User, Artist, Song, UserOnboardingArtist, UserOnboardingSong, Playlist, PlaylistSong

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(ensure_csrf_cookie, name='dispatch')
class GoogleLoginView(APIView):
    def post(self, request):
        token = request.data.get('token')
        
        try:
            # 1. 驗證 Google ID Token
            # 注意：需在 settings.py 設定 GOOGLE_CLIENT_ID
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)

            # 2. 取得 email
            email = idinfo.get('email')

            '''
            # 因為不限制域名，所以不檢查
            if not email.endswith('@nycu.edu.tw') and not email.endswith('@g.nycu.edu.tw'):
                return Response({
                    "status": "error",
                    "message": "Only NYCU school emails are allowed.",
                    "code": "INVALID_DOMAIN"
                }, status=status.HTTP_403_FORBIDDEN)
            '''

            # 3. 取得或建立使用者 (核心邏輯：登入即註冊)
            user, created = User.objects.get_or_create(
                google_id=idinfo['sub'],
                defaults={
                    'email': email,
                    'google_name': idinfo.get('name', ''),
                    'username': email, # Django 必須有 username，暫時用 email 代替
                    'profile_picture': idinfo.get('picture', '')
                }
            )

            login(request, user)

            # 4. 回傳前端需要的 profile_completed 狀態
            return Response({
                "status": "success",
                "data": {
                    "profile_completed": user.profile_completed
                }
            }, status=status.HTTP_200_OK)

        except ValueError:
            # Token 無效或過期
            return Response({
                "status": "error",
                "message": "Google authentication failed. Please try again.",
                "code": "INVALID_GOOGLE_TOKEN"
            }, status=status.HTTP_401_UNAUTHORIZED)

class RegisterProfileView(APIView):
    permission_classes = [IsAuthenticated]
    VALID_LANGUAGES = {'Chinese', 'English', 'Japanese', 'Korean'}

    def post(self, request):
        user = request.user

        nickname = request.data.get('nickname', '').strip()
        gender = request.data.get('gender')
        age = request.data.get('age')
        languages = request.data.get('languages', [])
        other_language = request.data.get('other_language', '').strip()

        # 1. Nickname
        if not nickname or not re.fullmatch(r'[a-zA-Z0-9]{1,16}', nickname):
            return Response({
                "status": "error",
                "message": "Nickname must be 1-16 alphanumeric characters.",
                "code": "INVALID_NICKNAME",
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2. Gender
        if gender not in ('M', 'F', 'O'):
            return Response({
                "status": "error",
                "message": "Please select a gender.",
                "code": "INVALID_GENDER",
            }, status=status.HTTP_400_BAD_REQUEST)

        # 3. Age
        try:
            age = int(age)
            if age < 0 or age > 150:
                raise ValueError
        except (TypeError, ValueError):
            return Response({
                "status": "error",
                "message": "Age must be an integer between 0 and 150.",
                "code": "INVALID_AGE",
            }, status=status.HTTP_400_BAD_REQUEST)

        # 4. Languages
        if not isinstance(languages, list) or len(languages) == 0:
            return Response({
                "status": "error",
                "message": "Please select at least one language.",
                "code": "INVALID_LANGUAGES",
            }, status=status.HTTP_400_BAD_REQUEST)

        # 4b. "Other" must be Chinese characters ending with 文
        has_other = 'Other' in languages
        if has_other:
            if not other_language or not re.fullmatch(r'[\u4e00-\u9fff]+文', other_language):
                return Response({
                    "status": "error",
                    "message": "Please enter the language name in Chinese (e.g. 泰文).",
                    "code": "INVALID_OTHER_LANGUAGE",
                }, status=status.HTTP_400_BAD_REQUEST)

        # 4c. Validate language options
        base_languages = [lang for lang in languages if lang != 'Other']
        if not all(lang in self.VALID_LANGUAGES for lang in base_languages):
            return Response({
                "status": "error",
                "message": "Invalid language option detected.",
                "code": "INVALID_LANGUAGE_OPTION",
            }, status=status.HTTP_400_BAD_REQUEST)

        # --- Save ---
        user.nickname = nickname
        user.gender = gender
        user.age = age
        user.preferred_languages = ','.join(base_languages)
        user.other_language = other_language if has_other else ''
        user.profile_completed = True
        user.save()

        return Response({
            "status": "success",
            "message": "Registration complete.",
            }, status=status.HTTP_200_OK)


class AuthMeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        return Response({
            "status": "success",
            "data": {
                "username": user.nickname,
                "profile_picture": user.profile_picture,
            },
        }, status=status.HTTP_200_OK)

class OnboardingArtistsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        languages = request.query_params.get('languages', '')
        if not languages:
            return Response({
                "status": "error",
                "message": "Please provide languages parameter.",
                "code": "MISSING_LANGUAGES",
            }, status=status.HTTP_400_BAD_REQUEST)

        language_list = [lang.strip() for lang in languages.split(',') if lang.strip()]
        artists = Artist.objects.filter(language__in=language_list).values(
            'id', 'artist_name', 'artist_image', 'language'
        )

        return Response({
            "status": "success",
            "data": list(artists),
        }, status=status.HTTP_200_OK)

class OnboardingSongsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        languages = request.query_params.get('languages', '')
        if not languages:
            return Response({
                "status": "error",
                "message": "Please provide languages parameter.",
                "code": "MISSING_LANGUAGES",
            }, status=status.HTTP_400_BAD_REQUEST)

        language_list = [lang.strip() for lang in languages.split(',') if lang.strip()]
        songs = Song.objects.filter(language__in=language_list).select_related('artist')

        data = [
            {
                "id": song.id,
                "song_title": song.song_title,
                "artist_name": song.artist.artist_name,
                "song_image": song.song_image,
                "language": song.language,
            }
            for song in songs
        ]

        return Response({
            "status": "success",
            "data": data,
        }, status=status.HTTP_200_OK)

class OnboardingSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        artist_ids = request.data.get('artist_ids', [])
        song_ids = request.data.get('song_ids', [])

        if not isinstance(artist_ids, list) or len(artist_ids) == 0:
            return Response({
                "status": "error",
                "message": "Please select at least one artist.",
                "code": "INVALID_ARTISTS",
            }, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(song_ids, list) or len(song_ids) == 0:
            return Response({
                "status": "error",
                "message": "Please select at least one song.",
                "code": "INVALID_SONGS",
            }, status=status.HTTP_400_BAD_REQUEST)

        existing_artists = Artist.objects.filter(id__in=artist_ids)
        if existing_artists.count() != len(set(artist_ids)):
            return Response({
                "status": "error",
                "message": "Some artist IDs are invalid.",
                "code": "INVALID_ARTIST_IDS",
            }, status=status.HTTP_400_BAD_REQUEST)

        existing_songs = Song.objects.filter(id__in=song_ids)
        if existing_songs.count() != len(set(song_ids)):
            return Response({
                "status": "error",
                "message": "Some song IDs are invalid.",
                "code": "INVALID_SONG_IDS",
            }, status=status.HTTP_400_BAD_REQUEST)

        UserOnboardingArtist.objects.filter(user=user).delete()
        UserOnboardingSong.objects.filter(user=user).delete()

        UserOnboardingArtist.objects.bulk_create([
            UserOnboardingArtist(user=user, artist=artist)
            for artist in existing_artists
        ])
        UserOnboardingSong.objects.bulk_create([
            UserOnboardingSong(user=user, song=song)
            for song in existing_songs
        ])

        return Response({
            "status": "success",
            "message": "Onboarding complete.",
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Songs API: Recommendations + Favorites (archive playlist)
# ---------------------------------------------------------------------------

ARCHIVE_PLAYLIST_NAME = "archive"


class RecommendationsView(APIView):
    """GET /api/songs/recommendations — 取得推薦歌曲列表（目前為 placeholder）"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # TODO: 接上真正的推薦引擎，目前先隨機回傳 9 首歌
        songs = Song.objects.order_by('?')[:9]

        data = [
            {
                "id": song.id,
                "song_title": song.song_title,
                "artist_name": song.artist_name,
                "song_image": song.song_image,
                "language": song.language,
            }
            for song in songs
        ]

        return Response({
            "status": "success",
            "data": data,
        }, status=status.HTTP_200_OK)


class FavoritesView(APIView):
    """
    GET  /api/songs/favorites — 取得收藏歌曲列表
    POST /api/songs/favorites — 加入收藏 { "song_id": 123 }
    """
    permission_classes = [IsAuthenticated]

    def _get_or_create_archive(self, user):
        playlist, _ = Playlist.objects.get_or_create(
            user=user,
            playlist_name=ARCHIVE_PLAYLIST_NAME,
        )
        return playlist

    def get(self, request):
        try:
            playlist = Playlist.objects.get(
                user=request.user,
                playlist_name=ARCHIVE_PLAYLIST_NAME,
            )
        except Playlist.DoesNotExist:
            return Response({
                "status": "success",
                "data": [],
            }, status=status.HTTP_200_OK)

        playlist_songs = PlaylistSong.objects.filter(
            playlist=playlist
        ).select_related('song').order_by('-added_at')

        data = [
            {
                "id": ps.song.id,
                "song_title": ps.song.song_title,
                "artist_name": ps.song.artist_name,
            }
            for ps in playlist_songs
        ]

        return Response({
            "status": "success",
            "data": data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        song_id = request.data.get('song_id')

        if song_id is None:
            return Response({
                "status": "error",
                "message": "song_id is required.",
                "code": "MISSING_SONG_ID",
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            song = Song.objects.get(id=song_id)
        except Song.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Song not found.",
                "code": "SONG_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        playlist = self._get_or_create_archive(request.user)

        _, created = PlaylistSong.objects.get_or_create(
            playlist=playlist,
            song=song,
        )

        if not created:
            return Response({
                "status": "error",
                "message": "Song already in favorites.",
                "code": "ALREADY_FAVORITED",
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "status": "success",
            "message": "Song added to favorites.",
        }, status=status.HTTP_201_CREATED)


class FavoriteDetailView(APIView):
    """DELETE /api/songs/favorites/<song_id> — 移除收藏"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, song_id):
        try:
            playlist = Playlist.objects.get(
                user=request.user,
                playlist_name=ARCHIVE_PLAYLIST_NAME,
            )
        except Playlist.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Favorite not found.",
                "code": "NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        deleted, _ = PlaylistSong.objects.filter(
            playlist=playlist,
            song_id=song_id,
        ).delete()

        if deleted == 0:
            return Response({
                "status": "error",
                "message": "Song not in favorites.",
                "code": "NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "status": "success",
            "message": "Song removed from favorites.",
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Dev-only: 模擬登入（僅在 DEBUG=True 時可用）
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class DevLoginView(APIView):
    """POST /api/auth/dev-login — 開發環境模擬登入，自動建立測試用戶並建立 session"""

    def post(self, request):
        if not settings.DEBUG:
            return Response(status=status.HTTP_404_NOT_FOUND)

        username = request.data.get('username', 'testuser')

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'google_id': f'dev_{username}',
                'google_name': username,
                'email': f'{username}@dev.local',
                'nickname': username[:16],
                'profile_completed': True,
            }
        )

        login(request, user)

        return Response({
            "status": "success",
            "message": f"Logged in as {username}" + (" (created)" if created else ""),
            "data": {
                "user_id": user.id,
                "username": user.username,
                "sessionid": request.session.session_key,
            }
        }, status=status.HTTP_200_OK)
