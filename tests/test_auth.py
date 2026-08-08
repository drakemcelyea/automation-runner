from app.db import SessionLocal
from app.models import User
from app.services.user_service import get_user_by_username

from .conftest import TEST_PASSWORD


def test_registration_creates_pending_viewer(client):
    response = client.post(
        "/register",
        json={
            "username": "new_viewer",
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    with SessionLocal() as db:
        user = get_user_by_username(db, "new_viewer")
        assert user is not None
        assert user.role == "viewer"
        assert user.enabled is False


def test_pending_user_cannot_login(client, make_user, login):
    make_user("pending_user", enabled=False)

    response = login(client, "pending_user")

    assert response.status_code == 200
    assert response.json() == {
        "status": "error",
        "message": "Invalid credentials",
    }


def test_enabled_user_can_login_and_me_reports_role(client, make_user, login):
    make_user("operator1", role="operator")

    response = login(client, "operator1")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["role"] == "operator"

    me = client.get("/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True
    assert me.json()["user"] == "operator1"
    assert me.json()["role"] == "operator"


def test_bad_password_does_not_authenticate(client, make_user, login):
    make_user("viewer1")

    response = login(client, "viewer1", "DefinitelyWrongPassword1!")

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert client.get("/me").json() == {"authenticated": False}


def test_disabled_user_session_is_invalidated(client, make_user, login):
    user = make_user("viewer1")
    assert login(client, "viewer1").json()["status"] == "ok"

    with SessionLocal() as db:
        stored = db.get(User, user.id)
        stored.enabled = False
        db.commit()

    protected = client.get("/inventory")
    assert protected.status_code == 401
    assert client.get("/me").json() == {"authenticated": False}
