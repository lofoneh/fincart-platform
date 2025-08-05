from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'admin_tools'

router = DefaultRouter()
router.register(r'action-logs', views.AdminActionLogViewSet, basename='action_log')
router.register(r'seller-approvals', views.SellerApprovalRequestViewSet, basename='seller_approval')
router.register(r'notifications', views.SystemNotificationViewSet, basename='notification')
router.register(r'settings', views.PlatformSettingsViewSet, basename='setting')
router.register(r'reports', views.UserReportViewSet, basename='report')

urlpatterns = [
    # Admin Dashboard
    path('dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('analytics/', views.PlatformAnalyticsView.as_view(), name='platform_analytics'),
    
    # User Management
    path('users/', views.UserManagementView.as_view(), name='user_management'),
    path('users/<uuid:user_id>/ban/', views.BanUserView.as_view(), name='ban_user'),
    path('users/<uuid:user_id>/unban/', views.UnbanUserView.as_view(), name='unban_user'),
    
    # Seller Management
    path('sellers/', views.SellerManagementView.as_view(), name='seller_management'),
    path('sellers/<uuid:seller_id>/approve/', views.ApproveSellerView.as_view(), name='approve_seller'),
    path('sellers/<uuid:seller_id>/reject/', views.RejectSellerView.as_view(), name='reject_seller'),
    path('sellers/<uuid:seller_id>/suspend/', views.SuspendSellerView.as_view(), name='suspend_seller'),
    
    # Product Management
    path('products/', views.ProductManagementView.as_view(), name='product_management'),
    path('products/<uuid:product_id>/feature/', views.FeatureProductView.as_view(), name='feature_product'),
    path('products/<uuid:product_id>/delete/', views.DeleteProductView.as_view(), name='delete_product'),
    
    # Include router URLs
    path('', include(router.urls)),
]