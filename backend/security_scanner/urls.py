from django.urls import path

from . import views

urlpatterns = [
    path("security-scans/hosts/", views.scan_hosts),
    path("security-scans/tasks/", views.scan_tasks),
    path("security-scans/tasks/<int:task_id>/findings/", views.scan_task_findings),
    path("security-scans/tasks/<int:task_id>/export/", views.scan_task_export),
    path("security-scans/tasks/<int:task_id>/", views.scan_task_detail),
]
