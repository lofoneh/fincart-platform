from django.contrib import admin
from .models import SellerProfile, SellerBankAccount

@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ['business_name', 'user', 'approval_status', 'rating', 'total_orders', 'created_at']
    list_filter = ['approval_status', 'created_at']
    search_fields = ['business_name', 'user__email', 'business_email']
    readonly_fields = ['created_at', 'updated_at', 'total_sales', 'total_orders']
    
    fieldsets = (
        ('Business Information', {
            'fields': ('user', 'business_name', 'business_description', 'business_address')
        }),
        ('Contact Details', {
            'fields': ('business_phone', 'business_email')
        }),
        ('Legal Information', {
            'fields': ('business_registration_number', 'tax_identification_number')
        }),
        ('Documents', {
            'fields': ('business_license', 'tax_certificate', 'identity_document')
        }),
        ('Status & Metrics', {
            'fields': ('approval_status', 'approval_date', 'rating', 'total_sales', 'total_orders')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )

@admin.register(SellerBankAccount)
class SellerBankAccountAdmin(admin.ModelAdmin):
    list_display = ['seller', 'bank_name', 'account_name', 'is_primary', 'verified']
    list_filter = ['is_primary', 'verified', 'bank_name']
    search_fields = ['seller__business_name', 'account_name', 'account_number']