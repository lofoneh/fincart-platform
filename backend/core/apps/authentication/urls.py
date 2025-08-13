# apps/authentication/urls.py (Updated)
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'authentication'

urlpatterns = [
    # Authentication
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Email Verification (Optional for now)
    path('verify-email/', views.EmailVerificationView.as_view(), name='verify_email'),
    path('skip-verification/', views.SkipEmailVerificationView.as_view(), name='skip_verification'),
    path('resend-verification/', views.ResendVerificationView.as_view(), name='resend_verification'),
    
    # Password Reset
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Profile
    path('me/', views.CurrentUserView.as_view(), name='current_user'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
]