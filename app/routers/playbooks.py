from pathlib import Path

from fastapi import APIRouter

from app.config import PLAYBOOK_DIR
from app.services.ansible_service import list_playbooks
from app.services.run_service import syntax_check


router = APIRouter(prefix="/playbooks", tags=["playbooks"])


@router.get("")
def get_playbooks():
    return {"playbooks": list_playbooks()}


@router.get("/{playbook_name}")
def get_playbook(playbook_name: str):
    safe_name = Path(playbook_name).name
    path = PLAYBOOK_DIR / safe_name

    if not path.exists():
        return {"status": "not_found", "content": ""}

    return {"name": safe_name, "content": path.read_text(encoding="utf-8")}


@router.post("/save")
def save_playbook(payload: dict):
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
    return {"status": "saved", "name": safe_name}


@router.delete("/{playbook_name}")
def delete_playbook(playbook_name: str):
    safe_name = Path(playbook_name).name
    path = PLAYBOOK_DIR / safe_name

    if path.exists():
        path.unlink()
        return {"status": "deleted", "name": safe_name}

    return {"status": "not_found", "name": safe_name}


@router.post("/{playbook_name}/syntax-check")
def syntax_check_playbook(playbook_name: str):
    return syntax_check(playbook_name)
