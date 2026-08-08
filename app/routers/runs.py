from fastapi import APIRouter, Depends, Request

from app.models import User
from app.security.permissions import require_admin, require_authenticated, require_operator
from app.services.audit_service import write_audit_event
from app.services.run_service import clear_runs, execute_run, get_run_logs, list_runs, run_stats

router = APIRouter(tags=["runs"])

@router.get("/runs")
def get_runs(_=Depends(require_authenticated)):
    return {"runs": list_runs()}

@router.get("/stats")
def get_stats(_=Depends(require_authenticated)):
    return run_stats()

@router.delete("/runs")
def delete_runs(request: Request, current_user: User = Depends(require_admin)):
    clear_runs()
    write_audit_event(request=request, action="run.clear_history", actor=current_user, resource_type="run_history")
    return {"status": "cleared"}

@router.post("/run-demo")
def run_demo(request: Request, payload: dict | None = None, current_user: User = Depends(require_operator)):
    result = execute_run(payload)
    write_audit_event(request=request, action="run.execute", actor=current_user,
                      outcome="success" if result.get("status") == "successful" else "failure",
                      resource_type="run", resource_id=result.get("run_id"),
                      details={"playbook": result.get("playbook"), "target": result.get("target"),
                               "status": result.get("status"), "rc": result.get("rc"),
                               "duration": result.get("duration")})
    return result

@router.get("/run-demo/{run_id}/logs")
def get_logs(run_id: str, _=Depends(require_authenticated)):
    return {"logs": get_run_logs(run_id)}
