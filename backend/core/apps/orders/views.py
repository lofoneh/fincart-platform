# apps/orders/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Order, OrderItem
from .serializers import OrderSerializer, OrderCreateSerializer
from apps.cart.models import Cart
import requests
import os

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_seller:
            # Sellers see orders for their products
            return Order.objects.filter(items__seller__user=user).distinct()
        else:
            # Buyers see their own orders
            return Order.objects.filter(user=user)
    
    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get user's cart
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not cart.items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create order from cart
        order = self.create_order_from_cart(cart, serializer.validated_data)
        
        # Process payment via wallet service
        payment_result = self.process_payment(order, request.user)
        
        if payment_result['success']:
            order.payment_status = 'paid'
            order.status = 'confirmed'
            order.save()
            
            # Clear cart
            cart.items.all().delete()
            
            # Send notifications
            # send_order_confirmation.delay(order.id)
            
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        else:
            order.delete()
            return Response({
                'error': 'Payment failed',
                'details': payment_result['error']
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def create_order_from_cart(self, cart, validated_data):
        # Calculate totals
        subtotal = cart.get_total_price()
        shipping_cost = validated_data.get('shipping_cost', 0)
        tax_amount = subtotal * 0.125  # 12.5% VAT
        total_amount = subtotal + shipping_cost + tax_amount
        
        # Create order
        order = Order.objects.create(
            user=cart.user,
            order_number=Order().generate_order_number(),
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            tax_amount=tax_amount,
            total_amount=total_amount,
            shipping_address=validated_data['shipping_address']
        )
        
        # Create order items
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                seller=cart_item.product.seller,
                quantity=cart_item.quantity,
                unit_price=cart_item.product.price,
                total_price=cart_item.get_total_price(),
                product_name=cart_item.product.name,
                product_sku=cart_item.product.id
            )
        
        return order
    
    def process_payment(self, order, user):
        """Process payment via FastAPI wallet service"""
        wallet_service_url = os.getenv('WALLET_SERVICE_URL', 'http://fastapi_wallet:8001')
        
        payload = {
            'user_id': str(user.id),
            'amount': float(order.total_amount),
            'currency': order.currency,
            'reference_id': str(order.id),
            'description': f'Payment for order {order.order_number}'
        }
        
        try:
            response = requests.post(
                f'{wallet_service_url}/transactions/',
                json=payload,
                headers={
                    'Authorization': f'Bearer {self.request.auth}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return {'success': True, 'transaction_id': response.json()['id']}
            else:
                return {'success': False, 'error': response.json().get('detail', 'Payment failed')}
                
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        notes = request.data.get('notes', '')
        
        if new_status not in dict(Order.ORDER_STATUS):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update order status
        order.status = new_status
        order.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
            notes=notes,
            created_by=request.user
        )
        
        # Send notification to buyer
        # send_order_status_update.delay(order.id, new_status)
        
        return Response({'message': 'Order status updated successfully'})