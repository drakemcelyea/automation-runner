from fastapi import APIRouter, Depends

from app.security.permissions import require_admin
from app.services.vault_service import save_vault, test_vault, vault_status


router = APIRouter(
    prefix="/vault",
    tags=["vault"],
    dependencies=[Depends(require_admin)],
)


@router.get("/status")
def get_vault_status():
    return vault_status()


@router.post("/save")
def update_vault(payload: dict):
    return save_vault(payload)


@router.post("/test")
def validate_vault():
    return test_vault()
