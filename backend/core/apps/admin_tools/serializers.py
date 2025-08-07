from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    AdminActionLog, SellerApprovalRequest, SystemNotification,
    PlatformSettings, UserReport
)
from apps.sellers.models import SellerProfile
from apps.products.models import Product

User = get_user_model()

class AdminActionLogSerializer(serializers.ModelSerializer):
    admin_user_email = serializers.CharField(source='admin_user.email', read_only=True)
    target_user_email = serializers.CharField(source='target_user.email', read_only=True)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    
    class Meta:
        model = AdminActionLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

class SellerApprovalRequestSerializer(serializers.ModelSerializer):
    seller_business_name = serializers.CharField(source='seller.business_name', read_only=True)
    seller_email = serializers.CharField(source='seller.user.email', read_only=True)
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = SellerApprovalRequest
        fields = '__all__'
        read_only_fields = ['id', 'seller', 'submitted_at', 'reviewed_at']

class SystemNotificationSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    class Meta:
        model = SystemNotification
        fields = '__all__'
        read_only_fields = ['id', 'created_by', 'created_at']

    def validate(self, data):
        # Ensure expires_at is after now if provided
        if data.get('expires_at') and data['expires_at'] <= timezone.now():
            raise serializers.ValidationError({
                'expires_at': 'Expiration date must be in the future'
            })
        return data

class PlatformSettingsSerializer(serializers.ModelSerializer):
    updated_by_email = serializers.CharField(source='updated_by.email', read_only=True)
    setting_type_display = serializers.CharField(source='get_setting_type_display', read_only=True)
    
    class Meta:
        model = PlatformSettings
        fields = '__all__'
        read_only_fields = ['updated_by', 'updated_at']

    def validate_key(self, value):
        if not value.replace('_', '').replace('-', '').isalnum():
            raise serializers.ValidationError(
                "Setting key can only contain alphanumeric characters, underscores, and hyphens"
            )
        return value.lower()

class UserReportSerializer(serializers.ModelSerializer):
    reporter_email = serializers.CharField(source='reporter.email', read_only=True)
    reported_user_email = serializers.CharField(source='reported_user.email', read_only=True)
    handled_by_email = serializers.CharField(source='handled_by.email', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = UserReport
        fields = '__all__'
        read_only_fields = [
            'id', 'reporter', 'created_at', 'resolved_at', 
            'handled_by', 'admin_response'
        ]

# Dashboard and Analytics Serializers
class AdminDashboardSerializer(serializers.Serializer):
    user_stats = serializers.DictField()
    product_stats = serializers.DictField()
    order_stats = serializers.DictField()
    revenue_stats = serializers.DictField()
    system_health = serializers.DictField()

class PlatformAnalyticsSerializer(serializers.Serializer):
    date_range = serializers.DictField()
    user_growth = serializers.ListField()
    order_trends = serializers.ListField()
    top_categories = serializers.ListField()
    top_sellers = serializers.ListField()

class UserManagementSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    last_login_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 
            'full_name', 'is_active', 'is_seller', 'is_staff', 
            'date_joined', 'last_login', 'last_login_formatted', 'phone_number'
        ]
        read_only_fields = ['id', 'date_joined']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username
    
    def get_last_login_formatted(self, obj):
        return obj.last_login.strftime('%Y-%m-%d %H:%M') if obj.last_login else 'Never'

class SellerManagementSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    approval_status_display = serializers.CharField(source='get_approval_status_display', read_only=True)
    days_since_registration = serializers.SerializerMethodField()
    
    class Meta:
        model = SellerProfile
        fields = [
            'id', 'business_name', 'user_email', 'approval_status', 
            'approval_status_display', 'rating', 'total_sales', 
            'total_orders', 'created_at', 'days_since_registration'
        ]
        read_only_fields = ['id', 'created_at', 'total_sales', 'total_orders']
    
    def get_days_since_registration(self, obj):
        return (timezone.now().date() - obj.created_at.date()).days

class ProductManagementSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='seller.business_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'seller_name', 'category_name', 'price', 
            'stock_quantity', 'status', 'status_display', 'is_featured', 
            'view_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'view_count']