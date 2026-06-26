from django.urls import path

from . import views

urlpatterns = [
    path("web-terminal/tree/", views.terminal_tree),
    path("web-terminal/sessions/", views.terminal_sessions),
    path("web-terminal/sessions/<uuid:session_id>/commands/", views.terminal_commands),
    path("web-terminal/hosts/<int:host_id>/files/list/", views.terminal_file_list),
    path("web-terminal/hosts/<int:host_id>/files/preview/", views.terminal_file_preview),
    path("web-terminal/hosts/<int:host_id>/files/download/", views.terminal_file_download),
    path("web-terminal/hosts/<int:host_id>/files/upload/", views.terminal_file_upload),
]
