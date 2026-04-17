from django.urls import path
from .views import (
    GoogleLoginView,
    RegisterProfileView,
    OnboardingArtistsView,
    OnboardingSongsView,
    OnboardingSubmitView,
    AuthMeView,
    DevLoginView,
)

urlpatterns = [
    path('google-login', GoogleLoginView.as_view(), name='google-login'),
    path('register', RegisterProfileView.as_view(), name='register'),

    path('me', AuthMeView.as_view(), name='auth_me'),

    # Dev-only: 模擬登入（僅 DEBUG=True 時可用）
    path('dev-login', DevLoginView.as_view(), name='dev-login'),
]