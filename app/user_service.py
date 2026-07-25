from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password


VALID_ROLES = {
    "admin",
    "operator",
    "viewer",
}


def normalize_username(username: str) -> str:
    return username.strip().lower()


def get_user_by_username(
    db: Session,
    username: str,
) -> User | None:
    normalized = normalize_username(username)

    if not normalized:
        return None

    statement = select(User).where(
        User.username == normalized
    )

    return db.scalar(statement)


def create_user(
    db: Session,
    username: str,
    password: str,
    role: str = "viewer",
) -> User:
    normalized = normalize_username(username)

    if not normalized:
        raise ValueError("Username cannot be empty")

    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")

    if get_user_by_username(db, normalized):
        raise ValueError("Username already exists")

    user = User(
        username=normalized,
        password_hash=hash_password(password),
        role=role,
        enabled=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def record_login(
    db: Session,
    user: User,
) -> None:
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
