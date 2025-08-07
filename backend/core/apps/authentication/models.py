from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import timedelta
import uuid
import secrets
import string


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    
    # Improved phone number validation
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$', 
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(
        validators=[phone_regex], 
        max_length=17, 
        unique=True,
        db_index=True
    )
    
    # User type fields with better validation
    is_seller = models.BooleanField(default=False, db_index=True)
    is_buyer = models.BooleanField(default=True, db_index=True)
    
    # Verification fields
    email_verified = models.BooleanField(default=False, db_index=True)
    phone_verified = models.BooleanField(default=False, db_index=True)
    
    # Additional profile fields
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    profile_image = models.URLField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Account status
    is_active = models.BooleanField(default=True)
    is_suspended = models.BooleanField(default=False)
    suspended_until = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'phone_number']

    class Meta:
        db_table = 'auth_user'
        indexes = [
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['phone_number', 'phone_verified']),
            models.Index(fields=['is_seller', 'is_active']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.username

    def is_verified(self):
        """Check if user has verified both email and phone"""
        return self.email_verified and self.phone_verified

    def can_login(self):
        """Check if user can login (active, not suspended, verified)"""
        if not self.is_active:
            return False, "Account is deactivated"
        
        if self.is_suspended:
            if self.suspended_until and timezone.now() < self.suspended_until:
                return False, f"Account suspended until {self.suspended_until}"
            elif not self.suspended_until:
                return False, "Account is permanently suspended"
            else:
                # Suspension period has passed
                self.is_suspended = False
                self.suspended_until = None
                self.save(update_fields=['is_suspended', 'suspended_until'])
        
        if not self.email_verified:
            return False, "Email not verified"
        
        return True, "OK"

    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login_at = timezone.now()
        self.save(update_fields=['last_login_at'])


class Address(models.Model):
    ADDRESS_TYPES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    
    # Address fields
    type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='home')
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=17, blank=True)
    street_address = models.CharField(max_length=255)
    apartment = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='Ghana')
    
    # Additional fields
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'auth_address'
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['postal_code', 'city']),
        ]
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'
        
    def __str__(self):
        return f"{self.full_name} - {self.street_address}, {self.city}"

    def save(self, *args, **kwargs):
        # Ensure only one default address per user
        if self.is_default:
            Address.objects.filter(
                user=self.user, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)

    def get_formatted_address(self):
        """Return formatted address string"""
        parts = [self.street_address]
        if self.apartment:
            parts.append(f"Apt {self.apartment}")
        parts.extend([self.city, self.state, self.postal_code, self.country])
        return ", ".join(parts)


class BaseTokenModel(models.Model):
    """Abstract base class for token models"""
    TOKEN_LENGTH = 32
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    is_used = models.BooleanField(default=False, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['token', 'is_used']),
            models.Index(fields=['user', 'is_used']),
            models.Index(fields=['expires_at', 'is_used']),
        ]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_secure_token()
        super().save(*args, **kwargs)

    @classmethod
    def generate_secure_token(cls):
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(cls.TOKEN_LENGTH)

    def is_valid(self):
        """Check if token is valid (not used and not expired)"""
        return not self.is_used and timezone.now() < self.expires_at

    def use_token(self):
        """Mark token as used"""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])


class EmailVerificationToken(BaseTokenModel):
    VALIDITY_HOURS = 24
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=self.VALIDITY_HOURS)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'auth_email_verification_token'
        verbose_name = 'Email Verification Token'
        verbose_name_plural = 'Email Verification Tokens'

    def __str__(self):
        return f"Email verification for {self.user.email}"


class PasswordResetToken(BaseTokenModel):
    VALIDITY_HOURS = 1
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=self.VALIDITY_HOURS)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'auth_password_reset_token'
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'

    def __str__(self):
        return f"Password reset for {self.user.email}"


class PhoneVerificationToken(BaseTokenModel):
    VALIDITY_MINUTES = 10
    TOKEN_LENGTH = 6  # For SMS codes
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=self.VALIDITY_MINUTES)
        super().save(*args, **kwargs)

    @classmethod
    def generate_secure_token(cls):
        """Generate 6-digit numeric token for SMS"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))

    class Meta:
        db_table = 'auth_phone_verification_token'
        verbose_name = 'Phone Verification Token'
        verbose_name_plural = 'Phone Verification Tokens'

    def __str__(self):
        return f"Phone verification for {self.user.phone_number}"


class LoginHistory(models.Model):
    LOGIN_METHODS = [
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('social', 'Social Login'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    
    # Login details
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    method = models.CharField(max_length=10, choices=LOGIN_METHODS, default='email')
    
    # Geolocation (optional)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Status
    is_successful = models.BooleanField(default=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    
    # Session tracking
    session_id = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    login_at = models.DateTimeField(auto_now_add=True, db_index=True)
    logout_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'auth_login_history'
        ordering = ['-login_at']
        indexes = [
            models.Index(fields=['user', 'login_at']),
            models.Index(fields=['user', 'is_successful']),
            models.Index(fields=['ip_address', 'login_at']),
            models.Index(fields=['login_at']),
        ]
        verbose_name = 'Login History'
        verbose_name_plural = 'Login Histories'

    def __str__(self):
        status = "successful" if self.is_successful else "failed"
        return f"{self.user.email} - {status} login at {self.login_at}"

    def get_session_duration(self):
        """Get session duration if logged out"""
        if self.logout_at:
            return self.logout_at - self.login_at
        return None


class UserActivity(models.Model):
    """Track user activities for security and analytics"""
    ACTIVITY_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('password_change', 'Password Change'),
        ('email_change', 'Email Change'),
        ('profile_update', 'Profile Update'),
        ('address_add', 'Address Added'),
        ('address_update', 'Address Updated'),
        ('verification', 'Verification'),
        ('suspension', 'Account Suspension'),
        ('reactivation', 'Account Reactivation'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'auth_user_activity'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'activity_type']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['activity_type', 'created_at']),
        ]
        verbose_name = 'User Activity'
        verbose_name_plural = 'User Activities'

    def __str__(self):
        return f"{self.user.email} - {self.get_activity_type_display()}"