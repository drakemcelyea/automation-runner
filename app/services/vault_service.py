import subprocess

from app.config import VAULT_DIR, VAULT_FILE, VAULT_PASSWORD_FILE
from app.services.ansible_service import ansible_environment


def vault_status() -> dict:
    encrypted = False

    if VAULT_FILE.exists():
        try:
            first_line = VAULT_FILE.read_text(
                encoding="utf-8",
                errors="ignore",
            ).splitlines()[0]
            encrypted = first_line.startswith("$ANSIBLE_VAULT")
        except (OSError, IndexError):
            encrypted = False

    return {
        "vault_dir": str(VAULT_DIR),
        "vault_file": str(VAULT_FILE),
        "vault_password_file": str(VAULT_PASSWORD_FILE),
        "vault_file_exists": VAULT_FILE.exists(),
        "vault_password_file_exists": VAULT_PASSWORD_FILE.exists(),
        "vault_encrypted": encrypted,
    }


def save_vault(payload: dict) -> dict:
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

    result = subprocess.run(
        [
            "ansible-vault",
            "encrypt",
            str(VAULT_FILE),
            "--vault-password-file",
            str(VAULT_PASSWORD_FILE),
        ],
        capture_output=True,
        text=True,
        env=ansible_environment(),
        check=False,
    )

    if result.returncode != 0:
        return {
            "status": "error",
            "message": "Vault save failed.",
            "output": result.stdout + result.stderr,
        }

    return {"status": "saved", "message": "Vault saved and encrypted."}


def test_vault() -> dict:
    if not VAULT_FILE.exists():
        return {"status": "error", "output": "Vault file does not exist."}

    if not VAULT_PASSWORD_FILE.exists():
        return {"status": "error", "output": "Vault password file does not exist."}

    result = subprocess.run(
        [
            "ansible-vault",
            "view",
            str(VAULT_FILE),
            "--vault-password-file",
            str(VAULT_PASSWORD_FILE),
        ],
        capture_output=True,
        text=True,
        env=ansible_environment(),
        check=False,
    )

    return {
        "status": "successful" if result.returncode == 0 else "failed",
        "rc": result.returncode,
        "output": (
            "Vault decrypted successfully."
            if result.returncode == 0
            else result.stdout + result.stderr
        ),
    }
