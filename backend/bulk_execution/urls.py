from django.urls import path

from . import views

urlpatterns = [
    path("bulk-execution/targets/", views.targets),
    path("bulk-execution/tasks/", views.tasks),
    path("bulk-execution/tasks/<int:task_id>/cancel/", views.task_cancel),
    path("bulk-execution/tasks/<int:task_id>/", views.task_detail),
]
