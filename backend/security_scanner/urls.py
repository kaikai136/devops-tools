from django.urls import path

from . import views

urlpatterns = [
    path("security-scans/targets/", views.scan_targets),
    path("security-scans/summary/", views.scan_summary),
    path("security-scans/tasks/", views.scan_tasks),
    path("security-scans/tasks/<int:task_id>/cancel/", views.scan_task_cancel),
    path("security-scans/tasks/<int:task_id>/retry-failed/", views.scan_task_retry_failed),
    path("security-scans/tasks/<int:task_id>/findings/", views.scan_task_findings),
    path("security-scans/tasks/<int:task_id>/export/", views.scan_task_export),
    path("security-scans/tasks/<int:task_id>/", views.scan_task_detail),
]
