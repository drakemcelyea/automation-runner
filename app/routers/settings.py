from fastapi import APIRouter

from app.services.settings_service import load_settings, update_settings


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings():
    return load_settings()


@router.post("")
def save_settings(payload: dict):
    return update_settings(payload)
