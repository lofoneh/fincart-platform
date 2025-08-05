from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('refresh/', views.RefreshTokenView.as_view(), name='refresh_token'),
    path('me/', views.UserProfileView.as_view(), name='user_profile'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='verify_email'),
    path('verify-phone/', views.VerifyPhoneView.as_view(), name='verify_phone'),
    path('password-reset/', views.PasswordResetView.as_view(), name='password_reset'),
    path('password-reset-confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]