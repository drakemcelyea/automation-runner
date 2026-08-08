from fastapi import APIRouter, Depends, Request

from app.models import User
from app.security.permissions import require_admin, require_authenticated
from app.services.audit_service import write_audit_event
from app.services.inventory_service import add_host, delete_host, list_groups, load_inventory, toggle_host

router = APIRouter(prefix="/inventory", tags=["inventory"])

@router.get("")
def get_inventory(_=Depends(require_authenticated)):
    return {"hosts": load_inventory()}

@router.get("/groups")
def get_inventory_groups(_=Depends(require_authenticated)):
    return {"groups": list_groups()}

@router.post("/add")
def add_inventory_host(request: Request, host: dict, current_user: User = Depends(require_admin)):
    created = add_host(host)
    write_audit_event(request=request, action="inventory.add", actor=current_user,
                      resource_type="inventory_host", resource_id=created.get("id"),
                      details={"name": created.get("name"), "ip": created.get("ip"), "type": created.get("type")})
    return created

@router.delete("/{host_id}")
def delete_inventory_host(request: Request, host_id: str, current_user: User = Depends(require_admin)):
    delete_host(host_id)
    write_audit_event(request=request, action="inventory.delete", actor=current_user,
                      resource_type="inventory_host", resource_id=host_id)
    return {"status": "deleted", "id": host_id}

@router.post("/{host_id}/toggle")
def toggle_inventory_host(request: Request, host_id: str, current_user: User = Depends(require_admin)):
    host = toggle_host(host_id)
    write_audit_event(request=request, action="inventory.toggle", actor=current_user,
                      outcome="success" if host else "failure", resource_type="inventory_host", resource_id=host_id,
                      details={"enabled": host.get("enabled")} if host else {"reason": "not_found"})
    return host or {"status": "not_found", "id": host_id}
