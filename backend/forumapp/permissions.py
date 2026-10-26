"""DRF permission classes for the forum."""
from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    """Доступ только для администраторов (role=admin или superuser)."""

    message = "Требуется роль администратора"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_admin_role", False)
        )


class OwnerOrAdminDelete(BasePermission):
    """Удаление: владелец или администратор. Изменение: только владелец."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        is_owner = getattr(obj, "owner_id", None) == getattr(user, "id", None)
        is_admin = getattr(user, "is_admin_role", False)
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return is_owner or is_admin
        # PUT/PATCH — только владелец
        return is_owner


class OwnerOnlyEdit(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        return getattr(obj, "owner_id", None) == getattr(user, "id", None)
