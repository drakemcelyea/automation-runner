from fastapi import APIRouter

from app.services.run_service import (
    clear_runs,
    execute_run,
    get_run_logs,
    list_runs,
    run_stats,
)


router = APIRouter(tags=["runs"])


@router.get("/runs")
def get_runs():
    return {"runs": list_runs()}


@router.get("/stats")
def get_stats():
    return run_stats()


@router.delete("/runs")
def delete_runs():
    clear_runs()
    return {"status": "cleared"}


@router.post("/run-demo")
def run_demo(payload: dict | None = None):
    return execute_run(payload)


@router.get("/run-demo/{run_id}/logs")
def get_logs(run_id: str):
    return {"logs": get_run_logs(run_id)}
