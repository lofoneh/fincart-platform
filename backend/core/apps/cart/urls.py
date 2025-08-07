from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CartViewSet, CartItemViewSet

app_name = 'cart'

router = DefaultRouter()
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'items', CartItemViewSet, basename='cartitem')

urlpatterns = [
    path('', include(router.urls)),
]