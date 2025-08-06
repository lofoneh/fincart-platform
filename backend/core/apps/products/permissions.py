from rest_framework import permissions


class IsSellerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow sellers to create/edit products.
    Read-only access for everyone else.
    """
    
    def has_permission(self, request, view):
        # Read permissions for any request (GET, HEAD, OPTIONS)
        if request.method in permissions.READONLY_METHODS:
            return True
        
        # Write permissions only for authenticated sellers
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has seller profile and is verified seller
        return hasattr(request.user, 'is_seller') and request.user.is_seller

    def has_object_permission(self, request, view, obj):
        # Read permissions for any request
        if request.method in permissions.READONLY_METHODS:
            return True
        
        # Write permissions only for the seller who owns the product or admin
        if request.user.is_staff:
            return True
        
        return obj.seller.user == request.user


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for any request
        if request.method in permissions.READONLY_METHODS:
            return True
        
        # Write permissions only for the owner of the object or admin
        if request.user.is_staff:
            return True
        
        # For products, check seller ownership
        if hasattr(obj, 'seller'):
            return obj.seller.user == request.user
        
        # For other objects with direct user relationship
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class IsSellerOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission specifically for seller-owned resources.
    Allows read access to all, write access only to the seller owner.
    """
    
    def has_permission(self, request, view):
        # Allow read access to all
        if request.method in permissions.READONLY_METHODS:
            return True
        
        # For write operations, user must be authenticated
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions for everyone
        if request.method in permissions.READONLY_METHODS:
            return True
        
        # Admin can do anything
        if request.user.is_staff:
            return True
        
        # Check seller ownership
        if hasattr(obj, 'seller') and hasattr(obj.seller, 'user'):
            return obj.seller.user == request.user
        
        return False


class IsAdminOrSellerReadOnly(permissions.BasePermission):
    """
    Permission that allows admin full access and sellers read-only access to all products.
    Regular users get no access.
    """
    
    def has_permission(self, request, view):
        # Admin gets full access
        if request.user.is_staff:
            return True
        
        # Sellers get read-only access
        if (request.user.is_authenticated and 
            hasattr(request.user, 'is_seller') and 
            request.user.is_seller):
            return request.method in permissions.READONLY_METHODS
        
        return False


class IsSuperUserOrReadOnly(permissions.BasePermission):
    """
    Permission that allows superuser full access and read-only access for others.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.READONLY_METHODS:
            return True
        
        return request.user and request.user.is_superuser


class CanManageProducts(permissions.BasePermission):
    """
    Permission for product management operations.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can manage all products
        if request.user.is_staff:
            return True
        
        # Sellers can manage their own products
        if hasattr(request.user, 'is_seller') and request.user.is_seller:
            # For list/create operations
            if view.action in ['list', 'create']:
                return True
            # For detail operations, check in has_object_permission
            return True
        
        return False

    def has_object_permission(self, request, view, obj):
        # Admin can manage all
        if request.user.is_staff:
            return True
        
        # Seller can only manage their own products
        if (hasattr(request.user, 'is_seller') and 
            request.user.is_seller and 
            hasattr(obj, 'seller')):
            return obj.seller.user == request.user
        
        return False


class CanToggleFeatured(permissions.BasePermission):
    """
    Permission for toggling featured status of products.
    Only admin and product owner can toggle featured status.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Admin can toggle any product
        if request.user.is_staff:
            return True
        
        # Product owner can toggle their own product
        if hasattr(obj, 'seller') and obj.seller.user == request.user:
            return True
        
        return False


class IsVerifiedSeller(permissions.BasePermission):
    """
    Permission that checks if user is a verified seller.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user is a verified seller
        return (hasattr(request.user, 'is_seller') and 
                request.user.is_seller and
                hasattr(request.user, 'seller_profile'))


class CanViewAnalytics(permissions.BasePermission):
    """
    Permission for viewing product analytics and statistics.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can view all analytics
        if request.user.is_staff:
            return True
        
        # Sellers can view their own product analytics
        return hasattr(request.user, 'is_seller') and request.user.is_seller

    def has_object_permission(self, request, view, obj):
        # Admin can view all
        if request.user.is_staff:
            return True
        
        # Seller can only view their own product analytics
        if (hasattr(request.user, 'is_seller') and 
            request.user.is_seller and 
            hasattr(obj, 'seller')):
            return obj.seller.user == request.user
        
        return False