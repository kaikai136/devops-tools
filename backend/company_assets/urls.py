from django.urls import path

from . import views

urlpatterns = [
    path("company-devices/", views.company_devices),
    path("company-devices/<int:device_id>/", views.company_device_detail),
]
