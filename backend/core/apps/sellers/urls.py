from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'sellers'

router = DefaultRouter()
router.register(r'bank-accounts', views.SellerBankAccountViewSet, basename='bank_account')

urlpatterns = [
    # Seller Registration & Profile
    path('register/', views.SellerRegistrationView.as_view(), name='seller_register'),
    path('profile/', views.SellerProfileView.as_view(), name='seller_profile'),
    path('profile/update/', views.UpdateSellerProfileView.as_view(), name='update_seller_profile'),
    
    # Seller Dashboard
    path('dashboard/', views.SellerDashboardView.as_view(), name='seller_dashboard'),
    path('analytics/', views.SellerAnalyticsView.as_view(), name='seller_analytics'),
    
    # Public Seller Info
    path('<uuid:seller_id>/', views.PublicSellerProfileView.as_view(), name='public_seller_profile'),
    path('<uuid:seller_id>/products/', views.SellerProductsPublicView.as_view(), name='seller_products_public'),
    
    # Include router URLs
    path('', include(router.urls)),
]
