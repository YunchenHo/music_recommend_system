import logging
import random
import re
from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.conf import settings
from django.contrib.auth import login, logout
from django.db import connection
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction

from google.oauth2 import id_token
from google.auth.transport import requests

from . import onboarding_itemknn_store
from .affinity_score import AFFINITY_FILTER_THRESHOLD
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
    UserSongAffinity,
    Friendship,
    UserXP,
    DailyChallenge,
    DailyChallengeProgress,
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

@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(APIView):
    """POST /api/auth/logout — 登出當前使用者，清除 session"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({
            "status": "success",
            "message": "Logout successful.",
        }, status=status.HTTP_200_OK)


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

        # 4. 載入批次內所有候選（之後要重排與過濾，不能只取前 9）
        items = list(
            RecommendationItem.objects
            .filter(batch=batch)
            .select_related('song')
        )

        # 5. 取使用者對候選歌的 affinity（沒紀錄者預設 0）
        song_ids = [item.song_id for item in items]
        affinity_map = dict(
            UserSongAffinity.objects
            .filter(user=user, song_id__in=song_ids)
            .values_list('song_id', 'score')
        )

        # 6. 套重排公式 final = itemknn_score * (1 + affinity)，並過濾 affinity < threshold
        reranked: list[tuple[float, RecommendationItem]] = []
        for item in items:
            affinity = affinity_map.get(item.song_id, 0.0)
            if affinity < AFFINITY_FILTER_THRESHOLD:
                continue
            final_score = item.score * (1.0 + affinity)
            reranked.append((final_score, item))

        # 7. 依 final_score 重排，取前 9
        reranked.sort(key=lambda pair: pair[0], reverse=True)
        top = reranked[:9]

        data = [
            {
                "rank": new_rank,
                "id": item.song.id,
                "song_title": item.song.song_title,
                "artist_name": item.song.artist_name,
                "song_image": item.song.song_image,
                "language": item.song.language,
            }
            for new_rank, (_, item) in enumerate(top, start=1)
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

        _increment_challenge(request.user, 2)  # 加入收藏也算進「加入清單」挑戰

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
        _increment_challenge(request.user, 5)  # 新創清單

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

        _increment_challenge(request.user, 2)  # 加歌到清單

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

        # 記錄「是否已有過此歌的播放紀錄」（重聽判斷用，在 create 前查）
        has_prior_history = History.objects.filter(user=user, song=song, is_hidden=False).exists()

        history = History.objects.create(user=user, song=song, watch_seconds=watch_seconds, source=source)

        # 挑戰追蹤：只在「一開始就達到 120 秒」時觸發（通常 PATCH 才會到，但保險起見也加）
        if watch_seconds >= 120:
            _increment_challenge(user, 1)   # 聆聽 N 首歌曲
            if source == History.SourceChoices.RECOMMENDATION:
                _increment_challenge(user, 6)  # 從推薦清單聆聽
            if has_prior_history:
                _increment_challenge(user, 4)  # 重聽

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
            limit = min(limit, self.MAX_LIMIT)
        except ValueError:
            return Response({
                "status": "error",
                "message": "Invalid limit or offset.",
                "code": "INVALID_LIMIT_OR_OFFSET",
            }, status=status.HTTP_400_BAD_REQUEST)

        base_qs = History.objects.filter(user=user, is_hidden=False)

        if song_id is not None:
            base_qs = base_qs.filter(song_id=song_id)

        if source is not None:
            if source not in History.SourceChoices.values:
                return Response({
                    "status": "error",
                    "message": "Invalid source.",
                    "code": "INVALID_SOURCE",
                }, status=status.HTTP_400_BAD_REQUEST)
            base_qs = base_qs.filter(source=source)

        # 以 song_id 去重，取每首最近播放時間，limit 語意 = N 首不同歌
        from django.db.models import Max
        distinct_qs = (
            base_qs
            .values('song_id')
            .annotate(last_played=Max('played_at'))
            .order_by('-last_played')
        )

        total = distinct_qs.count()
        paged = list(distinct_qs[offset:offset + limit])

        results = []
        for item in paged:
            h = (
                History.objects
                .filter(user=user, song_id=item['song_id'], is_hidden=False)
                .select_related('song')
                .order_by('-played_at')
                .first()
            )
            if h:
                results.append({
                    "id": h.id,
                    "song_id": h.song_id,
                    "song_title": h.song.song_title,
                    "artist_name": h.song.artist_name,
                    "album_name": h.song.album_name,
                    "song_image": h.song.song_image,
                    "language": h.song.language,
                    "watch_seconds": h.watch_seconds,
                    "source": h.source,
                    "played_at": h.played_at,
                    "created_at": h.created_at,
                })

        return Response({
            "status": "success",
            "data": results,
            "total": total,
            "limit": limit,
            "offset": offset,
        }, status=status.HTTP_200_OK)

class HistoryDetailView(APIView):
    """
    PATCH /api/auth/history/<pk> — 更新某筆歷史紀錄的 watch_seconds
    僅允許更新「本人建立」的紀錄。
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            history = History.objects.get(pk=pk)
        except History.DoesNotExist:
            return Response({
                "status": "error",
                "message": "History not found.",
                "code": "HISTORY_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        if history.user_id != request.user.id:
            # 不是本人的紀錄一律 404，避免洩漏 id 是否存在
            return Response({
                "status": "error",
                "message": "History not found.",
                "code": "HISTORY_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        watch_seconds = request.data.get('watch_seconds')
        if watch_seconds is None:
            return Response({
                "status": "error",
                "message": "watch_seconds is required.",
                "code": "MISSING_WATCH_SECONDS",
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            watch_seconds = int(watch_seconds)
            if watch_seconds < 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({
                "status": "error",
                "message": "watch_seconds must be an integer >= 0",
                "code": "INVALID_WATCH_SECONDS",
            }, status=status.HTTP_400_BAD_REQUEST)

        # 單調遞增保護：避免 race condition 導致較新的小值蓋掉較大的值
        # （例如重新整理時末段 PATCH 比中段 PATCH 晚抵達）
        if watch_seconds > history.watch_seconds:
            old_ws = history.watch_seconds
            history.watch_seconds = watch_seconds
            history.save(update_fields=['watch_seconds'])

            # 挑戰追蹤：首次跨過 120 秒門檻時觸發（old < 120 <= new）
            if old_ws < 120 <= watch_seconds:
                _increment_challenge(request.user, 1)  # 聆聽 N 首歌曲
                if history.source == History.SourceChoices.RECOMMENDATION:
                    _increment_challenge(request.user, 6)  # 從推薦清單聆聽
                # 重聽：此 history 建立前就已有此歌的其他紀錄
                is_replay = History.objects.filter(
                    user=request.user, song=history.song, is_hidden=False
                ).exclude(pk=history.pk).exists()
                if is_replay:
                    _increment_challenge(request.user, 4)  # 重聽

        return Response({
            "status": "success",
            "message": "History updated.",
            "data": {
                "id": history.id,
                "song_id": history.song_id,
                "watch_seconds": history.watch_seconds,
                "source": history.source,
            },
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        try:
            history = History.objects.get(pk=pk)
        except History.DoesNotExist:
            return Response({
                "status": "error",
                "message": "History not found.",
                "code": "HISTORY_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        if history.user_id != request.user.id:
            return Response({
                "status": "error",
                "message": "History not found.",
                "code": "HISTORY_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        history.is_hidden = True
        history.save(update_fields=['is_hidden'])

        return Response({
            "status": "success",
            "message": "History hidden.",
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
        _increment_challenge(request.user, 3)  # 按讚或倒讚（設定時算，取消不算）
        return Response({"status": "success", "data": {"is_liked": intent_like}})
    

class FriendSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        email = request.query_params.get("email", "").strip()

        if not email:
            return Response({
                "status": "error",
                "message": "email is required.",
                "code": "MISSING_EMAIL",
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                "status": "error",
                "message": "User not found.",
                "code": "USER_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        if user.id == request.user.id:
            return Response({
                "status": "error",
                "message": "You cannot add yourself.",
                "code": "CANNOT_ADD_SELF",
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "status": "success",
            "data": {
                "id": user.id,
                "username": user.nickname or user.username,
                "email": user.email,
                "profile_picture": user.profile_picture,
            }
        })
    

class FriendListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        friendships = Friendship.objects.filter(
            user=request.user
        ).select_related("friend")

        data = [
            {
                "id": item.friend.id,
                "username": item.friend.nickname or item.friend.username,
                "email": item.friend.email,
                "profile_picture": item.friend.profile_picture,
            }
            for item in friendships
        ]

        return Response({
            "status": "success",
            "data": data,
        })

    def post(self, request):
        friend_id = request.data.get("friend_id")

        if not friend_id:
            return Response({
                "status": "error",
                "message": "friend_id is required.",
                "code": "MISSING_FRIEND_ID",
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            friend = User.objects.get(id=friend_id)
        except User.DoesNotExist:
            return Response({
                "status": "error",
                "message": "User not found.",
                "code": "USER_NOT_FOUND",
            }, status=status.HTTP_404_NOT_FOUND)

        if friend.id == request.user.id:
            return Response({
                "status": "error",
                "message": "You cannot add yourself.",
                "code": "CANNOT_ADD_SELF",
            }, status=status.HTTP_400_BAD_REQUEST)

        friendship, created = Friendship.objects.get_or_create(
            user=request.user,
            friend=friend,
        )

        if not created:
            return Response({
                "status": "error",
                "message": "Already friends.",
                "code": "ALREADY_FRIENDS",
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "status": "success",
            "message": "Friend added.",
        }, status=status.HTTP_201_CREATED)
    

class FriendListeningView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        friendships = Friendship.objects.filter(
            user=request.user
        ).select_related("friend")

        data = []

        for friendship in friendships:
            friend = friendship.friend

            latest_history = (
                History.objects
                .filter(user=friend, is_hidden=False)
                .select_related("song")
                .order_by("-played_at")
                .first()
            )

            if latest_history is None:
                continue

            song = latest_history.song

            data.append({
                "id": f"{friend.id}-{song.id}",
                "friend_id": friend.id,
                "friend_name": friend.nickname or friend.username,
                "song_id": song.id,
                "song_title": song.song_title,
                "artist_name": song.artist_name,
                "song_image": song.song_image,
                "played_at": latest_history.played_at,
            })

        return Response({
            "status": "success",
            "data": data,
        }, status=status.HTTP_200_OK)


# ── 養漢堡 / Daily Challenge ──────────────────────────────

# 升到各等級所需的「累積總 XP」門檻：LV2=50, LV3=100, ..., LV6=800
LEVEL_XP_THRESHOLDS = [50, 100, 200, 400, 800]


def _compute_level(total_xp):
    """從累積總 XP 計算當前等級（1–6）。"""
    lv = 1
    for threshold in LEVEL_XP_THRESHOLDS:
        if total_xp >= threshold:
            lv += 1
        else:
            break
    return lv  # 最大就是 6，因為 LEVEL_XP_THRESHOLDS 只有 5 個門檻


def _get_or_create_xp(user):
    """取得（或初始化）用戶的 XP 記錄。"""
    xp_obj, _ = UserXP.objects.get_or_create(user=user)
    return xp_obj


def _add_xp(user, amount=5):
    """加 XP，XP 永不歸零，等級由總 XP 決定。滿級後不再累加。"""
    xp_obj = _get_or_create_xp(user)
    if xp_obj.lv >= 6:
        return xp_obj  # 已滿級，什麼都不做
    xp_obj.xp += amount
    xp_obj.lv = _compute_level(xp_obj.xp)
    xp_obj.save()
    return xp_obj


def _increment_challenge(user, challenge_type, today=None):
    """
    今日對應類型任務的 current_count +1。
    若 current_count 達到 target_n，自動標記完成並給 +5 XP。
    已完成或今日沒有這個類型的任務則直接略過。

    challenge_type 對照：
      1 = 聆聽（watch_seconds ≥ 120）
      2 = 加入歌曲至清單
      3 = 按讚或倒讚
      4 = 重聽
      5 = 新創清單
      6 = 從推薦清單聆聽
    """
    if today is None:
        today = timezone.localdate()
    try:
        progress = DailyChallengeProgress.objects.get(
            user=user,
            challenge__challenge_type=challenge_type,
            date=today,
            is_completed=False,
        )
    except DailyChallengeProgress.DoesNotExist:
        return  # 今日無此任務或已完成，略過

    progress.current_count = min(progress.current_count + 1, progress.target_n)
    if progress.current_count >= progress.target_n:
        progress.is_completed = True
        progress.save()
        _add_xp(user, amount=5)
    else:
        progress.save()


class ChallengeXPView(APIView):
    """GET /api/challenge/xp/ — 回傳當前用戶的等級和 XP。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        xp_obj = _get_or_create_xp(request.user)
        lv = xp_obj.lv
        total_xp = xp_obj.xp

        if lv < 6:
            # 本等級起始門檻（LV1 起點 = 0）
            lv_start = LEVEL_XP_THRESHOLDS[lv - 2] if lv > 1 else 0
            lv_end   = LEVEL_XP_THRESHOLDS[lv - 1]
            xp_in_level  = total_xp - lv_start   # 本等級已累積
            xp_for_level = lv_end - lv_start      # 本等級需要幾 XP 才升級
        else:
            xp_in_level  = total_xp - LEVEL_XP_THRESHOLDS[-1]
            xp_for_level = None  # 滿級

        return Response({
            "lv": lv,
            "xp": total_xp,            # 累積總 XP
            "xp_in_level": xp_in_level,   # 本等級內已累積（給前端進度條用）
            "xp_for_level": xp_for_level,  # 本等級升級需要幾 XP
        })


class ChallengeTodayView(APIView):
    """GET /api/challenge/today/ — 回傳今日 3 個任務。

    規則：
    - 今天已有 3 筆 → 直接回傳（當天任務固定不換）
    - 今天沒有 → 看昨天的記錄：
        * 昨天未完成的任務 → 今天繼續（沿用相同任務 + N 值，進度歸零）
        * 昨天已完成的任務 → 今天重新隨機抽一個新的
        * 完全沒有昨天的記錄（新用戶）→ 全部隨機抽 3 個
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        user = request.user

        # 今天已有任務 → 直接回傳
        today_qs = list(
            DailyChallengeProgress.objects
            .filter(user=user, date=today)
            .select_related('challenge')
        )
        if len(today_qs) >= 3:
            return Response(self._serialize(today_qs))

        all_challenges = list(DailyChallenge.objects.all())
        if len(all_challenges) < 3:
            return Response({"error": "任務尚未初始化，請執行 seed_challenges"}, status=500)

        # 看昨天的記錄
        prev_qs = list(
            DailyChallengeProgress.objects
            .filter(user=user, date=yesterday)
            .select_related('challenge')
        )

        new_today = []

        if prev_qs:
            uncompleted = [p for p in prev_qs if not p.is_completed]
            completed   = [p for p in prev_qs if p.is_completed]

            # 昨天未完成 → 今天繼續，進度重置為 0
            for p in uncompleted:
                new_p, _ = DailyChallengeProgress.objects.get_or_create(
                    user=user, challenge=p.challenge, date=today,
                    defaults={"target_n": p.target_n},
                )
                new_today.append(new_p)

            # 昨天完成的 → 重新抽（排除已選的任務，避免重複）
            used_ids = {p.challenge_id for p in uncompleted}
            pool = [c for c in all_challenges if c.id not in used_ids]
            for _ in completed:
                if not pool:
                    break
                challenge = random.choice(pool)
                pool.remove(challenge)
                n = random.randint(challenge.min_n, challenge.max_n)
                new_p, _ = DailyChallengeProgress.objects.get_or_create(
                    user=user, challenge=challenge, date=today,
                    defaults={"target_n": n},
                )
                new_today.append(new_p)
        else:
            # 新用戶或第一次，全部隨機抽 3 個
            for challenge in random.sample(all_challenges, 3):
                n = random.randint(challenge.min_n, challenge.max_n)
                new_p, _ = DailyChallengeProgress.objects.get_or_create(
                    user=user, challenge=challenge, date=today,
                    defaults={"target_n": n},
                )
                new_today.append(new_p)

        return Response(self._serialize(new_today))

    @staticmethod
    def _serialize(progresses):
        return [
            {
                "id": p.id,
                "challenge_type": p.challenge.challenge_type,
                "prefix": p.challenge.prefix,
                "n": p.target_n,
                "suffix": p.challenge.suffix,
                "current_count": p.current_count,
                "is_completed": p.is_completed,
            }
            for p in progresses
        ]


class ChallengeCompleteView(APIView):
    """POST /api/challenge/complete/<pk>/ — 標記任務完成並加 5 XP。"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            progress = DailyChallengeProgress.objects.get(id=pk, user=request.user)
        except DailyChallengeProgress.DoesNotExist:
            return Response({"error": "任務不存在"}, status=status.HTTP_404_NOT_FOUND)

        if progress.is_completed:
            return Response({"message": "已完成", "already_done": True})

        progress.is_completed = True
        progress.save()

        xp_obj = _add_xp(request.user, amount=5)
        lv = xp_obj.lv
        total_xp = xp_obj.xp
        if lv < 6:
            lv_start = LEVEL_XP_THRESHOLDS[lv - 2] if lv > 1 else 0
            lv_end   = LEVEL_XP_THRESHOLDS[lv - 1]
            xp_in_level  = total_xp - lv_start
            xp_for_level = lv_end - lv_start
        else:
            xp_in_level  = total_xp - LEVEL_XP_THRESHOLDS[-1]
            xp_for_level = None
        return Response({
            "message": "+5 XP",
            "lv": lv,
            "xp": total_xp,
            "xp_in_level": xp_in_level,
            "xp_for_level": xp_for_level,
        })


