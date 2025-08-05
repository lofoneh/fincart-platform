from rest_framework import generics, viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Avg, Q
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import SellerProfile, SellerBankAccount
from apps.authentication.models import User
from apps.products.models import Product
from apps.orders.models import Order, OrderItem
from .serializers import (
    SellerRegistrationSerializer, SellerProfileSerializer,
    UpdateSellerProfileSerializer, SellerBankAccountSerializer,
    SellerDashboardSerializer, SellerAnalyticsSerializer,
    PublicSellerProfileSerializer
)
from .permissions import IsSellerOwner

class SellerRegistrationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Check if user is already a seller
        if hasattr(request.user, 'sellerprofile'):
            return Response(
                {'error': 'User is already registered as a seller'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = SellerRegistrationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            # Create seller profile
            seller_profile = serializer.save(user=request.user)
            
            # Update user to mark as seller
            request.user.is_seller = True
            request.user.save()
        
        return Response({
            'message': 'Seller registration submitted successfully. Awaiting admin approval.',
            'seller_profile': SellerProfileSerializer(seller_profile, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)

class SellerProfileView(generics.RetrieveAPIView):
    serializer_class = SellerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        try:
            return SellerProfile.objects.get(user=self.request.user)
        except SellerProfile.DoesNotExist:
            return Response(
                {'error': 'Seller profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class UpdateSellerProfileView(generics.UpdateAPIView):
    serializer_class = UpdateSellerProfileSerializer
    permission_classes = [IsSellerOwner]

    def get_object(self):
        return get_object_or_404(SellerProfile, user=self.request.user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # If seller is updating profile while pending approval, reset to pending
        if instance.approval_status == 'rejected':
            instance.approval_status = 'pending'
            instance.save()
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            'message': 'Seller profile updated successfully',
            'data': serializer.data
        })

class SellerDashboardView(APIView):
    permission_classes = [IsSellerOwner]

    def get(self, request):
        try:
            seller_profile = SellerProfile.objects.get(user=request.user)
        except SellerProfile.DoesNotExist:
            return Response(
                {'error': 'Seller profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get dashboard data
        dashboard_data = self.get_dashboard_data(seller_profile)
        serializer = SellerDashboardSerializer(dashboard_data)
        return Response(serializer.data)
    
    def get_dashboard_data(self, seller_profile):
        # Get date ranges
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        last_7_days = today - timedelta(days=7)
        
        # Product statistics
        products = Product.objects.filter(seller=seller_profile)
        total_products = products.count()
        active_products = products.filter(status='active').count()
        low_stock_products = products.filter(
            stock_quantity__lte=models.F('low_stock_threshold'),
            track_inventory=True
        ).count()
        
        # Order statistics
        orders = Order.objects.filter(items__seller=seller_profile).distinct()
        total_orders = orders.count()
        pending_orders = orders.filter(status__in=['pending', 'confirmed']).count()
        completed_orders = orders.filter(status='delivered').count()
        
        # Recent orders (last 30 days)
        recent_orders = orders.filter(created_at__date__gte=last_30_days)
        orders_last_30_days = recent_orders.count()
        orders_last_7_days = orders.filter(created_at__date__gte=last_7_days).count()
        
        # Revenue statistics
        order_items = OrderItem.objects.filter(seller=seller_profile)
        total_revenue = order_items.aggregate(
            total=Sum('total_price')
        )['total'] or 0
        
        revenue_last_30_days = order_items.filter(
            created_at__date__gte=last_30_days
        ).aggregate(total=Sum('total_price'))['total'] or 0
        
        revenue_last_7_days = order_items.filter(
            created_at__date__gte=last_7_days
        ).aggregate(total=Sum('total_price'))['total'] or 0
        
        return {
            'seller_info': {
                'business_name': seller_profile.business_name,
                'approval_status': seller_profile.approval_status,
                'rating': seller_profile.rating,
                'total_sales': seller_profile.total_sales,
                'total_orders': seller_profile.total_orders,
            },
            'product_stats': {
                'total_products': total_products,
                'active_products': active_products,
                'low_stock_products': low_stock_products,
            },
            'order_stats': {
                'total_orders': total_orders,
                'pending_orders': pending_orders,
                'completed_orders': completed_orders,
                'orders_last_30_days': orders_last_30_days,
                'orders_last_7_days': orders_last_7_days,
            },
            'revenue_stats': {
                'total_revenue': total_revenue,
                'revenue_last_30_days': revenue_last_30_days,
                'revenue_last_7_days': revenue_last_7_days,
            }
        }

class SellerAnalyticsView(APIView):
    permission_classes = [IsSellerOwner]

    def get(self, request):
        try:
            seller_profile = SellerProfile.objects.get(user=request.user)
        except SellerProfile.DoesNotExist:
            return Response(
                {'error': 'Seller profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get analytics data
        analytics_data = self.get_analytics_data(seller_profile, request)
        serializer = SellerAnalyticsSerializer(analytics_data)
        return Response(serializer.data)
    
    def get_analytics_data(self, seller_profile, request):
        # Get date range from query parameters
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)
        
        # Top selling products
        top_products = OrderItem.objects.filter(
            seller=seller_profile,
            created_at__date__gte=start_date
        ).values('product__name').annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('total_price')
        ).order_by('-total_sold')[:5]
        
        # Daily sales data
        daily_sales = OrderItem.objects.filter(
            seller=seller_profile,
            created_at__date__gte=start_date
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            orders=Count('order', distinct=True),
            revenue=Sum('total_price')
        ).order_by('day')
        
        # Order status distribution
        order_status_data = Order.objects.filter(
            items__seller=seller_profile,
            created_at__date__gte=start_date
        ).values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            'date_range': {
                'start_date': start_date,
                'end_date': timezone.now().date(),
                'days': days
            },
            'top_products': list(top_products),
            'daily_sales': list(daily_sales),
            'order_status_distribution': list(order_status_data)
        }

class PublicSellerProfileView(generics.RetrieveAPIView):
    serializer_class = PublicSellerProfileSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    lookup_url_kwarg = 'seller_id'

    def get_queryset(self):
        return SellerProfile.objects.filter(approval_status='approved')

class SellerProductsPublicView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'price', 'view_count']
    ordering = ['-created_at']

    def get_queryset(self):
        seller_id = self.kwargs['seller_id']
        seller = get_object_or_404(SellerProfile, id=seller_id, approval_status='approved')
        
        from apps.products.serializers import ProductSerializer
        return Product.objects.filter(
            seller=seller,
            status='active'
        ).select_related('seller', 'category')

    def get_serializer_class(self):
        from apps.products.serializers import ProductSerializer
        return ProductSerializer

class SellerBankAccountViewSet(viewsets.ModelViewSet):
    serializer_class = SellerBankAccountSerializer
    permission_classes = [IsSellerOwner]

    def get_queryset(self):
        try:
            seller_profile = SellerProfile.objects.get(user=self.request.user)
            return SellerBankAccount.objects.filter(seller=seller_profile)
        except SellerProfile.DoesNotExist:
            return SellerBankAccount.objects.none()

    def perform_create(self, serializer):
        seller_profile = get_object_or_404(SellerProfile, user=self.request.user)
        
        # If this is set as primary, remove primary from other accounts
        if serializer.validated_data.get('is_primary', False):
            SellerBankAccount.objects.filter(seller=seller_profile).update(is_primary=False)
        
        serializer.save(seller=seller_profile)

    def perform_update(self, serializer):
        # If this is set as primary, remove primary from other accounts
        if serializer.validated_data.get('is_primary', False):
            SellerBankAccount.objects.filter(
                seller=serializer.instance.seller
            ).exclude(id=serializer.instance.id).update(is_primary=False)
        
        serializer.save()

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        bank_account = self.get_object()
        
        # Remove primary from other accounts
        SellerBankAccount.objects.filter(
            seller=bank_account.seller
        ).update(is_primary=False)
        
        # Set this account as primary
        bank_account.is_primary = True
        bank_account.save()
        
        return Response({
            'message': 'Primary bank account updated successfully'
        })

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        bank_account = self.get_object()
        
        # Only admins can verify bank accounts
        if not request.user.is_staff:
            return Response(
                {'error': 'Only administrators can verify bank accounts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        bank_account.verified = True
        bank_account.save()
        
        return Response({
            'message': 'Bank account verified successfully'
        })