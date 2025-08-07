from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'authentication'

# Router for viewsets
router = DefaultRouter()
router.register(r'addresses', views.AddressViewSet, basename='address')

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Authentication endpoints
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Email verification
    path('verify-email/', views.EmailVerificationView.as_view(), name='verify_email'),
    path('resend-verification/', views.ResendVerificationView.as_view(), name='resend_verification'),
    
    # Phone verification
    path('verify-phone/request/', views.PhoneVerificationRequestView.as_view(), name='phone_verification_request'),
    path('verify-phone/confirm/', views.PhoneVerificationConfirmView.as_view(), name='phone_verification_confirm'),
    
    # Password management
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Profile management
    path('me/', views.CurrentUserView.as_view(), name='current_user'),
    path('login-history/', views.LoginHistoryView.as_view(), name='login_history'),
    path('activity/', views.UserActivityView.as_view(), name='user_activity'),
    path('security/', views.AccountSecurityView.as_view(), name='account_security'),
]