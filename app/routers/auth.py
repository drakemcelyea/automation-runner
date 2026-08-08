from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from app.db import SessionLocal
from app.security.csrf import get_or_create_csrf_token, rotate_csrf_token
from app.security.passwords import verify_password
from app.services.audit_service import write_audit_event
from app.services.auth_security_service import (
    ip_throttle_remaining_seconds,
    prepare_account_for_login,
    record_account_login_failure,
    record_ip_login_failure,
    request_ip,
)
from app.services.user_service import (
    create_user,
    get_user_by_id,
    get_user_by_username,
    normalize_username,
    record_login,
)


router = APIRouter(tags=["authentication"])


@router.get("/csrf-token")
def csrf_token(request: Request):
    return {"csrf_token": get_or_create_csrf_token(request)}


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
    ip_address = request_ip(request)

    with SessionLocal() as db:
        ip_retry_after = ip_throttle_remaining_seconds(db, ip_address)

    if ip_retry_after:
        write_audit_event(
            request=request,
            action="security.login_throttled",
            outcome="failure",
            actor_username=username or None,
            resource_type="ip_address",
            resource_id=ip_address,
            details={"retry_after_seconds": ip_retry_after},
        )
        return JSONResponse(
            status_code=429,
            content={
                "status": "error",
                "message": "Too many failed login attempts. Try again later.",
                "retry_after": ip_retry_after,
            },
            headers={"Retry-After": str(ip_retry_after)},
        )

    if not username or not password:
        with SessionLocal() as db:
            blocked_now, retry_after = record_ip_login_failure(db, ip_address)
        write_audit_event(
            request=request,
            action="auth.login",
            outcome="failure",
            actor_username=username or None,
            details={"reason": "missing_credentials"},
        )
        if blocked_now:
            write_audit_event(
                request=request,
                action="security.login_throttled",
                outcome="failure",
                actor_username=username or None,
                resource_type="ip_address",
                resource_id=ip_address,
                details={"retry_after_seconds": retry_after},
            )
        return {"status": "error", "message": "Missing credentials"}

    with SessionLocal() as db:
        user = get_user_by_username(db, username)

        if user is not None and user.enabled:
            account_retry_after = prepare_account_for_login(db, user)
            if account_retry_after:
                record_ip_login_failure(db, ip_address)
                write_audit_event(
                    request=request,
                    action="security.account_locked",
                    outcome="failure",
                    actor_username=username,
                    resource_type="user",
                    resource_id=user.id,
                    details={"retry_after_seconds": account_retry_after},
                )
                return JSONResponse(
                    status_code=423,
                    content={
                        "status": "error",
                        "message": "Account temporarily locked. Try again later.",
                        "retry_after": account_retry_after,
                    },
                    headers={"Retry-After": str(account_retry_after)},
                )

        password_ok = bool(
            user is not None
            and user.enabled
            and verify_password(password, user.password_hash)
        )

        if not password_ok:
            reason = "invalid_credentials"
            account_locked_now = False
            account_retry_after = 0

            if user is not None and not user.enabled:
                reason = "account_disabled_or_pending"
            elif user is not None and user.enabled:
                account_locked_now, account_retry_after = record_account_login_failure(db, user)
                if account_locked_now:
                    reason = "account_locked"

            ip_blocked_now, ip_retry_after = record_ip_login_failure(db, ip_address)

            write_audit_event(
                request=request,
                action="auth.login",
                outcome="failure",
                actor_username=username,
                resource_type="user",
                resource_id=user.id if user else None,
                details={"reason": reason},
            )

            if account_locked_now:
                write_audit_event(
                    request=request,
                    action="security.account_locked",
                    outcome="failure",
                    actor_username=username,
                    resource_type="user",
                    resource_id=user.id,
                    details={"retry_after_seconds": account_retry_after},
                )

            if ip_blocked_now:
                write_audit_event(
                    request=request,
                    action="security.login_throttled",
                    outcome="failure",
                    actor_username=username,
                    resource_type="ip_address",
                    resource_id=ip_address,
                    details={"retry_after_seconds": ip_retry_after},
                )

            if account_locked_now:
                return JSONResponse(
                    status_code=423,
                    content={
                        "status": "error",
                        "message": "Account temporarily locked. Try again later.",
                        "retry_after": account_retry_after,
                    },
                    headers={"Retry-After": str(account_retry_after)},
                )

            if ip_blocked_now:
                return JSONResponse(
                    status_code=429,
                    content={
                        "status": "error",
                        "message": "Too many failed login attempts. Try again later.",
                        "retry_after": ip_retry_after,
                    },
                    headers={"Retry-After": str(ip_retry_after)},
                )

            return {"status": "error", "message": "Invalid credentials"}

        record_login(db, user)
        request.session.clear()
        request.session["user"] = user.username
        request.session["user_id"] = user.id
        request.session["role"] = user.role
        new_csrf_token = rotate_csrf_token(request)

        write_audit_event(
            request=request,
            action="auth.login",
            actor=user,
            resource_type="user",
            resource_id=user.id,
            details={"role": user.role},
        )
        return {
            "status": "ok",
            "user": user.username,
            "user_id": user.id,
            "role": user.role,
            "csrf_token": new_csrf_token,
        }


@router.post("/logout")
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
