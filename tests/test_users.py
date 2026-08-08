from fastapi.testclient import TestClient

from app.main import app


def test_admin_can_approve_pending_user(client, make_user, login):
    admin = make_user("admin1", role="admin")
    pending = make_user("pending1", role="viewer", enabled=False)

    assert login(client, admin.username).json()["status"] == "ok"

    users = client.get("/users")
    assert users.status_code == 200
    assert {user["username"] for user in users.json()["users"]} == {"admin1", "pending1"}

    approved = client.post(f"/users/{pending.id}/approve")
    assert approved.status_code == 200
    assert approved.json()["user"]["enabled"] is True

    with TestClient(app) as pending_client:
        login_response = login(pending_client, "pending1")
        assert login_response.status_code == 200
        assert login_response.json()["status"] == "ok"


def test_admin_cannot_disable_delete_or_demote_self(client, make_user, login):
    admin = make_user("admin1", role="admin")
    assert login(client, admin.username).json()["status"] == "ok"

    assert client.post(f"/users/{admin.id}/disable").status_code == 400
    assert client.delete(f"/users/{admin.id}").status_code == 400
    assert client.post(f"/users/{admin.id}/role", json={"role": "viewer"}).status_code == 400


def test_final_enabled_admin_cannot_be_disabled_deleted_or_demoted_by_another_admin(
    client,
    make_user,
    login,
):
    primary = make_user("primary_admin", role="admin", enabled=True)
    actor = make_user("actor_admin", role="admin", enabled=True)
    assert login(client, actor.username).json()["status"] == "ok"

    # First disable the primary administrator while two enabled admins exist.
    assert client.post(f"/users/{primary.id}/disable").status_code == 200

    # The actor is now the final enabled admin and self-protection must apply.
    assert client.post(f"/users/{actor.id}/disable").status_code == 400
    assert client.delete(f"/users/{actor.id}").status_code == 400
    assert client.post(f"/users/{actor.id}/role", json={"role": "operator"}).status_code == 400
