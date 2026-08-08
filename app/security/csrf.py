import hmac
import secrets

from fastapi import Request


SESSION_CSRF_KEY = "_csrf_token"
CSRF_HEADER = "X-CSRF-Token"


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get(SESSION_CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_CSRF_KEY] = token
    return token


def rotate_csrf_token(request: Request) -> str:
    token = secrets.token_urlsafe(32)
    request.session[SESSION_CSRF_KEY] = token
    return token


def csrf_token_is_valid(request: Request) -> bool:
    expected = request.session.get(SESSION_CSRF_KEY)
    supplied = request.headers.get(CSRF_HEADER)

    if not expected or not supplied:
        return False

    return hmac.compare_digest(str(expected), str(supplied))
