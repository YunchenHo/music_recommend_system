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

from google.oauth2 import id_token
from google.auth.transport import requests

from . import onboarding_itemknn_store
from .models import (
    User,
    Artist,
    Song,
    UserOnboardingArtist,
    UserOnboardingSong,
    UserItemKNNRawCandidate,
    UserItemKNNRecommendation,
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


class OnboardingRecommendationsView(APIView):
    """讀取已快取之 ItemKNN 推薦（onboarding 送出時寫入）；?refresh=1 時依種子重算。回傳 song id 列表。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            top_n = int(request.query_params.get("top_n", 30))
        except (TypeError, ValueError):
            return Response(
                {
                    "status": "error",
                    "message": "top_n must be an integer.",
                    "code": "INVALID_TOP_N",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if top_n < 1 or top_n > 200:
            return Response(
                {
                    "status": "error",
                    "message": "top_n must be between 1 and 200.",
                    "code": "INVALID_TOP_N",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        seed_ids = list(
            UserOnboardingSong.objects.filter(user=user).values_list("song_id", flat=True)
        )
        if not seed_ids:
            return Response(
                {
                    "status": "error",
                    "message": "No onboarding songs yet.",
                    "code": "NO_ONBOARDING_SONGS",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        want_refresh = request.query_params.get("refresh") in ("1", "true", "yes")
        skipped: list[int] = []

        if want_refresh:
            try:
                _, skipped = onboarding_itemknn_store.refresh_stored_itemknn_recommendations(
                    user, top_n=top_n
                )
            except FileNotFoundError as exc:
                return Response(
                    {
                        "status": "error",
                        "message": str(exc),
                        "code": "ITEMKNN_ARTIFACT_MISSING",
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            except ValueError as exc:
                return Response(
                    {
                        "status": "error",
                        "message": str(exc),
                        "code": "ITEMKNN_ARTIFACT_INVALID",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        elif not UserItemKNNRecommendation.objects.filter(user=user).exists():
            store_n = min(200, max(top_n, onboarding_itemknn_store.DEFAULT_STORE_TOP_N))
            try:
                _, skipped = onboarding_itemknn_store.refresh_stored_itemknn_recommendations(
                    user, top_n=store_n
                )
            except FileNotFoundError as exc:
                return Response(
                    {
                        "status": "error",
                        "message": str(exc),
                        "code": "ITEMKNN_ARTIFACT_MISSING",
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            except ValueError as exc:
                return Response(
                    {
                        "status": "error",
                        "message": str(exc),
                        "code": "ITEMKNN_ARTIFACT_INVALID",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        song_ids = list(
            UserItemKNNRecommendation.objects.filter(user=user)
            .order_by("position")
            .values_list("song_id", flat=True)[:top_n]
        )

        raw_candidates = list(
            UserItemKNNRawCandidate.objects.filter(user=user)
            .order_by("position")
            .values("song_id", "score", "position")
        )

        return Response(
            {
                "status": "success",
                "data": {
                    "song_ids": song_ids,
                    "raw_candidates": raw_candidates,
                    "skipped_seed_ids": skipped,
                },
            },
            status=status.HTTP_200_OK,
        )
