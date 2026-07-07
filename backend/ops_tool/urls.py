from django.contrib import admin
from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

from . import frontend

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("operations.urls")),
]

if settings.SERVE_MEDIA_FILES:
    urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]

urlpatterns += [
    path("", frontend.frontend_index, name="frontend-index"),
    path("terminal.html", frontend.frontend_terminal, name="frontend-terminal"),
    re_path(r"^(?P<path>[^/]+\.(?:png|jpg|jpeg|gif|webp|svg|ico|txt|webmanifest))$", frontend.frontend_asset, name="frontend-asset"),
    re_path(r"^(?!api/|admin/|media/|static/|ws/).*$", frontend.frontend_index, name="frontend-fallback"),
]
