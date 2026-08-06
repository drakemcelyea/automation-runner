import json
import os
import shutil
import subprocess
from pathlib import Path

from app.config import DATA_DIR, PLAYBOOK_DIR, VAULT_FILE, VAULT_PASSWORD_FILE
from app.services.inventory_service import load_inventory


def ansible_environment() -> dict[str, str]:
    env = os.environ.copy()
    home_dir = DATA_DIR / "home"
    ansible_home = home_dir / ".ansible"
    local_temp = ansible_home / "tmp"

    local_temp.mkdir(parents=True, exist_ok=True)

    env.update(
        {
            "HOME": str(home_dir),
            "ANSIBLE_HOME": str(ansible_home),
            "ANSIBLE_LOCAL_TEMP": str(local_temp),
        }
    )
    return env


def copy_project_files(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)

    for source_path in source_dir.rglob("*"):
        relative_path = source_path.relative_to(source_dir)
        destination_path = destination_dir / relative_path

        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
        elif source_path.is_file():
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination_path)


def parse_extra_vars(raw_vars: str | None) -> dict:
    if not raw_vars or not raw_vars.strip():
        return {}

    raw_vars = raw_vars.strip()

    if raw_vars.startswith("{"):
        try:
            parsed = json.loads(raw_vars)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass

    extra_vars: dict[str, object] = {}

    for line in raw_vars.splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = (part.strip() for part in line.split("=", 1))

        if value.lower() == "true":
            parsed_value: object = True
        elif value.lower() == "false":
            parsed_value = False
        elif value.isdigit():
            parsed_value = int(value)
        else:
            parsed_value = value

        extra_vars[key] = parsed_value

    return extra_vars


def write_ansible_inventory(private_data_dir: Path) -> None:
    hosts = load_inventory()
    inventory_path = private_data_dir / "inventory"
    groups: dict[str, list[dict]] = {}

    for host in hosts:
        if not host.get("enabled", True):
            continue

        host_type = host.get("type", "linux")
        groups.setdefault(host_type, []).append(host)

    inventory_path.parent.mkdir(parents=True, exist_ok=True)

    with inventory_path.open("w", encoding="utf-8") as file_handle:
        if not groups:
            file_handle.write("[local]\nlocalhost ansible_connection=local\n")
            return

        for group, group_hosts in groups.items():
            file_handle.write(f"[{group}]\n")
            for host in group_hosts:
                name = host.get("name", "").replace(" ", "_")
                ip = host.get("ip", "")
                file_handle.write(f"{name} ansible_host={ip}\n")
            file_handle.write("\n")

        for linux_group in ("rhel9", "rhel8", "linux"):
            if linux_group in groups:
                file_handle.write(f"[{linux_group}:vars]\n")
                file_handle.write("ansible_user=lcl_admin\n")
                file_handle.write("ansible_become=true\n")
                file_handle.write("ansible_become_method=sudo\n")
                file_handle.write("ansible_password={{ vault_linux_password }}\n")
                file_handle.write(
                    "ansible_become_password={{ vault_linux_become_password }}\n\n"
                )

        if "windows" in groups:
            file_handle.write("[windows:vars]\n")
            file_handle.write("ansible_connection=ssh\n")
            file_handle.write("ansible_shell_type=powershell\n")
            file_handle.write("ansible_user=lcl_admin\n")
            file_handle.write("ansible_password={{ vault_windows_password }}\n")
            file_handle.write("ansible_become=false\n\n")


def prepare_vault_for_run(private_data_dir: Path) -> None:
    if not VAULT_FILE.exists():
        return

    group_vars_dir = private_data_dir / "project" / "group_vars" / "all"
    group_vars_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VAULT_FILE, group_vars_dir / "admin_secret.yml")


def vault_cmdline() -> str:
    if VAULT_PASSWORD_FILE.exists():
        return f"--vault-password-file {VAULT_PASSWORD_FILE}"
    return ""


def run_command(command: list[str]) -> dict:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=ansible_environment(),
        check=False,
    )
    return {
        "rc": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output": result.stdout + result.stderr,
    }


def list_playbooks() -> list[dict]:
    PLAYBOOK_DIR.mkdir(parents=True, exist_ok=True)
    paths = sorted(PLAYBOOK_DIR.glob("*.yml")) + sorted(PLAYBOOK_DIR.glob("*.yaml"))
    return [{"name": path.name, "path": str(path)} for path in paths]
