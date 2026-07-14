from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from host_management.models import ManagedHost
from operations.responses import bad_request

from ..services import TerminalConnectionError, get_remote_resource_monitor
from .common import terminal_login_required


@api_view(["POST"])
@terminal_login_required
def terminal_monitor(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(get_remote_resource_monitor(host))
    except TerminalConnectionError as error:
        return bad_request(error)
