from django.urls import path

from . import views

urlpatterns = [
    path("local-ip/", views.local_ip),
    path("scan/ip/", views.ip_scan),
    path("scan/ports/", views.port_scan),
    path("scan/ports/quick/", views.quick_port_test),
    path("ping/", views.ping),
    path("subnet/calculate/", views.subnet_calculate),
]
