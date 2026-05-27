from django.urls import path
from .views import (
    GoogleLoginView,
    LogoutView,
    RegisterProfileView,
    OnboardingArtistsView,
    OnboardingSongsView,
    OnboardingSubmitView,
    AuthMeView,
    DevLoginView,
    HistoryView,
    HistoryDetailView,
    UserSongLikeView,
    FriendSearchView,
    FriendListeningView,

    FriendSearchView,
    FriendListView,
    SendFriendRequestView,
    FriendRequestListView,
    AcceptFriendRequestView,
    RejectFriendRequestView,
    FriendListeningView,
)

urlpatterns = [
    path('google-login', GoogleLoginView.as_view(), name='google-login'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('register', RegisterProfileView.as_view(), name='register'),

    path('me', AuthMeView.as_view(), name='auth_me'),

    # Dev-only: 模擬登入（僅 DEBUG=True 時可用）
    path('dev-login', DevLoginView.as_view(), name='dev-login'),
    path('history', HistoryView.as_view(), name='history'),
    path('history/<int:pk>', HistoryDetailView.as_view(), name='history-detail'),
    path('like', UserSongLikeView.as_view(), name='like'),
    path('friends/search', FriendSearchView.as_view(), name='friend-search'),
    path('friends/listening', FriendListeningView.as_view(), name='friend-listening'),
    path('friends/search', FriendSearchView.as_view(), name='friend-search'),
    path('friends', FriendListView.as_view(), name='friends'),
    path('friends/request', SendFriendRequestView.as_view(), name='friend-request'),
    path('friends/requests', FriendRequestListView.as_view(), name='friend-requests'),
    path('friends/requests/<int:request_id>/accept', AcceptFriendRequestView.as_view(), name='friend-request-accept'),
    path('friends/requests/<int:request_id>/reject', RejectFriendRequestView.as_view(), name='friend-request-reject'),
    path('friends/listening', FriendListeningView.as_view(), name='friend-listening'),
]