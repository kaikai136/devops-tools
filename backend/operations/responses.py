from rest_framework import status
from rest_framework.response import Response


def bad_request(error: Exception | str) -> Response:
    return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)
