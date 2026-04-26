import logging
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
from django.db import transaction

from google.oauth2 import id_token
from google.auth.transport import requests

from . import onboarding_itemknn_store
from .models import (
    User,
    Artist,
    Song,
    UserOnboardingArtist,
    UserOnboardingSong,
    Playlist,
    PlaylistSong,
    RecommendationBatch,
    RecommendationItem,
    History,
    UserSongLike,
)

logger = logging.getLogger(__name__)

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

        try:
            onboarding_itemknn_store.refresh_stored_itemknn_recommendations(user)
        except FileNotFoundError as exc:
            logger.warning("ItemKNN refresh skipped (artifact missing): %s", exc)
        except ValueError as exc:
            logger.warning("ItemKNN refresh skipped (invalid artifact): %s", exc)

        return Response({
            "status": "success",
            "message": "Onboarding complete.",
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Songs API: Recommendations + Favorites (archive playlist)
# ---------------------------------------------------------------------------

ARCHIVE_PLAYLIST_NAME = "archive"


class RecommendationsView(APIView):
    """GET /api/songs/recommendations — 取得推薦歌曲列表（ItemKNN）"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. 防呆：沒有 onboarding 種子歌曲
        seed_exists = UserOnboardingSong.objects.filter(user=user).exists()
        if not seed_exists:
            return Response({
                "status": "success",
                "data": [],
                "message": "No recommendations yet. Complete onboarding first.",
            }, status=status.HTTP_200_OK)

        # 2. 查找該使用者最新的推薦批次
        batch = RecommendationBatch.objects.filter(
            user=user,
        ).order_by('-generated_at').first()

        # 3. Fallback：DB 沒有推薦紀錄時自動算一次
        if batch is None:
            try:
                onboarding_itemknn_store.refresh_stored_itemknn_recommendations(user, top_n=30)
                batch = RecommendationBatch.objects.filter(
                    user=user,
                ).order_by('-generated_at').first()
            except FileNotFoundError as exc:
                logger.warning("ItemKNN refresh failed (artifact missing): %s", exc)
            except ValueError as exc:
                logger.warning("ItemKNN refresh failed (invalid artifact): %s", exc)

        if batch is None:
            return Response({
                "status": "success",
                "data": [],
                "message": "Recommendations temporarily unavailable.",
            }, status=status.HTTP_200_OK)

        # 4. 從批次中讀取前 9 首，帶出歌曲資訊
        items = (
            RecommendationItem.objects
            .filter(batch=batch)
            .select_related('song')
            .order_by('rank')[:9]
        )

        data = [
            {
                "rank": item.rank,
                "id": item.song.id,
                "song_title": item.song.song_title,
                "artist_name": item.song.artist_name,
                "song_image": item.song.song_image,
                "language": item.song.language,
            }
            for item in items
        ]

        return Response({
            "status": "success",
            "data": data,
        }, status=status.HTTP_200_OK)


class SongDetailView(APIView):
    """GET /api/songs/<song_id> — 取得單首歌曲詳細資訊（含收藏狀態）"""
    permission_classes = [IsAuthenticated]

    def get(self, request, song_id):
        try:
            song = Song.objects.get(id=song_id)
        except Song.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Song not found.",
                "code": "SONG_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        is_favorited = PlaylistSong.objects.filter(
            playlist__user=request.user,
            playlist__playlist_name=ARCHIVE_PLAYLIST_NAME,
            song=song,
        ).exists()

        return Response({
            "status": "success",
            "data": {
                "id": song.id,
                "song_title": song.song_title,
                "artist_name": song.artist_name,
                "album_name": song.album_name,
                "language": song.language,
                "song_image": song.song_image,
                "is_favorited": is_favorited,
            },
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

class HistoryView(APIView):
    """
    GET /api/history — 取得播放紀錄列表
    POST /api/history — 新增播放紀錄
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        song_id = request.data.get('song_id')
        watch_seconds = request.data.get('watch_seconds')
        source = request.data.get('source')

        if song_id is None:
            return Response({
                "status": "error",
                "message": "song_id is required.",
                "code": "MISSING_SONG_ID",
            }, status=status.HTTP_400_BAD_REQUEST)

        if watch_seconds is None:
            return Response({
                "status": "error",
                "message": "watch_seconds is required.",
                "code": "MISSING_WATCH_SECONDS",
            }, status=status.HTTP_400_BAD_REQUEST)

        if source is None or source == '': # source is not None and not empty
            return Response({
                "status": "error",
                "message": "source is required.",
                "code": "MISSING_SOURCE",
            }, status=status.HTTP_400_BAD_REQUEST)

        if source not in History.SourceChoices.values:
            return Response({
                "status": "error",
                "message": "Invalid source.",
                "code": "INVALID_SOURCE",
            }, status=status.HTTP_400_BAD_REQUEST)

        # Song exists check
        try:
            song = Song.objects.get(id=song_id)
        except Song.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Song not found.",
                "code": "SONG_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            watch_seconds = int(watch_seconds)
            if watch_seconds < 0:
                raise ValueError
        except ValueError:
            return Response(
                {
                    "status": "error",
                    "message": "watch_seconds must be an integer >= 0",
                    "code": "INVALID_WATCH_SECONDS",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        history = History.objects.create(user=user, song=song, watch_seconds=watch_seconds, source=source)

        return Response({
            "status": "success",
            "message": "History created.",
            "data": {
                "id": history.id,
                "song_id": history.song.id,
                "watch_seconds": history.watch_seconds,
                "source": history.source,
            },
        }, status=status.HTTP_201_CREATED)

    def get(self, request):
        user = request.user

        limit = request.query_params.get('limit', 20)
        offset = request.query_params.get('offset', 0)
        song_id = request.query_params.get('song_id')
        source = request.query_params.get('source')

        try:
            limit = int(limit)
            offset = int(offset)
            if limit <= 0 or offset < 0:
                raise ValueError
        except ValueError:
            return Response({
                "status": "error",
                "message": "Invalid limit or offset.",
                "code": "INVALID_LIMIT_OR_OFFSET",
            }, status=status.HTTP_400_BAD_REQUEST)

        queryset = History.objects.filter(user=user)

        if song_id is not None:
            queryset = queryset.filter(song_id=song_id)

        if source is not None:
            if source not in History.SourceChoices.values:
                return Response({
                    "status": "error",
                    "message": "Invalid source.",
                    "code": "INVALID_SOURCE",
                }, status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(source=source)

        queryset = queryset.order_by('-played_at') # 按 played_at 排序，最新在前

        # 取得總筆數
        total = queryset.count()
        queryset = queryset[offset:offset+limit]

        results = [ ]
        for history in queryset:
            results.append({
                "id": history.id,
                "song_id": history.song_id, # 這裡是直接取 history.song_id
                "watch_seconds": history.watch_seconds,
                "source": history.source,
                "created_at": history.created_at,
            })

        return Response({
            "status": "success",
            "data": results,
            "total": total,
            "limit": limit,
            "offset": offset,
        }, status=status.HTTP_200_OK)

class UserSongLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        song_id = request.data.get('song_id')
        intent_like = request.data.get('is_like') # 前端傳回來的意圖

        if not isinstance(intent_like, bool):
            return Response({"status": "error",
                "message": "is_like must be a boolean.",
                "code": "INVALID_IS_LIKE",
            }, status=status.HTTP_400_BAD_REQUEST)
        if not Song.objects.filter(id=song_id).exists():
            return Response({"status": "error",
                "message": "Song not found.",
                "code": "SONG_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        # 使用 transaction.atomic() 來確保操作的原子性
        with transaction.atomic():
            existing = UserSongLike.objects.select_for_update().filter(
                user=request.user,
                song_id=song_id,
            ).first()
            if existing and existing.is_liked == intent_like:
                existing.delete()
                return Response({"status": "success", "data": {"is_liked": None}})
            UserSongLike.objects.update_or_create(
                user=request.user, song_id=song_id,
                defaults={'is_liked': intent_like},
            )
        return Response({"status": "success", "data": {"is_liked": intent_like}})