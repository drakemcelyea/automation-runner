from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from app.db import SessionLocal
from app.models import User
from app.security.permissions import require_admin
from app.services.audit_service import write_audit_event
from app.services.user_service import (
    VALID_ROLES, count_enabled_admins, delete_user, get_user_by_id, list_users,
    serialize_user, set_user_enabled, set_user_role,
)

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


def _required_user(user_id: int):
    db = SessionLocal()
    user = get_user_by_id(db, user_id)
    if user is None:
        db.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return db, user


@router.get("")
def get_users():
    with SessionLocal() as db:
        return {"users": [serialize_user(user) for user in list_users(db)]}


@router.post("/{user_id}/approve")
def approve_user(request: Request, user_id: int, current_user: User = Depends(require_admin)):
    db, user = _required_user(user_id)
    try:
        updated = set_user_enabled(db, user, True)
        write_audit_event(request=request, action="user.approve", actor=current_user,
                          resource_type="user", resource_id=user_id,
                          details={"target_username": updated.username})
        return {"status": "ok", "user": serialize_user(updated)}
    finally:
        db.close()


@router.post("/{user_id}/enable")
def enable_user(request: Request, user_id: int, current_user: User = Depends(require_admin)):
    db, user = _required_user(user_id)
    try:
        updated = set_user_enabled(db, user, True)
        write_audit_event(request=request, action="user.enable", actor=current_user,
                          resource_type="user", resource_id=user_id,
                          details={"target_username": updated.username})
        return {"status": "ok", "user": serialize_user(updated)}
    finally:
        db.close()


@router.post("/{user_id}/disable")
def disable_user(request: Request, user_id: int, current_user: User = Depends(require_admin)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot disable your own account")
    db, user = _required_user(user_id)
    try:
        if user.role == "admin" and user.enabled and count_enabled_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="The final enabled administrator cannot be disabled")
        updated = set_user_enabled(db, user, False)
        write_audit_event(request=request, action="user.disable", actor=current_user,
                          resource_type="user", resource_id=user_id,
                          details={"target_username": updated.username})
        return {"status": "ok", "user": serialize_user(updated)}
    finally:
        db.close()


@router.post("/{user_id}/role")
def update_user_role(request: Request, user_id: int, payload: dict = Body(...), current_user: User = Depends(require_admin)):
    role = str(payload.get("role", "")).strip().lower()
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Role must be admin, operator, or viewer")
    if user_id == current_user.id and role != "admin":
        raise HTTPException(status_code=400, detail="You cannot remove your own administrator role")

    db, user = _required_user(user_id)
    try:
        if user.role == "admin" and role != "admin" and user.enabled and count_enabled_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="The final enabled administrator must remain an administrator")
        previous_role = user.role
        updated = set_user_role(db, user, role)
        write_audit_event(request=request, action="user.role_change", actor=current_user,
                          resource_type="user", resource_id=user_id,
                          details={"target_username": updated.username, "from": previous_role, "to": role})
        return {"status": "ok", "user": serialize_user(updated)}
    finally:
        db.close()


@router.delete("/{user_id}")
def remove_user(request: Request, user_id: int, current_user: User = Depends(require_admin)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    db, user = _required_user(user_id)
    try:
        if user.role == "admin" and user.enabled and count_enabled_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="The final enabled administrator cannot be deleted")
        username = user.username
        delete_user(db, user)
        write_audit_event(request=request, action="user.delete", actor=current_user,
                          resource_type="user", resource_id=user_id,
                          details={"target_username": username})
        return {"status": "deleted", "user": username}
    finally:
        db.close()
