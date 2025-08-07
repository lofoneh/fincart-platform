from rest_framework import serializers
from django.shortcuts import get_object_or_404
from .models import Cart, CartItem
from apps.products.models import Product, ProductVariant


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.CharField(source='product.image_url', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'variant', 'quantity',
            'product_name', 'product_image', 'variant_name',
            'unit_price', 'total_price', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate(self, data):
        product = data.get('product')
        variant = data.get('variant')
        quantity = data.get('quantity', 1)
        
        # Validate variant belongs to product
        if variant and variant.product != product:
            raise serializers.ValidationError("Variant must belong to the selected product")
        
        # Check stock availability
        if hasattr(product, 'stock') and product.stock < quantity:
            raise serializers.ValidationError(f"Only {product.stock} items available in stock")
        
        if variant and hasattr(variant, 'stock') and variant.stock < quantity:
            raise serializers.ValidationError(f"Only {variant.stock} variant items available in stock")
        
        return data


class CartItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['product', 'variant', 'quantity']

    def create(self, validated_data):
        cart = self.context['cart']
        product = validated_data['product']
        variant = validated_data.get('variant')
        quantity = validated_data['quantity']
        
        # Check if item already exists in cart
        try:
            cart_item = CartItem.objects.get(
                cart=cart,
                product=product,
                variant=variant
            )
            # Update existing item
            cart_item.quantity += quantity
            cart_item.save()
        except CartItem.DoesNotExist:
            # Create new item
            cart_item = CartItem.objects.create(
                cart=cart,
                **validated_data
            )
        
        return cart_item


class CartItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['quantity']

    def update(self, instance, validated_data):
        quantity = validated_data.get('quantity')
        if quantity <= 0:
            instance.delete()
            return None
        else:
            instance.quantity = quantity
            instance.save()
            return instance


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    unique_items_count = serializers.IntegerField(read_only=True)
    is_empty = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Cart
        fields = [
            'id', 'user', 'items', 'total_items', 'total_price',
            'unique_items_count', 'is_empty', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']