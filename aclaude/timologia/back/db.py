"""Database connection and migration runner."""
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from config import DB_PATH

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.close()


def run_migrations():
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
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


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
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
