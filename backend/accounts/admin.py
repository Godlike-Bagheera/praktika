from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["id"]
    list_display = ["email", "username", "role", "is_staff", "created_at"]
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Роли", {"fields": ("role", "is_staff", "is_superuser", "is_active")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2"),
        }),
    )
