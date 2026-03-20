from django.urls import path
from .views import GoogleLoginView

urlpatterns = [
    # 對應規格書的 /api/auth/google-login
    path('auth/google-login', GoogleLoginView.as_view(), name='google-login'),
]