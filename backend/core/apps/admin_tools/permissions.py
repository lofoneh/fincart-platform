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
    
    def has_object_permission(self, request, view, obj):
        # Allow read-only access to non-authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        # Allow write access only to admin users
        return request.user and request.user.is_staff
        return Response(
            {'error': 'Only sellers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
        return super().has_permission(request, view)