from rest_framework import status, generics, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from datetime import timedelta
import logging

from .models import (
    User, Address, EmailVerificationToken, PasswordResetToken, 
    PhoneVerificationToken, LoginHistory, UserActivity
)
from .serializers import (
    UserRegistrationSerializer, CustomTokenObtainPairSerializer,
    EmailVerificationSerializer, PhoneVerificationSerializer,
    PhoneVerificationConfirmSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, ChangePasswordSerializer,
    UserProfileSerializer, UserSerializer, AddressSerializer,
    AddressCreateSerializer, LoginHistorySerializer, UserActivitySerializer
)
from .permissions import IsOwnerOrReadOnly
from .utils import send_verification_email, send_password_reset_email, send_sms_code

logger = logging.getLogger(__name__)


class RegistrationThrottle(AnonRateThrottle):
    scope = 'registration'
    rate = '5/hour'


class LoginThrottle(AnonRateThrottle):
    scope = 'login'
    rate = '10/minute'


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegistrationThrottle]

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            user = serializer.save()
            
            # Create email verification token
            email_token = EmailVerificationToken.objects.create(
                user=user,
                ip_address=self.get_client_ip(request)
            )
            
            # Send verification email
            try:
                send_verification_email(user, email_token.token)
            except Exception as e:
                logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
            
            # Log registration
            logger.info(f"New user registered: {user.email}")
        
        return Response({
            'message': 'User registered successfully. Please check your email for verification.',
            'user_id': str(user.id),
            'email': user.email
        }, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def post(self, request, *args, **kwargs):
        email = request.data.get('email', '').lower()
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check for brute force attempts
        cache_key = f"login_attempts_{ip_address}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:  # Max 5 attempts per IP
            return Response({
                'error': 'Too many login attempts. Please try again later.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        try:
            response = super().post(request, *args, **kwargs)
            
            if response.status_code == 200:
                # Successful login
                user = User.objects.get(email=email)
                
                with transaction.atomic():
                    # Create login history
                    LoginHistory.objects.create(
                        user=user,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        method='email',
                        is_successful=True
                    )
                    
                    # Log activity
                    UserActivity.objects.create(
                        user=user,
                        activity_type='login',
                        description='Successful login',
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                
                # Clear failed attempts
                cache.delete(cache_key)
                
                logger.info(f"Successful login for {email} from {ip_address}")
                
            else:
                # Failed login
                cache.set(cache_key, attempts + 1, timeout=3600)  # 1 hour timeout
                
                if User.objects.filter(email=email).exists():
                    user = User.objects.get(email=email)
                    LoginHistory.objects.create(
                        user=user,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        method='email',
                        is_successful=False,
                        failure_reason='Invalid password'
                    )
                
                logger.warning(f"Failed login attempt for {email} from {ip_address}")
            
            return response
            
        except Exception as e:
            logger.error(f"Login error for {email}: {str(e)}")
            cache.set(cache_key, attempts + 1, timeout=3600)
            return Response({
                'error': 'Login failed. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            if not refresh_token:
                return Response(
                    {'error': 'Refresh token is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Blacklist token
                token = RefreshToken(refresh_token)
                token.blacklist()
                
                # Update login history
                LoginHistory.objects.filter(
                    user=request.user,
                    logout_at__isnull=True
                ).update(logout_at=timezone.now())
                
                # Log activity
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='logout',
                    description='User logged out',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
            
            logger.info(f"User {request.user.email} logged out")
            return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Logout error for user {request.user.email}: {str(e)}")
            return Response({'error': 'Logout failed'}, status=status.HTTP_400_BAD_REQUEST)


class EmailVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token_obj = serializer._token_obj
        user = token_obj.user
        
        with transaction.atomic():
            # Mark user as verified
            user.email_verified = True
            user.save(update_fields=['email_verified'])
            
            # Mark token as used
            token_obj.use_token()
            
            # Log activity
            UserActivity.objects.create(
                user=user,
                activity_type='verification',
                description='Email verified successfully',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        logger.info(f"Email verified for user {user.email}")
        return Response({'message': 'Email verified successfully'})


class ResendVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        user = request.user
        
        if user.email_verified:
            return Response({'message': 'Email already verified'})
        
        # Check for recent verification emails
        recent_tokens = EmailVerificationToken.objects.filter(
            user=user,
            created_at__gt=timezone.now() - timedelta(minutes=5)
        ).count()
        
        if recent_tokens > 0:
            return Response({
                'error': 'Verification email already sent recently. Please wait before requesting another.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        with transaction.atomic():
            # Invalidate old tokens
            EmailVerificationToken.objects.filter(
                user=user, 
                is_used=False
            ).update(is_used=True)
            
            # Create new token
            token = EmailVerificationToken.objects.create(
                user=user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Send email
            try:
                send_verification_email(user, token.token)
            except Exception as e:
                logger.error(f"Failed to resend verification email to {user.email}: {str(e)}")
                return Response({
                    'error': 'Failed to send verification email'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({'message': 'Verification email sent'})


class PhoneVerificationRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        serializer = PhoneVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone_number = serializer.validated_data['phone_number']
        user = request.user
        
        # Check if phone number is already verified by another user
        if User.objects.filter(phone_number=phone_number, phone_verified=True).exclude(pk=user.pk).exists():
            return Response({
                'error': 'This phone number is already verified by another user'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for recent SMS codes
        recent_tokens = PhoneVerificationToken.objects.filter(
            user=user,
            created_at__gt=timezone.now() - timedelta(minutes=2)
        ).count()
        
        if recent_tokens > 0:
            return Response({
                'error': 'SMS code already sent recently. Please wait before requesting another.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        with transaction.atomic():
            # Update user's phone number
            user.phone_number = phone_number
            user.phone_verified = False
            user.save(update_fields=['phone_number', 'phone_verified'])
            
            # Invalidate old tokens
            PhoneVerificationToken.objects.filter(
                user=user,
                is_used=False
            ).update(is_used=True)
            
            # Create new token
            token = PhoneVerificationToken.objects.create(
                user=user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Send SMS
            try:
                send_sms_code(phone_number, token.token)
            except Exception as e:
                logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
                return Response({
                    'error': 'Failed to send SMS code'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({'message': 'SMS verification code sent'})


class PhoneVerificationConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        serializer = PhoneVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['code']
        user = request.user
        
        try:
            token_obj = PhoneVerificationToken.objects.get(
                user=user,
                token=code,
                is_used=False
            )
            
            if not token_obj.is_valid():
                return Response({
                    'error': 'Verification code has expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify phone number matches
            if user.phone_number != phone_number:
                return Response({
                    'error': 'Phone number mismatch'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Mark phone as verified
                user.phone_verified = True
                user.save(update_fields=['phone_verified'])
                
                # Mark token as used
                token_obj.use_token()
                
                # Log activity
                UserActivity.objects.create(
                    user=user,
                    activity_type='verification',
                    description='Phone number verified',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
            
            logger.info(f"Phone verified for user {user.email}")
            return Response({'message': 'Phone number verified successfully'})
            
        except PhoneVerificationToken.DoesNotExist:
            return Response({
                'error': 'Invalid verification code'
            }, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        # Check rate limiting per email
        cache_key = f"password_reset_{email}"
        if cache.get(cache_key):
            return Response({
                'message': 'If email exists, reset instructions will be sent'
            })
        
        try:
            user = User.objects.get(email=email)
            
            with transaction.atomic():
                # Invalidate old tokens
                PasswordResetToken.objects.filter(
                    user=user,
                    is_used=False
                ).update(is_used=True)
                
                # Create new token
                token = PasswordResetToken.objects.create(
                    user=user,
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                # Send reset email
                try:
                    send_password_reset_email(user, token.token)
                except Exception as e:
                    logger.error(f"Failed to send password reset email to {email}: {str(e)}")
                
                # Log activity
                UserActivity.objects.create(
                    user=user,
                    activity_type='password_change',
                    description='Password reset requested',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                # Set rate limit
                cache.set(cache_key, True, timeout=300)  # 5 minutes
                
        except User.DoesNotExist:
            # Don't reveal if email exists
            pass
        
        return Response({
            'message': 'If email exists, reset instructions will be sent'
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token_obj = serializer._token_obj
        new_password = serializer.validated_data['new_password']
        user = token_obj.user
        
        with transaction.atomic():
            # Set new password
            user.set_password(new_password)
            user.save()
            
            # Mark token as used
            token_obj.use_token()
            
            # Log activity
            UserActivity.objects.create(
                user=user,
                activity_type='password_change',
                description='Password reset completed',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Invalidate all active sessions
            # This would require implementing a custom token blacklist
        
        logger.info(f"Password reset completed for user {user.email}")
        return Response({'message': 'Password reset successful'})


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        new_password = serializer.validated_data['new_password']
        
        with transaction.atomic():
            user.set_password(new_password)
            user.save()
            
            # Log activity
            UserActivity.objects.create(
                user=user,
                activity_type='password_change',
                description='Password changed',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        logger.info(f"Password changed for user {user.email}")
        return Response({'message': 'Password changed successfully'})


class CurrentUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Log profile update
            UserActivity.objects.create(
                user=request.user,
                activity_type='profile_update',
                description='Profile updated',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        return response


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_queryset(self):
        return Address.objects.filter(user=self.request.user, is_active=True)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AddressCreateSerializer
        return AddressSerializer
    
    def perform_create(self, serializer):
        address = serializer.save()
        
        # Log activity
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='address_add',
            description=f'Address added: {address.city}',
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
    
    def perform_update(self, serializer):
        address = serializer.save()
        
        # Log activity
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='address_update',
            description=f'Address updated: {address.city}',
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Soft delete
        instance.is_active = False
        instance.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        address = self.get_object()
        
        with transaction.atomic():
            # Remove default from all other addresses
            Address.objects.filter(
                user=request.user,
                is_default=True
            ).update(is_default=False)
            
            # Set this address as default
            address.is_default = True
            address.save()
        
        return Response({'message': 'Default address updated'})


class LoginHistoryView(generics.ListAPIView):
    serializer_class = LoginHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return LoginHistory.objects.filter(user=self.request.user).order_by('-login_at')[:50]


class UserActivityView(generics.ListAPIView):
    serializer_class = UserActivitySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserActivity.objects.filter(user=self.request.user).order_by('-created_at')[:100]


class AccountSecurityView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get security metrics
        recent_logins = LoginHistory.objects.filter(
            user=user,
            login_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        failed_attempts = LoginHistory.objects.filter(
            user=user,
            is_successful=False,
            login_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        active_tokens = EmailVerificationToken.objects.filter(
            user=user,
            is_used=False,
            expires_at__gt=timezone.now()
        ).count() + PasswordResetToken.objects.filter(
            user=user,
            is_used=False,
            expires_at__gt=timezone.now()
        ).count()
        
        return Response({
            'account_status': {
                'is_active': user.is_active,
                'is_suspended': user.is_suspended,
                'email_verified': user.email_verified,
                'phone_verified': user.phone_verified,
                'is_fully_verified': user.is_verified()
            },
            'security_metrics': {
                'recent_logins_30_days': recent_logins,
                'failed_attempts_7_days': failed_attempts,
                'active_tokens': active_tokens,
                'last_password_change': None,  # Would need to track this
                'account_age_days': (timezone.now().date() - user.created_at.date()).days
            },
            'recommendations': self.get_security_recommendations(user)
        })
    
    def get_security_recommendations(self, user):
        recommendations = []
        
        if not user.email_verified:
            recommendations.append("Verify your email address for better security")
        
        if not user.phone_verified:
            recommendations.append("Add and verify your phone number for two-factor authentication")
        
        if not user.first_name or not user.last_name:
            recommendations.append("Complete your profile information")
        
        return recommendations