from rest_framework import generics, viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from datetime import timedelta
import logging

from .models import (
    AdminActionLog, SellerApprovalRequest, SystemNotification,
    PlatformSettings, UserReport
)
from apps.authentication.models import User
from apps.sellers.models import SellerProfile
from apps.products.models import Product
from .serializers import (
    AdminActionLogSerializer, SellerApprovalRequestSerializer,
    SystemNotificationSerializer, PlatformSettingsSerializer,
    UserReportSerializer, AdminDashboardSerializer,
    PlatformAnalyticsSerializer, UserManagementSerializer,
    SellerManagementSerializer, ProductManagementSerializer
)
from .permissions import IsAdminUser

# Set up logging
logger = logging.getLogger(__name__)

class AdminBaseView(APIView):
    """Base class for admin views with common utilities"""
    
    def get_client_ip(self, request):
        """Safely get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        # Basic IP validation
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return ip
        except (ValueError, ipaddress.AddressValueError):
            return '0.0.0.0'
    
    def log_admin_action(self, request, action_type, description, target_user=None, 
                        target_object_id=None, target_object_type=None):
        """Centralized admin action logging"""
        try:
            AdminActionLog.objects.create(
                admin_user=request.user,
                action_type=action_type,
                target_user=target_user,
                target_object_id=target_object_id,
                target_object_type=target_object_type,
                description=description,
                ip_address=self.get_client_ip(request)
            )
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")

class AdminDashboardView(AdminBaseView):
    permission_classes = [IsAdminUser]

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def get(self, request):
        dashboard_data = self.get_dashboard_data()
        serializer = AdminDashboardSerializer(dashboard_data)
        return Response(serializer.data)
    
    def get_dashboard_data(self):
        # Date ranges
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        
        # User statistics
        user_stats = User.objects.aggregate(
            total_users=Count('id'),
            new_users_30_days=Count('id', filter=Q(date_joined__date__gte=last_30_days)),
        )
        
        # Seller statistics
        seller_stats = SellerProfile.objects.aggregate(
            active_sellers=Count('id', filter=Q(approval_status='approved')),
            pending_seller_approvals=Count('id', filter=Q(approval_status='pending'))
        )
        
        # Product statistics
        try:
            product_stats = Product.objects.aggregate(
                total_products=Count('id'),
                active_products=Count('id', filter=Q(status='active')),
                featured_products=Count('id', filter=Q(is_featured=True))
            )
        except:
            product_stats = {'total_products': 0, 'active_products': 0, 'featured_products': 0}
        
        # Order statistics
        try:
            from apps.orders.models import Order
            order_stats = Order.objects.aggregate(
                total_orders=Count('id'),
                orders_30_days=Count('id', filter=Q(created_at__date__gte=last_30_days)),
                pending_orders=Count('id', filter=Q(status__in=['pending', 'confirmed']))
            )
            
            # Revenue statistics
            revenue_stats = Order.objects.filter(payment_status='paid').aggregate(
                total_revenue=Sum('total_amount'),
                revenue_30_days=Sum('total_amount', filter=Q(created_at__date__gte=last_30_days))
            )
        except:
            order_stats = {'total_orders': 0, 'orders_30_days': 0, 'pending_orders': 0}
            revenue_stats = {'total_revenue': 0, 'revenue_30_days': 0}
        
        # System health
        system_health = {
            'pending_reports': UserReport.objects.filter(status='pending').count(),
            'active_notifications': SystemNotification.objects.filter(is_active=True).count()
        }
        
        # Combine user and seller stats
        combined_user_stats = {**user_stats, **seller_stats}
        
        return {
            'user_stats': combined_user_stats,
            'product_stats': product_stats,
            'order_stats': order_stats,
            'revenue_stats': {
                'total_revenue': revenue_stats.get('total_revenue') or 0,
                'revenue_30_days': revenue_stats.get('revenue_30_days') or 0
            },
            'system_health': system_health
        }

class PlatformAnalyticsView(AdminBaseView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        analytics_data = self.get_analytics_data(days)
        serializer = PlatformAnalyticsSerializer(analytics_data)
        return Response(serializer.data)
    
    def get_analytics_data(self, days):
        start_date = timezone.now().date() - timedelta(days=days)
        
        # User growth over time
        user_growth = User.objects.filter(
            date_joined__date__gte=start_date
        ).extra(
            select={'day': 'date(date_joined)'}
        ).values('day').annotate(
            new_users=Count('id')
        ).order_by('day')
        
        # Initialize default values
        order_trends = []
        top_categories = []
        top_sellers = []
        
        try:
            from apps.orders.models import Order
            # Order trends
            order_trends = Order.objects.filter(
                created_at__date__gte=start_date
            ).extra(
                select={'day': 'date(created_at)'}
            ).values('day').annotate(
                orders=Count('id'),
                revenue=Sum('total_amount')
            ).order_by('day')
        except:
            pass
        
        try:
            # Top categories
            top_categories = Product.objects.filter(
                status='active'
            ).values('category__name').annotate(
                product_count=Count('id')
            ).order_by('-product_count')[:5]
        except:
            pass
        
        try:
            # Top sellers
            top_sellers_queryset = SellerProfile.objects.filter(
                approval_status='approved'
            ).annotate(
                product_count=Count('products')
            ).order_by('-total_sales')[:5]
            
            top_sellers = [
                {
                    'business_name': seller.business_name,
                    'product_count': seller.product_count,
                    'total_revenue': float(seller.total_sales or 0)
                }
                for seller in top_sellers_queryset
            ]
        except:
            pass
        
        return {
            'date_range': {
                'start_date': start_date,
                'end_date': timezone.now().date(),
                'days': days
            },
            'user_growth': list(user_growth),
            'order_trends': list(order_trends),
            'top_categories': list(top_categories),
            'top_sellers': top_sellers
        }

class UserManagementView(generics.ListAPIView):
    serializer_class = UserManagementSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['email', 'username', 'phone_number']
    ordering_fields = ['date_joined', 'last_login']
    ordering = ['-date_joined']

    def get_queryset(self):
        return User.objects.all()

class BanUserView(AdminBaseView):
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        if not request.data.get('reason'):
            return Response(
                {'error': 'Reason is required for banning users'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = get_object_or_404(User, id=user_id)
        reason = request.data['reason'].strip()
        
        if user == request.user:
            return Response(
                {'error': 'Cannot ban yourself'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.is_staff and not request.user.is_superuser:
            return Response(
                {'error': 'Cannot ban other admin users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user.is_active = False
        user.save(update_fields=['is_active'])
        
        self.log_admin_action(
            request=request,
            action_type='ban_user',
            target_user=user,
            description=f'User banned. Reason: {reason}'
        )
        
        return Response({
            'message': 'User banned successfully',
            'user_email': user.email
        })

class UnbanUserView(AdminBaseView):
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        
        user.is_active = True
        user.save(update_fields=['is_active'])
        
        self.log_admin_action(
            request=request,
            action_type='unban_user',
            target_user=user,
            description='User unbanned'
        )
        
        return Response({
            'message': 'User unbanned successfully',
            'user_email': user.email
        })

class SellerManagementView(generics.ListAPIView):
    serializer_class = SellerManagementSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['business_name', 'user__email']
    ordering_fields = ['created_at', 'approval_date', 'total_sales']
    ordering = ['-created_at']

    def get_queryset(self):
        return SellerProfile.objects.select_related('user')

class ApproveSellerView(AdminBaseView):
    permission_classes = [IsAdminUser]

    def post(self, request, seller_id):
        seller = get_object_or_404(SellerProfile, id=seller_id)
        notes = request.data.get('notes', '').strip()
        
        if seller.approval_status == 'approved':
            return Response(
                {'error': 'Seller is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        seller.approval_status = 'approved'
        seller.approval_date = timezone.now()
        seller.save(update_fields=['approval_status', 'approval_date'])
        
        # Update or create approval request
        approval_request, created = SellerApprovalRequest.objects.get_or_create(
            seller=seller,
            defaults={
                'status': 'approved',
                'reviewed_by': request.user,
                'review_notes': notes,
                'reviewed_at': timezone.now()
            }
        )
        
        if not created:
            approval_request.status = 'approved'
            approval_request.reviewed_by = request.user
            approval_request.review_notes = notes
            approval_request.reviewed_at = timezone.now()
            approval_request.save()
        
        self.log_admin_action(
            request=request,
            action_type='approve_seller',
            target_user=seller.user,
            description=f'Seller approved: {seller.business_name}. Notes: {notes}'
        )
        
        return Response({
            'message': 'Seller approved successfully',
            'business_name': seller.business_name
        })

class RejectSellerView(AdminBaseView):
    permission_classes = [IsAdminUser]

    def post(self, request, seller_id):
        seller = get_object_or_404(SellerProfile, id=seller_id)
        reason = request.data.get('reason', 'Application does not meet requirements').strip()
        
        seller.approval_status = 'rejected'
        seller.save(update_fields=['approval_status'])
        
        # Update or create approval request
        approval_request, created = SellerApprovalRequest.objects.get_or_create(
            seller=seller,
            defaults={
                'status': 'rejected',
                'reviewed_by': request.user,
                'review_notes': reason,
                'reviewed_at': timezone.now()
            }
        )
        
        if not created:
            approval_request.status = 'rejected'
            approval_request.reviewed_by = request.user
            approval_request.review_notes = reason
            approval_request.reviewed_at = timezone.now()
            approval_request.save()
        
        self.log_admin_action(
            request=request,
            action_type='reject_seller',
            target_user=seller.user,
            description=f'Seller rejected: {seller.business_name}. Reason: {reason}'
        )
        
        return Response({
            'message': 'Seller rejected successfully',
            'business_name': seller.business_name
        })

class SuspendSellerView(AdminBaseView):
    permission_classes = [IsAdminUser]

    def post(self, request, seller_id):
        seller = get_object_or_404(SellerProfile, id=seller_id)
        reason = request.data.get('reason', 'Policy violation').strip()
        
        seller.approval_status = 'suspended'
        seller.save(update_fields=['approval_status'])
        
        self.log_admin_action(
            request=request,
            action_type='suspend_seller',
            target_user=seller.user,
            description=f'Seller suspended: {seller.business_name}. Reason: {reason}'
        )
        
        return Response({
            'message': 'Seller suspended successfully',
            'business_name': seller.business_name
        })

class ProductManagementView(generics.ListAPIView):
    serializer_class = ProductManagementSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'seller__business_name']
    ordering_fields = ['created_at', 'price', 'view_count']
    ordering = ['-created_at']

    def get_queryset(self):
        try:
            return Product.objects.select_related('seller', 'category')
        except:
            return Product.objects.none()

class FeatureProductView(AdminBaseView):
    permission_classes = [IsAdminUser]

    def post(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)
            
            product.is_featured = not product.is_featured
            product.save(update_fields=['is_featured'])
            
            action = 'feature_product' if product.is_featured else 'unfeature_product'
            
            self.log_admin_action(
                request=request,
                action_type=action,
                target_object_id=str(product.id),
                target_object_type='Product',
                description=f'Product {"featured" if product.is_featured else "unfeatured"}: {product.name}'
            )
            
            return Response({
                'message': f'Product {"featured" if product.is_featured else "unfeatured"} successfully'
            })
        except:
            return Response(
                {'error': 'Product management not available'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

class DeleteProductView(AdminBaseView):
    permission_classes = [IsAdminUser]

    def delete(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)
            product_name = product.name
            
            product.delete()
            
            self.log_admin_action(
                request=request,
                action_type='delete_product',
                target_object_id=str(product_id),
                target_object_type='Product',
                description=f'Product deleted: {product_name}'
            )
            
            return Response({'message': 'Product deleted successfully'})
        except:
            return Response(
                {'error': 'Product management not available'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

# ViewSets for CRUD operations
class AdminActionLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AdminActionLogSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['action_type', 'admin_user']
    ordering = ['-created_at']

    def get_queryset(self):
        return AdminActionLog.objects.select_related('admin_user', 'target_user')

class SellerApprovalRequestViewSet(viewsets.ModelViewSet):
    serializer_class = SellerApprovalRequestSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering = ['-submitted_at']

    def get_queryset(self):
        return SellerApprovalRequest.objects.select_related('seller', 'reviewed_by')

class SystemNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = SystemNotificationSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_active', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        return SystemNotification.objects.select_related('created_by')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class PlatformSettingsViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformSettingsSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['setting_type', 'is_public']

    def get_queryset(self):
        return PlatformSettings.objects.select_related('updated_by')

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

class UserReportViewSet(viewsets.ModelViewSet):
    serializer_class = UserReportSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'report_type']
    ordering = ['-created_at']

    def get_queryset(self):
        return UserReport.objects.select_related('reporter', 'reported_user', 'handled_by')

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        report = self.get_object()
        
        if report.status in ['resolved', 'dismissed']:
            return Response(
                {'error': 'Report has already been handled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response_text = request.data.get('response', '').strip()
        if not response_text:
            return Response(
                {'error': 'Response text is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report.status = 'resolved'
        report.admin_response = response_text
        report.handled_by = request.user
        report.resolved_at = timezone.now()
        report.save()
        
        return Response({
            'message': 'Report resolved successfully',
            'report_id': str(report.id)
        })

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        report = self.get_object()
        
        if report.status in ['resolved', 'dismissed']:
            return Response(
                {'error': 'Report has already been handled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response_text = request.data.get('response', '').strip()
        
        report.status = 'dismissed'
        report.admin_response = response_text
        report.handled_by = request.user
        report.resolved_at = timezone.now()
        report.save()
        
        return Response({
            'message': 'Report dismissed successfully',
            'report_id': str(report.id)
        })