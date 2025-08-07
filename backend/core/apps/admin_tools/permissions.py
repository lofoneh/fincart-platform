from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users to access admin tools.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_staff
        )
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

class IsAdminUserOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow read-only access to non-admin users,
    but full access to admin users.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_staff
        )
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

class IsSuperAdminUser(permissions.BasePermission):
    """
    Permission for super sensitive operations like platform settings.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_superuser
        )