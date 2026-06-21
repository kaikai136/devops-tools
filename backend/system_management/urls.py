from django.urls import path

from . import views

urlpatterns = [
    path("system/login-logs/", views.login_logs),
    path("system/users/", views.system_users),
    path("system/users/<int:user_id>/", views.system_user_detail),
    path("system/roles/", views.roles),
    path("system/roles/<int:role_id>/", views.role_detail),
    path("system/permissions/", views.permissions),
    path("system/settings/", views.system_settings),
    path("system/settings/<str:setting_key>/", views.system_setting_detail),
]
