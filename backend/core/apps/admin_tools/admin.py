from django.contrib import admin
from .models import (
    AdminActionLog, SellerApprovalRequest, SystemNotification,
    PlatformSettings, UserReport
)

@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    list_display = ['admin_user', 'action_type', 'target_user', 'created_at']
    list_filter = ['action_type', 'created_at']
    search_fields = ['admin_user__email', 'target_user__email', 'description']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False  # Prevent manual creation
    
    def has_change_permission(self, request, obj=None):
        return False  # Prevent editing

@admin.register(SellerApprovalRequest)
class SellerApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ['seller', 'status', 'reviewed_by', 'submitted_at']
    list_filter = ['status', 'submitted_at', 'reviewed_at']
    search_fields = ['seller__business_name', 'seller__user__email']
    readonly_fields = ['submitted_at', 'reviewed_at']

@admin.register(SystemNotification)
class SystemNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'notification_type', 'priority', 'is_active', 'created_at']
    list_filter = ['notification_type', 'priority', 'is_active', 'target_user_type']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at']

@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'setting_type', 'is_public', 'updated_at']
    list_filter = ['setting_type', 'is_public']
    search_fields = ['key', 'description']
    readonly_fields = ['updated_at']

@admin.register(UserReport)
class UserReportAdmin(admin.ModelAdmin):
    list_display = ['reporter', 'reported_user', 'report_type', 'status', 'created_at']
    list_filter = ['report_type', 'status', 'created_at']
    search_fields = ['reporter__email', 'reported_user__email', 'description']
    readonly_fields = ['created_at', 'resolved_at']