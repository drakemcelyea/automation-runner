from fastapi import APIRouter, Depends, Query

from app.db import SessionLocal
from app.security.permissions import require_admin
from app.services.audit_service import list_audit_events, serialize_audit_event


router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_admin)],
)


@router.get("")
def get_audit_log(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
):
    with SessionLocal() as db:
        events = list_audit_events(
            db,
            limit=limit,
            offset=offset,
            actor=actor,
            action=action,
            outcome=outcome,
        )
        return {"events": [serialize_audit_event(event) for event in events]}
