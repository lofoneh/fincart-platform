from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
import requests
import os
import logging

from .models import Order, OrderItem, OrderStatusHistory, OrderRefund
from .serializers import (
    OrderSerializer, OrderCreateSerializer, OrderUpdateSerializer,
    OrderStatusUpdateSerializer, OrderRefundCreateSerializer
)
from apps.cart.models import Cart

logger = logging.getLogger(__name__)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.select_related(
            'user', 'shipping_address', 'billing_address'
        ).prefetch_related(
            'items__product',
            'items__variant',
            'items__seller',
            'status_history',
            'refunds'
        )
        
        if user.is_seller:
            # Sellers see orders containing their products
            return queryset.filter(items__seller__user=user).distinct()
        else:
            # Buyers see their own orders
            return queryset.filter(user=user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OrderUpdateSerializer
        return OrderSerializer
    
    def create(self, request, *args, **kwargs):
        """Create order from user's cart"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                # Get and validate cart
                cart = self.get_user_cart(request.user)
                
                # Create order
                order = self.create_order_from_cart(cart, serializer.validated_data)
                
                # Process payment
                payment_result = self.process_payment(order, request.user)
                
                if payment_result['success']:
                    # Update order status
                    order.payment_status = 'paid'
                    order.payment_reference = payment_result.get('transaction_id', '')
                    order.status = 'confirmed'
                    order.confirmed_at = timezone.now()
                    order.save()
                    
                    # Create status history
                    self.create_status_history(order, 'confirmed', 'Order confirmed after payment')
                    
                    # Clear cart
                    cart.items.all().delete()
                    
                    # Send notifications (implement as needed)
                    # self.send_order_confirmation(order)
                    
                    logger.info(f"Order {order.order_number} created successfully for user {request.user.id}")
                    
                    return Response(
                        OrderSerializer(order).data, 
                        status=status.HTTP_201_CREATED
                    )
                else:
                    # Payment failed, rollback will happen automatically
                    logger.error(f"Payment failed for order: {payment_result['error']}")
                    return Response({
                        'error': 'Payment failed',
                        'details': payment_result['error']
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
        except Exception as e:
            logger.error(f"Order creation failed: {str(e)}")
            return Response({
                'error': 'Order creation failed',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_user_cart(self, user):
        """Get user's cart and validate it's not empty"""
        try:
            cart = Cart.objects.prefetch_related(
                'items__product',
                'items__variant'
            ).get(user=user)
        except Cart.DoesNotExist:
            raise ValueError('Cart not found')
        
        if not cart.items.exists():
            raise ValueError('Cart is empty')
        
        return cart
    
    def create_order_from_cart(self, cart, validated_data):
        """Create order from cart items"""
        # Calculate amounts
        subtotal = cart.get_total_price()
        shipping_cost = Decimal(str(validated_data.get('shipping_cost', 0)))
        tax_rate = Decimal('0.125')  # 12.5% VAT
        tax_amount = subtotal * tax_rate
        total_amount = subtotal + shipping_cost + tax_amount
        
        # Create order
        order = Order.objects.create(
            user=cart.user,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            tax_amount=tax_amount,
            total_amount=total_amount,
            shipping_address=validated_data['shipping_address_id'],
            billing_address=validated_data.get('billing_address_id'),
            shipping_method=validated_data.get('shipping_method', ''),
            payment_method=validated_data.get('payment_method', 'wallet'),
            customer_notes=validated_data.get('customer_notes', '')
        )
        
        # Create order items
        for cart_item in cart.items.all():
            unit_price = cart_item.get_unit_price()
            total_price = cart_item.get_total_price()
            
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                seller=cart_item.product.seller,
                quantity=cart_item.quantity,
                unit_price=unit_price,
                total_price=total_price,
                product_name=cart_item.product.name,
                product_sku=getattr(cart_item.product, 'sku', str(cart_item.product.id)),
                variant_name=cart_item.variant.name if cart_item.variant else ''
            )
        
        # Create initial status history
        self.create_status_history(order, 'pending', 'Order created')
        
        return order
    
    def create_status_history(self, order, status, notes=''):
        """Create status history entry"""
        OrderStatusHistory.objects.create(
            order=order,
            status=status,
            notes=notes,
            created_by=self.request.user
        )
    
    def process_payment(self, order, user):
        """Process payment via FastAPI wallet service"""
        wallet_service_url = os.getenv('WALLET_SERVICE_URL', 'http://localhost:8001')
        
        payload = {
            'user_id': str(user.id),
            'amount': float(order.total_amount),
            'currency': order.currency,
            'reference_id': str(order.id),
            'description': f'Payment for order {order.order_number}'
        }
        
        try:
            response = requests.post(
                f'{wallet_service_url}/api/v1/transactions/debit/',
                json=payload,
                headers={
                    'Authorization': f'Bearer {getattr(self.request, "auth", "")}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                transaction_data = response.json()
                return {
                    'success': True, 
                    'transaction_id': transaction_data.get('id', ''),
                    'reference': transaction_data.get('reference', '')
                }
            else:
                error_detail = 'Payment service error'
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', error_detail)
                except:
                    pass
                
                return {'success': False, 'error': error_detail}
                
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Payment service timeout'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Unable to connect to payment service'}
        except Exception as e:
            return {'success': False, 'error': f'Payment processing error: {str(e)}'}
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update order status with validation"""
        order = self.get_object()
        
        # Check permissions
        if not request.user.is_staff and not request.user.is_seller:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = OrderStatusUpdateSerializer(
            data=request.data,
            context={'order': order}
        )
        
        if serializer.is_valid():
            new_status = serializer.validated_data['status']
            notes = serializer.validated_data.get('notes', '')
            
            with transaction.atomic():
                # Update order status
                old_status = order.status
                order.status = new_status
                order.save()
                
                # Create status history
                self.create_status_history(order, new_status, notes)
                
                logger.info(f"Order {order.order_number} status updated from {old_status} to {new_status}")
            
            # Send notification (implement as needed)
            # self.send_status_update_notification(order, old_status, new_status)
            
            return Response({
                'message': 'Order status updated successfully',
                'old_status': old_status,
                'new_status': new_status
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel order"""
        order = self.get_object()
        
        # Check if order can be cancelled
        if not order.can_be_cancelled():
            return Response(
                {'error': 'Order cannot be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Only order owner or staff can cancel
        if order.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        reason = request.data.get('reason', 'Cancelled by customer')
        
        with transaction.atomic():
            order.status = 'cancelled'
            order.cancelled_at = timezone.now()
            order.save()
            
            # Create status history
            self.create_status_history(order, 'cancelled', reason)
            
            # Process refund if payment was made
            if order.payment_status == 'paid':
                self.process_refund_for_cancellation(order, reason)
        
        logger.info(f"Order {order.order_number} cancelled by user {request.user.id}")
        
        return Response({'message': 'Order cancelled successfully'})
    
    def process_refund_for_cancellation(self, order, reason):
        """Process automatic refund for cancelled paid orders"""
        try:
            # Create refund record
            refund = OrderRefund.objects.create(
                order=order,
                amount=order.total_amount,
                reason=f"Automatic refund for cancellation: {reason}",
                created_by=self.request.user
            )
            
            # Process refund via wallet service (implement as needed)
            # refund_result = self.process_wallet_refund(order, refund)
            
            logger.info(f"Refund created for cancelled order {order.order_number}")
            
        except Exception as e:
            logger.error(f"Failed to process refund for order {order.order_number}: {str(e)}")
    
    @action(detail=True, methods=['post'])
    def create_refund(self, request, pk=None):
        """Create manual refund"""
        order = self.get_object()
        
        # Check permissions (only staff or seller)
        if not request.user.is_staff and not request.user.is_seller:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if order can be refunded
        if not order.can_be_refunded():
            return Response(
                {'error': 'Order cannot be refunded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = OrderRefundCreateSerializer(
            data=request.data,
            context={'order': order}
        )
        
        if serializer.is_valid():
            with transaction.atomic():
                refund = serializer.save(
                    order=order,
                    created_by=request.user
                )
            
            return Response({
                'message': 'Refund created successfully',
                'refund_id': refund.id
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get order summary for current user"""
        user = request.user
        orders = self.get_queryset()
        
        summary = {
            'total_orders': orders.count(),
            'pending_orders': orders.filter(status='pending').count(),
            'confirmed_orders': orders.filter(status='confirmed').count(),
            'shipped_orders': orders.filter(status='shipped').count(),
            'delivered_orders': orders.filter(status='delivered').count(),
            'cancelled_orders': orders.filter(status='cancelled').count(),
        }
        
        if not user.is_seller:
            # Add spending summary for buyers
            from django.db.models import Sum
            total_spent = orders.filter(
                payment_status='paid'
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            summary['total_spent'] = total_spent
        
        return Response(summary)