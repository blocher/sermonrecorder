from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import DeviceRegistration, ExternalIdentity, SavedRecipient, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "display_name", "is_staff", "is_active")
    search_fields = ("email", "display_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "display_name",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(SavedRecipient)
class SavedRecipientAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "owner", "updated_at")
    search_fields = ("name", "email", "owner__email")
    list_filter = ("updated_at",)


@admin.register(DeviceRegistration)
class DeviceRegistrationAdmin(admin.ModelAdmin):
    list_display = ("owner", "platform", "active", "updated_at")
    search_fields = ("owner__email",)
    list_filter = ("platform", "active", "updated_at")
    readonly_fields = ("token",)


@admin.register(ExternalIdentity)
class ExternalIdentityAdmin(admin.ModelAdmin):
    list_display = ("provider", "owner", "created_at")
    search_fields = ("owner__email", "subject")
    list_filter = ("provider", "created_at")
    readonly_fields = ("provider", "subject", "owner", "created_at", "updated_at")
