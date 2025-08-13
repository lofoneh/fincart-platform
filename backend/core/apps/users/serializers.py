from rest_framework import serializers
from apps.authentication.models import User, Address


class UserDashboardSerializer(serializers.ModelSerializer):
    """Serializer for user dashboard information"""
    full_name = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'is_seller', 'is_buyer', 'email_verified', 'phone_verified',
            'date_joined', 'last_login', 'total_orders', 'total_spent'
        ]
        read_only_fields = ['id', 'email', 'date_joined', 'last_login', 
                            'email_verified', 'phone_verified']
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username
    
    
class UpdateUserProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile information"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'is_seller', 'is_buyer', 'email_verified', 'phone_verified'
        ]
        read_only_fields = ['id', 'email_verified', 'phone_verified']
        
class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'is_seller', 'is_buyer', 'email_verified', 'phone_verified',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'email', 'date_joined', 'last_login', 'email_verified', 'phone_verified']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

class AddressSerializer(serializers.ModelSerializer):
    """Serializer for user addresses"""
    
    class Meta:
        model = Address
        fields = [
            'id', 'user', 'street_address', 'city', 'state', 
            'postal_code', 'country', 'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Set the user from the request context
        validated_data['user'] = self.context['request'].user
        
        # If this is set as default, unset other default addresses
        if validated_data.get('is_default', False):
            Address.objects.filter(
                user=validated_data['user'], 
                is_default=True
            ).update(is_default=False)
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # If this is being set as default, unset other default addresses
        if validated_data.get('is_default', False):
            Address.objects.filter(
                user=instance.user, 
                is_default=True
            ).exclude(id=instance.id).update(is_default=False)
        
        return super().update(instance, validated_data)

class UserAddressListSerializer(serializers.ModelSerializer):
    """Serializer for listing user addresses"""
    addresses = AddressSerializer(many=True, read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'addresses']

# Optional: Create a comprehensive user profile serializer
class CompleteUserProfileSerializer(serializers.ModelSerializer):
    """Complete user profile with addresses and additional info"""
    addresses = AddressSerializer(many=True, read_only=True)
    full_name = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'is_seller', 'is_buyer', 'email_verified', 'phone_verified',
            'date_joined', 'last_login', 'addresses', 'total_orders'
        ]
        read_only_fields = ['id', 'email', 'date_joined', 'last_login', 'email_verified', 'phone_verified']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_total_orders(self, obj):
        # Implement based on your Order model
        try:
            # Replace with actual order count logic
            # return obj.orders.count()
            return 0
        except AttributeError:
            return 0