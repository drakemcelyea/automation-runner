import json
import shutil
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path

import ansible_runner

from app.config import PLAYBOOK_DIR, RUNS_DIR, RUNS_FILE, VAULT_PASSWORD_FILE
from app.services.ansible_service import (
    ansible_environment,
    copy_project_files,
    parse_extra_vars,
    prepare_vault_for_run,
    vault_cmdline,
    write_ansible_inventory,
)
from app.services.json_store import read_json, write_json
from app.services.settings_service import load_settings


RUNS: dict[str, dict] = read_json(RUNS_FILE, {})


def save_runs() -> None:
    write_json(RUNS_FILE, RUNS)


def list_runs() -> list[dict]:
    return list(RUNS.values())[::-1]


def run_stats() -> dict[str, int]:
    return {
        "total": len(RUNS),
        "successful": sum(run.get("status") == "successful" for run in RUNS.values()),
        "failed": sum(run.get("status") == "failed" for run in RUNS.values()),
        "errors": sum(run.get("status") == "error" for run in RUNS.values()),
    }


def clear_runs() -> None:
    RUNS.clear()
    save_runs()


def syntax_check(playbook_name: str) -> dict:
    safe_name = Path(playbook_name).name
    source_playbook = PLAYBOOK_DIR / safe_name

    if not source_playbook.exists():
        return {"status": "error", "output": "Playbook not found."}

    temp_dir = RUNS_DIR / f"syntax-{uuid.uuid4()}"
    project_dir = temp_dir / "project"

    try:
        project_dir.mkdir(parents=True, exist_ok=False)
        destination_playbook = project_dir / safe_name
        shutil.copyfile(source_playbook, destination_playbook)
        write_ansible_inventory(temp_dir)
        prepare_vault_for_run(temp_dir)

        command = [
            "ansible-playbook",
            "-i",
            str(temp_dir / "inventory"),
            str(destination_playbook),
        ]

        if VAULT_PASSWORD_FILE.exists():
            command.extend(["--vault-password-file", str(VAULT_PASSWORD_FILE)])

        command.append("--syntax-check")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=ansible_environment(),
            check=False,
        )

        return {
            "status": "successful" if result.returncode == 0 else "failed",
            "rc": result.returncode,
            "output": result.stdout + result.stderr,
        }
    except Exception as exc:
        return {"status": "error", "rc": -1, "output": str(exc)}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def execute_run(payload: dict | None = None) -> dict:
    payload = payload or {}
    playbook = Path(payload.get("playbook", "ping.yml")).name
    target = payload.get("target", "all")
    extra_vars = parse_extra_vars(payload.get("extra_vars", ""))
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
            envvars=ansible_environment(),
        )

        RUNS[run_id] = {
            "run_id": run_id,
            "playbook": playbook,
            "target": target,
            "extra_vars": extra_vars,
            "status": result.status,
            "rc": result.rc,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "duration": round(time.time() - start_timer, 2),
            "private_data_dir": str(private_data_dir),
        }
    except Exception as exc:
        RUNS[run_id] = {
            "run_id": run_id,
            "playbook": playbook,
            "target": target,
            "extra_vars": extra_vars,
            "status": "error",
            "rc": -1,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "duration": round(time.time() - start_timer, 2),
            "error": str(exc),
            "private_data_dir": str(RUNS_DIR / run_id),
        }

    save_runs()
    return RUNS[run_id]


def get_run_logs(run_id: str) -> str:
    artifacts_dir = RUNS_DIR / run_id / "artifacts"

    if not artifacts_dir.exists():
        return "No artifacts found yet."

    output_lines: list[str] = []

    for artifact_run in artifacts_dir.iterdir():
        job_events_dir = artifact_run / "job_events"

        if not job_events_dir.exists():
            continue

        for event_file in sorted(job_events_dir.glob("*.json")):
            try:
                with event_file.open("r", encoding="utf-8") as file_handle:
                    event = json.load(file_handle)
                stdout = event.get("stdout")
                if stdout:
                    output_lines.append(stdout)
            except (OSError, json.JSONDecodeError):
                continue

    return "\n".join(output_lines) if output_lines else "No logs found."
