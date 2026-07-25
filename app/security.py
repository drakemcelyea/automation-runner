from pwdlib import PasswordHash


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")

    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    if not plain_password or not password_hash:
        return False

    try:
        return password_hasher.verify(
            plain_password,
            password_hash,
        )
    except Exception:
        return False
