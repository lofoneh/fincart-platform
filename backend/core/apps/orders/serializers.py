from rest_framework import serializers
from django.db import transaction
from .models import Order, OrderItem, OrderStatusHistory, OrderRefund
from apps.authentication.serializers import AddressSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(read_only=True)
    variant_name = serializers.CharField(read_only=True)
    seller_name = serializers.CharField(source='seller.business_name', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'variant', 'seller', 'quantity',
            'unit_price', 'total_price', 'product_name',
            'product_sku', 'variant_name', 'seller_name',
            'created_at'
        ]
        read_only_fields = [
            'id', 'product_name', 'product_sku', 'variant_name', 
            'seller_name', 'total_price', 'created_at'
        ]


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = OrderStatusHistory
        fields = [
            'id', 'status', 'status_display', 'notes', 
            'created_by_username', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class OrderRefundSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = OrderRefund
        fields = [
            'id', 'order', 'amount', 'reason', 'status', 
            'status_display', 'refund_reference', 'created_by_username',
            'created_at', 'processed_at'
        ]
        read_only_fields = ['id', 'created_at', 'processed_at']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    refunds = OrderRefundSerializer(many=True, read_only=True)
    shipping_address = AddressSerializer(read_only=True)
    billing_address = AddressSerializer(read_only=True)
    
    # Computed fields
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    can_be_cancelled = serializers.BooleanField(read_only=True)
    can_be_refunded = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'status', 'status_display',
            'payment_status', 'payment_status_display', 'subtotal',
            'shipping_cost', 'tax_amount', 'discount_amount', 'total_amount',
            'currency', 'shipping_address', 'billing_address', 'shipping_method',
            'tracking_number', 'payment_reference', 'payment_method',
            'customer_notes', 'items', 'status_history', 'refunds',
            'total_items', 'can_be_cancelled', 'can_be_refunded',
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at',
            'delivered_at', 'cancelled_at'
        ]
        read_only_fields = [
            'id', 'order_number', 'user', 'created_at', 'updated_at',
            'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at'
        ]


class OrderCreateSerializer(serializers.Serializer):
    shipping_address_id = serializers.UUIDField()
    billing_address_id = serializers.UUIDField(required=False)
    shipping_method = serializers.CharField(max_length=100, required=False)
    payment_method = serializers.CharField(max_length=50, required=False, default='wallet')
    customer_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_shipping_address_id(self, value):
        from apps.authentication.models import Address
        user = self.context['request'].user
        
        try:
            address = Address.objects.get(id=value, user=user)
            return address
        except Address.DoesNotExist:
            raise serializers.ValidationError("Invalid shipping address")
    
    def validate_billing_address_id(self, value):
        if value:
            from apps.authentication.models import Address
            user = self.context['request'].user
            
            try:
                address = Address.objects.get(id=value, user=user)
                return address
            except Address.DoesNotExist:
                raise serializers.ValidationError("Invalid billing address")
        return None


class OrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'shipping_method', 'tracking_number', 'customer_notes',
            'internal_notes'
        ]


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.ORDER_STATUS)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_status(self, value):
        order = self.context['order']
        current_status = order.status
        
        # Define valid status transitions
        valid_transitions = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['processing', 'cancelled'],
            'processing': ['shipped', 'cancelled'],
            'shipped': ['delivered'],
            'delivered': [],  # Final state
            'cancelled': ['refunded'],  # Can only refund cancelled orders
            'refunded': [],  # Final state
        }
        
        if value not in valid_transitions.get(current_status, []):
            raise serializers.ValidationError(
                f"Cannot change status from {current_status} to {value}"
            )
        
        return value


class OrderRefundCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderRefund
        fields = ['amount', 'reason']
    
    def validate_amount(self, value):
        order = self.context['order']
        
        # Check if refund amount exceeds order total
        if value > order.total_amount:
            raise serializers.ValidationError(
                "Refund amount cannot exceed order total"
            )
        
        # Check existing refunds
        existing_refunds = order.refunds.filter(
            status__in=['completed', 'processing']
        ).aggregate(total=serializers.models.Sum('amount'))['total'] or 0
        
        if (existing_refunds + value) > order.total_amount:
            available_refund = order.total_amount - existing_refunds
            raise serializers.ValidationError(
                f"Only {available_refund} available for refund"
            )
        
        return value