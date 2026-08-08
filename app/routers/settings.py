from fastapi import APIRouter, Depends, Request

from app.models import User
from app.security.permissions import require_admin, require_authenticated
from app.services.audit_service import write_audit_event
from app.services.settings_service import load_settings, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("")
def get_settings(_=Depends(require_authenticated)):
    return load_settings()

@router.post("")
def save_settings(request: Request, payload: dict, current_user: User = Depends(require_admin)):
    updated = update_settings(payload)
    write_audit_event(request=request, action="settings.update", actor=current_user,
                      resource_type="settings", details={
                          "theme": updated.get("theme"),
                          "accent": updated.get("accent"),
                          "logging_enabled": updated.get("logging_enabled"),
                      })
    return updated
