from fastapi import APIRouter, Body, Request

from app.db import SessionLocal
from app.security.passwords import verify_password
from app.services.user_service import (
    create_user,
    get_user_by_username,
    normalize_username,
    record_login,
)


router = APIRouter(tags=["authentication"])


@router.post("/register")
def register(payload: dict = Body(...)):
    username = normalize_username(str(payload.get("username", "")))
    password = str(payload.get("password", ""))
    confirm_password = str(payload.get("confirm_password", ""))

    if not username:
        return {"status": "error", "message": "Username is required"}

    if len(username) < 3:
        return {"status": "error", "message": "Username must be at least 3 characters"}

    if len(username) > 50:
        return {"status": "error", "message": "Username cannot exceed 50 characters"}

    if not username.replace("_", "").replace("-", "").isalnum():
        return {
            "status": "error",
            "message": (
                "Username may only contain letters, numbers, underscores, and hyphens"
            ),
        }

    if len(password) < 12:
        return {"status": "error", "message": "Password must be at least 12 characters"}

    if password != confirm_password:
        return {"status": "error", "message": "Passwords do not match"}

    with SessionLocal() as db:
        try:
            user = create_user(
                db=db,
                username=username,
                password=password,
                role="viewer",
                enabled=False,
            )
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

    return {
        "status": "ok",
        "message": (
            "Account created. An administrator must approve the account "
            "before you can sign in."
        ),
        "user": user.username,
    }


@router.post("/login")
def login(request: Request, payload: dict = Body(...)):
    username = normalize_username(str(payload.get("username", "")))
    password = str(payload.get("password", ""))

    if not username or not password:
        return {"status": "error", "message": "Missing credentials"}

    with SessionLocal() as db:
        user = get_user_by_username(db, username)

        if user is None or not user.enabled or not verify_password(password, user.password_hash):
            return {"status": "error", "message": "Invalid credentials"}

        record_login(db, user)
        request.session.clear()
        request.session["user"] = user.username
        request.session["user_id"] = user.id
        request.session["role"] = user.role

        return {"status": "ok", "user": user.username, "role": user.role}


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return {"status": "logged_out"}


@router.get("/me")
def me(request: Request):
    username = request.session.get("user")

    if not username:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user": username,
        "user_id": request.session.get("user_id"),
        "role": request.session.get("role"),
    }
