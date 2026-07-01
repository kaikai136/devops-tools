AUTH_LOCKED_SESSION_KEY = "auth_locked"


def is_session_locked(request) -> bool:
    return bool(request.session.get(AUTH_LOCKED_SESSION_KEY))


def lock_session(request) -> None:
    request.session[AUTH_LOCKED_SESSION_KEY] = True
    request.session.modified = True


def unlock_session(request) -> None:
    request.session.pop(AUTH_LOCKED_SESSION_KEY, None)
    request.session.modified = True
