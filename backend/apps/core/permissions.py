from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsManager(BasePermission):
    """Allow access only to users with the manager or admin role."""

    message = "Manager access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_manager)


class IsAdmin(BasePermission):
    """Admin-only. Used where a manager could otherwise escalate privileges."""

    message = "Admin access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == user.Role.ADMIN)


class IsManagerOrReadOnly(BasePermission):
    """Everyone signed in can read; only managers can write."""

    message = "Manager access required to modify this resource."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or user.is_manager
