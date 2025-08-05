from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'users'

router = DefaultRouter()
router.register(r'addresses', views.AddressViewSet, basename='address')

urlpatterns = [
    # Profile Management
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('profile/update/', views.UpdateUserProfileView.as_view(), name='update_profile'),
    
    # Address Management
    path('', include(router.urls)),
    
    # User Dashboard
    path('dashboard/', views.UserDashboardView.as_view(), name='dashboard'),
]