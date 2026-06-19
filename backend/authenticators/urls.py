from django.urls import path

from . import views

urlpatterns = [
    path("authenticators/", views.authenticators),
    path("authenticators/<int:entry_id>/", views.authenticator_detail),
    path("authenticators/<int:entry_id>/code/", views.authenticator_code),
    path("authenticators/<int:entry_id>/qrcode/", views.authenticator_qrcode),
]
