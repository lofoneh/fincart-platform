from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from apps.authentication.models import User


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile details."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'is_seller', 
                 'is_buyer', 'email_verified', 'phone_verified', 'date_joined']
        read_only_fields = ['id', 'date_joined']
class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile details.""" 
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'is_seller', 
                 'is_buyer', 'email_verified', 'phone_verified']
        read_only_fields = ['email_verified', 'phone_verified']

class AddressSerializer(serializers.ModelSerializer):
    """Serializer for user address details."""
    class Meta:
        model = User
        fields = ['address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country']
        read_only_fields = ['country']

class UserDashboardSerializer(serializers.ModelSerializer):
    """Serializer for user dashboard details."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'is_seller', 
                 'is_buyer', 'email_verified', 'phone_verified', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'password', 'password_confirm']
        
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user
    
class UserLoginSerializer(TokenObtainPairSerializer):
    username_field = 'email'
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'is_seller', 
                 'is_buyer', 'email_verified', 'phone_verified', 'date_joined']
        read_only_fields = ['id', 'date_joined']
        
class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField()
    
class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    
class UserProfilePictureSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile picture."""
    profile_picture = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = ['profile_picture']
        read_only_fields = ['profile_picture']
        
class UpdateUserProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile details.""" 
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'is_seller', 
                 'is_buyer', 'email_verified', 'phone_verified']
        read_only_fields = ['email_verified', 'phone_verified']
    
