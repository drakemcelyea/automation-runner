from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import (
    SESSION_COOKIE_NAME,
    SESSION_HTTPS_ONLY,
    SESSION_MAX_AGE,
    SESSION_SAME_SITE,
    SESSION_SECRET,
    STATIC_DIR,
)
from app.routers import audit, auth, health, inventory, playbooks, runs, settings, ui, users, vault
from app.security.csrf_middleware import CSRFMiddleware


def _validate_session_settings() -> None:
    if not SESSION_SECRET or SESSION_SECRET == "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET":
        raise RuntimeError("SESSION_SECRET must be configured")
    if len(SESSION_SECRET) < 32:
        raise RuntimeError("SESSION_SECRET must be at least 32 characters")
    if SESSION_SAME_SITE not in {"lax", "strict", "none"}:
        raise RuntimeError("SESSION_SAME_SITE must be lax, strict, or none")
    if SESSION_SAME_SITE == "none" and not SESSION_HTTPS_ONLY:
        raise RuntimeError("SESSION_SAME_SITE=none requires SESSION_HTTPS_ONLY=true")


def create_app() -> FastAPI:
    _validate_session_settings()

    application = FastAPI(title="Automation Runner")

    # CSRF must run inside SessionMiddleware so request.session is available.
    application.add_middleware(CSRFMiddleware)
    application.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET,
        session_cookie=SESSION_COOKIE_NAME,
        max_age=SESSION_MAX_AGE,
        same_site=SESSION_SAME_SITE,
        https_only=SESSION_HTTPS_ONLY,
    )

    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(inventory.router)
    application.include_router(playbooks.router)
    application.include_router(runs.router)
    application.include_router(settings.router)
    application.include_router(vault.router)
    application.include_router(users.router)
    application.include_router(audit.router)
    application.include_router(ui.router)

    return application


app = create_app()
