import argparse
import getpass
import sys

from app.db import Base, SessionLocal, engine
from app.models import User  # noqa: F401
from app.user_service import create_user


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create an Automation Runner administrator"
    )

    parser.add_argument(
        "--username",
        required=True,
        help="Administrator username",
    )

    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 1

    if len(password) < 12:
        print(
            "Password must contain at least 12 characters.",
            file=sys.stderr,
        )
        return 1

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        try:
            user = create_user(
                db=db,
                username=args.username,
                password=password,
                role="admin",
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    print(
        f"Created administrator '{user.username}' "
        f"with ID {user.id}."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
