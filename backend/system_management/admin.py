from django.contrib import admin

from .models import LoginLog, SystemSetting


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ("username", "user", "ip_address", "status", "message", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("username", "ip_address", "message")
    readonly_fields = ("user", "username", "ip_address", "user_agent", "status", "message", "created_at")


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "updated_at")
    search_fields = ("key", "label", "description")
