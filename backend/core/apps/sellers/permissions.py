from rest_framework import permissions
from .models import SellerProfile

class IsSellerOwner(permissions.BasePermission):
    """
    Custom permission to only allow sellers to access their own data.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            hasattr(request.user, 'sellerprofile')
        )
    
    def has_object_permission(self, request, view, obj):
        # Check if the user owns the seller profile
        if hasattr(obj, 'seller'):
            return obj.seller.user == request.user
        elif isinstance(obj, SellerProfile):
            return obj.user == request.user
        return False

class IsApprovedSeller(permissions.BasePermission):
    """
    Permission to check if seller is approved.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            hasattr(request.user, 'sellerprofile') and
            request.user.sellerprofile.approval_status == 'approved'
        )