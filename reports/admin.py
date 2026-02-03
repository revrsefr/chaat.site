from django.contrib import admin

from .models import UserReport


@admin.register(UserReport)
class UserReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reporter",
        "reported",
        "status",
        "created_at",
        "resolved_by",
    )
    list_filter = ("status", "created_at", "resolved_at")
    search_fields = ("reporter__username", "reported__username", "motive")
    readonly_fields = ("created_at", "updated_at")
