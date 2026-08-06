from app.config import SETTINGS_FILE
from app.services.json_store import read_json, write_json


DEFAULT_SETTINGS = {
    "theme": "light",
    "accent": "primary",
    "logging_enabled": True,
}


def load_settings() -> dict:
    return read_json(SETTINGS_FILE, DEFAULT_SETTINGS.copy())


def save_settings(settings: dict) -> None:
    write_json(SETTINGS_FILE, settings)


def update_settings(payload: dict) -> dict:
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
