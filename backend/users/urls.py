from django.urls import path
from .views import (
    GoogleLoginView,
    RegisterProfileView,
    OnboardingArtistsView,
    OnboardingSongsView,
    OnboardingSubmitView,
    AuthMeView,
    DevLoginView,
    HistoryView,
    HistoryDetailView,
    UserSongLikeView,
)

urlpatterns = [
    path('google-login', GoogleLoginView.as_view(), name='google-login'),
    path('register', RegisterProfileView.as_view(), name='register'),

    path('me', AuthMeView.as_view(), name='auth_me'),

    # Dev-only: 模擬登入（僅 DEBUG=True 時可用）
    path('dev-login', DevLoginView.as_view(), name='dev-login'),
    path('history', HistoryView.as_view(), name='history'),
    path('history/<int:pk>', HistoryDetailView.as_view(), name='history-detail'),
    path('like', UserSongLikeView.as_view(), name='like'),
]