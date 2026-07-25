import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DEFAULT_DATABASE_PATH = (
    "/var/lib/automation-runner/settings/auth.db"
)

DATABASE_PATH = Path(
    os.getenv("AUTH_DATABASE_PATH", DEFAULT_DATABASE_PATH)
)

DATABASE_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
