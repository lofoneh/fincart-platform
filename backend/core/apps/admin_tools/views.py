from rest_framework import generics, viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

from .models import (
    AdminActionLog, SellerApprovalRequest, SystemNotification,
    PlatformSettings, UserReport
)
from apps.authentication.models import User
from apps.sellers.models import SellerProfile
from apps.products.models import Product
from apps.orders.models import Order
from .serializers import (
    AdminActionLogSerializer, SellerApprovalRequestSerializer,
    SystemNotificationSerializer, PlatformSettingsSerializer,
    UserReportSerializer, AdminDashboardSerializer,
    PlatformAnalyticsSerializer, UserManagementSerializer,
    SellerManagementSerializer, ProductManagementSerializer
)
from .permissions import IsAdminUser

class AdminDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        dashboard_data = self.get_dashboard_data()
        serializer = AdminDashboardSerializer(dashboard_data)
        return Response(serializer.data)
    
    def get_dashboard_data(self):
        # Date ranges
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        last_7_days = today - timedelta(days=7)
        
        # User statistics
        total_users = User.objects.count()
        new_users_30_days = User.objects.filter(date_joined__date__gte=last_30_days).count()
        active_sellers = SellerProfile.objects.filter(approval_status='approved').count()
        pending_seller_approvals = SellerProfile.objects.filter(approval_status='pending').count()
        
        # Product statistics
        total_products = Product.objects.count()
        active_products = Product.objects.filter(status='active').count()
        featured_products = Product.objects.filter(is_featured=True).count()
        
        # Order statistics
        total_orders = Order.objects.count()
        orders_30_days = Order.objects.filter(created_at__date__gte=last_30_days).count()
        pending_orders = Order.objects.filter(status__in=['pending', 'confirmed']).count()
        
        # Revenue statistics
        total_revenue = Order.objects.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        revenue_30_days = Order.objects.filter(
            payment_status='paid',
            created_at__date__gte=last_30_days
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # System health
        pending_reports = UserReport.objects.filter(status='pending').count()
        active_notifications = SystemNotification.objects.filter(is_active=True).count()
        
        return {
            'user_stats': {
                'total_users': total_users,
                'new_users_30_days': new_users_30_days,
                'active_sellers': active_sellers,
                'pending_seller_approvals': pending_seller_approvals,
            },
            'product_stats': {
                'total_products': total_products,
                'active_products': active_products,
                'featured_products': featured_products,
            },
            'order_stats': {
                'total_orders': total_orders,
                'orders_30_days': orders_30_days,
                'pending_orders': pending_orders,
            },
            'revenue_stats': {
                'total_revenue': total_revenue,
                'revenue_30_days': revenue_30_days,
            },
            'system_health': {
                'pending_reports': pending_reports,
                'active_notifications': active_notifications,
            }
        }

class PlatformAnalyticsView(APIView):
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
        
        # Order trends
        order_trends = Order.objects.filter(
            created_at__date__gte=start_date
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            orders=Count('id'),
            revenue=Sum('total_amount')
        ).order_by('day')
        
        # Top categories
        top_categories = Product.objects.filter(
            status='active'
        ).values('category__name').annotate(
            product_count=Count('id')
        ).order_by('-product_count')[:5]
        
        # Seller performance
        top_sellers = SellerProfile.objects.filter(
            approval_status='approved'
        ).annotate(
            product_count=Count('products'),
            total_revenue=Sum('products__orderitem__total_price')
        ).order_by('-total_revenue')[:5]
        
        return {
            'date_range': {
                'start_date': start_date,
                'end_date': timezone.now().date(),
                'days': days
            },
            'user_growth': list(user_growth),
            'order_trends': list(order_trends),
            'top_categories': list(top_categories),
            'top_sellers': [
                {
                    'business_name': seller.business_name,
                    'product_count': seller.product_count,
                    'total_revenue': seller.total_revenue or 0
                }
                for seller in top_sellers
            ]
        }

class UserManagementView(generics.ListAPIView):
    serializer_class = UserManagementSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['email', 'username', 'phone_number']
    ordering_fields = ['date_joined', 'last_login']
    ordering = ['-date_joined']

    def get_queryset(self):
        return User.objects.all().select_related('userprofile')

class BanUserView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        reason = request.data.get('reason', 'Administrative action')
        
        user.is_active = False
        user.save()
        
        # Log the action
        AdminActionLog.objects.create(
            admin_user=request.user,
            action_type='ban_user',
            target_user=user,
            description=f'User banned. Reason: {reason}',
            ip_address=self.get_client_ip(request)
        )
        
        return Response({'message': 'User banned successfully'})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class UnbanUserView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        
        user.is_active = True
        user.save()
        
        # Log the action
        AdminActionLog.objects.create(
            admin_user=request.user,
            action_type='unban_user',
            target_user=user,
            description='User unbanned',
            ip_address=self.get_client_ip(request)
        )
        
        return Response({'message': 'User unbanned successfully'})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class SellerManagementView(generics.ListAPIView):
    serializer_class = SellerManagementSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['business_name', 'user__email']
    ordering_fields = ['created_at', 'approval_date', 'total_sales']
    ordering = ['-created_at']

    def get_queryset(self):
        return SellerProfile.objects.all().select_related('user')

class ApproveSellerView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, seller_id):
        seller = get_object_or_404(SellerProfile, id=seller_id)
        notes = request.data.get('notes', '')
        
        seller.approval_status = 'approved'
        seller.approval_date = timezone.now()
        seller.save()
        
        # Update approval request if exists
        try:
            approval_request = SellerApprovalRequest.objects.get(seller=seller)
            approval_request.status = 'approved'
            approval_request.reviewed_by = request.user
            approval_request.review_notes = notes
            approval_request.reviewed_at = timezone.now()
            approval_request.save()
        except SellerApprovalRequest.DoesNotExist:
            pass
        
        # Log the action
        AdminActionLog.objects.create(
            admin_user=request.user,
            action_type='approve_seller',
            target_user=seller.user,
            description=f'Seller approved: {seller.business_name}. Notes: {notes}',
            ip_address=self.get_client_ip(request)
        )
        
        return Response({'message': 'Seller approved successfully'})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class RejectSellerView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, seller_id):
        seller = get_object_or_404(SellerProfile, id=seller_id)
        reason = request.data.get('reason', 'Application does not meet requirements')
        
        seller.approval_status = 'rejected'
        seller.save()
        
        # Update approval request if exists
        try:
            approval_request = SellerApprovalRequest.objects.get(seller=seller)
            approval_request.status = 'rejected'
            approval_request.reviewed_by = request.user
            approval_request.review_notes = reason
            approval_request.reviewed_at = timezone.now()
            approval_request.save()
        except SellerApprovalRequest.DoesNotExist:
            pass
        
        # Log the action
        AdminActionLog.objects.create(
            admin_user=request.user,
            action_type='reject_seller',
            target_user=seller.user,
            description=f'Seller rejected: {seller.business_name}. Reason: {reason}',
            ip_address=self.get_client_ip(request)
        )
        
        return Response({'message': 'Seller rejected successfully'})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class SuspendSellerView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, seller_id):
        seller = get_object_or_404(SellerProfile, id=seller_id)
        reason = request.data.get('reason', 'Policy violation')
        
        seller.approval_status = 'suspended'
        seller.save()
        
        # Log the action
        AdminActionLog.objects.create(
            admin_user=request.user,
            action_type='suspend_seller',
            target_user=seller.user,
            description=f'Seller suspended: {seller.business_name}. Reason: {reason}',
            ip_address=self.get_client_ip(request)
        )
        
        return Response({'message': 'Seller suspended successfully'})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class ProductManagementView(generics.ListAPIView):
    serializer_class = ProductManagementSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'seller__business_name']
    ordering_fields = ['created_at', 'price', 'view_count']
    ordering = ['-created_at']

    def get_queryset(self):
        return Product.objects.all().select_related('seller', 'category')

class FeatureProductView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        
        product.is_featured = not product.is_featured
        product.save()
        
        action = 'feature_product' if product.is_featured else 'unfeature_product'
        
        # Log the action
        AdminActionLog.objects.create(
            admin_user=request.user,
            action_type=action,
            target_object_id=str(product.id),
            target_object_type='Product',
            description=f'Product {"featured" if product.is_featured else "unfeatured"}: {product.name}',
            ip_address=self.get_client_ip(request)
        )
        
        return Response({
            'message': f'Product {"featured" if product.is_featured else "unfeatured"} successfully'
        })
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class DeleteProductView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        product_name = product.name
        
        product.delete()
        
        # Log the action
        AdminActionLog.objects.create(
            admin_user=request.user,
            action_type='delete_product',
            target_object_id=str(product_id),
            target_object_type='Product',
            description=f'Product deleted: {product_name}',
            ip_address=self.get_client_ip(request)
        )
        
        return Response({'message': 'Product deleted successfully'})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

# ViewSets for CRUD operations
class AdminActionLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AdminActionLogSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        return AdminActionLog.objects.all().select_related('admin_user', 'target_user')

class SellerApprovalRequestViewSet(viewsets.ModelViewSet):
    serializer_class = SellerApprovalRequestSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-submitted_at']

    def get_queryset(self):
        return SellerApprovalRequest.objects.all().select_related('seller', 'reviewed_by')

class SystemNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = SystemNotificationSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        return SystemNotification.objects.all().select_related('created_by')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class PlatformSettingsViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformSettingsSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        return PlatformSettings.objects.all().select_related('updated_by')

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

class UserReportViewSet(viewsets.ModelViewSet):
    serializer_class = UserReportSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        return UserReport.objects.all().select_related('reporter', 'reported_user', 'handled_by')

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        report = self.get_object()
        response_text = request.data.get('response', '')
        
        report.status = 'resolved'
        report.admin_response = response_text
        report.handled_by = request.user
        report.resolved_at = timezone.now()
        report.save()
        
        return Response({'message': 'Report resolved successfully'})

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        report = self.get_object()
        response_text = request.data.get('response', '')
        
        report.status = 'dismissed'
        report.admin_response = response_text
        report.handled_by = request.user
        report.resolved_at = timezone.now()
        report.save()
        
        return Response({'message': 'Report dismissed successfully'})