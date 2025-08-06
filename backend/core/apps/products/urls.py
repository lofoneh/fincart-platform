from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'products'

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'items', views.ProductViewSet, basename='product')

urlpatterns = [
    # Custom API Views (if you prefer them over ViewSet actions)
    path('search/', views.ProductSearchView.as_view(), name='product_search'),
    path('featured/', views.FeaturedProductsView.as_view(), name='featured_products'),
    path('by-category/<slug:category_slug>/', views.ProductsByCategoryView.as_view(), name='products_by_category'),
    path('my-products/', views.SellerProductsView.as_view(), name='seller_products'),
    
    # Product Management (for sellers)
    path('my-products/', views.SellerProductsView.as_view(), name='seller_products'),
    
    # Include router URLs
    path('', include(router.urls)),
]