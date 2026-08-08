from fastapi import APIRouter, Body, Request

from app.db import SessionLocal
from app.security.passwords import verify_password
from app.services.audit_service import write_audit_event
from app.services.user_service import (
    create_user,
    get_user_by_id,
    get_user_by_username,
    normalize_username,
    record_login,
)


router = APIRouter(tags=["authentication"])


@router.post("/register")
def register(request: Request, payload: dict = Body(...)):
    username = normalize_username(str(payload.get("username", "")))
    password = str(payload.get("password", ""))
    confirm_password = str(payload.get("confirm_password", ""))

    def registration_error(message: str):
        write_audit_event(
            request=request,
            action="auth.register",
            outcome="failure",
            actor_username=username or None,
            resource_type="user",
            resource_id=username or None,
            details={"reason": message},
        )
        return {"status": "error", "message": message}

    if not username:
        return registration_error("Username is required")
    if len(username) < 3:
        return registration_error("Username must be at least 3 characters")
    if len(username) > 50:
        return registration_error("Username cannot exceed 50 characters")
    if not username.replace("_", "").replace("-", "").isalnum():
        return registration_error("Username may only contain letters, numbers, underscores, and hyphens")
    if len(password) < 12:
        return registration_error("Password must be at least 12 characters")
    if password != confirm_password:
        return registration_error("Passwords do not match")

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
            return registration_error(str(exc))

    write_audit_event(
        request=request,
        action="auth.register",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        details={"username": user.username, "role": user.role, "enabled": user.enabled},
    )
    return {
        "status": "ok",
        "message": "Account created. An administrator must approve the account before you can sign in.",
        "user": user.username,
    }


@router.post("/login")
def login(request: Request, payload: dict = Body(...)):
    username = normalize_username(str(payload.get("username", "")))
    password = str(payload.get("password", ""))

    if not username or not password:
        write_audit_event(
            request=request, action="auth.login", outcome="failure",
            actor_username=username or None, details={"reason": "Missing credentials"}
        )
        return {"status": "error", "message": "Missing credentials"}

    with SessionLocal() as db:
        user = get_user_by_username(db, username)

        if user is None or not user.enabled or not verify_password(password, user.password_hash):
            reason = "invalid_credentials"
            if user is not None and not user.enabled:
                reason = "account_disabled_or_pending"
            write_audit_event(
                request=request,
                action="auth.login",
                outcome="failure",
                actor_username=username,
                resource_type="user",
                resource_id=user.id if user else None,
                details={"reason": reason},
            )
            return {"status": "error", "message": "Invalid credentials"}

        record_login(db, user)
        request.session.clear()
        request.session["user"] = user.username
        request.session["user_id"] = user.id
        request.session["role"] = user.role

        write_audit_event(
            request=request,
            action="auth.login",
            actor=user,
            resource_type="user",
            resource_id=user.id,
            details={"role": user.role},
        )
        return {"status": "ok", "user": user.username, "user_id": user.id, "role": user.role}


@router.get("/logout")
def logout(request: Request):
    actor_username = request.session.get("user")
    actor_id = request.session.get("user_id")
    actor = None
    if actor_id:
        with SessionLocal() as db:
            actor = get_user_by_id(db, actor_id)
            if actor:
                db.expunge(actor)

    write_audit_event(
        request=request,
        action="auth.logout",
        actor=actor,
        actor_username=actor_username,
        resource_type="user",
        resource_id=actor_id,
    )
    request.session.clear()
    return {"status": "logged_out"}


@router.get("/me")
def me(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return {"authenticated": False}

    with SessionLocal() as db:
        user = get_user_by_id(db, user_id)
        if user is None or not user.enabled:
            request.session.clear()
            return {"authenticated": False}

        request.session["user"] = user.username
        request.session["role"] = user.role
        return {
            "authenticated": True,
            "user": user.username,
            "user_id": user.id,
            "role": user.role,
        }
