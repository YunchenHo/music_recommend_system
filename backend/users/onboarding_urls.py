from django.urls import path
from .views import OnboardingArtistsView, OnboardingSongsView, OnboardingSubmitView

urlpatterns = [
    path('artists', OnboardingArtistsView.as_view(), name='onboarding-artists'),
    path('songs', OnboardingSongsView.as_view(), name='onboarding-songs'),
    path('submit', OnboardingSubmitView.as_view(), name='onboarding-submit'),
]
