from django.urls import path
from .views import ChallengeXPView, ChallengeTodayView, ChallengeCompleteView

urlpatterns = [
    path('xp/',              ChallengeXPView.as_view(),      name='challenge-xp'),
    path('today/',           ChallengeTodayView.as_view(),   name='challenge-today'),
    path('complete/<int:pk>/', ChallengeCompleteView.as_view(), name='challenge-complete'),
]
