import json
from typing import Any

from fastapi import Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AuditLog, User


def _request_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    value = request.headers.get("user-agent")
    return value[:512] if value else None


def write_audit_event(
    *,
    request: Request | None,
    action: str,
    outcome: str = "success",
    actor: User | None = None,
    actor_username: str | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Best-effort audit write. Never include passwords, vault secrets, or session tokens."""
    event = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_username=actor.username if actor else actor_username,
        action=action,
        outcome=outcome,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=json.dumps(details, sort_keys=True, default=str) if details else None,
        ip_address=_request_ip(request),
        user_agent=_user_agent(request),
    )

    try:
        with SessionLocal() as db:
            db.add(event)
            db.commit()
    except Exception as exc:
        # Audit failures should not take the controller down; surface them in container logs.
        print(f"AUDIT_WRITE_FAILED action={action!r}: {exc}")


def list_audit_events(
    db: Session,
    *,
    limit: int = 200,
    offset: int = 0,
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
) -> list[AuditLog]:
    statement = select(AuditLog)

    if actor:
        statement = statement.where(AuditLog.actor_username == actor.strip().lower())
    if action:
        statement = statement.where(AuditLog.action == action.strip())
    if outcome:
        statement = statement.where(AuditLog.outcome == outcome.strip().lower())

    statement = statement.order_by(desc(AuditLog.created_at), desc(AuditLog.id)).offset(offset).limit(limit)
    return list(db.scalars(statement))


def serialize_audit_event(event: AuditLog) -> dict:
    details = None
    if event.details:
        try:
            details = json.loads(event.details)
        except json.JSONDecodeError:
            details = {"message": event.details}

    return {
        "id": event.id,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "actor_user_id": event.actor_user_id,
        "actor_username": event.actor_username,
        "action": event.action,
        "outcome": event.outcome,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "details": details,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
    }
