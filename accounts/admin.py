from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

# ✅ Register CustomUser in Django Admin
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("username", "email", "is_active", "is_staff", "is_superuser", "avatar_tag")
    search_fields = ("username", "email")
    readonly_fields = ("avatar_tag",)

    fieldsets = (
        ("User Info", {"fields": ("username", "email", "password")}),
        ("Profile", {"fields": ("avatar", "age", "gender", "city", "description")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important Dates", {"fields": ("last_login", "date_joined")}),
    )

    def avatar_tag(self, obj):
        """Show avatar preview in Admin Panel"""
        if obj.avatar:
            return f'<img src="{obj.avatar.url}" style="width:50px;height:50px;border-radius:50%;" />'
        return "No Avatar"
    
    avatar_tag.allow_tags = True
    avatar_tag.short_description = "Avatar"

