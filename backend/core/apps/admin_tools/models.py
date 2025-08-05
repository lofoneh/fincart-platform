# apps/admin_tools/models.py
from django.db import models
from apps.authentication.models import User
from apps.sellers.models import SellerProfile
import uuid

class AdminActionLog(models.Model):
    ACTION_TYPES = [
        ('approve_seller', 'Approve Seller'),
        ('reject_seller', 'Reject Seller'),
        ('suspend_seller', 'Suspend Seller'),
        ('ban_user', 'Ban User'),
        ('unban_user', 'Unban User'),
        ('delete_product', 'Delete Product'),
        ('feature_product', 'Feature Product'),
        ('refund_order', 'Refund Order'),
        ('cancel_order', 'Cancel Order'),
        ('system_maintenance', 'System Maintenance'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_actions')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    target_object_id = models.CharField(max_length=100, blank=True)  # For any object ID
    target_object_type = models.CharField(max_length=50, blank=True)  # Model name
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.admin_user.email} - {self.get_action_type_display()}"

    class Meta:
        ordering = ['-created_at']

class SellerApprovalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('needs_info', 'Needs Additional Information'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.OneToOneField(SellerProfile, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    review_notes = models.TextField(blank=True)
    additional_info_requested = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.seller.business_name} - {self.get_status_display()}"

class SystemNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('system_alert', 'System Alert'),
        ('maintenance', 'Maintenance'),
        ('feature_update', 'Feature Update'),
        ('policy_change', 'Policy Change'),
        ('security_alert', 'Security Alert'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    is_active = models.BooleanField(default=True)
    target_user_type = models.CharField(max_length=20, choices=[
        ('all', 'All Users'),
        ('buyers', 'Buyers Only'),
        ('sellers', 'Sellers Only'),
        ('admins', 'Admins Only'),
    ], default='all')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.get_priority_display()}"

    class Meta:
        ordering = ['-created_at']

class PlatformSettings(models.Model):
    SETTING_TYPES = [
        ('general', 'General'),
        ('payment', 'Payment'),
        ('shipping', 'Shipping'),
        ('security', 'Security'),
        ('notification', 'Notification'),
    ]
    
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    setting_type = models.CharField(max_length=20, choices=SETTING_TYPES)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)  # Can be accessed via API
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key}: {self.value[:50]}"

class UserReport(models.Model):
    REPORT_TYPES = [
        ('spam', 'Spam'),
        ('fraud', 'Fraud'),
        ('inappropriate_content', 'Inappropriate Content'),
        ('fake_product', 'Fake Product'),
        ('poor_service', 'Poor Service'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_received')
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    description = models.TextField()
    evidence_file = models.FileField(upload_to='reports/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_response = models.TextField(blank=True)
    handled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Report by {self.reporter.email} against {self.reported_user.email}"

    class Meta:
        ordering = ['-created_at']