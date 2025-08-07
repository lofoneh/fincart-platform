from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import Cart, CartItem
from .serializers import (
    CartSerializer, 
    CartItemSerializer, 
    CartItemCreateSerializer,
    CartItemUpdateSerializer
)
from apps.products.models import Product, ProductVariant


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user).prefetch_related(
            'items__product',
            'items__variant'
        )
    
    def get_or_create_cart(self):
        """Get or create cart for current user"""
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        return cart
    
    def list(self, request, *args, **kwargs):
        """Get user's cart"""
        cart = self.get_or_create_cart()
        serializer = self.get_serializer(cart)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def add_item(self, request):
        """Add item to cart"""
        cart = self.get_or_create_cart()
        
        serializer = CartItemCreateSerializer(
            data=request.data,
            context={'cart': cart}
        )
        
        if serializer.is_valid():
            with transaction.atomic():
                cart_item = serializer.save()
                
            # Return updated cart
            cart_serializer = CartSerializer(cart)
            return Response(cart_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['put'])
    def update_item(self, request):
        """Update cart item quantity"""
        cart = self.get_or_create_cart()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response(
                {'error': 'item_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        
        serializer = CartItemUpdateSerializer(cart_item, data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                updated_item = serializer.save()
                
            if updated_item is None:  # Item was deleted
                return Response({'message': 'Item removed from cart'})
            
            # Return updated cart
            cart_serializer = CartSerializer(cart)
            return Response(cart_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['delete'])
    def remove_item(self, request):
        """Remove item from cart"""
        cart = self.get_or_create_cart()
        item_id = request.query_params.get('item_id')
        
        if not item_id:
            return Response(
                {'error': 'item_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        
        with transaction.atomic():
            cart_item.delete()
        
        # Return updated cart
        cart_serializer = CartSerializer(cart)
        return Response(cart_serializer.data)
    
    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """Clear all items from cart"""
        cart = self.get_or_create_cart()
        
        with transaction.atomic():
            cart.clear()
        
        cart_serializer = CartSerializer(cart)
        return Response(cart_serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get cart summary"""
        cart = self.get_or_create_cart()
        
        summary = {
            'total_items': cart.get_total_items(),
            'unique_items': cart.get_unique_items_count(),
            'total_price': cart.get_total_price(),
            'is_empty': cart.is_empty(),
            'currency': 'GHS'
        }
        
        return Response(summary)


class CartItemViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_cart = Cart.objects.filter(user=self.request.user).first()
        if user_cart:
            return CartItem.objects.filter(cart=user_cart).select_related(
                'product', 'variant'
            )
        return CartItem.objects.none()
    
    def perform_create(self, serializer):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        serializer.save(cart=cart)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        with transaction.atomic():
            self.perform_destroy(instance)
        
        return Response(status=status.HTTP_204_NO_CONTENT)