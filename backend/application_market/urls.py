from django.urls import path

from . import views

urlpatterns = [
    path("application-market/catalog/", views.catalog_view),
    path("application-market/apps/<str:app_id>/", views.app_detail),
    path("application-market/targets/", views.target_list),
    path("application-market/installed/", views.installed_list),
    path("application-market/preview/", views.preview),
    path("application-market/tasks/", views.tasks_view),
    path("application-market/tasks/<int:task_id>/", views.task_detail),
    path("application-market/tasks/<int:task_id>/cancel/", views.task_cancel),
    path("application-market/sources/", views.source_list),
    path("application-market/sources/sync/", views.source_sync),
    path("application-market/sources/<int:source_id>/", views.source_detail),
]
