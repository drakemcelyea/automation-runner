from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.security.passwords import hash_password


VALID_ROLES = {"admin", "operator", "viewer"}


def normalize_username(username: str) -> str:
    return username.strip().lower()


def get_user_by_username(db: Session, username: str) -> User | None:
    normalized = normalize_username(username)

    if not normalized:
        return None

    return db.scalar(select(User).where(User.username == normalized))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.asc())))


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "enabled": user.enabled,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def create_user(
    db: Session,
    username: str,
    password: str,
    role: str = "viewer",
    enabled: bool = True,
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
        enabled=enabled,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_user_enabled(db: Session, user: User, enabled: bool) -> User:
    user.enabled = enabled
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_user_role(db: Session, user: User, role: str) -> User:
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")

    user.role = role
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()


def count_enabled_admins(db: Session) -> int:
    statement = select(func.count()).select_from(User).where(
        User.role == "admin",
        User.enabled.is_(True),
    )
    return int(db.scalar(statement) or 0)


def record_login(db: Session, user: User) -> None:
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
