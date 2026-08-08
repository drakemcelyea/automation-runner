from fastapi import APIRouter, Depends, Request

from app.models import User
from app.security.permissions import require_admin
from app.services.audit_service import write_audit_event
from app.services.vault_service import save_vault, test_vault, vault_status

router = APIRouter(prefix="/vault", tags=["vault"], dependencies=[Depends(require_admin)])

@router.get("/status")
def get_vault_status():
    return vault_status()

@router.post("/save")
def update_vault(request: Request, payload: dict, current_user: User = Depends(require_admin)):
    result = save_vault(payload)
    write_audit_event(request=request, action="vault.save", actor=current_user,
                      outcome="success" if result.get("status") == "saved" else "failure",
                      resource_type="vault",
                      details={"status": result.get("status")})
    return result

@router.post("/test")
def validate_vault(request: Request, current_user: User = Depends(require_admin)):
    result = test_vault()
    write_audit_event(request=request, action="vault.test", actor=current_user,
                      outcome="success" if result.get("status") == "successful" else "failure",
                      resource_type="vault", details={"status": result.get("status"), "rc": result.get("rc")})
    return result
