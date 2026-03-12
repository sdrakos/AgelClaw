"""JWT authentication: register, login, middleware."""
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException
from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_HOURS
from db import get_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


def register_user(email: str, password: str, name: str) -> dict:
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            raise HTTPException(409, "Email already registered")
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
            (email, hash_password(password), name),
        )
        user_id = cur.lastrowid
    return {"id": user_id, "email": email, "name": name, "role": "user"}


def login_user(email: str, password: str) -> dict:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, email, name, role, password_hash FROM users WHERE email=?",
            (email,),
        ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(row["id"], row["role"])
    return {"token": token, "user": {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"]}}


async def get_current_user(request: Request) -> dict:
    """Dependency: extract user from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    payload = decode_token(auth[7:])
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, email, name, role FROM users WHERE id=?", (payload["sub"],)
        ).fetchone()
    if not row:
        raise HTTPException(401, "User not found")
    return dict(row)


def get_member_role(user_id: int, company_id: int) -> str | None:
    """Return user's role in a company, or None if not a member."""
    with get_db() as conn:
        user = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
        if user and user["role"] == "admin":
            return "admin"
        row = conn.execute(
            "SELECT role FROM company_members WHERE user_id=? AND company_id=?",
            (user_id, company_id),
        ).fetchone()
    return row["role"] if row else None


def require_role(user_id: int, company_id: int, min_role: str):
    """Raise 403 if user doesn't have minimum role."""
    role_order = {"viewer": 0, "accountant": 1, "owner": 2, "admin": 3}
    role = get_member_role(user_id, company_id)
    if role is None:
        raise HTTPException(403, "Not a member of this company")
    if role_order.get(role, -1) < role_order.get(min_role, 99):
        raise HTTPException(403, f"Requires {min_role} role")
