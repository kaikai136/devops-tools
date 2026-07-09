from django.urls import include, path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("", include("accounts.urls")),
    path("", include("network_tools.urls")),
    path("", include("passwords.urls")),
    path("", include("authenticators.urls")),
    path("", include("host_management.urls")),
    path("", include("web_terminal.urls")),
    path("", include("security_scanner.urls")),
    path("", include("system_management.urls")),
]
