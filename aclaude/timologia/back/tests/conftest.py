"""Shared fixtures for Timologia tests."""
import os
import sys
import sqlite3
import pytest
from pathlib import Path
from contextlib import contextmanager

# Add back/ to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set env before any imports
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["FERNET_KEY"] = "F-LMmV1rug2lGxJAVV-ZAeXA_IZkXznxK6O96Kj6Th4="

# Global test DB path — modules read this at call time
_TEST_DB_PATH = None


def _make_get_db():
    """Create a get_db that always uses the current test DB path."""
    @contextmanager
    def get_db():
        conn = sqlite3.connect(str(_TEST_DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return get_db


# Patch get_db in db module AND all modules that import it
import db as db_module
_patched_get_db = _make_get_db()
db_module.get_db = _patched_get_db

import auth
auth.get_db = _patched_get_db

import app as app_module
app_module.get_db = _patched_get_db

# Silence admin email notifications in tests
auth._notify_admin = lambda *a, **kw: None

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


@pytest.fixture(autouse=True)
def test_db(tmp_path):
    """Create a fresh DB for each test."""
    global _TEST_DB_PATH
    _TEST_DB_PATH = tmp_path / "test.db"

    # Run migrations on fresh DB
    conn = sqlite3.connect(str(_TEST_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations "
        "(name TEXT PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    applied = {r[0] for r in conn.execute("SELECT name FROM _migrations").fetchall()}
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if sql_file.name not in applied:
            conn.executescript(sql_file.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO _migrations (name) VALUES (?)", (sql_file.name,))
            conn.commit()
    conn.close()

    yield _TEST_DB_PATH


@pytest.fixture
def client(test_db):
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    return TestClient(app_module.app)


@pytest.fixture
def auth_header(client):
    """Register a user and return auth header."""
    resp = client.post("/api/auth/register", json={
        "email": "test@test.com",
        "password": "Test1234!",
        "name": "Test User",
    })
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_header(client, test_db):
    """Register an admin user and return auth header."""
    client.post("/api/auth/register", json={
        "email": "admin@test.com",
        "password": "Admin1234!",
        "name": "Admin User",
    })
    # Make admin directly in DB
    conn = sqlite3.connect(str(test_db))
    conn.execute("UPDATE users SET role='admin' WHERE email='admin@test.com'")
    conn.commit()
    conn.close()
    # Re-login to get admin token
    resp = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin1234!",
    })
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}
