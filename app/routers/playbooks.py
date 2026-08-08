from pathlib import Path

from fastapi import APIRouter, Depends, Request

from app.config import PLAYBOOK_DIR
from app.models import User
from app.security.permissions import require_admin, require_authenticated, require_operator
from app.services.ansible_service import list_playbooks
from app.services.audit_service import write_audit_event
from app.services.run_service import syntax_check

router = APIRouter(prefix="/playbooks", tags=["playbooks"])

@router.get("")
def get_playbooks(_=Depends(require_authenticated)):
    return {"playbooks": list_playbooks()}

@router.get("/{playbook_name}")
def get_playbook(playbook_name: str, _=Depends(require_authenticated)):
    safe_name = Path(playbook_name).name
    path = PLAYBOOK_DIR / safe_name
    if not path.exists():
        return {"status": "not_found", "content": ""}
    return {"name": safe_name, "content": path.read_text(encoding="utf-8")}

@router.post("/save")
def save_playbook(request: Request, payload: dict, current_user: User = Depends(require_admin)):
    name = payload.get("name", "").strip()
    content = payload.get("content", "")
    if not name:
        return {"status": "error", "message": "Playbook name is required"}
    if not name.endswith((".yml", ".yaml")):
        name = f"{name}.yml"
    safe_name = Path(name).name
    path = PLAYBOOK_DIR / safe_name
    PLAYBOOK_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    write_audit_event(request=request, action="playbook.save", actor=current_user,
                      resource_type="playbook", resource_id=safe_name,
                      details={"bytes": len(content.encode("utf-8"))})
    return {"status": "saved", "name": safe_name}

@router.delete("/{playbook_name}")
def delete_playbook(request: Request, playbook_name: str, current_user: User = Depends(require_admin)):
    safe_name = Path(playbook_name).name
    path = PLAYBOOK_DIR / safe_name
    if path.exists():
        path.unlink()
        write_audit_event(request=request, action="playbook.delete", actor=current_user,
                          resource_type="playbook", resource_id=safe_name)
        return {"status": "deleted", "name": safe_name}
    write_audit_event(request=request, action="playbook.delete", actor=current_user, outcome="failure",
                      resource_type="playbook", resource_id=safe_name, details={"reason": "not_found"})
    return {"status": "not_found", "name": safe_name}

@router.post("/{playbook_name}/syntax-check")
def syntax_check_playbook(request: Request, playbook_name: str, current_user: User = Depends(require_operator)):
    result = syntax_check(playbook_name)
    write_audit_event(request=request, action="playbook.syntax_check", actor=current_user,
                      outcome="success" if result.get("status") == "successful" else "failure",
                      resource_type="playbook", resource_id=Path(playbook_name).name,
                      details={"status": result.get("status"), "rc": result.get("rc")})
    return result
