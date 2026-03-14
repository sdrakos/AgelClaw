"""Tests for authentication endpoints."""


def test_register(client):
    resp = client.post("/api/auth/register", json={
        "email": "new@test.com",
        "password": "Pass1234!",
        "name": "New User",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == "new@test.com"
    assert data["user"]["role"] == "user"


def test_register_duplicate(client):
    client.post("/api/auth/register", json={
        "email": "dup@test.com", "password": "Pass1234!", "name": "User1",
    })
    resp = client.post("/api/auth/register", json={
        "email": "dup@test.com", "password": "Pass1234!", "name": "User2",
    })
    assert resp.status_code == 409


def test_login_success(client):
    client.post("/api/auth/register", json={
        "email": "login@test.com", "password": "Pass1234!", "name": "Login User",
    })
    resp = client.post("/api/auth/login", json={
        "email": "login@test.com", "password": "Pass1234!",
    })
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={
        "email": "wrong@test.com", "password": "Pass1234!", "name": "User",
    })
    resp = client.post("/api/auth/login", json={
        "email": "wrong@test.com", "password": "WrongPass!",
    })
    assert resp.status_code == 401


def test_login_nonexistent(client):
    resp = client.post("/api/auth/login", json={
        "email": "nobody@test.com", "password": "Pass1234!",
    })
    assert resp.status_code == 401


def test_protected_endpoint_no_token(client):
    resp = client.get("/api/companies")
    assert resp.status_code == 401


def test_protected_endpoint_with_token(client, auth_header):
    resp = client.get("/api/companies", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json() == []
