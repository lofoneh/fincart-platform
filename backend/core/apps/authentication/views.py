from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import authenticate
from .serializers import UserRegistrationSerializer, LoginSerializer, UserProfileSerializer

class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Send verification email
        # send_verification_email.delay(user.id)
        
        return Response({
            'message': 'User registered successfully',
            'user_id': user.id
        }, status=status.HTTP_201_CREATED)

class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user