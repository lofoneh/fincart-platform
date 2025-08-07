from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import SellerProfile, SellerBankAccount

User = get_user_model()

class SellerRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerProfile
        fields = [
            'business_name', 'business_description', 'business_address',
            'business_phone', 'business_email', 'business_registration_number',
            'tax_identification_number', 'business_license', 'tax_certificate',
            'identity_document'
        ]
        
    def validate_business_email(self, value):
        if SellerProfile.objects.filter(business_email=value).exists():
            raise serializers.ValidationError("Business email already registered")
        return value

class SellerProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = SellerProfile
        fields = '__all__'
        read_only_fields = ['user', 'approval_status', 'approval_date', 'rating', 
                           'total_sales', 'total_orders', 'created_at', 'updated_at']

class UpdateSellerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerProfile
        fields = [
            'business_name', 'business_description', 'business_address',
            'business_phone', 'business_email', 'business_registration_number',
            'tax_identification_number', 'business_license', 'tax_certificate',
            'identity_document'
        ]

class SellerBankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerBankAccount
        fields = '__all__'
        read_only_fields = ['seller', 'verified', 'created_at']

class SellerDashboardSerializer(serializers.Serializer):
    seller_info = serializers.DictField()
    product_stats = serializers.DictField()
    order_stats = serializers.DictField()
    revenue_stats = serializers.DictField()

class SellerAnalyticsSerializer(serializers.Serializer):
    date_range = serializers.DictField()
    top_products = serializers.ListField()
    daily_sales = serializers.ListField()
    order_status_distribution = serializers.ListField()

class PublicSellerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerProfile
        fields = ['id', 'business_name', 'business_description', 'rating', 
                 'total_orders', 'created_at']