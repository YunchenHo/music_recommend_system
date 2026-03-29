from django.urls import path
from .views import (
    GoogleLoginView,
    RegisterProfileView,
    OnboardingArtistsView,
    OnboardingSongsView,
    OnboardingSubmitView,
)

urlpatterns = [
    path('google-login', GoogleLoginView.as_view(), name='google-login'),
    path('register', RegisterProfileView.as_view(), name='register'),
]