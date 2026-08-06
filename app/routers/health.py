from datetime import datetime

from fastapi import APIRouter

from app.config import APP_DIR, RUNS_DIR


router = APIRouter(tags=["health"])


@router.get("/")
def root():
    return {"status": "ok"}


@router.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "automation-runner",
        "time": datetime.now().isoformat(),
        "runs_dir": str(RUNS_DIR),
        "app_dir": str(APP_DIR),
    }
