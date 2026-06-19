from django.urls import path

from . import views

urlpatterns = [
    path("web-terminal/tree/", views.terminal_tree),
    path("web-terminal/sessions/", views.terminal_sessions),
    path("web-terminal/sessions/<uuid:session_id>/commands/", views.terminal_commands),
]
