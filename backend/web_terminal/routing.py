from django.urls import path

from .consumers import RdpTerminalConsumer, TerminalConsumer

websocket_urlpatterns = [
    path("ws/web-terminal/rdp/<int:host_id>/", RdpTerminalConsumer.as_asgi()),
    path("ws/web-terminal/<int:host_id>/", TerminalConsumer.as_asgi()),
]
