from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import User, Address, LoginHistory, UserActivity
import re


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id', 'type', 'full_name', 'phone_number', 'street_address',
            'apartment', 'city', 'state', 'postal_code', 'country',
            'is_default', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_phone_number(self, value):
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Invalid phone number format")
        return value

    def validate_postal_code(self, value):
        # Basic postal code validation - can be customized per country
        if not re.match(r'^[A-Za-z0-9\s-]{3,10}$', value):
            raise serializers.ValidationError("Invalid postal code format")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """Detailed user profile serializer"""
    addresses = AddressSerializer(many=True, read_only=True)
    full_name = serializers.CharField(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'profile_image', 'date_of_birth', 'is_seller', 'is_buyer',
            'email_verified', 'phone_verified', 'is_verified', 'addresses',
            'created_at', 'last_login_at'
        ]
        read_only_fields = [
            'id', 'email_verified', 'phone_verified', 'created_at', 'last_login_at'
        ]

    def validate_date_of_birth(self, value):
        if value and value > timezone.now().date():
            raise serializers.ValidationError("Birth date cannot be in the future")
        return value

    def validate_phone_number(self, value):
        if value:
            # Check if phone number is already taken by another user
            user = self.instance
            if User.objects.filter(phone_number=value).exclude(pk=user.pk if user else None).exists():
                raise serializers.ValidationError("This phone number is already registered")
        return value


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    terms_accepted = serializers.BooleanField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'phone_number', 'first_name', 'last_name',
            'password', 'password_confirm', 'terms_accepted'
        ]

    def validate_username(self, value):
        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', value):
            raise serializers.ValidationError(
                "Username must be 3-30 characters long and contain only letters, numbers, and underscores"
            )
        return value

    def validate_email(self, value):
        # Additional email validation
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("This email is already registered")
        return value.lower()

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("This phone number is already registered")
        return value

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the terms and conditions")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': "Passwords don't match"
            })
        return attrs

    def create(self, validated_data):
        # Remove extra fields
        validated_data.pop('password_confirm')
        validated_data.pop('terms_accepted')
        
        # Create user
        user = User.objects.create_user(**validated_data)
        
        # Log registration activity
        UserActivity.objects.create(
            user=user,
            activity_type='verification',
            description='User registered',
            ip_address=self.context.get('request').META.get('REMOTE_ADDR') if self.context.get('request') else None
        )
        
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with enhanced validation"""
    
    def validate(self, attrs):
        email = attrs.get('email') or attrs.get(self.username_field)
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError("Email and password are required")
        
        # Get user and check login eligibility
        try:
            user = User.objects.get(email=email.lower())
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials")
        
        # Check if user can login
        can_login, message = user.can_login()
        if not can_login:
            raise serializers.ValidationError(message)
        
        # Authenticate
        user = authenticate(
            request=self.context.get('request'),
            username=email.lower(),
            password=password
        )
        
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        
        # Get tokens
        data = super().validate(attrs)
        
        # Add custom claims
        data['user'] = {
            'id': str(user.id),
            'email': user.email,
            'username': user.username,
            'full_name': user.get_full_name(),
            'is_seller': user.is_seller,
            'is_buyer': user.is_buyer,
            'is_verified': user.is_verified(),
        }
        
        # Update last login
        user.update_last_login()
        
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        token['is_seller'] = user.is_seller
        token['is_buyer'] = user.is_buyer
        token['is_verified'] = user.is_verified()
        
        return token


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for public data"""
    full_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'is_seller', 'is_buyer', 'email_verified', 'phone_verified',
            'created_at'
        ]
        read_only_fields = [
            'id', 'email_verified', 'phone_verified', 'created_at'
        ]


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=32, max_length=255)
    
    def validate_token(self, value):
        from .models import EmailVerificationToken
        
        try:
            token_obj = EmailVerificationToken.objects.get(
                token=value,
                is_used=False
            )
            if not token_obj.is_valid():
                raise serializers.ValidationError("Token has expired")
            
            # Store token object for use in view
            self._token_obj = token_obj
            return value
            
        except EmailVerificationToken.DoesNotExist:
            raise serializers.ValidationError("Invalid verification token")


class PhoneVerificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    
    def validate_phone_number(self, value):
        if not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Invalid phone number format")
        return value


class PhoneVerificationConfirmSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField(min_length=6, max_length=6)
    
    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Code must be 6 digits")
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=32, max_length=255)
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': "Passwords don't match"
            })
        return attrs
    
    def validate_token(self, value):
        from .models import PasswordResetToken
        
        try:
            token_obj = PasswordResetToken.objects.get(
                token=value,
                is_used=False
            )
            if not token_obj.is_valid():
                raise serializers.ValidationError("Token has expired")
            
            self._token_obj = token_obj
            return value
            
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Invalid reset token")


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': "Passwords don't match"
            })
        return attrs
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Invalid current password")
        return value


class LoginHistorySerializer(serializers.ModelSerializer):
    session_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = LoginHistory
        fields = [
            'id', 'ip_address', 'user_agent', 'method', 'country', 'city',
            'is_successful', 'failure_reason', 'login_at', 'logout_at',
            'session_duration'
        ]
        read_only_fields = ['id']
    
    def get_session_duration(self, obj):
        duration = obj.get_session_duration()
        if duration:
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return None


class UserActivitySerializer(serializers.ModelSerializer):
    activity_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    
    class Meta:
        model = UserActivity
        fields = [
            'id', 'activity_type', 'activity_display', 'description',
            'ip_address', 'created_at', 'metadata'
        ]
        read_only_fields = ['id']


class AddressCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'type', 'full_name', 'phone_number', 'street_address',
            'apartment', 'city', 'state', 'postal_code', 'country',
            'is_default'
        ]
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    def validate_email(self, value):
        return value.lower()
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        if not email or not password:
            raise serializers.ValidationError("Email and password are required")
        user = authenticate(username=email, password=password)
        if user is None:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("User account is inactive")
        attrs['user'] = user
        return attrs

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    def validate_email(self, value):
        if not User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("No user found with this email")
        return value.lower()

    def create(self, validated_data):
        user = User.objects.get(email=validated_data['email'])
        # Logic to send password reset email with token
        # ...
        return user