from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("auth/login/", views.auth_login),
    path("auth/logout/", views.auth_logout),
    path("auth/me/", views.auth_me),
    path("users/", views.users),
    path("users/<int:user_id>/", views.user_detail),
    path("local-ip/", views.local_ip),
    path("scan/ip/", views.ip_scan),
    path("scan/ports/", views.port_scan),
    path("scan/ports/quick/", views.quick_port_test),
    path("ping/", views.ping),
    path("subnet/calculate/", views.subnet_calculate),
    path("passwords/generate/", views.password_generate),
    path("passwords/history/", views.password_history),
    path("passwords/history/<int:record_id>/", views.password_history_item),
    path("authenticators/", views.authenticators),
    path("authenticators/<int:entry_id>/", views.authenticator_detail),
    path("authenticators/<int:entry_id>/code/", views.authenticator_code),
    path("authenticators/<int:entry_id>/qrcode/", views.authenticator_qrcode),
]
