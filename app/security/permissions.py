from fastapi import HTTPException, Request, status

from app.db import SessionLocal
from app.models import User


ROLE_LEVELS = {
    "viewer": 10,
    "operator": 20,
    "admin": 30,
}


def _load_session_user(request: Request) -> User:
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    with SessionLocal() as db:
        user = db.get(User, user_id)

        if user is None or not user.enabled:
            request.session.clear()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is unavailable",
            )

        db.expunge(user)

    request.session["user"] = user.username
    request.session["role"] = user.role
    return user


def require_authenticated(request: Request) -> User:
    return _load_session_user(request)


def require_minimum_role(request: Request, required_role: str) -> User:
    user = _load_session_user(request)
    user_level = ROLE_LEVELS.get(user.role, 0)
    required_level = ROLE_LEVELS[required_role]

    if user_level < required_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{required_role.title()} access required",
        )

    return user


def require_operator(request: Request) -> User:
    return require_minimum_role(request, "operator")


def require_admin(request: Request) -> User:
    return require_minimum_role(request, "admin")
