from rest_framework import generics, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.models import User, Address
from .serializers import (
    UserProfileSerializer, AddressSerializer, 
    UserDashboardSerializer, UpdateUserProfileSerializer
)

class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, created = User.objects.get_or_create(user=self.request.user)
        return profile

class UpdateUserProfileView(generics.UpdateAPIView):
    serializer_class = UpdateUserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, created = User.objects.get_or_create(user=self.request.user)
        return profile

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            'message': 'Profile updated successfully',
            'data': serializer.data
        })

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # If this is set as default, remove default from other addresses
        if serializer.validated_data.get('is_default', False):
            Address.objects.filter(
                user=self.request.user,
                type=serializer.validated_data['type']
            ).update(is_default=False)
        
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        # If this is set as default, remove default from other addresses
        if serializer.validated_data.get('is_default', False):
            Address.objects.filter(
                user=self.request.user,
                type=serializer.validated_data['type']
            ).exclude(id=serializer.instance.id).update(is_default=False)
        
        serializer.save()

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        address = self.get_object()
        
        # Remove default from other addresses of same type
        Address.objects.filter(
            user=request.user,
            type=address.type
        ).update(is_default=False)
        
        # Set this address as default
        address.is_default = True
        address.save()
        
        return Response({
            'message': f'Default {address.get_type_display().lower()} address updated'
        })

    @action(detail=False, methods=['get'])
    def default_shipping(self, request):
        try:
            address = Address.objects.get(
                user=request.user,
                type='shipping',
                is_default=True
            )
            serializer = self.get_serializer(address)
            return Response(serializer.data)
        except Address.DoesNotExist:
            return Response(
                {'message': 'No default shipping address found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def default_billing(self, request):
        try:
            address = Address.objects.get(
                user=request.user,
                type='billing',
                is_default=True
            )
            serializer = self.get_serializer(address)
            return Response(serializer.data)
        except Address.DoesNotExist:
            return Response(
                {'message': 'No default billing address found'},
                status=status.HTTP_404_NOT_FOUND
            )

class UserDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get user statistics
        from apps.orders.models import Order
        from apps.sellers.models import SellerProfile
        
        dashboard_data = {
            'user_info': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'is_seller': user.is_seller,
                'is_buyer': user.is_buyer,
                'email_verified': user.email_verified,
                'phone_verified': user.phone_verified,
                'date_joined': user.date_joined,
            },
            'order_stats': {
                'total_orders': Order.objects.filter(user=user).count(),
                'pending_orders': Order.objects.filter(user=user, status='pending').count(),
                'delivered_orders': Order.objects.filter(user=user, status='delivered').count(),
            },
            'seller_info': None
        }
        
        # Add seller information if user is a seller
        if user.is_seller:
            try:
                seller_profile = SellerProfile.objects.get(user=user)
                dashboard_data['seller_info'] = {
                    'business_name': seller_profile.business_name,
                    'approval_status': seller_profile.approval_status,
                    'rating': seller_profile.rating,
                    'total_sales': seller_profile.total_sales,
                    'total_orders': seller_profile.total_orders,
                }
            except SellerProfile.DoesNotExist:
                pass
        
        serializer = UserDashboardSerializer(dashboard_data)
        return Response(serializer.data)