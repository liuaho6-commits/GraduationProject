from rest_framework.permissions import BasePermission

class IsSuperUser(BasePermission):
    """
    自定义权限：只允许超级管理员访问
    """
    def has_permission(self, request, view):
        # request.user 必须登录，且 is_superuser 必须为 True
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)