from rest_framework import status
from rest_framework.response import Response


def bad_request(error: Exception | str) -> Response:
    return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)


def not_found(message: str) -> Response:
    return Response({"error": message}, status=status.HTTP_404_NOT_FOUND)


def first_serializer_error(errors):
    if isinstance(errors, dict):
        first = next(iter(errors.values()))
        if isinstance(first, list) and first:
            return first[0]
        return first
    if isinstance(errors, list) and errors:
        return errors[0]
    return errors


def serializer_bad_request(serializer) -> Response:
    return bad_request(first_serializer_error(serializer.errors))


def bounded_int(value, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)
