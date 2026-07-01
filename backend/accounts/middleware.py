from django.http import JsonResponse

from .session_lock import is_session_locked


class SessionLockMiddleware:
    ALLOWED_PATHS = {
        "/api/auth/me/",
        "/api/auth/unlock/",
        "/api/auth/logout/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_block(request):
            return JsonResponse({"error": "当前会话已锁定，请先解锁"}, status=423)
        return self.get_response(request)

    def _should_block(self, request) -> bool:
        if not request.path.startswith("/api/"):
            return False
        if request.path in self.ALLOWED_PATHS:
            return False
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return is_session_locked(request)
