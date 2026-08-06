from fastapi import APIRouter

from app.services.inventory_service import (
    add_host,
    delete_host,
    list_groups,
    load_inventory,
    toggle_host,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("")
def get_inventory():
    return {"hosts": load_inventory()}


@router.get("/groups")
def get_inventory_groups():
    return {"groups": list_groups()}


@router.post("/add")
def add_inventory_host(host: dict):
    return add_host(host)


@router.delete("/{host_id}")
def delete_inventory_host(host_id: str):
    delete_host(host_id)
    return {"status": "deleted", "id": host_id}


@router.post("/{host_id}/toggle")
def toggle_inventory_host(host_id: str):
    host = toggle_host(host_id)
    return host or {"status": "not_found", "id": host_id}
