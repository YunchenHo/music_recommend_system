import logging
import re

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.conf import settings
from django.contrib.auth import login
from django.db import connection
from django.db.models import Count
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


# ---------------------------------------------------------------------------
# Playlists API: CRUD for playlists and playlist songs
# ---------------------------------------------------------------------------


class PlaylistListCreateView(APIView):
    """
    GET  /api/playlists/      — 列出使用者自訂清單（排除 archive）+ 歌曲數量
    POST /api/playlists/      — 建立新清單 { "playlist_name": "..." }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        playlists = (
            Playlist.objects
            .filter(user=request.user)
            .exclude(playlist_name=ARCHIVE_PLAYLIST_NAME)
            .annotate(song_count=Count('songs'))
            .order_by('created_at')
        )

        data = [
            {
                "id": p.id,
                "playlist_name": p.playlist_name,
                "song_count": p.song_count,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in playlists
        ]

        return Response({
            "status": "success",
            "data": data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        playlist_name = request.data.get('playlist_name', '').strip()

        if not playlist_name:
            return Response({
                "status": "error",
                "message": "Playlist name is required.",
                "code": "MISSING_PLAYLIST_NAME",
            }, status=status.HTTP_400_BAD_REQUEST)

        if playlist_name.lower() == ARCHIVE_PLAYLIST_NAME:
            return Response({
                "status": "error",
                "message": "Cannot use reserved playlist name.",
                "code": "RESERVED_NAME",
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(playlist_name) > 255:
            return Response({
                "status": "error",
                "message": "Playlist name is too long (max 255 characters).",
                "code": "NAME_TOO_LONG",
            }, status=status.HTTP_400_BAD_REQUEST)

        playlist = Playlist.objects.create(
            user=request.user,
            playlist_name=playlist_name,
        )

        return Response({
            "status": "success",
            "message": "Playlist created.",
            "data": {
                "id": playlist.id,
                "playlist_name": playlist.playlist_name,
                "song_count": 0,
                "created_at": playlist.created_at.isoformat(),
                "updated_at": playlist.updated_at.isoformat(),
            },
        }, status=status.HTTP_201_CREATED)


class PlaylistDetailView(APIView):
    """
    PATCH  /api/playlists/<id>/  — 修改清單名稱
    DELETE /api/playlists/<id>/  — 刪除清單
    """
    permission_classes = [IsAuthenticated]

    def _get_playlist(self, request, playlist_id):
        """取得清單，確認屬於當前使用者。回傳 (playlist, error_response)。"""
        try:
            playlist = Playlist.objects.get(id=playlist_id, user=request.user)
        except Playlist.DoesNotExist:
            return None, Response({
                "status": "error",
                "message": "Playlist not found.",
                "code": "PLAYLIST_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)
        return playlist, None

    def patch(self, request, playlist_id):
        playlist, err = self._get_playlist(request, playlist_id)
        if err:
            return err

        if playlist.playlist_name == ARCHIVE_PLAYLIST_NAME:
            return Response({
                "status": "error",
                "message": "Cannot rename the archive playlist.",
                "code": "CANNOT_MODIFY_ARCHIVE",
            }, status=status.HTTP_403_FORBIDDEN)

        new_name = request.data.get('playlist_name', '').strip()
        if not new_name:
            return Response({
                "status": "error",
                "message": "Playlist name is required.",
                "code": "MISSING_PLAYLIST_NAME",
            }, status=status.HTTP_400_BAD_REQUEST)

        if new_name.lower() == ARCHIVE_PLAYLIST_NAME:
            return Response({
                "status": "error",
                "message": "Cannot use reserved playlist name.",
                "code": "RESERVED_NAME",
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(new_name) > 255:
            return Response({
                "status": "error",
                "message": "Playlist name is too long (max 255 characters).",
                "code": "NAME_TOO_LONG",
            }, status=status.HTTP_400_BAD_REQUEST)

        playlist.playlist_name = new_name
        playlist.save()

        return Response({
            "status": "success",
            "message": "Playlist renamed.",
            "data": {
                "id": playlist.id,
                "playlist_name": playlist.playlist_name,
            },
        }, status=status.HTTP_200_OK)

    def delete(self, request, playlist_id):
        playlist, err = self._get_playlist(request, playlist_id)
        if err:
            return err

        if playlist.playlist_name == ARCHIVE_PLAYLIST_NAME:
            return Response({
                "status": "error",
                "message": "Cannot delete the archive playlist.",
                "code": "CANNOT_DELETE_ARCHIVE",
            }, status=status.HTTP_403_FORBIDDEN)

        playlist.delete()

        return Response({
            "status": "success",
            "message": "Playlist deleted.",
        }, status=status.HTTP_200_OK)


class PlaylistSongListCreateView(APIView):
    """
    GET  /api/playlists/<id>/songs/  — 取得清單內歌曲
    POST /api/playlists/<id>/songs/  — 加歌到清單 { "song_id": 123 }
    """
    permission_classes = [IsAuthenticated]

    def _get_playlist(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id, user=request.user)
        except Playlist.DoesNotExist:
            return None, Response({
                "status": "error",
                "message": "Playlist not found.",
                "code": "PLAYLIST_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)
        return playlist, None

    def get(self, request, playlist_id):
        playlist, err = self._get_playlist(request, playlist_id)
        if err:
            return err

        playlist_songs = (
            PlaylistSong.objects
            .filter(playlist=playlist)
            .select_related('song')
            .order_by('-added_at')
        )

        data = [
            {
                "id": ps.song.id,
                "song_title": ps.song.song_title,
                "artist_name": ps.song.artist_name,
                "song_image": ps.song.song_image,
                "album_name": ps.song.album_name,
                "added_at": ps.added_at.isoformat(),
            }
            for ps in playlist_songs
        ]

        return Response({
            "status": "success",
            "data": data,
        }, status=status.HTTP_200_OK)

    def post(self, request, playlist_id):
        playlist, err = self._get_playlist(request, playlist_id)
        if err:
            return err

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

        _, created = PlaylistSong.objects.get_or_create(
            playlist=playlist,
            song=song,
        )

        if not created:
            return Response({
                "status": "error",
                "message": "Song already in this playlist.",
                "code": "ALREADY_IN_PLAYLIST",
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "status": "success",
            "message": "Song added to playlist.",
        }, status=status.HTTP_201_CREATED)


class PlaylistSongDetailView(APIView):
    """DELETE /api/playlists/<id>/songs/<song_id>/ — 從清單移除歌曲"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, playlist_id, song_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id, user=request.user)
        except Playlist.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Playlist not found.",
                "code": "PLAYLIST_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        deleted, _ = PlaylistSong.objects.filter(
            playlist=playlist,
            song_id=song_id,
        ).delete()

        if deleted == 0:
            return Response({
                "status": "error",
                "message": "Song not in this playlist.",
                "code": "NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "status": "success",
            "message": "Song removed from playlist.",
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Search API: FULLTEXT search on song_title + artist_name
# ---------------------------------------------------------------------------

class SearchSongsView(APIView):
    """
    GET /api/songs/search?q=keyword — 搜尋歌曲
    使用 MySQL FULLTEXT INDEX (ngram parser) 做全文搜尋，
    以相關性分數排序，回傳前 20 筆結果。
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()

        if not query:
            return Response({
                "status": "error",
                "message": "Search query is required.",
                "code": "MISSING_QUERY",
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(query) > 100:
            return Response({
                "status": "error",
                "message": "Search query is too long (max 100 characters).",
                "code": "QUERY_TOO_LONG",
            }, status=status.HTTP_400_BAD_REQUEST)

        # 使用 MySQL FULLTEXT MATCH ... AGAINST 搜尋
        # IN BOOLEAN MODE 支援部分匹配；用 + 和 * 強化匹配效果
        # 若 FULLTEXT INDEX 尚未建立，會 fallback 到 icontains
        try:
            sql = """
                SELECT id, song_title, artist_name, album_name, song_image, language,
                       MATCH(song_title, artist_name) AGAINST(%s IN BOOLEAN MODE) AS relevance
                FROM users_song
                WHERE MATCH(song_title, artist_name) AGAINST(%s IN BOOLEAN MODE)
                ORDER BY relevance DESC
                LIMIT 20
            """
            # 在 BOOLEAN MODE 下，加上 * 做前綴匹配
            search_term = f'*{query}*'

            with connection.cursor() as cursor:
                cursor.execute(sql, [search_term, search_term])
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()

            data = [
                {
                    "id": row[0],
                    "song_title": row[1],
                    "artist_name": row[2],
                    "album_name": row[3],
                    "song_image": row[4],
                    "language": row[5],
                }
                for row in rows
            ]
        except Exception:
            # Fallback: 若 FULLTEXT INDEX 不存在，用 icontains
            logger.warning("FULLTEXT search failed, falling back to icontains")
            songs = Song.objects.filter(
                song_title__icontains=query
            ).union(
                Song.objects.filter(artist_name__icontains=query)
            )[:20]

            data = [
                {
                    "id": s.id,
                    "song_title": s.song_title,
                    "artist_name": s.artist_name,
                    "album_name": s.album_name,
                    "song_image": s.song_image,
                    "language": s.language,
                }
                for s in songs
            ]

        return Response({
            "status": "success",
            "data": data,
        }, status=status.HTTP_200_OK)
class HistoryView(APIView):
    """
    GET /api/history — 取得播放紀錄列表
    POST /api/history — 新增播放紀錄
    """
    permission_classes = [IsAuthenticated]
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 50

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
                "song_id": history.song_id,
                "watch_seconds": history.watch_seconds,
                "source": history.source,
            },
        }, status=status.HTTP_201_CREATED)

    def get(self, request):
        user = request.user

        limit = request.query_params.get('limit', self.DEFAULT_LIMIT)
        offset = request.query_params.get('offset', 0)
        song_id = request.query_params.get('song_id')
        source = request.query_params.get('source')

        try:
            limit = int(limit)
            offset = int(offset)
            if limit <= 0 or offset < 0:
                raise ValueError
            limit = min(limit, self.MAX_LIMIT) # 上限保護
        except ValueError:
            return Response({
                "status": "error",
                "message": "Invalid limit or offset.",
                "code": "INVALID_LIMIT_OR_OFFSET",
            }, status=status.HTTP_400_BAD_REQUEST)

        queryset = History.objects.filter(user=user).select_related('song')

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
            song = history.song
            results.append({
                "id": history.id,
                "song_id": history.song_id,
                "song_title": song.song_title,
                "artist_name": song.artist_name,
                "album_name": song.album_name,
                "song_image": song.song_image,
                "language": song.language,
                "watch_seconds": history.watch_seconds,
                "source": history.source,
                "played_at": history.played_at,
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

    def get(self, request):
        """
        GET /api/auth/like?song_id=<id> — 取得目前使用者對某首歌的喜歡狀態
        回傳 is_liked: true / false / null（null 表示尚未設定）
        """
        song_id = request.query_params.get('song_id')
        if song_id is None:
            return Response({
                "status": "error",
                "message": "song_id is required.",
                "code": "MISSING_SONG_ID",
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            song_id_int = int(song_id)
        except (TypeError, ValueError):
            return Response({
                "status": "error",
                "message": "song_id must be an integer.",
                "code": "INVALID_SONG_ID",
            }, status=status.HTTP_400_BAD_REQUEST)

        if not Song.objects.filter(id=song_id_int).exists():
            return Response({
                "status": "error",
                "message": "Song not found.",
                "code": "SONG_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        like = UserSongLike.objects.filter(user=request.user, song_id=song_id_int).first()
        is_liked = like.is_liked if like is not None else None

        return Response({
            "status": "success",
            "data": {
                "song_id": song_id_int,
                "is_liked": is_liked,
            },
        }, status=status.HTTP_200_OK)

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
