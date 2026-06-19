from django.urls import path

from .consumers import TerminalConsumer

websocket_urlpatterns = [
    path("ws/web-terminal/<int:host_id>/", TerminalConsumer.as_asgi()),
]
