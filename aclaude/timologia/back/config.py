"""Application configuration from environment variables."""
import os
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    import secrets as _s
    JWT_SECRET = _s.token_hex(32)
    _env = BASE_DIR / ".env"
    if _env.exists():
        _c = _env.read_text()
        if "JWT_SECRET=" in _c:
            _c = _c.replace("JWT_SECRET=", f"JWT_SECRET={JWT_SECRET}", 1)
        else:
            _c += f"\nJWT_SECRET={JWT_SECRET}\n"
        _env.write_text(_c)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Fernet — auto-generate on first run if missing
_fernet_key = os.environ.get("FERNET_KEY")
if not _fernet_key:
    _fernet_key = Fernet.generate_key().decode()
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        # Replace empty FERNET_KEY= line or append
        content = env_file.read_text()
        if "FERNET_KEY=" in content:
            content = content.replace("FERNET_KEY=", f"FERNET_KEY={_fernet_key}", 1)
            env_file.write_text(content)
        else:
            with open(env_file, "a") as f:
                f.write(f"\nFERNET_KEY={_fernet_key}\n")
FERNET = Fernet(_fernet_key.encode() if isinstance(_fernet_key, str) else _fernet_key)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
PORT = int(os.environ.get("PORT", "8100"))

OUTLOOK_CLIENT_ID = os.environ.get("OUTLOOK_CLIENT_ID", "")
OUTLOOK_CLIENT_SECRET = os.environ.get("OUTLOOK_CLIENT_SECRET", "")
OUTLOOK_TENANT_ID = os.environ.get("OUTLOOK_TENANT_ID", "")
OUTLOOK_USER_EMAIL = os.environ.get("OUTLOOK_USER_EMAIL", "")

DB_PATH = BASE_DIR / "data" / "timologia.db"
REPORTS_DIR = BASE_DIR / "data" / "reports"
APP_URL = os.environ.get("APP_URL", "http://localhost:5173")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")

# CORS — comma-separated origins
ALLOWED_ORIGINS = [
    o.strip() for o in
    os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]
