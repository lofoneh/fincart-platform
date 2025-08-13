# apps/admin_tools/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    AdminActionLog, SellerApprovalRequest, SystemNotification,
    PlatformSettings, UserReport
)
from apps.sellers.models import SellerProfile
from apps.products.models import Product
from apps.orders.models import Order

User = get_user_model()

class AdminActionLogSerializer(serializers.ModelSerializer):
    admin_user_email = serializers.CharField(source='admin_user.email', read_only=True)
    target_user_email = serializers.CharField(source='target_user.email', read_only=True)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)

    class Meta:
        model = AdminActionLog
        fields = [
            'id', 'admin_user', 'admin_user_email', 'action_type', 'action_type_display',
            'target_user', 'target_user_email', 'target_object_id', 'target_object_type',
            'description', 'ip_address', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class SellerApprovalRequestSerializer(serializers.ModelSerializer):
    seller_business_name = serializers.CharField(source='seller.business_name', read_only=True)
    seller_email = serializers.CharField(source='seller.user.email', read_only=True)
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SellerApprovalRequest
        fields = [
            'id', 'seller', 'seller_business_name', 'seller_email', 'status', 'status_display',
            'reviewed_by', 'reviewed_by_email', 'review_notes', 'additional_info_requested',
            'submitted_at', 'reviewed_at'
        ]
        read_only_fields = ['id', 'submitted_at', 'reviewed_at']

class SystemNotificationSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    target_user_type_display = serializers.CharField(source='get_target_user_type_display', read_only=True)

    class Meta:
        model = SystemNotification
        fields = [
            'id', 'title', 'message', 'notification_type', 'notification_type_display',
            'priority', 'priority_display', 'is_active', 'target_user_type', 
            'target_user_type_display', 'created_by', 'created_by_email', 
            'created_at', 'expires_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at']

class PlatformSettingsSerializer(serializers.ModelSerializer):
    updated_by_email = serializers.CharField(source='updated_by.email', read_only=True)
    setting_type_display = serializers.CharField(source='get_setting_type_display', read_only=True)

    class Meta:
        model = PlatformSettings
        fields = [
            'key', 'value', 'setting_type', 'setting_type_display', 'description',
            'is_public', 'updated_by', 'updated_by_email', 'updated_at'
        ]
        read_only_fields = ['updated_by', 'updated_at']

class UserReportSerializer(serializers.ModelSerializer):
    reporter_email = serializers.CharField(source='reporter.email', read_only=True)
    reported_user_email = serializers.CharField(source='reported_user.email', read_only=True)
    handled_by_email = serializers.CharField(source='handled_by.email', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = UserReport
        fields = [
            'id', 'reporter', 'reporter_email', 'reported_user', 'reported_user_email',
            'report_type', 'report_type_display', 'description', 'evidence_file',
            'status', 'status_display', 'admin_response', 'handled_by', 'handled_by_email',
            'created_at', 'resolved_at'
        ]
        read_only_fields = ['id', 'created_at', 'resolved_at']

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

# Management Serializers
class UserManagementSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    login_count = serializers.SerializerMethodField()
    last_login_ip = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'full_name', 'is_active',
            'is_seller', 'is_buyer', 'email_verified', 'phone_verified',
            'date_joined', 'last_login', 'login_count', 'last_login_ip'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_login_count(self, obj):
        return obj.login_history.filter(is_successful=True).count()

    def get_last_login_ip(self, obj):
        last_login = obj.login_history.filter(is_successful=True).first()
        return last_login.ip_address if last_login else None

class SellerManagementSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    approval_status_display = serializers.CharField(source='get_approval_status_display', read_only=True)
    total_products = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()

    class Meta:
        model = SellerProfile
        fields = '__all__'  # Use all fields initially
        read_only_fields = ['id', 'created_at', 'approval_date']

    def get_total_products(self, obj):
        try:
            return obj.products.count()
        except AttributeError:
            return 0

    def get_total_orders(self, obj):
        # Implement based on your Order model structure
        try:
            # Replace with actual order counting logic
            return 0
        except AttributeError:
            return 0

    def to_representation(self, instance):
        """Override to safely handle missing fields"""
        data = super().to_representation(instance)
        
        # Add computed fields
        data['user_email'] = instance.user.email if hasattr(instance, 'user') and instance.user else None
        data['total_products'] = self.get_total_products(instance)
        data['total_orders'] = self.get_total_orders(instance)
        
        # Add display fields if they exist
        if hasattr(instance, 'get_approval_status_display'):
            data['approval_status_display'] = instance.get_approval_status_display()
        
        return data

class ProductManagementSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='seller.business_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_sales = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'seller', 'seller_name', 'category', 'category_name',
            'price', 'status', 'status_display', 'is_featured', 'stock_quantity',
            'view_count', 'created_at', 'updated_at', 'total_sales'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'view_count']

    def get_total_sales(self, obj):
        # Implement based on your OrderItem model
        return 0  # Replace with actual calculation