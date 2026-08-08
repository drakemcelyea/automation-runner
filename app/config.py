import os
from pathlib import Path


APP_DIR = Path(
    os.getenv(
        "AUTOMATION_RUNNER_APP_DIR",
        "/opt/automation-runner",
    )
)

DATA_DIR = Path(
    os.getenv(
        "AUTOMATION_RUNNER_DATA_DIR",
        "/var/lib/automation-runner",
    )
)

CONFIG_DIR = Path(
    os.getenv(
        "AUTOMATION_RUNNER_CONFIG_DIR",
        "/etc/automation-runner",
    )
)

STATIC_DIR = APP_DIR / "app" / "static"
TEMPLATE_DIR = APP_DIR / "app" / "templates"

PROJECTS_DIR = DATA_DIR / "projects"
PLAYBOOK_DIR = PROJECTS_DIR / "demo" / "project"

RUNS_DIR = DATA_DIR / "runs"
RUNS_FILE = DATA_DIR / "runs.json"

INVENTORY_FILE = DATA_DIR / "inventory.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

VAULT_DIR = DATA_DIR / "vault"
VAULT_FILE = VAULT_DIR / "admin_secret.yml"
VAULT_PASSWORD_FILE = CONFIG_DIR / "vault_pass.txt"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SESSION_SECRET = os.getenv("SESSION_SECRET", "")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "automation_runner_session")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "28800"))
SESSION_SAME_SITE = os.getenv("SESSION_SAME_SITE", "lax").strip().lower()
SESSION_HTTPS_ONLY = env_bool("SESSION_HTTPS_ONLY", False)
