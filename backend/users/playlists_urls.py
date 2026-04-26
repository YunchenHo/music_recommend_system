from django.urls import path

from . import views

urlpatterns = [
    path('', views.PlaylistListCreateView.as_view(), name='playlist-list-create'),
    path('<int:playlist_id>/', views.PlaylistDetailView.as_view(), name='playlist-detail'),
    path('<int:playlist_id>/songs/', views.PlaylistSongListCreateView.as_view(), name='playlist-song-list-create'),
    path('<int:playlist_id>/songs/<int:song_id>/', views.PlaylistSongDetailView.as_view(), name='playlist-song-detail'),
]
