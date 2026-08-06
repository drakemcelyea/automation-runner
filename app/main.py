import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import STATIC_DIR
from app.db import Base, engine
from app.routers import auth, health, inventory, playbooks, runs, settings, ui, vault


def create_app() -> FastAPI:
    application = FastAPI(title="Automation Runner")

    session_secret = os.getenv(
        "SESSION_SECRET",
        "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET",
    )

    application.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        same_site="lax",
        https_only=False,
    )

    Base.metadata.create_all(bind=engine)
    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(inventory.router)
    application.include_router(playbooks.router)
    application.include_router(runs.router)
    application.include_router(settings.router)
    application.include_router(vault.router)
    application.include_router(ui.router)

    return application


app = create_app()
