from fastapi import APIRouter, Depends

from app.security.permissions import require_admin, require_authenticated
from app.services.settings_service import load_settings, update_settings


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(_=Depends(require_authenticated)):
    return load_settings()


@router.post("")
def save_settings(payload: dict, _=Depends(require_admin)):
    return update_settings(payload)
