import pytest

from app.routers import playbooks as playbooks_router
from app.routers import runs as runs_router


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/inventory"),
        ("get", "/playbooks"),
        ("get", "/runs"),
        ("get", "/settings"),
    ],
)
def test_unauthenticated_read_endpoints_require_login(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401


def test_viewer_has_read_only_access(client, make_user, login):
    make_user("viewer1", role="viewer")
    assert login(client, "viewer1").json()["status"] == "ok"

    assert client.get("/inventory").status_code == 200
    assert client.get("/playbooks").status_code == 200
    assert client.get("/runs").status_code == 200
    assert client.get("/settings").status_code == 200

    assert client.post("/run-demo", json={"playbook": "test.yml"}).status_code == 403
    assert client.post("/playbooks/test.yml/syntax-check").status_code == 403
    assert client.post("/inventory/add", json={"name": "host1", "ip": "127.0.0.1"}).status_code == 403
    assert client.post("/playbooks/save", json={"name": "test.yml", "content": "---\n"}).status_code == 403
    assert client.post("/settings", json={"theme": "dark"}).status_code == 403
    assert client.get("/vault/status").status_code == 403
    assert client.get("/users").status_code == 403
    assert client.get("/audit").status_code == 403


def test_operator_can_execute_and_syntax_check_but_not_administer(
    client,
    make_user,
    login,
    monkeypatch,
):
    make_user("operator1", role="operator")
    assert login(client, "operator1").json()["status"] == "ok"

    monkeypatch.setattr(
        runs_router,
        "execute_run",
        lambda payload: {
            "run_id": "test-run",
            "playbook": "test.yml",
            "target": "all",
            "status": "successful",
            "rc": 0,
            "duration": 0.01,
        },
    )
    monkeypatch.setattr(
        playbooks_router,
        "syntax_check",
        lambda playbook_name: {
            "status": "successful",
            "rc": 0,
            "output": "syntax ok",
        },
    )

    run_response = client.post("/run-demo", json={"playbook": "test.yml"})
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "successful"

    syntax_response = client.post("/playbooks/test.yml/syntax-check")
    assert syntax_response.status_code == 200
    assert syntax_response.json()["status"] == "successful"

    assert client.post("/inventory/add", json={"name": "host1", "ip": "127.0.0.1"}).status_code == 403
    assert client.post("/playbooks/save", json={"name": "test.yml", "content": "---\n"}).status_code == 403
    assert client.post("/settings", json={"theme": "dark"}).status_code == 403
    assert client.get("/vault/status").status_code == 403
    assert client.get("/users").status_code == 403
    assert client.get("/audit").status_code == 403


def test_role_change_takes_effect_without_relogin(client, make_user, login, monkeypatch):
    viewer = make_user("promote_me", role="viewer")
    make_user("admin1", role="admin")

    with client as viewer_client:
        assert login(viewer_client, "promote_me").json()["status"] == "ok"
        assert viewer_client.post("/run-demo", json={"playbook": "test.yml"}).status_code == 403

        with type(client)(client.app) as admin_client:
            assert login(admin_client, "admin1").json()["status"] == "ok"
            change = admin_client.post(f"/users/{viewer.id}/role", json={"role": "operator"})
            assert change.status_code == 200

        monkeypatch.setattr(
            runs_router,
            "execute_run",
            lambda payload: {
                "run_id": "promoted-run",
                "playbook": "test.yml",
                "target": "all",
                "status": "successful",
                "rc": 0,
                "duration": 0.01,
            },
        )
        assert viewer_client.post("/run-demo", json={"playbook": "test.yml"}).status_code == 200
