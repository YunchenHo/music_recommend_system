from django.urls import path
from .views import GoogleLoginView, RegisterProfileView

urlpatterns = [
    # 對應規格書的 /api/auth/google-login
    path('google-login', GoogleLoginView.as_view(), name='google-login'),
    path('register', RegisterProfileView.as_view(), name='register'),
]