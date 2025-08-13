from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import status

class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin/staff users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff
    
    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_authenticated and request.user.is_staff

class IsAdminUserOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admin users to edit objects.
    Non-admin users can only read objects.
    """
    def has_permission(self, request, view):
        # Allow read-only access to authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        # Allow write access only to admin users
        return request.user and request.user.is_authenticated and request.user.is_staff
    
    def has_object_permission(self, request, view, obj):
        # Allow read-only access to authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        # Allow write access only to admin users
        return request.user and request.user.is_authenticated and request.user.is_staff

class IsSellerOrReadOnly(permissions.BasePermission):
    """
    Custom permission for seller-only access with read-only for others.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow read-only access to all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Allow write access only to sellers
        return request.user.is_seller
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow read-only access to all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Allow write access only to sellers (and object owner if applicable)
        return request.user.is_seller