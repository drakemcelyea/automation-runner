import hashlib
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LoginThrottle, User


ACCOUNT_FAILURE_LIMIT = int(os.getenv("LOGIN_ACCOUNT_FAILURE_LIMIT", "5"))
ACCOUNT_LOCKOUT_MINUTES = int(os.getenv("LOGIN_ACCOUNT_LOCKOUT_MINUTES", "15"))
IP_FAILURE_LIMIT = int(os.getenv("LOGIN_IP_FAILURE_LIMIT", "30"))
IP_WINDOW_MINUTES = int(os.getenv("LOGIN_IP_WINDOW_MINUTES", "5"))
IP_BLOCK_MINUTES = int(os.getenv("LOGIN_IP_BLOCK_MINUTES", "5"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def request_ip(request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _ip_key(ip_address: str) -> str:
    return hashlib.sha256(ip_address.encode("utf-8")).hexdigest()


def account_lock_remaining_seconds(user: User, now: datetime | None = None) -> int:
    now = now or utc_now()
    locked_until = _aware(user.locked_until)
    if not locked_until or locked_until <= now:
        return 0
    return max(1, int((locked_until - now).total_seconds()))


def prepare_account_for_login(db: Session, user: User, now: datetime | None = None) -> int:
    now = now or utc_now()
    remaining = account_lock_remaining_seconds(user, now)
    if remaining:
        return remaining

    if user.locked_until is not None:
        user.locked_until = None
        user.failed_login_attempts = 0
        db.add(user)
        db.commit()
        db.refresh(user)

    return 0


def record_account_login_failure(db: Session, user: User) -> tuple[bool, int]:
    user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
    locked_now = False
    retry_after = 0

    if user.failed_login_attempts >= ACCOUNT_FAILURE_LIMIT:
        user.locked_until = utc_now() + timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)
        locked_now = True
        retry_after = ACCOUNT_LOCKOUT_MINUTES * 60

    db.add(user)
    db.commit()
    db.refresh(user)
    return locked_now, retry_after


def reset_account_login_security(db: Session, user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)
    db.commit()
    db.refresh(user)


def _get_ip_throttle(db: Session, ip_address: str) -> LoginThrottle | None:
    key = _ip_key(ip_address)
    return db.scalar(select(LoginThrottle).where(LoginThrottle.key_hash == key))


def ip_throttle_remaining_seconds(
    db: Session,
    ip_address: str,
    now: datetime | None = None,
) -> int:
    now = now or utc_now()
    throttle = _get_ip_throttle(db, ip_address)
    if throttle is None:
        return 0

    blocked_until = _aware(throttle.blocked_until)
    if blocked_until and blocked_until > now:
        return max(1, int((blocked_until - now).total_seconds()))

    if blocked_until and blocked_until <= now:
        throttle.blocked_until = None
        throttle.attempt_count = 0
        throttle.window_started_at = now
        throttle.updated_at = now
        db.add(throttle)
        db.commit()

    return 0


def record_ip_login_failure(db: Session, ip_address: str) -> tuple[bool, int]:
    now = utc_now()
    key = _ip_key(ip_address)
    throttle = _get_ip_throttle(db, ip_address)

    if throttle is None:
        throttle = LoginThrottle(
            key_hash=key,
            window_started_at=now,
            attempt_count=0,
            updated_at=now,
        )
        db.add(throttle)

    window_started = _aware(throttle.window_started_at) or now
    if now - window_started >= timedelta(minutes=IP_WINDOW_MINUTES):
        throttle.window_started_at = now
        throttle.attempt_count = 0
        throttle.blocked_until = None

    throttle.attempt_count = int(throttle.attempt_count or 0) + 1
    throttle.updated_at = now

    blocked_now = False
    retry_after = 0
    if throttle.attempt_count >= IP_FAILURE_LIMIT:
        throttle.blocked_until = now + timedelta(minutes=IP_BLOCK_MINUTES)
        blocked_now = True
        retry_after = IP_BLOCK_MINUTES * 60

    db.add(throttle)
    db.commit()
    return blocked_now, retry_after


def clear_account_lockout(db: Session, user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)
    db.commit()
    db.refresh(user)
