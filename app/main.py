from fastapi import FastAPI, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import ansible_runner
import uuid
import shutil
import json
import time
import subprocess
import os
from pathlib import Path
from datetime import datetime

from app.db import Base, SessionLocal, engine
from app.models import User
from app.security import verify_password

from app.user_service import (
    create_user,
    get_user_by_username,
    normalize_username,
    record_login,
)

from app.config import (
    APP_DIR,
    STATIC_DIR,
    TEMPLATE_DIR,
    PLAYBOOK_DIR,
    RUNS_DIR,
    RUNS_FILE,
    INVENTORY_FILE,
    SETTINGS_FILE,
    VAULT_DIR,
    VAULT_FILE,
    VAULT_PASSWORD_FILE,
)

app = FastAPI()

SESSION_SECRET = os.getenv(
    "SESSION_SECRET",
    "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
)

Base.metadata.create_all(bind=engine)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)

templates = Jinja2Templates(
    directory=str(TEMPLATE_DIR)
)

def read_json(path: Path, default):
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def ansible_environment():
    env = os.environ.copy()

    home_dir = Path("/var/lib/automation-runner/home")
    ansible_home = home_dir / ".ansible"
    local_temp = ansible_home / "tmp"

    home_dir.mkdir(parents=True, exist_ok=True)
    ansible_home.mkdir(parents=True, exist_ok=True)
    local_temp.mkdir(parents=True, exist_ok=True)

    env.update(
        {
            "HOME": str(home_dir),
            "ANSIBLE_HOME": str(ansible_home),
            "ANSIBLE_LOCAL_TEMP": str(local_temp),
        }
    )

    return env

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def copy_project_files(source_dir: Path, destination_dir: Path):
    destination_dir.mkdir(parents=True, exist_ok=True)

    for source_path in source_dir.rglob("*"):
        relative_path = source_path.relative_to(source_dir)
        destination_path = destination_dir / relative_path

        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
        elif source_path.is_file():
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination_path)


RUNS = read_json(RUNS_FILE, {})


def save_runs():
    write_json(RUNS_FILE, RUNS)


def load_inventory():
    return read_json(INVENTORY_FILE, [])


def save_inventory(hosts):
    write_json(INVENTORY_FILE, hosts)


def load_settings():
    return read_json(
        SETTINGS_FILE,
        {
            "theme": "light",
            "accent": "primary",
            "logging_enabled": True,
        },
    )


def save_settings(settings):
    write_json(SETTINGS_FILE, settings)


def parse_extra_vars(raw_vars):
    if not raw_vars:
        return {}

    raw_vars = raw_vars.strip()

    if not raw_vars:
        return {}

    try:
        if raw_vars.startswith("{"):
            return json.loads(raw_vars)
    except Exception:
        pass

    extra_vars = {}

    for line in raw_vars.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.isdigit():
            value = int(value)

        extra_vars[key] = value

    return extra_vars


def write_ansible_inventory(private_data_dir: Path):
    hosts = load_inventory()
    inventory_path = private_data_dir / "inventory"
    groups = {}

    for host in hosts:
        if not host.get("enabled", True):
            continue

        host_type = host.get("type", "linux")
        groups.setdefault(host_type, []).append(host)

    with inventory_path.open("w", encoding="utf-8") as f:
        if not groups:
            f.write("[local]\nlocalhost ansible_connection=local\n")
            return

        for group, group_hosts in groups.items():
            f.write(f"[{group}]\n")
            for host in group_hosts:
                name = host.get("name", "").replace(" ", "_")
                ip = host.get("ip", "")
                f.write(f"{name} ansible_host={ip}\n")
            f.write("\n")

        for linux_group in ["rhel9", "rhel8", "linux"]:
            if linux_group in groups:
                f.write(f"[{linux_group}:vars]\n")
                f.write("ansible_user=lcl_admin\n")
                f.write("ansible_become=true\n")
                f.write("ansible_become_method=sudo\n")
                f.write("ansible_password={{ vault_linux_password }}\n")
                f.write("ansible_become_password={{ vault_linux_become_password }}\n\n")

        if "windows" in groups:
            f.write("[windows:vars]\n")
            f.write("ansible_connection=ssh\n")
            f.write("ansible_shell_type=powershell\n")
            f.write("ansible_user=lcl_admin\n")
            f.write("ansible_password={{ vault_windows_password }}\n")
            f.write("ansible_become=false\n\n")


def prepare_vault_for_run(private_data_dir: Path):
    if not VAULT_FILE.exists():
        return

    group_vars_dir = private_data_dir / "project" / "group_vars" / "all"
    group_vars_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(VAULT_FILE, group_vars_dir / "admin_secret.yml")


def vault_cmdline():
    if VAULT_PASSWORD_FILE.exists():
        return f"--vault-password-file {VAULT_PASSWORD_FILE}"
    return ""


def run_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, env=ansible_environment())
    return {
        "rc": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output": result.stdout + result.stderr,
    }


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "automation-runner",
        "time": datetime.now().isoformat(),
        "runs_dir": str(RUNS_DIR),
        "app_dir": str(APP_DIR),
    }


@app.post("/login")
def login(request: Request, payload: dict = Body(...)):
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not username or not password:
        return {
            "status": "error",
            "message": "Missing credentials",
        }

    with SessionLocal() as db:
        user = get_user_by_username(db, username)

        if (
            user is None
            or not user.enabled
            or not verify_password(password, user.password_hash)
        ):
            return {
                "status": "error",
                "message": "Invalid credentials",
            }

        record_login(db, user)

        request.session.clear()
        request.session["user"] = user.username
        request.session["user_id"] = user.id
        request.session["role"] = user.role

        return {
            "status": "ok",
            "user": user.username,
            "role": user.role,
        }

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return {"status": "logged_out"}


@app.get("/me")
def me(request: Request):
    username = request.session.get("user")

    if not username:
        return {
            "authenticated": False,
        }

    return {
        "authenticated": True,
        "user": username,
        "user_id": request.session.get("user_id"),
        "role": request.session.get("role"),
    }

@app.get("/runs")
def list_runs():
    return {"runs": list(RUNS.values())[::-1]}


@app.get("/stats")
def stats():
    return {
        "total": len(RUNS),
        "successful": len([r for r in RUNS.values() if r.get("status") == "successful"]),
        "failed": len([r for r in RUNS.values() if r.get("status") == "failed"]),
        "errors": len([r for r in RUNS.values() if r.get("status") == "error"]),
    }


@app.delete("/runs")
def clear_runs():
    RUNS.clear()
    save_runs()
    return {"status": "cleared"}


@app.get("/inventory")
def get_inventory():
    return {"hosts": load_inventory()}


@app.get("/inventory/groups")
def get_inventory_groups():
    hosts = load_inventory()
    groups = sorted({h.get("type", "linux") for h in hosts if h.get("enabled", True)})
    return {"groups": ["all"] + groups}


@app.post("/inventory/add")
def add_inventory_host(host: dict):
    hosts = load_inventory()

    new_host = {
        "id": str(uuid.uuid4()),
        "name": host.get("name"),
        "ip": host.get("ip"),
        "type": host.get("type", "linux"),
        "enabled": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    hosts.append(new_host)
    save_inventory(hosts)

    return new_host


@app.delete("/inventory/{host_id}")
def delete_inventory_host(host_id: str):
    hosts = load_inventory()
    hosts = [h for h in hosts if h.get("id") != host_id]
    save_inventory(hosts)

    return {"status": "deleted", "id": host_id}


@app.post("/inventory/{host_id}/toggle")
def toggle_inventory_host(host_id: str):
    hosts = load_inventory()

    for host in hosts:
        if host.get("id") == host_id:
            host["enabled"] = not host.get("enabled", True)
            save_inventory(hosts)
            return host

    return {"status": "not_found", "id": host_id}


@app.get("/playbooks")
def list_playbooks():
    PLAYBOOK_DIR.mkdir(parents=True, exist_ok=True)

    playbooks = []
    for item in sorted(PLAYBOOK_DIR.glob("*.yml")) + sorted(PLAYBOOK_DIR.glob("*.yaml")):
        playbooks.append({"name": item.name, "path": str(item)})

    return {"playbooks": playbooks}


@app.get("/playbooks/{playbook_name}")
def get_playbook(playbook_name: str):
    safe_name = Path(playbook_name).name
    path = PLAYBOOK_DIR / safe_name

    if not path.exists():
        return {"status": "not_found", "content": ""}

    return {"name": safe_name, "content": path.read_text(encoding="utf-8")}


@app.post("/playbooks/save")
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


@app.delete("/playbooks/{playbook_name}")
def delete_playbook(playbook_name: str):
    safe_name = Path(playbook_name).name
    path = PLAYBOOK_DIR / safe_name

    if path.exists():
        path.unlink()
        return {"status": "deleted", "name": safe_name}

    return {"status": "not_found", "name": safe_name}


@app.post("/playbooks/{playbook_name}/syntax-check")
def syntax_check_playbook(playbook_name: str):
    safe_name = Path(playbook_name).name
    source_playbook = PLAYBOOK_DIR / safe_name

    if not source_playbook.exists():
        return {
            "status": "error",
            "output": "Playbook not found.",
        }

    temp_dir = RUNS_DIR / f"syntax-{uuid.uuid4()}"
    project_dir = temp_dir / "project"

    try:
        project_dir.mkdir(parents=True, exist_ok=False)

        # Copy file contents without copying SELinux/xattr metadata.
        destination_playbook = project_dir / safe_name
        shutil.copyfile(source_playbook, destination_playbook)

        write_ansible_inventory(temp_dir)
        prepare_vault_for_run(temp_dir)

        cmd = [
            "ansible-playbook",
            "-i",
            str(temp_dir / "inventory"),
            str(destination_playbook),
        ]

        if VAULT_PASSWORD_FILE.exists():
            cmd.extend([
                "--vault-password-file",
                str(VAULT_PASSWORD_FILE),
            ])

        cmd.append("--syntax-check")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=ansible_environment()
        )

        return {
            "status": "successful" if result.returncode == 0 else "failed",
            "rc": result.returncode,
            "output": result.stdout + result.stderr,
        }

    except Exception as exc:
        return {
            "status": "error",
            "rc": -1,
            "output": str(exc),
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/run-demo")
def run_demo(payload: dict = None):
    payload = payload or {}

    playbook = Path(payload.get("playbook", "ping.yml")).name
    target = payload.get("target", "all")
    raw_extra_vars = payload.get("extra_vars", "")
    extra_vars = parse_extra_vars(raw_extra_vars)

    run_id = str(uuid.uuid4())
    started_at = datetime.now()
    start_timer = time.time()

    try:
        private_data_dir = RUNS_DIR / run_id
        project_dir = private_data_dir / "project"

        private_data_dir.mkdir(parents=True, exist_ok=True)

        copy_project_files(PLAYBOOK_DIR, project_dir)

        write_ansible_inventory(private_data_dir)
        prepare_vault_for_run(private_data_dir)

        settings = load_settings()

        result = ansible_runner.run(
            private_data_dir=str(private_data_dir),
            playbook=playbook,
            quiet=not settings.get("logging_enabled", True),
            cmdline=vault_cmdline(),
            limit=None if target == "all" else target,
            extravars=extra_vars,
            envvars=ansible_environment()
        )

        finished_at = datetime.now()
        duration = round(time.time() - start_timer, 2)

        RUNS[run_id] = {
            "run_id": run_id,
            "playbook": playbook,
            "target": target,
            "extra_vars": extra_vars,
            "status": result.status,
            "rc": result.rc,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration": duration,
            "private_data_dir": str(private_data_dir),
        }

        save_runs()
        return RUNS[run_id]

    except Exception as exc:
        finished_at = datetime.now()
        duration = round(time.time() - start_timer, 2)

        RUNS[run_id] = {
            "run_id": run_id,
            "playbook": playbook,
            "target": target,
            "extra_vars": extra_vars,
            "status": "error",
            "rc": -1,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration": duration,
            "error": str(exc),
            "private_data_dir": str(RUNS_DIR / run_id),
        }

        save_runs()
        return RUNS[run_id]


@app.get("/run-demo/{run_id}/logs")
def get_run_logs(run_id: str):
    artifacts_dir = RUNS_DIR / run_id / "artifacts"

    if not artifacts_dir.exists():
        return {"logs": "No artifacts found yet."}

    output_lines = []

    for artifact_run in artifacts_dir.iterdir():
        job_events_dir = artifact_run / "job_events"

        if not job_events_dir.exists():
            continue

        for event_file in sorted(job_events_dir.glob("*.json")):
            try:
                with event_file.open("r", encoding="utf-8") as f:
                    event = json.load(f)

                stdout = event.get("stdout")
                if stdout:
                    output_lines.append(stdout)

            except Exception:
                continue

    return {"logs": "\n".join(output_lines) if output_lines else "No logs found."}


@app.get("/settings")
def get_settings():
    return load_settings()


@app.post("/settings")
def update_settings(payload: dict):
    settings = load_settings()

    settings.update(
        {
            "theme": payload.get("theme", settings.get("theme", "light")),
            "accent": payload.get("accent", settings.get("accent", "primary")),
            "logging_enabled": payload.get(
                "logging_enabled",
                settings.get("logging_enabled", True),
            ),
        }
    )

    save_settings(settings)
    return settings


@app.get("/vault/status")
def get_vault_status():
    encrypted = False

    if VAULT_FILE.exists():
        try:
            first_line = VAULT_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
            encrypted = first_line.startswith("$ANSIBLE_VAULT")
        except Exception:
            encrypted = False

    return {
        "vault_dir": str(VAULT_DIR),
        "vault_file": str(VAULT_FILE),
        "vault_password_file": str(VAULT_PASSWORD_FILE),
        "vault_file_exists": VAULT_FILE.exists(),
        "vault_password_file_exists": VAULT_PASSWORD_FILE.exists(),
        "vault_encrypted": encrypted,
    }


@app.post("/vault/save")
def save_vault(payload: dict):
    vault_password = payload.get("vault_password", "").strip()
    linux_password = payload.get("vault_linux_password", "")
    linux_become_password = payload.get("vault_linux_become_password", "")
    windows_password = payload.get("vault_windows_password", "")

    if not vault_password:
        return {"status": "error", "message": "Vault password is required."}

    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    VAULT_PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)

    VAULT_PASSWORD_FILE.write_text(vault_password + "\n", encoding="utf-8")
    VAULT_PASSWORD_FILE.chmod(0o600)

    plain_content = (
        f'vault_linux_password: "{linux_password}"\n'
        f'vault_linux_become_password: "{linux_become_password}"\n'
        f'vault_windows_password: "{windows_password}"\n'
    )

    VAULT_FILE.write_text(plain_content, encoding="utf-8")

    encrypt_cmd = [
        "ansible-vault",
        "encrypt",
        str(VAULT_FILE),
        "--vault-password-file",
        str(VAULT_PASSWORD_FILE),
    ]

    result = subprocess.run(encrypt_cmd, capture_output=True, text=True, env=ansible_environment())

    if result.returncode != 0:
        return {
            "status": "error",
            "message": "Vault save failed.",
            "output": result.stdout + result.stderr,
        }

    return {"status": "saved", "message": "Vault saved and encrypted."}


@app.post("/vault/test")
def test_vault():
    if not VAULT_FILE.exists():
        return {"status": "error", "output": "Vault file does not exist."}

    if not VAULT_PASSWORD_FILE.exists():
        return {"status": "error", "output": "Vault password file does not exist."}

    cmd = [
        "ansible-vault",
        "view",
        str(VAULT_FILE),
        "--vault-password-file",
        str(VAULT_PASSWORD_FILE),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, env=ansible_environment())

    return {
        "status": "successful" if result.returncode == 0 else "failed",
        "rc": result.returncode,
        "output": "Vault decrypted successfully." if result.returncode == 0 else result.stdout + result.stderr,
    }


@app.post("/register")
def register(payload: dict = Body(...)):
    username = normalize_username(
        str(payload.get("username", ""))
    )
    password = str(payload.get("password", ""))
    confirm_password = str(
        payload.get("confirm_password", "")
    )

    if not username:
        return {
            "status": "error",
            "message": "Username is required",
        }

    if len(username) < 3:
        return {
            "status": "error",
            "message": "Username must be at least 3 characters",
        }

    if len(username) > 50:
        return {
            "status": "error",
            "message": "Username cannot exceed 50 characters",
        }

    if not username.replace("_", "").replace("-", "").isalnum():
        return {
            "status": "error",
            "message": (
                "Username may only contain letters, numbers, "
                "underscores, and hyphens"
            ),
        }

    if len(password) < 12:
        return {
            "status": "error",
            "message": "Password must be at least 12 characters",
        }

    if password != confirm_password:
        return {
            "status": "error",
            "message": "Passwords do not match",
        }

    with SessionLocal() as db:
        try:
            user = create_user(
                db=db,
                username=username,
                password=password,
                role="viewer",
                enabled=False,
            )
        except ValueError as exc:
            return {
                "status": "error",
                "message": str(exc),
            }

        return {
            "status": "ok",
            "message": (
                "Account created. An administrator must approve "
                "the account before you can sign in."
            ),
            "user": user.username,
        }

@app.get("/ui", response_class=HTMLResponse)
def ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
