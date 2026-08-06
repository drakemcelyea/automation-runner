from fastapi import APIRouter, Depends

from app.security.permissions import require_admin, require_authenticated, require_operator
from app.services.run_service import clear_runs, execute_run, get_run_logs, list_runs, run_stats


router = APIRouter(tags=["runs"])


@router.get("/runs")
def get_runs(_=Depends(require_authenticated)):
    return {"runs": list_runs()}


@router.get("/stats")
def get_stats(_=Depends(require_authenticated)):
    return run_stats()


@router.delete("/runs")
def delete_runs(_=Depends(require_admin)):
    clear_runs()
    return {"status": "cleared"}


@router.post("/run-demo")
def run_demo(payload: dict | None = None, _=Depends(require_operator)):
    return execute_run(payload)


@router.get("/run-demo/{run_id}/logs")
def get_logs(run_id: str, _=Depends(require_authenticated)):
    return {"logs": get_run_logs(run_id)}
