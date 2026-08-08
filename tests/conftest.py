import os
import shutil
import tempfile
from pathlib import Path

import pytest


TEST_ROOT = Path(tempfile.mkdtemp(prefix="automation-runner-tests-"))
DATA_DIR = TEST_ROOT / "data"
CONFIG_DIR = TEST_ROOT / "config"
DATABASE_PATH = DATA_DIR / "settings" / "auth.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# These must be set before importing the application because config.py/db.py
# resolve their paths at import time.
os.environ["AUTOMATION_RUNNER_DATA_DIR"] = str(DATA_DIR)
os.environ["AUTOMATION_RUNNER_CONFIG_DIR"] = str(CONFIG_DIR)
os.environ["AUTH_DATABASE_PATH"] = str(DATABASE_PATH)
os.environ["SESSION_SECRET"] = "pytest-session-secret-not-for-production"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.run_service import RUNS  # noqa: E402
from app.services.user_service import create_user  # noqa: E402


TEST_PASSWORD = "CorrectHorseBattery1!"


@pytest.fixture(autouse=True)
def clean_test_state():
    """Give every test a fresh database and filesystem-backed app state."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    RUNS.clear()

    for path in (
        DATA_DIR / "inventory.json",
        DATA_DIR / "runs.json",
        DATA_DIR / "settings.json",
        CONFIG_DIR / "vault_pass.txt",
    ):
        path.unlink(missing_ok=True)

    shutil.rmtree(DATA_DIR / "projects", ignore_errors=True)
    shutil.rmtree(DATA_DIR / "runs", ignore_errors=True)
    shutil.rmtree(DATA_DIR / "vault", ignore_errors=True)

    (DATA_DIR / "projects" / "demo" / "project").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "runs").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "vault").mkdir(parents=True, exist_ok=True)

    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user():
    def _make_user(
        username: str,
        *,
        role: str = "viewer",
        enabled: bool = True,
        password: str = TEST_PASSWORD,
    ):
        with SessionLocal() as db:
            return create_user(
                db=db,
                username=username,
                password=password,
                role=role,
                enabled=enabled,
            )

    return _make_user


@pytest.fixture
def login():
    def _login(test_client: TestClient, username: str, password: str = TEST_PASSWORD):
        return test_client.post(
            "/login",
            json={"username": username, "password": password},
        )

    return _login


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
