"""Tests for company endpoints."""
from unittest.mock import patch, AsyncMock


def test_create_company_requires_aade_credentials(client, auth_header):
    """Company creation without AADE credentials should fail."""
    resp = client.post("/api/companies", headers=auth_header, json={
        "name": "Test Company",
        "afm": "094388099",
        "aade_user_id": "",
        "aade_subscription_key": "",
        "aade_env": "dev",
    })
    assert resp.status_code == 400
    assert "ΑΑΔΕ" in resp.json()["detail"]


def test_create_company_duplicate_afm(client, auth_header):
    """Duplicate AFM should return error."""
    with patch("aade_client.MyDataClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client._get = AsyncMock(return_value=b"<response><statusCode>Success</statusCode></response>")
        mock_client.close = AsyncMock()
        mock_cls.return_value = mock_client

        # Create first
        resp1 = client.post("/api/companies", headers=auth_header, json={
            "name": "Company A", "afm": "094388099",
            "aade_user_id": "user1", "aade_subscription_key": "key1", "aade_env": "dev",
        })
        assert resp1.status_code == 200
        # Try duplicate
        resp = client.post("/api/companies", headers=auth_header, json={
            "name": "Company B", "afm": "094388099",
            "aade_user_id": "user2", "aade_subscription_key": "key2", "aade_env": "dev",
        })
    assert resp.status_code == 400
    assert "ΑΦΜ" in resp.json()["detail"]


def test_list_companies_empty(client, auth_header):
    resp = client.get("/api/companies", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_members_not_member(client, auth_header):
    """Non-member should get 403."""
    resp = client.get("/api/companies/999/members", headers=auth_header)
    assert resp.status_code == 403
