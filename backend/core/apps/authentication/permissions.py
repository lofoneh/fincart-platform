from rest_framework import permissions


class IsAdminUserOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admin users to edit objects.
    Non-admin users can only read objects.
    """
    def has_permission(self, request, view):
        # Allow read-only access to non-authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        # Allow write access only to admin users
        return request.user and request.user.is_staff


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only to the owner of the object
        return obj.user == request.user


class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    """
    def has_object_permission(self, request, view, obj):
        # Check if obj has user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # For user objects, check if it's the same user
        if hasattr(obj, 'email'):
            return obj == request.user
        
        return False


class IsVerifiedUser(permissions.BasePermission):
    """
    Permission for verified users only.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.is_verified()

    message = "You must verify your email and phone number to access this resource."


class IsActiveUser(permissions.BasePermission):
    """
    Permission for active users only (not suspended).
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        can_access, message = request.user.can_login()
        return can_access

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsSeller(permissions.BasePermission):
    """
    Permission for seller users only.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_seller and
            request.user.is_verified()
        )

    message = "You must be a verified seller to access this resource."


class IsBuyer(permissions.BasePermission):
    """
    Permission for buyer users only.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_buyer
        )

    message = "You must be a buyer to access this resource."


class IsSellerOwner(permissions.BasePermission):
    """
    Permission for seller who owns the object.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_seller
        )

    def has_object_permission(self, request, view, obj):
        # Check if the seller owns this object
        if hasattr(obj, 'seller') and hasattr(obj.seller, 'user'):
            return obj.seller.user == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user and request.user.is_seller
        
        return False


class CanModifyProfile(permissions.BasePermission):
    """
    Permission to modify user profile with additional checks.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Users can modify their own profile
        if obj == request.user:
            return True
        
        # Staff can modify any profile
        if request.user.is_staff:
            return True
        
        return False


class CanManageAddresses(permissions.BasePermission):
    """
    Permission to manage user addresses.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Users can manage their own addresses
        return obj.user == request.user


class IsStaffOrOwner(permissions.BasePermission):
    """
    Permission for staff users or object owners.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Staff can access any object
        if request.user.is_staff:
            return True
        
        # Check ownership based on object type
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # For user objects
        if hasattr(obj, 'email'):
            return obj == request.user
        
        return False


class RateLimitPermission(permissions.BasePermission):
    """
    Custom permission to handle rate limiting at the permission level.
    """
    def has_permission(self, request, view):
        # This would integrate with Django cache for rate limiting
        # Implementation depends on your rate limiting strategy
        return True


class SecureActionPermission(permissions.BasePermission):
    """
    Permission for sensitive actions that require additional verification.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has verified their identity recently
        # This could check for recent password confirmation, 2FA, etc.
        sensitive_actions = ['change_password', 'delete_account', 'update_email']
        
        if hasattr(view, 'action') and view.action in sensitive_actions:
            # Add additional security checks here
            # For now, just require verified users
            return request.user.is_verified()
        
        return True

    message = "This action requires additional verification."
    
class AllowAny(permissions.BasePermission):
    """
    Custom permission to allow any user to access the view.
    """
    def has_permission(self, request, view):
        # Allow any user to access the view
        return True