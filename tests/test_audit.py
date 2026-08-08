def test_login_attempts_are_audited_and_only_admin_can_read_log(client, make_user, login):
    make_user("admin1", role="admin")
    make_user("viewer1", role="viewer")

    failed = login(client, "viewer1", "WrongPassword123!")
    assert failed.json()["status"] == "error"

    assert login(client, "viewer1").json()["status"] == "ok"
    assert client.get("/audit").status_code == 403

    client.get("/logout")
    assert login(client, "admin1").json()["status"] == "ok"

    response = client.get("/audit?action=auth.login")
    assert response.status_code == 200

    events = response.json()["events"]
    assert any(
        event["actor_username"] == "viewer1" and event["outcome"] == "failure"
        for event in events
    )
    assert any(
        event["actor_username"] == "viewer1" and event["outcome"] == "success"
        for event in events
    )
    assert any(
        event["actor_username"] == "admin1" and event["outcome"] == "success"
        for event in events
    )
