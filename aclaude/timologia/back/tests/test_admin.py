"""Tests for admin endpoints."""


def test_admin_overview_as_user(client, auth_header):
    """Regular user should get 403."""
    resp = client.get("/api/admin/overview", headers=auth_header)
    assert resp.status_code == 403


def test_admin_overview_as_admin(client, admin_header):
    resp = client.get("/api/admin/overview", headers=admin_header)
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    assert "companies" in data
    assert "invoices" in data


def test_admin_list_users(client, admin_header):
    resp = client.get("/api/admin/users", headers=admin_header)
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 1
    assert any(u["email"] == "admin@test.com" for u in users)


def test_admin_list_companies(client, admin_header):
    resp = client.get("/api/admin/companies", headers=admin_header)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_admin_change_role(client, admin_header, auth_header):
    """Admin can change another user's role."""
    # Get user id
    users = client.get("/api/admin/users", headers=admin_header).json()
    target = next(u for u in users if u["email"] == "test@test.com")

    resp = client.patch(
        f"/api/admin/users/{target['id']}/role",
        headers=admin_header,
        json={"role": "admin"},
    )
    assert resp.status_code == 200

    # Verify
    users = client.get("/api/admin/users", headers=admin_header).json()
    target = next(u for u in users if u["email"] == "test@test.com")
    assert target["role"] == "admin"


def test_admin_cannot_change_own_role(client, admin_header):
    users = client.get("/api/admin/users", headers=admin_header).json()
    me = next(u for u in users if u["email"] == "admin@test.com")
    resp = client.patch(
        f"/api/admin/users/{me['id']}/role",
        headers=admin_header,
        json={"role": "user"},
    )
    assert resp.status_code == 400


def test_admin_delete_user(client, admin_header, auth_header):
    users = client.get("/api/admin/users", headers=admin_header).json()
    target = next(u for u in users if u["email"] == "test@test.com")
    resp = client.delete(
        f"/api/admin/users/{target['id']}",
        headers=admin_header,
    )
    assert resp.status_code == 200

    # Verify deleted
    users = client.get("/api/admin/users", headers=admin_header).json()
    assert not any(u["email"] == "test@test.com" for u in users)


def test_admin_cannot_delete_self(client, admin_header):
    users = client.get("/api/admin/users", headers=admin_header).json()
    me = next(u for u in users if u["email"] == "admin@test.com")
    resp = client.delete(
        f"/api/admin/users/{me['id']}",
        headers=admin_header,
    )
    assert resp.status_code == 400


def test_user_cannot_access_admin(client, auth_header):
    """Regular users should get 403 on all admin endpoints."""
    assert client.get("/api/admin/users", headers=auth_header).status_code == 403
    assert client.get("/api/admin/companies", headers=auth_header).status_code == 403
    assert client.delete("/api/admin/users/1", headers=auth_header).status_code == 403
