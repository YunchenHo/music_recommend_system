from django.urls import path

from . import views

urlpatterns = [
    path('recommendations', views.RecommendationsView.as_view(), name='recommendations'),
    path('favorites', views.FavoritesView.as_view(), name='favorites'),
    path('favorites/<int:song_id>', views.FavoriteDetailView.as_view(), name='favorite-detail'),
]
