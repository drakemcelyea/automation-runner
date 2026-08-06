import uuid
from datetime import datetime

from app.config import INVENTORY_FILE
from app.services.json_store import read_json, write_json


def load_inventory() -> list[dict]:
    return read_json(INVENTORY_FILE, [])


def save_inventory(hosts: list[dict]) -> None:
    write_json(INVENTORY_FILE, hosts)


def list_groups() -> list[str]:
    hosts = load_inventory()
    groups = sorted(
        {
            host.get("type", "linux")
            for host in hosts
            if host.get("enabled", True)
        }
    )
    return ["all", *groups]


def add_host(payload: dict) -> dict:
    hosts = load_inventory()
    new_host = {
        "id": str(uuid.uuid4()),
        "name": payload.get("name"),
        "ip": payload.get("ip"),
        "type": payload.get("type", "linux"),
        "enabled": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    hosts.append(new_host)
    save_inventory(hosts)
    return new_host


def delete_host(host_id: str) -> None:
    hosts = [host for host in load_inventory() if host.get("id") != host_id]
    save_inventory(hosts)


def toggle_host(host_id: str) -> dict | None:
    hosts = load_inventory()

    for host in hosts:
        if host.get("id") == host_id:
            host["enabled"] = not host.get("enabled", True)
            save_inventory(hosts)
            return host

    return None
