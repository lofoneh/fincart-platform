from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import User, EmailVerificationToken, PasswordResetToken, LoginHistory
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, 
    EmailVerificationSerializer, PasswordResetSerializer,
    PasswordResetConfirmSerializer, ChangePasswordSerializer,
    UserSerializer
)

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create email verification token
        token = EmailVerificationToken.objects.create(
            user=user,
            token=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # TODO: Send verification email
        
        return Response({
            'message': 'User registered successfully. Please check your email for verification.',
            'user_id': user.id
        }, status=status.HTTP_201_CREATED)

class LoginView(TokenObtainPairView):
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Log successful login
            user = authenticate(
                email=request.data.get('email'),
                password=request.data.get('password')
            )
            if user:
                LoginHistory.objects.create(
                    user=user,
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    is_successful=True
                )
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            # Update login history
            LoginHistory.objects.filter(
                user=request.user,
                logout_at__isnull=True
            ).update(logout_at=timezone.now())
            
            return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

class EmailVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        
        try:
            verification_token = EmailVerificationToken.objects.get(
                token=token,
                is_used=False,
                expires_at__gt=timezone.now()
            )
            
            user = verification_token.user
            user.email_verified = True
            user.save()
            
            verification_token.is_used = True
            verification_token.save()
            
            return Response({'message': 'Email verified successfully'})
            
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {'error': 'Invalid or expired token'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class ResendVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        
        if user.email_verified:
            return Response({'message': 'Email already verified'})
        
        # Invalidate old tokens
        EmailVerificationToken.objects.filter(user=user, is_used=False).update(is_used=True)
        
        # Create new token
        token = EmailVerificationToken.objects.create(
            user=user,
            token=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # TODO: Send verification email
        
        return Response({'message': 'Verification email sent'})

class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Invalidate old tokens
            PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
            
            # Create new token
            token = PasswordResetToken.objects.create(
                user=user,
                token=str(uuid.uuid4()),
                expires_at=timezone.now() + timedelta(hours=1)
            )
            
            # TODO: Send password reset email
            
        except User.DoesNotExist:
            pass  # Don't reveal if email exists
        
        return Response({'message': 'If email exists, reset instructions will be sent'})

class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            reset_token = PasswordResetToken.objects.get(
                token=token,
                is_used=False,
                expires_at__gt=timezone.now()
            )
            
            user = reset_token.user
            user.set_password(new_password)
            user.save()
            
            reset_token.is_used = True
            reset_token.save()
            
            return Response({'message': 'Password reset successful'})
            
        except PasswordResetToken.DoesNotExist:
            return Response(
                {'error': 'Invalid or expired token'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class CurrentUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        
        if not check_password(old_password, user.password):
            return Response(
                {'error': 'Invalid old password'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        
        return Response({'message': 'Password changed successfully'})