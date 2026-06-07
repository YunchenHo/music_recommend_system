import logging
import re

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.conf import settings
from django.contrib.auth import login, logout
from django.db import connection
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction

from google.oauth2 import id_token
from google.auth.transport import requests

from . import lightfm_service, onboarding_itemknn_store
from .models import (
    User,
    Artist,
    Song,
    UserOnboardingArtist,
    UserOnboardingSong,
    PlaylistIcon,
    Playlist,
    PlaylistSong,
    RecommendationBatch,
    RecommendationItem,
    History,
    UserSongLike,
    UserSongAffinity,
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
            # NOTE: ItemKNN pre-computation kept for potential future use.
            # LightFM hybrid is now used for cold-start recommendations.
            onboarding_itemknn_store.refresh_stored_itemknn_recommendations(user)
        except (FileNotFoundError, ValueError, Exception):
            pass  # Non-critical; LightFM hybrid doesn't depend on this

        return Response({
            "status": "success",
            "message": "Onboarding complete.",
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Songs API: Recommendations + Favorites (archive playlist)
# ---------------------------------------------------------------------------

ARCHIVE_PLAYLIST_NAME = "archive"


class RecommendationsView(APIView):
    """GET /api/songs/recommendations — 取得推薦歌曲列表

    自動切換演算法：
    - 歷史不重複歌曲數 >= LIGHTFM_MIN_HISTORY → LightFM Pure CF
    - 否則 → LightFM Hybrid（user features + onboarding embeddings）
    """
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

        # 2. 取得歷史和 onboarding 歌曲
        history_song_ids = list(
            History.objects.filter(user=user)
            .values_list('song_id', flat=True).distinct()
        )
        current_count = len(history_song_ids)

        # 3. 判斷是否需要重新計算
        batch_count = RecommendationBatch.objects.filter(user=user).count()

        if batch_count > 0:
            needs_recalc = (current_count // 10) > (batch_count - 1)
        else:
            needs_recalc = True

        # 4. 不需要重算 → 從 DB 最新 batch 讀取
        if not needs_recalc:
            return self._read_latest_batch(user)

        # 5. 需要重算
        onboarding_song_ids = list(
            UserOnboardingSong.objects.filter(user=user)
            .values_list('song_id', flat=True)
        )
        exclude = set(history_song_ids) | set(onboarding_song_ids)

        # 6. 選擇演算法
        if current_count >= settings.LIGHTFM_MIN_HISTORY:
            result = self._recommend_purecf(user, history_song_ids, exclude)
            if result is not None:
                return result
            logger.info("PureCF unavailable for user %s, trying hybrid fallback", user.id)

        # 7. Hybrid 冷啟動（或 PureCF fallback）
        result = self._recommend_hybrid(user, onboarding_song_ids, exclude)
        if result is not None:
            return result

        # 8. 全部失敗
        return Response({
            "status": "success",
            "data": [],
            "message": "Recommendations temporarily unavailable.",
            "algorithm": "none",
        }, status=status.HTTP_200_OK)

    def _recommend_purecf(self, user, history_song_ids: list[int], exclude: set[int]):
        """Pure CF 推薦。成功回傳 Response，失敗回傳 None。"""
        from .affinity_score import compute_affinity_for_user

        # 即時計算最新 affinity
        compute_affinity_for_user(user)
        affinity_map = dict(
            UserSongAffinity.objects.filter(user=user).values_list('song_id', 'score')
        )

        try:
            rec_ids, scores = lightfm_service.recommend_purecf(
                history_song_ids=history_song_ids,
                exclude_song_ids=exclude,
                affinity_map=affinity_map,
                top_n=20,
            )
        except Exception as exc:
            logger.warning("PureCF recommend failed: %s", exc)
            return None

        if not rec_ids:
            return None

        return self._build_response(user, rec_ids, scores, "LightFM-PureCF")

    def _recommend_hybrid(self, user, onboarding_song_ids: list[int], exclude: set[int]):
        """Hybrid 冷啟動推薦。成功回傳 Response，失敗回傳 None。"""
        try:
            rec_ids, scores = lightfm_service.recommend_hybrid(
                user=user,
                onboarding_song_ids=onboarding_song_ids,
                exclude_song_ids=exclude,
                top_n=20,
            )
        except Exception as exc:
            logger.warning("Hybrid recommend failed: %s", exc)
            return None

        if not rec_ids:
            return None

        return self._build_response(user, rec_ids, scores, "LightFM-Hybrid")

    def _read_latest_batch(self, user):
        """從 DB 讀取最新的推薦批次回傳。"""
        latest_batch = (
            RecommendationBatch.objects.filter(user=user)
            .order_by('-generated_at')
            .first()
        )
        if latest_batch is None:
            return Response({
                "status": "success",
                "data": [],
                "message": "Recommendations temporarily unavailable.",
                "algorithm": "none",
            }, status=status.HTTP_200_OK)

        items = latest_batch.items.select_related('song').order_by('rank')[:9]
        data = []
        for item in items:
            song = item.song
            data.append({
                "rank": item.rank,
                "id": song.id,
                "song_title": song.song_title,
                "artist_name": song.artist_name,
                "song_image": song.song_image,
                "language": song.language,
            })

        return Response({
            "status": "success",
            "data": data,
            "algorithm": latest_batch.algorithm,
        }, status=status.HTTP_200_OK)

    def _build_response(self, user, rec_ids: list[int], scores: list[float], algorithm: str):
        """從推薦 song_id list 建構 API Response，並存入 DB。含 language re-rank。"""
        from django.utils import timezone

        songs = Song.objects.filter(id__in=rec_ids)
        song_map = {s.id: s for s in songs}

        # --- Language re-rank ---
        # 根據用戶語言偏好對非偏好語言歌曲施加懲罰，然後重新排序
        preferred_lang_codes = self._get_preferred_lang_codes(user)
        penalty = settings.LANGUAGE_PENALTY_FACTOR

        if preferred_lang_codes:
            adjusted = []
            for i, sid in enumerate(rec_ids):
                if sid not in song_map:
                    continue
                score = scores[i] if i < len(scores) else 0.0
                song_lang = song_map[sid].language or ''
                if song_lang not in preferred_lang_codes:
                    score *= penalty
                adjusted.append((sid, score))
            # 按調整後分數重新排序
            adjusted.sort(key=lambda x: -x[1])
            rec_ids = [item[0] for item in adjusted]
            scores = [item[1] for item in adjusted]

        data = []
        valid_ids = []
        valid_scores = []
        for i, sid in enumerate(rec_ids):
            if sid not in song_map:
                continue
            data.append({
                "rank": len(data) + 1,
                "id": sid,
                "song_title": song_map[sid].song_title,
                "artist_name": song_map[sid].artist_name,
                "song_image": song_map[sid].song_image,
                "language": song_map[sid].language,
            })
            valid_ids.append(sid)
            valid_scores.append(scores[i] if i < len(scores) else 0.0)
            if len(data) == 9:
                break

        if not data:
            return None

        # 寫入 DB
        batch = RecommendationBatch.objects.create(
            user=user,
            algorithm=algorithm,
            generated_at=timezone.now(),
            total_size=len(data),
        )
        RecommendationItem.objects.bulk_create([
            RecommendationItem(
                batch=batch,
                rank=i + 1,
                song_id=valid_ids[i],
                score=valid_scores[i],
            )
            for i in range(len(valid_ids))
        ])

        return Response({
            "status": "success",
            "data": data,
            "algorithm": algorithm,
        }, status=status.HTTP_200_OK)

    # Language code mapping: user preferred_languages → DB Song.language values
    # KKBOX codes: 3.0=Chinese(Mandarin), 24.0=Cantonese, 52.0=English,
    #              17.0=Japanese, 31.0=Korean
    _LANG_PREF_TO_CODES = {
        'Chinese': {'3.0', '24.0'},   # 國語 + 粵語
        'English': {'52.0'},
        'Japanese': {'17.0'},
        'Korean': {'31.0'},
    }

    def _get_preferred_lang_codes(self, user) -> set[str]:
        """將用戶 preferred_languages 轉為 DB Song.language 對應的 code set。"""
        if not user.preferred_languages:
            return set()
        codes: set[str] = set()
        for lang in user.preferred_languages.split(','):
            lang = lang.strip()
            mapped = self._LANG_PREF_TO_CODES.get(lang)
            if mapped:
                codes.update(mapped)
        return codes


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


class PlaylistIconListView(APIView):
    """GET /api/playlists/icons/ — 取得所有可用的 playlist icon"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        icons = PlaylistIcon.objects.all().order_by('id')
        data = [{"id": icon.id, "filename": icon.filename} for icon in icons]
        return Response({"status": "success", "data": data}, status=status.HTTP_200_OK)


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
            .select_related('icon')
            .annotate(song_count=Count('songs'))
            .order_by('created_at')
        )

        data = [
            {
                "id": p.id,
                "playlist_name": p.playlist_name,
                "icon": {"id": p.icon.id, "filename": p.icon.filename} if p.icon else None,
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

        # 處理 icon
        icon = None
        icon_id = request.data.get('icon_id')
        if icon_id is not None:
            try:
                icon = PlaylistIcon.objects.get(id=icon_id)
            except PlaylistIcon.DoesNotExist:
                pass

        playlist = Playlist.objects.create(
            user=request.user,
            playlist_name=playlist_name,
            icon=icon,
        )

        return Response({
            "status": "success",
            "message": "Playlist created.",
            "data": {
                "id": playlist.id,
                "playlist_name": playlist.playlist_name,
                "icon": {"id": icon.id, "filename": icon.filename} if icon else None,
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
        icon_id = request.data.get('icon_id')

        # 至少要有一個欄位要更新
        if not new_name and icon_id is None:
            return Response({
                "status": "error",
                "message": "playlist_name or icon_id is required.",
                "code": "MISSING_FIELDS",
            }, status=status.HTTP_400_BAD_REQUEST)

        if new_name:
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

        if icon_id is not None:
            try:
                playlist.icon = PlaylistIcon.objects.get(id=icon_id)
            except PlaylistIcon.DoesNotExist:
                return Response({
                    "status": "error",
                    "message": "Icon not found.",
                    "code": "ICON_NOT_FOUND",
                }, status=status.HTTP_404_NOT_FOUND)

        playlist.save()

        return Response({
            "status": "success",
            "message": "Playlist updated.",
            "data": {
                "id": playlist.id,
                "playlist_name": playlist.playlist_name,
                "icon": {"id": playlist.icon.id, "filename": playlist.icon.filename} if playlist.icon else None,
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
            history.watch_seconds = watch_seconds
            history.save(update_fields=['watch_seconds'])

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
